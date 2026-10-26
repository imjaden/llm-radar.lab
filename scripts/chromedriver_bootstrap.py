#!/usr/bin/env python3
"""chromedriver 版本守卫 —— Chrome 自动升级后自动跟随, 不再打死采集。

单一真源: `chromedriver-manager`（script-miner, CLI 别名 `~/.local/bin/chromedriver-manager`）
负责 下载 / 版本校验 / iCloud 归档。本模块只做三件事, 不自己下载驱动:

  · check()      → 读 `chromedriver-manager check --json`（verdict / chrome_version / paths / icloud）
  · ensure()     → verdict != compatible 时: iCloud 已有匹配版 ⇒ 只 `upgrade`; 否则先 `download` 再 `upgrade`;
                   最后复核。**离线优先**, 不重复造下载逻辑。
  · print_path() → 给采集器一个「已验证兼容」的驱动路径（供 $CHROMEDRIVER / $TWITTER_CHROMEDRIVER 注入）

消费方:
  · `llm-radar-run.sh` / `scripts/twitter-collector-cron.sh` —— 采集前注入路径（--print-path）
  · ops cron `llm-radar-chromedriver-guard`（每小时 :05, 与 :20/:40 错峰）—— `--watch`:
    状态不变 ⇒ 空 stdout（静默）; 升级成功/失败/恢复 ⇒ 单条消息（no_agent + 飞书投递）

状态文件: cache/records/chromedriver-guard.json
退出码: 0 正常·已升级·无需动作 / 1 未就绪(采集侧应回退或跳过) / 2 manager 不可用
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / 'cache' / 'records' / 'chromedriver-guard.json'
MANAGER = Path(os.environ.get('CHROMEDRIVER_MANAGER') or (Path.home() / '.local' / 'bin' / 'chromedriver-manager'))
# manager 升级时写入的「不带版本」稳定路径（已通过 `chromedriver-manager add --path` 注册）
STABLE = Path.home() / 'Library' / 'Application Support' / 'llm-radar' / 'chromedriver' / 'chromedriver'


def _ts():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _run(argv, timeout=120):
    """执行 manager 子命令 → (rc, stdout+stderr 文本)。异常不外抛。"""
    try:
        p = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()
    except Exception as e:  # noqa: BLE001
        return 99, f'{type(e).__name__}: {e}'


def manager_available():
    return MANAGER.exists()


def parse_check(text):
    """从 manager 输出里取最后一个 JSON 对象（--json 是单行, 但前面可能有 ✅ 提示行）。"""
    for line in reversed((text or '').splitlines()):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def check(timeout=90):
    """→ dict | None（None = manager 不可用或输出不可解析）"""
    if not manager_available():
        return None
    rc, out = _run([MANAGER, 'check', '--json'], timeout=timeout)
    return parse_check(out)


def state_summary(st):
    """把 check 结果压成可比较/可落盘的小结构。

    注意 manager 的 `verdict=compatible` 只要**任一**注册路径兼容就成立; 而采集器实际吃的是
    **稳定路径**, 所以这里单独给出 `stable_compatible`: 判定「采集是否真的可用」以它为准。
    """
    if not st:
        return {'verdict': 'unknown', 'chrome': None, 'drivers': [], 'stable': None,
                'stable_exists': False, 'stable_compatible': False, 'good': [],
                'icloud_has_compatible': False, 'paths': []}
    bad = [p for p in (st.get('paths') or []) if p.get('exists') and not p.get('compatible')]
    good = [p for p in (st.get('paths') or []) if p.get('exists') and p.get('compatible')]
    stable_compatible = next((p.get('path') for p in good
                              if os.path.realpath(str(p.get('path'))) == os.path.realpath(str(STABLE))), None)
    stable_listed = next((p for p in (st.get('paths') or [])
                          if os.path.realpath(str(p.get('path'))) == os.path.realpath(str(STABLE))), None)
    return {
        'verdict': st.get('verdict') or 'unknown',
        'chrome': st.get('chrome_version'),
        'drivers': sorted({str(p.get('version')) for p in bad}),
        'good': sorted({str(p.get('version')) for p in good}),
        'stable': stable_compatible,
        'stable_exists': bool(stable_listed and stable_listed.get('exists')) or STABLE.is_file(),
        'stable_compatible': bool(stable_compatible),
        'icloud_has_compatible': bool((st.get('icloud') or {}).get('has_compatible')),
        'paths': [p.get('path') for p in good],
    }


def _ready(s) -> bool:
    """采集侧是否真的可用: 稳定路径在就只认它（它才是被消费的那份）; 不在则任一兼容路径即可。

    用 `.get()`: 调用方可能传「精简摘要」（含历史状态文件里没有新字段的旧快照）。
    """
    if s.get('stable_compatible'):
        return True
    if s.get('stable_exists'):
        return False          # 稳定路径存在但不兼容 ⇒ 必须升级, 否则采集器将用到旧驱动
    return bool(s.get('paths'))


def usable_path(st=None):
    """挑一个「已验证兼容」的驱动: 优先稳定路径, 否则任一 compatible 路径。"""
    s = state_summary(st if st is not None else check())
    if s['stable'] and Path(s['stable']).is_file():
        return s['stable']
    for p in s['paths']:
        if p and Path(p).is_file():
            return p
    return None


# manager `download` 的**永久性**失败特征：无可用下载地址 ≠ 网络抖动 ⇒ 重试只是白等 5 分钟 + 多打一次 API
_PERMANENT_DOWNLOAD = ('未找到适配', '未找到下载地址', '无 Mac 平台包', '无法获取 Chrome 版本')
# manager `upgrade` 的专用退出码（v1.4 · DAILY-CHECKER-CL122）：0 真升级 / 3 无事可做(noop) / 1 失败
UPGRADE_NOOP_RC = 3


def _looks_permanent(out) -> bool:
    return any(k in (out or '') for k in _PERMANENT_DOWNLOAD)


def _acquire_lock():
    """跨入口互斥 → (fh|None, 'locked'|'busy'|'unavailable')。

    三个入口都会跑 ensure：守卫 cron :05 / 主采集 :40 / X 采集 :20。而 manager 的 upgrade 是
    `shutil.copy2` **覆盖同一个稳定路径（非原子）** ⇒ 并发写时采集器可能 exec 到半个二进制。
    拿不到锁 ⇒ 立刻返回（采集侧绝不排队、不阻塞）; flock 不可用 ⇒ 放行（退回不加锁的旧行为）。
    """
    path = STATE.parent / '.chromedriver-guard.lock'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, 'w', encoding='utf-8')
    except OSError:
        return None, 'unavailable'
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        return fh, 'unavailable'
    except OSError:
        fh.close()
        return None, 'busy'
    return fh, 'locked'


def _release_lock(fh):
    if not fh:
        return
    try:
        fh.close()          # close 即释放 flock
    except Exception:  # noqa: BLE001
        pass


def ensure(timeout=90, download_timeout=300, deadline=None):
    """就绪则零动作; 否则 upgrade（必要时先 download）→ 复核。

    `deadline`（秒）: 总预算上限（LR-CDG-007）。采集前置守卫用它把最坏等待从 990s 压到 ~60s,
    超预算 ⇒ action='deadline', 交回每小时 :05 的 cron 继续跟随（采集不陪等）。
    → (ok: bool, action: str, summary: dict, detail: str)
      action ∈ noop / busy / upgraded / deadline / download_failed / upgrade_failed /
               stable_unmanaged / still_incompatible / no_manager
    """
    start = time.monotonic()

    def budget(base):
        left = _left(start, deadline)
        return base if left is None else min(base, left)

    def exhausted():
        return deadline is not None and (_left(start, deadline) or 0.0) <= 0

    st = check(timeout=budget(timeout))
    if st is None:
        return False, 'no_manager', {}, f'manager 不可用: {MANAGER}'
    s = state_summary(st)
    if _ready(s):
        return True, 'noop', s, ''

    holder, lock_state = _acquire_lock()
    if lock_state == 'busy':
        return True, 'busy', s, '另一个入口正在 download/upgrade, 本入口跳过（不排队）'
    try:
        return _follow(s, budget, exhausted, timeout, download_timeout)
    finally:
        _release_lock(holder)


def _left(start, deadline):
    """→ None = 无预算限制; 否则剩余秒数（可为 0）。"""
    return None if deadline is None else max(0.0, float(deadline) - (time.monotonic() - start))


def _follow(s, budget, exhausted, timeout=90, download_timeout=300):
    detail = []
    if not s['icloud_has_compatible']:
        if exhausted():
            return False, 'deadline', s, '预算耗尽: 未开始 download'
        rc, out = _run([MANAGER, 'download', '--json'], timeout=budget(download_timeout))
        detail.append(f'download rc={rc} {out.splitlines()[-1][:120] if out else ""}')
        if rc != 0:
            if _looks_permanent(out):
                return False, 'download_failed', s, ' | '.join(detail)   # 永久性失败: 重试无意义
            if exhausted():
                return False, 'deadline', s, '预算耗尽: 放弃 download 重试'
            rc2, out2 = _run([MANAGER, 'download', '--json'], timeout=budget(download_timeout))
            detail.append(f'download retry rc={rc2} {out2.splitlines()[-1][:120] if out2 else ""}')
            if rc2 != 0:
                return False, 'download_failed', s, ' | '.join(detail)

    if exhausted():
        return False, 'deadline', s, '预算耗尽: 未开始 upgrade'
    # --all --json: 非交互地升级**全部**注册路径（不加 --json 会 input() 等待, cron 下会挂住）
    rc, out = _run([MANAGER, 'upgrade', '--all', '--json'], timeout=budget(download_timeout))
    detail.append(f'upgrade rc={rc} {out.splitlines()[-1][:120] if out else ""}')
    if rc not in (0, UPGRADE_NOOP_RC):
        return False, 'upgrade_failed', s, ' | '.join(detail)

    st2 = check(timeout=budget(timeout))
    s2 = state_summary(st2)
    if _ready(s2):
        return True, ('upgraded' if rc == 0 else 'noop'), s2, ' | '.join(detail)
    if rc == UPGRADE_NOOP_RC and s2['stable_exists']:
        # rc=3 是 manager 的「无事可做」码, 不是失败: 说明稳定路径**不是**受管路径 ⇒ upgrade 永远修不到它
        return False, 'stable_unmanaged', s2, ' | '.join(detail)
    return False, 'still_incompatible', s2, ' | '.join(detail)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}


def save_state(**kw):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(kw, ensure_ascii=False, indent=2), encoding='utf-8')


# ---------- 消息（空输出 = 静默，供 cron no_agent 使用） ----------
def message(action, ok, before, after, detail) -> str:
    head = '🔴 LLM Radar chromedriver 异常'
    if action in ('noop', 'busy'):
        return ''
    if ok and action == 'upgraded':
        old = "・".join(before.get('drivers') or before.get('good') or []) or '?'
        new = "・".join(after.get('good') or []) or '?'
        return (f'🔧 LLM Radar chromedriver 已自动跟随\n---\n**动作**\n'
                f'- 版本：{old} → {new}（Chrome {after.get("chrome")}）\n'
                f'- 来源：chromedriver-manager upgrade（iCloud 归档）\n'
                f'- 生效路径：{after.get("stable") or (after.get("paths") or ["?"])[0]}\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    if action == 'stable_unmanaged':
        return (f'{head}\n---\n**根因分析**\n'
                f'- 稳定路径在盘上但不是 chromedriver-manager 的**受管路径** ⇒ upgrade 只会返回 noop(rc=3),\n'
                f'  永远修不到它（采集侧只能靠回退路径）\n'
                f'- 稳定路径：{STABLE}\n'
                f'- 当前驱动：{"・".join(after.get("drivers") or []) or "未知"}（Chrome {after.get("chrome")}）\n'
                f'- 修复指令：chromedriver-manager add --path "{STABLE}" && chromedriver-manager upgrade --all --json\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    if action in ('download_failed', 'upgrade_failed', 'still_incompatible'):
        return (f'{head}\n---\n**根因分析**\n'
                f'- chromedriver 未能跟随 Chrome {after.get("chrome") or before.get("chrome")}\n'
                f'- 当前驱动：{"・".join(before.get("drivers") or before.get("good") or []) or "未知"}\n'
                f'- 失败环节：{action}\n'
                f'- 详情：{(detail or "")[:160]}\n'
                f'- 修复指令：chromedriver-manager download && chromedriver-manager upgrade --all --json\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    if action == 'no_manager':
        return (f'{head}\n---\n**根因分析**\n- 找不到可用的 chromedriver-manager（{MANAGER}）\n'
                f'- 采集侧将回退到本地缓存扫描（Chrome 升级后可能不匹配）\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    return ''


def _fingerprint(action, s) -> str:
    """故障/恢复指纹。

    ⚠️ 只取 `verdict|chrome|good` 会漏掉本设计的**核心场景**: manager 的 verdict=compatible
    只要任一注册路径兼容, 稳定路径被覆盖成旧版时这三项全不变 ⇒ 升级成功与失败消息都会被
    去重吞掉（2026-10-26 实证: 注入旧驱动到稳定路径后 watch 返回 ('', 1)）。
    这里额外带上 `ready`（采集是否真的可用）与 `action`（故障环节）。
    """
    return (f'ready={int(_ready(s))}|verdict={s.get("verdict")}|chrome={s.get("chrome")}'
            f'|good={",".join(s.get("good") or [])}|action={action}')


def watch(force=False):
    """cron 入口: 状态变化才输出。

    退出码**恒 0**（Q-4）：no_agent cron 对 rc≠0 会另发一条引擎级错误通知，
    与「正文去重」叠加就变成每小时重复响；失败信息一律走正文（兄弟 watchdog 同口径）。
    """
    try:
        return _watch(force)
    except Exception as e:  # noqa: BLE001  写盘/manager 异常不得静默
        return (f'🔴 LLM Radar chromedriver 守卫执行异常\n---\n**根因分析**\n'
                f'- {type(e).__name__}: {str(e)[:160]}\n'
                f'- 修复指令：python3 scripts/chromedriver_bootstrap.py --check\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard', 0)


def _watch(force=False):
    prev = load_state()
    ok, action, after, detail = ensure()
    sig = _fingerprint(action, after)
    since = None if ok else (prev.get('since') or _ts())   # 故障起点, 恢复消息引用（与 collect-watch 同口径）
    save_state(ts=_ts(), ok=ok, action=action, sig=sig, since=since,
               summary=after, detail=detail[:400])
    if action in ('noop', 'busy'):
        if action == 'noop' and prev.get('ok') is False:
            return (f'✅ LLM Radar chromedriver 已恢复\n---\n- Chrome {after.get("chrome")} 与驱动 '
                    f'{"・".join(after.get("good") or [])}\n'
                    f'- 故障起点：{prev.get("since") or "?"}\n'
                    f'---\n来源：cron job llm-radar-chromedriver-guard',
                    0)
        return '', 0
    if action == 'upgraded':          # 「事件」不是「状态」: 每次真升级都要报, 不做指纹去重
        return message(action, ok, prev.get('summary') or {}, after, detail), 0
    if prev.get('sig') == sig and not force:      # 同一故障指纹不重复发
        return '', 0
    return message(action, ok, prev.get('summary') or {}, after, detail), 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='chromedriver 版本守卫（单一真源: chromedriver-manager）')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--print-path', action='store_true', help='输出一个已验证兼容的驱动路径（无则空）')
    g.add_argument('--check', action='store_true', help='打印 check 摘要 JSON')
    g.add_argument('--ensure', action='store_true', help='不就绪则升级并复核')
    g.add_argument('--watch', action='store_true', help='cron 入口: 状态变化才输出消息')
    g.add_argument('--version', action='store_true', help='打印 chromedriver --version')
    ap.add_argument('--force', action='store_true', help='--watch 时忽略指纹去重')
    ap.add_argument('--deadline', type=float, default=None,
                    help='--ensure 的总预算秒数（采集前置守卫用 60；超预算即交回 cron）')
    a = ap.parse_args(argv)

    if a.print_path:
        p = usable_path()
        if p:
            print(p)
            return 0
        return 1
    if a.check:
        s = state_summary(check())          # 只调一次 manager: 打印快照与退出码必须同源
        print(json.dumps(s, ensure_ascii=False))
        return 0 if _ready(s) else 1        # 退出码 = 「采集是否真的可用」, 不是 manager 的全局 verdict
    if a.ensure:
        ok, action, after, detail = ensure(deadline=a.deadline)
        print(json.dumps({'ok': ok, 'action': action, 'detail': detail,
                          **after}, ensure_ascii=False))
        return 0 if ok else 1
    if a.watch:
        msg, rc = watch(force=a.force)
        if msg:
            print(msg)
        return rc
    if a.version:
        p = usable_path()
        if not p:
            print('(no compatible chromedriver)', file=sys.stderr)
            return 1
        rc, out = _run([p, '--version'], timeout=30)
        print(out)
        return rc
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
