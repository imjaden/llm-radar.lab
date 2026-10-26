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
    """采集侧是否真的可用: 稳定路径在就只认它（它才是被消费的那份）; 不在则任一兼容路径即可。"""
    if s['stable_compatible']:
        return True
    if s['stable_exists']:
        return False          # 稳定路径存在但不兼容 ⇒ 必须升级, 否则采集器将用到旧驱动
    return bool(s['paths'])


def usable_path(st=None):
    """挑一个「已验证兼容」的驱动: 优先稳定路径, 否则任一 compatible 路径。"""
    s = state_summary(st if st is not None else check())
    if s['stable'] and Path(s['stable']).is_file():
        return s['stable']
    for p in s['paths']:
        if p and Path(p).is_file():
            return p
    return None


def ensure(timeout=90, download_timeout=300):
    """就绪则零动作; 否则 upgrade（必要时先 download）→ 复核。

    → (ok: bool, action: str, summary: dict, detail: str)
      action ∈ noop / upgraded / download_failed / upgrade_failed / still_incompatible / no_manager
    """
    st = check(timeout=timeout)
    if st is None:
        return False, 'no_manager', {}, f'manager 不可用: {MANAGER}'
    s = state_summary(st)
    if _ready(s):
        return True, 'noop', s, ''

    detail = []
    if not s['icloud_has_compatible']:
        rc, out = _run([MANAGER, 'download', '--json'], timeout=download_timeout)
        detail.append(f'download rc={rc} {out.splitlines()[-1][:120] if out else ""}')
        if rc != 0:
            rc2, out2 = _run([MANAGER, 'download', '--json'], timeout=download_timeout)   # 网络抖动重试一次
            detail.append(f'download retry rc={rc2} {out2.splitlines()[-1][:120] if out2 else ""}')
            if rc2 != 0:
                return False, 'download_failed', s, ' | '.join(detail)

    # --all --json: 非交互地升级**全部**注册路径（不加 --json 会 input() 等待, cron 下会挂住）
    rc, out = _run([MANAGER, 'upgrade', '--all', '--json'], timeout=download_timeout)
    detail.append(f'upgrade rc={rc} {out.splitlines()[-1][:120] if out else ""}')
    if rc != 0:
        return False, 'upgrade_failed', s, ' | '.join(detail)

    st2 = check(timeout=timeout)
    s2 = state_summary(st2)
    if _ready(s2):
        return True, 'upgraded', s2, ' | '.join(detail)
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
    if action == 'noop':
        return ''
    if ok and action == 'upgraded':
        old = "・".join(before.get('drivers') or before.get('good') or []) or '?'
        new = "・".join(after.get('good') or []) or '?'
        return (f'🔧 LLM Radar chromedriver 已自动跟随\n---\n**动作**\n'
                f'- 版本：{old} → {new}（Chrome {after.get("chrome")}）\n'
                f'- 来源：chromedriver-manager upgrade（iCloud 归档）\n'
                f'- 生效路径：{after.get("stable") or (after.get("paths") or ["?"])[0]}\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    if action in ('download_failed', 'upgrade_failed', 'still_incompatible'):
        return (f'{head}\n---\n**根因分析**\n'
                f'- chromedriver 未能跟随 Chrome {after.get("chrome") or before.get("chrome")}\n'
                f'- 当前驱动：{"・".join(before.get("drivers") or before.get("good") or []) or "未知"}\n'
                f'- 失败环节：{action}\n'
                f'- 详情：{(detail or "")[:160]}\n'
                f'- 修复指令：chromedriver-manager download && chromedriver-manager upgrade\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    if action == 'no_manager':
        return (f'{head}\n---\n**根因分析**\n- 找不到 chromedriver-manager（{MANAGER}）\n'
                f'- 采集侧将回退到本地缓存扫描（Chrome 升级后可能不匹配）\n'
                f'---\n来源：cron job llm-radar-chromedriver-guard')
    return ''


def watch(force=False):
    """cron 入口: 状态变化才输出。→ (message_or_empty, exit_code)"""
    prev = load_state()
    ok, action, after, detail = ensure()
    sig = f'{after.get("verdict")}|{after.get("chrome")}|{",".join(after.get("good") or [])}'
    save_state(ts=_ts(), ok=ok, action=action, sig=sig, summary=after, detail=detail[:400])
    if action == 'noop':
        if prev.get('ok') is False and not prev.get('action') == 'noop':
            return (f'✅ LLM Radar chromedriver 已恢复\n---\n- Chrome {after.get("chrome")} 与驱动 '
                    f'{"・".join(after.get("good") or [])}\n---\n来源：cron job llm-radar-chromedriver-guard',
                    0)
        return '', 0
    if prev.get('sig') == sig and not force:      # 同一故障指纹不重复发
        return '', 0 if ok else 1
    return message(action, ok, prev.get('summary') or {}, after, detail), (0 if ok else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description='chromedriver 版本守卫（单一真源: chromedriver-manager）')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--print-path', action='store_true', help='输出一个已验证兼容的驱动路径（无则空）')
    g.add_argument('--check', action='store_true', help='打印 check 摘要 JSON')
    g.add_argument('--ensure', action='store_true', help='不就绪则升级并复核')
    g.add_argument('--watch', action='store_true', help='cron 入口: 状态变化才输出消息')
    g.add_argument('--version', action='store_true', help='打印 chromedriver --version')
    ap.add_argument('--force', action='store_true', help='--watch 时忽略指纹去重')
    a = ap.parse_args(argv)

    if a.print_path:
        p = usable_path()
        if p:
            print(p)
            return 0
        return 1
    if a.check:
        print(json.dumps(state_summary(check()), ensure_ascii=False))
        return 0 if state_summary(check()).get('verdict') == 'compatible' else 1
    if a.ensure:
        ok, action, after, detail = ensure()
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
