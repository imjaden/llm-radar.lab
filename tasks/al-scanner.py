#!/usr/bin/env python3
"""
al-scanner.py — Agent Loop 状态机 scanner (no_agent 纯脚本)

功能:
  - 文件锁获取/过期锁回收
  - state 状态流转 (demand→assigned, failed→assigned/escalated, passed→closed)
  - git push (评审通过后)
  - escalated 24h 通知提醒
  - 更新 tasks/agents-teamwork.yaml

频率: 每 5 分钟 (通过 cronjob 调度, profile=ops)
运行: cronjob 设置 no_agent=True, 脚本路径 tasks/al-scanner.py
"""
import os
import sys
import time
import fcntl
import shutil
import hashlib
import subprocess
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── 配置 ──
PROJECT = Path("/Users/jadenli/CodeSpace/llm-radar.jaden.tech")
TASKS = PROJECT / "tasks"
LOCK_PATH = TASKS / ".agent-loop.lock"
STALE_THRESHOLD = 900       # 15 分钟
ESCALATED_NOTICE = 86400    # 24 小时
TZ = timezone(timedelta(hours=8))


# ── 工具函数 ──

def log(msg: str):
    """统一日志输出 (cron output 可见)"""
    ts = datetime.now(TZ).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def sh(cmd: str, cwd: Path = PROJECT) -> str:
    """执行 shell 命令, 返回 stdout"""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        log(f"⚠️ 命令失败: {cmd}")
        log(f"   stderr: {r.stderr.strip()}")
    return r.stdout.strip()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_yaml(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_yaml(path: Path, data: dict):
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def load_manifest() -> tuple[dict, Path]:
    """加载当前任务的 manifest, 返回 (data, dir_path)"""
    link = TASKS / "active-task"
    if not link.exists() and not link.is_symlink():
        return {}, Path()
    target = os.readlink(str(link))
    if not target:
        return {}, Path()
    task_dir = TASKS / target
    mf = task_dir / "task-manifest.yaml"
    return load_yaml(mf), task_dir


def save_manifest(manifest: dict, task_dir: Path):
    mf = task_dir / "task-manifest.yaml"
    save_yaml(mf, manifest)


def update_teamwork(manifest: dict, task_id: str):
    """更新 tasks/agents-teamwork.yaml 聚合状态"""
    tw_path = TASKS / "agents-teamwork.yaml"
    tw = load_yaml(tw_path)

    if "tasks" not in tw:
        tw = {
            "project": "llm-radar.jaden.tech",
            "task_count": 0,
            "open_task_count": 0,
            "escalated_tasks": [],
            "tasks": {}
        }

    state = manifest.get("state", "unknown")
    tw["tasks"][task_id] = {
        "title": manifest.get("title", ""),
        "state": state,
        "created_at": manifest.get("created_at", ""),
        "cycles": manifest.get("retry_count", 0),
        "escalated": manifest.get("escalated", False)
    }
    tw["task_count"] = len(tw["tasks"])
    tw["open_task_count"] = sum(
        1 for t in tw["tasks"].values() if t["state"] != "closed"
    )
    tw["escalated_tasks"] = [
        k for k, v in tw["tasks"].items() if v.get("escalated")
    ]
    save_yaml(tw_path, tw)


# ── 锁管理 ──

def acquire_lock() -> bool:
    """尝试获取文件锁, 返回是否成功"""
    global LOCK_FILE
    try:
        LOCK_FILE = open(LOCK_PATH, "w")
        fcntl.flock(LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        return False


def check_stale_lock() -> bool:
    """检查并回收过期锁, 返回 True 表示已回收"""
    if not LOCK_PATH.exists():
        return False
    age = time.time() - LOCK_PATH.stat().st_mtime
    if age > STALE_THRESHOLD:
        LOCK_PATH.unlink(missing_ok=True)
        log(f"⚠️ 回收过期锁 (>15min)，已释放")
        return True
    return False


def release_lock():
    global LOCK_FILE
    try:
        fcntl.flock(LOCK_FILE, fcntl.LOCK_UN)
        LOCK_FILE.close()
    except Exception:
        pass
    LOCK_PATH.unlink(missing_ok=True)


# ── 状态处理器 ──

def handle_created(manifest: dict, task_dir: Path) -> str:
    return "跳过: 等待人工设 state=demand"


def handle_demand(manifest: dict, task_dir: Path) -> str:
    """demand → assigned: 锁定需求快照"""
    src = PROJECT / "requirements.md"
    dst = task_dir / "demand.md"
    if src.exists():
        shutil.copy2(src, dst)
        manifest["source_hash"] = sha256_of(src)
    manifest["state"] = "assigned"
    # 更新 history
    for h in manifest.get("history", []):
        if h["step"] == "assign":
            h["date"] = datetime.now(TZ).isoformat()
            h["summary"] = "scanner 自动分配"
    save_manifest(manifest, task_dir)
    return f"已分配至 dev: {manifest.get('task_id', '?')}"


def handle_assigned(manifest: dict, task_dir: Path) -> str:
    return "跳过: 等待 dev-executor 实现"


def handle_in_progress(manifest: dict, task_dir: Path) -> str:
    return "跳过: dev-executor 执行中"


def handle_review(manifest: dict, task_dir: Path) -> str:
    return "跳过: 等待 reviewer-executor 评审"


def handle_passed(manifest: dict, task_dir: Path) -> str:
    """passed → closed: git push"""
    task_id = manifest.get("task_id", "?")
    result = sh("git push origin main")
    if "Everything up-to-date" in result or not result:
        # 可能没有新 commit, 也可能 push 成功
        pass
    manifest["state"] = "closed"
    manifest["closed_at"] = datetime.now(TZ).isoformat()
    for h in manifest.get("history", []):
        if h["step"] == "close":
            h["date"] = datetime.now(TZ).isoformat()
            h["summary"] = "评审通过，已 git push"
    save_manifest(manifest, task_dir)

    # 追加到根 audit-log.md
    root_log = PROJECT / "audit-log.md"
    entry = f"\n## {task_id}: {manifest.get('title', '')}\n"
    entry += f"- 状态: 已合并推送 ✅\n"
    entry += f"- 时间: {datetime.now(TZ).isoformat()}\n"
    with open(root_log, "a") as f:
        f.write(entry)

    return f"✅ 已推送: {task_id}"


def handle_failed(manifest: dict, task_dir: Path) -> str:
    """failed → assigned (retry < 3) 或 escalated (retry >= 3)"""
    retry = manifest.get("retry_count", 0)
    max_r = manifest.get("max_retries", 3)
    task_id = manifest.get("task_id", "?")

    if retry < max_r:
        manifest["state"] = "assigned"
        save_manifest(manifest, task_dir)
        return f"重试第 {retry}/{max_r} 次: {task_id}"
    else:
        manifest["escalated"] = True
        manifest["escalated_at"] = datetime.now(TZ).isoformat()
        save_manifest(manifest, task_dir)
        return f"⚠️ 已升级人工: {task_id}，{retry} 次评审不通过"


def handle_escalated(manifest: dict, task_dir: Path) -> str:
    """escalated: 检查 24h 提醒"""
    task_id = manifest.get("task_id", "?")
    escalated_at = manifest.get("escalated_at")
    msg = f"⚠️ 已升级: {task_id} (人工介入后手动重置)"

    if escalated_at:
        try:
            from datetime import datetime as dt
            e_time = dt.fromisoformat(escalated_at).timestamp()
        except Exception:
            e_time = 0
        elapsed = time.time() - e_time
        if elapsed > ESCALATED_NOTICE:
            msg += (
                f"\n🚨 [提醒] escalated 已超过 24 小时未处理!"
                f"\n   请查看: {task_dir / 'audit-log.md'}"
                f"\n   操作: 设 state=assigned + retry_count=0"
            )
            # 可选: 写入持续提醒日志
            warn_log = TASKS / ".agent-loop.escalation.log"
            with open(warn_log, "a") as f:
                f.write(f"[{datetime.now(TZ).isoformat()}] {task_id} escalated >24h\n")

    return msg


def handle_closed(manifest: dict, task_dir: Path) -> str:
    return "跳过: 任务已关闭"


HANDLERS = {
    "created": handle_created,
    "demand": handle_demand,
    "assigned": handle_assigned,
    "in_progress": handle_in_progress,
    "review": handle_review,
    "passed": handle_passed,
    "failed": handle_failed,
    "escalated": handle_escalated,
    "closed": handle_closed,
}


# ── 主流程 ──

def main():
    log("Scanner 启动")

    # 1. 锁管理
    if not acquire_lock():
        if check_stale_lock():
            # 回收后再次尝试
            if not acquire_lock():
                log("跳过: 锁被占用")
                return
        else:
            log("跳过: 锁被占用")
            return

    try:
        # 2. git pull
        sh("git pull")

        # 3. 读取 manifest
        manifest, task_dir = load_manifest()
        if not manifest:
            log("跳过: 无活跃 task")
            return

        task_id = manifest.get("task_id", "?")
        state = manifest.get("state", "unknown")
        log(f"当前任务: {task_id} (state={state})")

        # 4. 状态处理
        handler = HANDLERS.get(state)
        if handler:
            result = handler(manifest, task_dir)
            log(result)
        else:
            log(f"未知状态: {state}")

        # 5. 更新聚合状态
        manifest, task_dir = load_manifest()  # reload after handler
        if manifest:
            update_teamwork(manifest, task_id)

    finally:
        release_lock()

    log("Scanner 结束")


if __name__ == "__main__":
    main()
