#!/usr/bin/env python3
"""LLM Radar 配置面自检（preflight）— 只读探针。

回答一个问题: **「外部配置还能不能打通」**，而不是等数据变陈旧再反推。
对照 2026-11-02~11-04 的 DEEPSEEK_API_KEY 401（持续 ~39h、26 轮、无一条告警点出根因）：
采集器只能给出「连续失败 N 次」，本脚本把每类外部依赖单独判一次。

检查项（顺序固定, 名称稳定, 供下游做指纹）:
  key_auth   DEEPSEEK_API_KEY 能否通过 /v1/models（200 / 401 / 超时）
  model      代码默认模型（deepseek-chat 别名）能否真正完成一次最小补全
  x_login    CDP 浏览器级 cookie 里有 auth_token（X 采集登录态）
  cdp_page   /json/list 里至少有 1 个 type=page（chromedriver attach 的前提）
  flclash    7890 是否 LISTEN（海外源 / X 采集的代理前置）
  driver     chromedriver 稳定指针路径是否与本机 Chrome 兼容
  mcp_key    LLM_RADAR_MCP_KEY 是否配置（缺 = MCP 写入面关闭, 不是故障）
  disk       repo 所在卷使用率 < 90%

用法:
  scripts/llm-radar-preflight.py [--json] [--only key_auth,x_login] [--max-age 600] [--record]

约定:
  · 只读: 唯一副作用是 `--record` 追加一行到 cache/records/preflight.log（gitignored）
  · 退出码恒 0（no_agent cron 的 rc≠0 会另发引擎级告警; 结论放在 JSON/正文里）
  · 判据宁可「可疑」不「假装 OK」: 探不动 ⇒ skip（带原因）, 不写成 ok
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# x.com 可达性真源（同目录 flclash_proxy）: 只读探测, 不拉起代理
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from flclash_proxy import probe_best as _probe_best     # noqa: E402
    from flclash_proxy import REACH_TIMEOUT as _REACH_TIMEOUT
except Exception:                                            # noqa: BLE001
    _probe_best = None
    _REACH_TIMEOUT = 5.0
RECORD_DIR = PROJECT_ROOT / 'cache' / 'records'
RECORD = RECORD_DIR / 'preflight.log'
CACHE_FILE = RECORD_DIR / 'preflight-cache.json'

API_BASE = (os.environ.get('LLM_RADAR_API_BASE') or 'https://api.deepseek.com/v1').rstrip('/')
PROBE_MODEL = os.environ.get('LLM_RADAR_PROBE_MODEL') or 'deepseek-chat'  # 与 _call_deepseek 默认一致
CDP_PORT = int(os.environ.get('TWITTER_CDP_PORT') or 9222)
PROXY_PORT = int(os.environ.get('TWITTER_FLCLASH_PORT') or 7890)
HTTP_TIMEOUT = float(os.environ.get('LLM_RADAR_PREFLIGHT_TIMEOUT') or 5)
DISK_LIMIT_PCT = 90

CHECK_NAMES = ('key_auth', 'model', 'x_login', 'cdp_page', 'x_reach', 'flclash', 'driver',
               'mcp_key', 'disk')


# ---------- 基础 ----------
def _result(name, status, value, detail='', remedy=''):
    return {'name': name, 'status': status, 'value': value, 'detail': detail[:200], 'remedy': remedy}


def _load_dotenv(path=None):
    """加载仓库 .env（不覆盖已存在的环境变量）。

    为什么要自己做: 探针会在 cron / 最小 env 下被调用，而 `DEEPSEEK_API_KEY` 只在
    `llm-radar-run.sh`（source .env）里才进环境 ⇒ 不加载就会把「最小 env」误报成「没配 key」。
    """
    p = Path(path) if path else (PROJECT_ROOT / '.env')
    if not p.is_file():
        return
    try:
        for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            k = k.strip()
            if not k or not k.replace('_', '').isalnum():
                continue
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        return


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _http_json(url, headers=None, timeout=HTTP_TIMEOUT, data=None):
    """极简 HTTP(JSON)。返回 (code, payload)；网络异常时 code=None。"""
    req = urllib.request.Request(url, headers=headers or {}, method='POST' if data else 'GET')
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, body, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8', 'replace') or '{}')
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode('utf-8', 'replace') or '{}')
        except Exception:  # noqa: BLE001
            payload = {}
        return e.code, payload
    except Exception as e:  # noqa: BLE001
        return None, {'error': f'{type(e).__name__}: {e}'}


def _port_open(port, timeout=0.6):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=timeout):
            return True
    except OSError:
        return False


def _load_collector():
    """复用采集器的 CDP 实现（单一真源）；加载失败返回 None。"""
    path = PROJECT_ROOT / 'llm-radar-collector.py'
    try:
        spec = importlib.util.spec_from_file_location('llm_radar_collector_preflight', path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001
        return None


# ---------- 各检查 ----------
def check_key_auth(_ctx):
    key = (os.environ.get('DEEPSEEK_API_KEY') or '').strip()
    if not key:
        return _result('key_auth', 'fail', 'no key',
                       '当前进程环境没有 DEEPSEEK_API_KEY（.env 未加载或未设置）',
                       '确认 .env 第 1 行；`lr` wrapper 的 .env 段属 GOV-1 手工 patch, 重生成会丢')
    code, payload = _http_json(f'{API_BASE}/models', {'Authorization': f'Bearer {key}'})
    if code == 200:
        ids = [m.get('id') for m in (payload.get('data') or [])]
        _ctx['catalog'] = ids
        return _result('key_auth', 'ok', 'ok', f'{len(ids)} 个模型可用')
    if code in (401, 403):
        return _result('key_auth', 'fail', f'auth {code}',
                       (payload.get('error') or {}).get('message', '鉴权失败'),
                       '换 key: 平台生成新 key → 改 .env 第 1 行 → lr run --force')
    if code == 402 or code == 429:
        return _result('key_auth', 'warn', f'quota {code}', '余额/限流问题，凭据本身有效',
                       '充值或用等待窗口重试')
    if code is None:
        return _result('key_auth', 'skip', 'unreachable',
                       f'无法连通 {API_BASE}: {payload.get("error", "")}', '先确认 FlClash / 网络')
    return _result('key_auth', 'warn', f'http {code}', json.dumps(payload)[:120])


def check_model(ctx):
    if ctx.get('catalog') is None:
        return _result('model', 'skip', 'unknown', 'key_auth 未通过，未探测模型')
    key = (os.environ.get('DEEPSEEK_API_KEY') or '').strip()
    code, payload = _http_json(
        f'{API_BASE}/chat/completions',
        {'Authorization': f'Bearer {key}'},
        data={'model': PROBE_MODEL, 'messages': [{'role': 'user', 'content': 'ok'}], 'max_tokens': 1},
    )
    if code == 200:
        served = payload.get('model') or PROBE_MODEL
        return _result('model', 'ok', served, f'请求 {PROBE_MODEL} → 实际 {served}')
    if code == 400:
        return _result('model', 'fail', f'model {PROBE_MODEL}',
                       json.dumps(payload.get('error') or payload)[:160],
                       '把 _call_deepseek 默认模型改成目录内 id（vendor 下线别名时会发生）')
    if code in (401, 403):
        return _result('model', 'fail', f'auth {code}', 'key 在模型探测时被拒',
                       '先修 key_auth')
    if code is None:
        return _result('model', 'skip', 'unreachable', '模型探测网络不通')
    return _result('model', 'warn', f'http {code}', json.dumps(payload)[:120])


def check_x_login(_ctx):
    mod = _load_collector()
    if mod is None:
        return _result('x_login', 'skip', 'unknown', '采集器模块加载失败, 无法读 CDP cookie')
    ready, logged, note = mod._chrome_state(CDP_PORT)
    if not ready:
        return _result('x_login', 'fail', 'cdp down', f'{CDP_PORT} 未就绪',
                       '起调试 Chrome: lr chrome --wait（launchd 常驻实例被停掉时会发生）')
    if not logged:
        return _result('x_login', 'fail', 'not logged in', note,
                       '人工重登: lr chrome --wait（先确保 FlClash 在跑）')
    return _result('x_login', 'ok', 'auth_token', note)


def check_cdp_page(_ctx):
    if not _port_open(CDP_PORT):
        return _result('cdp_page', 'fail', 'cdp down', f'{CDP_PORT} 未监听',
                       '起调试 Chrome: lr chrome --wait')
    code, payload = _http_json(f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=3)
    if code != 200 or not isinstance(payload, list):
        return _result('cdp_page', 'warn', 'unparsed', '无法解析 /json/list')
    pages = [t for t in payload if t.get('type') == 'page']
    if not pages:
        return _result('cdp_page', 'fail', '0 page',
                       f'{len(payload)} 个 target 但没有 page',
                       'PUT /json/new?https://x.com/home 或重载 launchd plist（末尾须带 URL）')
    return _result('cdp_page', 'ok', f'{len(pages)} page', f'共 {len(payload)} 个 target')


def check_flclash(_ctx):
    if os.uname().sysname != 'Darwin':
        return _result('flclash', 'skip', 'n/a', '非 macOS 平台无 FlClash')
    if _port_open(PROXY_PORT):
        return _result('flclash', 'ok', f'{PROXY_PORT} listen')
    return _result('flclash', 'warn', f'{PROXY_PORT} closed',
                   '代理未监听: 海外源(github-trending/huggingface)与 X 采集会失败',
                   'open -g -a FlClash（采集器内也有 on-demand ensure）')


def check_driver(_ctx):
    boot = PROJECT_ROOT / 'scripts' / 'chromedriver_bootstrap.py'
    if not boot.is_file():
        return _result('driver', 'skip', 'unknown', 'chromedriver_bootstrap.py 缺失')
    try:
        spec = importlib.util.spec_from_file_location('cd_bootstrap', boot)
        if spec is None or spec.loader is None:
            return _result('driver', 'skip', 'unknown', '无法加载 chromedriver_bootstrap')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        st = mod.check() or {}
        summary = mod.state_summary(st) or {}
    except Exception as e:  # noqa: BLE001
        return _result('driver', 'skip', 'unknown', f'读取驱动状态失败: {type(e).__name__}')
    chrome = st.get('chrome_version') if isinstance(st, dict) else None
    versions = ','.join(summary.get('good') or []) if isinstance(summary, dict) else ''
    # 判据只用 stable_compatible: manager 的 verdict 只要任一注册路径兼容就成立
    if isinstance(summary, dict) and summary.get('stable_compatible'):
        return _result('driver', 'ok', versions or 'stable ok',
                       f'chrome {chrome} / 稳定路径已兼容（驱动 {versions}）')
    return _result('driver', 'fail', 'stable incompatible',
                   f'chrome {chrome} / 稳定路径未兼容（可用 {versions or "无"}）',
                   'chromedriver-manager upgrade --all --json')


def check_x_reach(_ctx):
    """x.com 是否可达（直连或经 7890）。只探测, **不拉起代理**（preflight 必须只读）。"""
    if _probe_best is None:
        return _result('x_reach', 'skip', 'unknown', 'flclash_proxy 未加载')
    try:
        probe = _probe_best(timeout=min(float(_REACH_TIMEOUT), 3.0))
    except Exception as e:                                   # noqa: BLE001
        return _result('x_reach', 'skip', 'unknown', f'{type(e).__name__}: {str(e)[:80]}')
    if probe.get('ok'):
        where = '经代理' if probe.get('via') == 'proxy' else '直连'
        return _result('x_reach', 'ok', where, f"x.com {probe.get('elapsed')}s 可达（{where}）")
    return _result('x_reach', 'warn', f"unreachable {probe.get('class')}",
                   probe.get('detail', ''),
                   '先看 FlClash: python3 scripts/flclash_proxy.py reach；X 采集会按设计跳过')


def check_mcp_key(_ctx):
    key = (os.environ.get('LLM_RADAR_MCP_KEY') or '').strip()
    if key:
        return _result('mcp_key', 'ok', 'configured')
    return _result('mcp_key', 'info', 'absent',
                   'MCP 写入面未启用（本机 .env 无该键; 属关闭状态, 不是故障）')


def _df_facts(path):
    """解析 `df -k <path>` 的 used/avail（1K 块）。

    为什么不用 shutil.disk_usage: APFS 上它把**同容器其他卷**也算进 used（实测同一时刻
    527.5 GiB vs df 496.5 GiB，偏 3–6 个点），会让 90% 阈值在 86% 就误报。
    口径与 `df` 的 Capacity 列一致 = used/(used+avail)（那是用户在 Finder/df 里看到的值）。
    """
    try:
        r = subprocess.run(['df', '-k', str(path)], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        lines = r.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        parts = lines[1].split()
        if len(parts) < 4:
            return None
        total, used, avail = int(parts[1]), int(parts[2]), int(parts[3])
        if total <= 0:
            return None
        denom = (used + avail) or total
        return {'total_gib': total / 1048576, 'used_gib': used / 1048576,
                'avail_gib': avail / 1048576, 'pct': used / denom * 100,
                'mount': parts[-1]}
    except Exception:  # noqa: BLE001
        return None


def check_disk(_ctx):
    facts = _df_facts(PROJECT_ROOT)
    if facts is None:                     # 回退: shutil（偏差更大, 但至少给个结论）
        try:
            usage = shutil.disk_usage(str(PROJECT_ROOT))
        except OSError as e:
            return _result('disk', 'skip', 'unknown', str(e)[:80])
        facts = {'total_gib': usage.total / 1048576, 'used_gib': usage.used / 1048576,
                 'avail_gib': usage.free / 1048576,
                 'pct': usage.used / max(usage.total, 1) * 100, 'mount': 'shutil'}
    pct = facts['pct']
    detail = (f"used {facts['used_gib']:.1f}/{facts['total_gib']:.1f} GiB, "
              f"avail {facts['avail_gib']:.1f} GiB ({facts['mount']})")
    if pct >= DISK_LIMIT_PCT:
        return _result('disk', 'fail', f'{pct:.1f}%', detail,
                       '清理 cache/logs 归档或扩容（du 只作同层比较, 判容量用 df）')
    return _result('disk', 'ok', f'{pct:.1f}%', detail)


CHECKS = {
    'key_auth': check_key_auth,
    'model': check_model,
    'x_login': check_x_login,
    'cdp_page': check_cdp_page,
    'x_reach': check_x_reach,
    'flclash': check_flclash,
    'driver': check_driver,
    'mcp_key': check_mcp_key,
    'disk': check_disk,
}


# ---------- 入口 ----------
def run_checks(only=None):
    ctx = {}
    names = [n for n in CHECK_NAMES if not only or n in only]
    return [CHECKS[n](ctx) for n in names]


def summarize(checks):
    fails = [c['name'] for c in checks if c['status'] == 'fail']
    warns = [c['name'] for c in checks if c['status'] == 'warn']
    skips = [c['name'] for c in checks if c['status'] == 'skip']
    return {'ok': not fails, 'fails': fails, 'warns': warns, 'skips': skips}


def render_text(payload):
    lines = [f"preflight {'OK' if payload['ok'] else 'FAIL'}  {payload['generated_at']}"]
    for c in payload['checks']:
        lines.append(f"  [{c['status']:4}] {c['name']:<8} {c['value']:<16} {c['detail']}")
        if c['status'] in ('fail', 'warn') and c.get('remedy'):
            lines.append(f"         修复: {c['remedy']}")
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='LLM Radar 配置面自检（只读）')
    ap.add_argument('--json', action='store_true', help='机器可读输出')
    ap.add_argument('--only', default='', help='只跑部分检查, 逗号分隔')
    ap.add_argument('--max-age', type=int, default=0, help='复用 N 秒内的缓存结果（0=不复用）')
    ap.add_argument('--record', action='store_true', help='追加一行摘要到 cache/records/preflight.log')
    args = ap.parse_args(argv)

    only = {s.strip() for s in args.only.split(',') if s.strip()}
    _load_dotenv()
    if args.max_age > 0:
        try:
            cached = json.loads(CACHE_FILE.read_text())
            age = datetime.now().timestamp() - float(cached.get('ts') or 0)
            if 0 <= age <= args.max_age and not only:
                cached['cached'] = True
                print(json.dumps(cached, ensure_ascii=False) if args.json else render_text(cached))
                return 0
        except Exception:  # noqa: BLE001
            pass

    checks = run_checks(only)
    s = summarize(checks)
    payload = {'generated_at': _now(), 'ts': datetime.now().timestamp(), **s, 'checks': checks}

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False))
    except OSError:
        pass
    if args.record:
        brief = ' '.join(f'{c["name"]}={c["value"]}' for c in checks)
        with RECORD.open('a', encoding='utf-8') as fh:
            fh.write(f"{payload['generated_at']} ok={payload['ok']} {brief}\n")

    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_text(payload))
    return 0


if __name__ == '__main__':
    # 唯一捕获点 (§11.1-1)：文案/退出码同源 cli_interrupt（§11.2），禁手抄第二份
    from cli_interrupt import emit  # 入口段内 import ⇒ 被 importlib 加载时零副作用

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('python3 scripts/llm-radar-preflight.py', sys.argv)
