#!/usr/bin/env python3
"""
al-init.py — 初始化 agent-loop task

用法:
    python3 tasks/al-init.py "<标题>"                  # state = created
    python3 tasks/al-init.py "<标题>" --demand         # state = demand（直接就绪）

效果:
    - 创建 tasks/al-YYYYMMDD-NNN/
    - 复制 requirements.md → tasks/<id>/demand.md
    - 生成 task-manifest.yaml
    - 更新 tasks/active-task symlink
"""
import sys
import os
import pwd
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Hermes profile 会覆盖 HOME 环境变量，使用真实用户目录
REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir
PROJECT = Path(REAL_HOME) / "CodeSpace/llm-radar.jaden.tech"
TASKS = PROJECT / "tasks"
REQUIREMENTS = PROJECT / "requirements.md"
TZ = timezone(timedelta(hours=8))


def sha256_of(path: Path) -> str:
    """计算文件的 SHA256 哈希"""
    if path.exists():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def next_task_id() -> str:
    """获取下一个可用的 task ID (al-YYYYMMDD-NNN)"""
    date_prefix = datetime.now(TZ).strftime("%Y%m%d")
    ids = []
    if TASKS.exists():
        for d in TASKS.iterdir():
            if d.is_dir() and d.name.startswith(f"al-{date_prefix}"):
                try:
                    ids.append(int(d.name.split("-")[2]))
                except (IndexError, ValueError):
                    continue
    seq = max(ids) + 1 if ids else 1
    return f"al-{date_prefix}-{seq:03d}"


def build_manifest(task_id: str, title: str, state: str) -> str:
    """生成 task-manifest.yaml 内容"""
    now = datetime.now(TZ).isoformat()
    hash_val = sha256_of(REQUIREMENTS)
    use_demand = state == "demand"

    demand_date = f'"{now}"' if use_demand else "null"
    demand_summary = '"需求已锁定，可开始执行"' if use_demand else "null"

    return f"""task_id: "{task_id}"
title: "{title}"
author: "jaden"
created_at: "{now}"
closed_at: null
state: {state}
retry_count: 0
max_retries: 3
escalated: false
source: "requirements.md"
source_hash: "{hash_val}"
history:
  - step: created
    profile: research
    date: "{now}"
    summary: "任务已创建，需求待编写"
  - step: demand
    profile: research
    date: {demand_date}
    summary: {demand_summary}
  - step: assign
    profile: ops
    date: null
    summary: null
  - step: implement
    profile: dev
    date: null
    summary: null
  - step: review
    profile: review
    date: null
    summary: null
  - step: close
    profile: ops
    date: null
    summary: null
"""


def create_task_dir(task_id: str) -> Path:
    """创建 task 目录并返回 Path"""
    task_dir = TASKS / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def snapshot_requirements(task_dir: Path):
    """复制 requirements.md 快照到 demand.md"""
    src = REQUIREMENTS
    dst = task_dir / "demand.md"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"  demand.md: 已锁定 requirements.md 快照")
    else:
        dst.write_text("")  # 空文件占位
        print(f"  demand.md: (requirements.md 不存在，创建空占位)")


def update_symlink(task_id: str):
    """更新 tasks/active-task symlink"""
    link = TASKS / "active-task"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(task_id)
    print(f"  symlink: tasks/active-task -> {task_id}")


def main():
    # --- 参数解析 ---
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    title = sys.argv[1]
    use_demand = "--demand" in sys.argv

    # --- 创建 task ---
    task_id = next_task_id()
    task_dir = create_task_dir(task_id)

    print(f"创建 {task_id}: {title}")

    # 快照 requirements.md
    snapshot_requirements(task_dir)

    # 生成 manifest
    state = "demand" if use_demand else "created"
    manifest = build_manifest(task_id, title, state)
    (task_dir / "task-manifest.yaml").write_text(manifest)
    print(f"  task-manifest.yaml: state={state}")

    # 创建空文件
    (task_dir / "features.md").write_text("")
    (task_dir / "audit-log.md").write_text("")

    # symlink
    update_symlink(task_id)

    # --- 总结 ---
    print()
    print(f"✅ 完成: {task_id}")
    print(f"   路径: {task_dir}")
    print(f"   状态: {'demand' if use_demand else 'created'}")
    if use_demand:
        print(f"   就绪: 等待 scanner 自动拣起 (≤5min)")
    else:
        print(f"   下一步: 编辑 requirements.md → 确认后设 state=demand")
        print(f"         编辑 tasks/active-task/task-manifest.yaml，将 state 改为 demand")


if __name__ == "__main__":
    main()
