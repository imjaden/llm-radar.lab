#!/usr/bin/env python3
"""FlClash 代理生命周期单一真源: 探测 / 就绪 / 起停。

本模块是**唯一实现**——`llm-radar-collector.py`、`scripts/twitter-collector.py`(探测) 与
`scripts/twitter-collector-cron.sh`(起停编排, 经 CLI 子命令) 都必须走这里, 不得各自 pgrep/osascript。

命令与阈值口径对齐**声明层真源**(跨项目只读引用, 不在本仓另立一套):
  /Users/jadenli/CodeSpace/script-miner/projects/macosx/macosx-service-policy.json
  `services[FlClash].restart` = stop `osascript -e 'quit app "FlClash"'` / grace 20s /
  force_fallback `kill -TERM {pid}` / start `open -g -a FlClash` / verify `{ports:[7890], wait:180s}`。
  ⚠️ 历史上本仓 START_CMD 少了 `-g`（与上游 policy 及 daily-checker CL151 口径均不符），
  2026-10-23 已对齐为 `open -g -a FlClash`（`-g` = 不抢焦点，采集可能在用户前台工作时触发）。

检测口径(勿改回单一 `pgrep -f` + 应用名): 形如 `osascript -e 'quit app "FlClash"'` 的进程
命令行里同样出现 "FlClash" ⇒ `-f` 会把它自己命中, 产生**假阳性**(判"在跑"却没跑)。
真源用「精确名 `pgrep -x FlClash` ∪ 应用路径 `pgrep -f /Applications/FlClash.app`」双判据,
对上述形态不命中; 反例回归见 tests/test_flclash_proxy.py。

CLI:
  python3 scripts/flclash_proxy.py is-running [--json]   # 退出码 0=在跑 / 1=没跑
  python3 scripts/flclash_proxy.py pids                  # 空格分隔 pid (无则空行)
  python3 scripts/flclash_proxy.py ensure [--timeout 180] [--port 7890] [--json]   # 0=就绪 / 1=未就绪
  python3 scripts/flclash_proxy.py release [--grace 20] [--json]                   # 0=已释放 / 1=仍存活

通知面: **本模块不发任何通知**（CL151 R3：FlClash 侧只有 daily-checker 的「超时重启」一条通知；
采集侧「代理未就绪」只是跳过，不是异常）。历史上的 `notify` 子命令已于 2026-10-26 删除。

stdout = 机器可读单值(status word / JSON); 动作细节走 stderr(人类可读, 便于 cron 日志留痕)。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

APP_NAME = 'FlClash'
APP_PATH = '/Applications/FlClash.app'
START_CMD = ('open', '-g', '-a', APP_NAME)   # -g: 不抢焦点 (CL151)
STOP_CMD = ('osascript', '-e', 'quit app "FlClash"')
READY_PORT = 7890          # 对齐 policy services[FlClash].restart.verify.ports
READY_TIMEOUT = 180.0      # 对齐 policy ...verify.wait
STOP_GRACE = 20.0          # 对齐 policy ...restart.grace
POLL_INTERVAL = 2.0
PROBE_TIMEOUT = 2.0
TERM_WAIT = 3.0
# Q-1 (CL151 review SEC-1/LR-SEC-023): 「进程在」≠「代理通」。已在运行但端口未 LISTEN 时
# （代理暂停 / 端口改配 / 上轮 open 后端口尚未起的窗口）先给这么长的短预算, 仍不通 ⇒ not_ready。
RUNNING_PORT_GRACE = 10.0

# ── x.com 可达性预判（2026-11-04）────────────────────────────────────────────
# 场景: `lr chrome --wait` 等需要在「等待登录 600s」之前先判网络, 不通就按需拉起 FlClash。
# 判据: 拿到**任意 HTTP 响应**即链路可达（含 401/403/302 —— Cloudflare 挑战也算通）;
#       连接层失败/超时/TLS reset 才算不可达。纯 TCP 443 会假通（阻断常发生在 TLS 阶段）。
REACH_URL = os.environ.get('LLM_RADAR_X_PROBE_URL') or 'https://x.com/robots.txt'
REACH_TIMEOUT = 5.0          # 首探
REACH_RETRY_TIMEOUT = 8.0    # 直连「慢但通」的复探预算（防 5s 误判成不可达而多起代理）
REACH_SETTLE = 0.6           # 端口 LISTEN 后给上游握手的宽限


def _run(argv, timeout=30):
    """所有外部命令的唯一出口(测试注入点)。"""
    return subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout)


def _warn(msg):
    print(msg, file=sys.stderr, flush=True)


def _is_darwin():
    return platform.system() == 'Darwin'


def flclash_pids():
    """精确名 ∪ 应用路径双判据取 pid(平台无关, 便于在任意平台做反例回归)。"""
    pids = set()
    for argv in (('pgrep', '-x', APP_NAME), ('pgrep', '-f', APP_PATH)):
        try:
            r = _run(argv, timeout=5)
        except Exception:
            continue
        if r.returncode == 0:
            pids.update(int(t) for t in r.stdout.split() if t.isdigit())
    return sorted(pids)


def is_running():
    """FlClash 是否运行。非 macOS 恒 True(跳过探测, 保留既有语义); 探测异常 → False。"""
    if not _is_darwin():
        return True
    try:
        return bool(flclash_pids())
    except Exception:
        return False


def is_port_listening(port=READY_PORT, host='127.0.0.1', timeout=PROBE_TIMEOUT):
    """就绪判据: 端口可建立 TCP 连接。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _classify_probe_error(exc):
    """探测异常 → 稳定分类（供文案/日志, 不要把异常原文当判据）。"""
    text = f'{type(exc).__name__}: {exc}'.lower()
    if isinstance(exc, socket.gaierror) or 'name or service not known' in text or 'nodename' in text:
        return 'dns'
    if isinstance(exc, (socket.timeout, TimeoutError)) or 'timed out' in text or 'timeout' in text:
        return 'timeout'
    if isinstance(exc, ssl.SSLError) or 'ssl' in text or 'certificate' in text:
        return 'tls'
    if 'reset' in text or 'refused' in text or 'unreachable' in text or 'broken pipe' in text:
        return 'connect'
    return 'other'


def probe_url(url=None, timeout=None, proxy=None):
    """探测 URL 链路可达性（只读, 不拉起任何东西）。

    返回 {'ok', 'class', 'status', 'elapsed', 'url', 'via', 'detail'}
      ok=True  ⇔ 拿到任意 HTTP 响应（2xx/3xx/401/403 都算通）
      ok=False ⇒ class ∈ dns/timeout/tls/connect/other
      via      = 'direct'（默认, 强制忽略环境代理）/ 'proxy'（显式经 proxy 探测）
    为什么分两种: 「直连能不能通」决定**要不要起代理**（VPN/TUN 场景直连就通, 起了反而添乱）;
    而 FlClash 多以系统代理模式工作, 起来后 IPv4 直连仍被墙 ⇒ 复探必须能走 `127.0.0.1:7890`。
    """
    target = url or REACH_URL
    tmo = float(timeout or REACH_TIMEOUT)
    start = time.time()
    handlers = urllib.request.ProxyHandler(
        {} if not proxy else {'http': proxy, 'https': proxy})
    opener = urllib.request.build_opener(handlers)
    req = urllib.request.Request(target, method='GET',
                                 headers={'User-Agent': 'LLMRadarReach/1.0 (+preflight)'})
    via = 'proxy' if proxy else 'direct'
    try:
        with opener.open(req, timeout=tmo) as resp:
            return {'ok': True, 'class': 'http_ok', 'status': getattr(resp, 'status', None),
                    'elapsed': round(time.time() - start, 2), 'url': target, 'via': via,
                    'detail': ''}
    except urllib.error.HTTPError as e:          # 有响应头 ⇒ 链路可达
        return {'ok': True, 'class': 'http_ok', 'status': e.code,
                'elapsed': round(time.time() - start, 2), 'url': target, 'via': via,
                'detail': ''}
    except Exception as e:                       # noqa: BLE001  连接层失败才算不可达
        return {'ok': False, 'class': _classify_probe_error(e), 'status': None,
                'elapsed': round(time.time() - start, 2), 'url': target, 'via': via,
                'detail': f'{type(e).__name__}: {e}'[:150]}


def proxy_url(port=READY_PORT, host='127.0.0.1'):
    return f'http://{host}:{port}'


def probe_best(url=None, timeout=None, port=READY_PORT, prefer='direct'):
    """按 `prefer` 决定先直连还是先经代理, 另一条路作兜底; 返回「最好」的那份结果。

    典型本机事实（2026-11-04 实测）: 直连 x.com 6s 超时 HTTP 000; 经 7890 0.8s 200。
    所以只探直连会把「代理已被 FlClash 带起来」误报成不可达。
    `prefer='proxy'` 用于「代理刚被确认就绪」之后: 先走 7890（快且准）, 直连只在 TUN 模式下才是好路径。
    """
    port_open = is_port_listening(port)
    order = []
    if prefer == 'proxy' and port_open:
        order = [proxy_url(port), None]
    else:
        order = [None] + ([proxy_url(port)] if port_open else [])
    fallback = None
    for proxy in order:
        got = probe_url(url, timeout, proxy=proxy)
        if got['ok']:
            return got
        fallback = fallback or got
    return fallback or probe_url(url, timeout)


def ensure_ready(timeout=READY_TIMEOUT, port=READY_PORT, running_grace=RUNNING_PORT_GRACE):
    """未运行 → `open -g -a FlClash` + 轮询等端口 LISTEN; 已在运行 → 先验端口, 通则复用、不通则短预算等待后判 not_ready。"""
    if not _is_darwin():
        return {'ok': True, 'started': False, 'reason': 'non_darwin', 'pids': []}
    if is_running():
        pids = flclash_pids()
        if is_port_listening(port):
            return {'ok': True, 'started': False, 'reason': 'already_running', 'pids': pids}
        # Q-1: 进程在但端口不通 —— 短预算等待（覆盖「刚 open 完端口还没起」的窗口), 仍不通 ⇒ 未就绪
        deadline = time.time() + max(float(running_grace), 0.0)
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            if is_port_listening(port):
                return {'ok': True, 'started': False, 'reason': 'already_running', 'pids': pids}
        _warn(f'[flclash] ⚠️  进程在运行(pid: {" ".join(map(str, pids))}) 但 {port} 在 {running_grace:g}s 内不可达 '
              f'⇒ 未就绪 (代理可能被暂停/端口改配)')
        return {'ok': False, 'started': False, 'reason': 'port_closed', 'pids': pids, 'port': port}

    _warn(f'[flclash] 启动: {" ".join(START_CMD)} (等 {port} LISTEN ≤{timeout:g}s)')
    try:
        _run(START_CMD, timeout=30)
    except Exception as exc:                      # best-effort: 失败也要走完等待, 由就绪判据定论
        _warn(f'[flclash] 启动命令异常: {exc}')

    deadline = time.time() + max(float(timeout), 0.0)
    ready = is_port_listening(port)
    while not ready and time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        ready = is_port_listening(port)
    pids = flclash_pids()
    if ready:
        _warn(f'[flclash] ✅ 已就绪 ({port} LISTEN, pid: {" ".join(map(str, pids))})')
    else:
        _warn(f'[flclash] ❌ {timeout:g}s 内 {port} 未 LISTEN')
    return {'ok': ready, 'started': True, 'reason': 'started' if ready else 'not_ready',
            'pids': pids, 'port': port}


def ensure_for_url(url=None, ensure=True, probe_timeout=None, retry_timeout=None,
                   ensure_timeout=READY_TIMEOUT, port=READY_PORT, settle=REACH_SETTLE):
    """访问某 URL 前的「网络门」: 直连可达就绝不起代理; 否则按需 ensure + 复探。

    返回 {'ok', 'state', 'started', 'probe', 'first_probe', 'ensure', 'url', 'elapsed'}
      state:
        direct_ok      直连可达（**未**触碰 FlClash —— VPN/TUN 场景的关键护栏）
        proxy_ok       FlClash 原本在跑且复探可达（不归属本次）
        proxy_started  本轮拉起 FlClash 且复探可达（调用方负责决定是否释放）
        port_closed    进程在但 7890 不通（沿用 Q-1 语义）
        unreachable    代理也没救回来
        ensure_disabled ensure=False 且直连不可达（只探测, 不动环境）
    """
    started_at = time.time()
    first = probe_url(url, probe_timeout)
    if not first['ok'] and (retry_timeout or 0) > 0:
        # 直连「慢但通」的复探: 避免 5s 阈值把慢链路误判成不可达而多起一个代理
        again = probe_url(url, retry_timeout)
        if again['ok']:
            first = again
    if first['ok']:
        return {'ok': True, 'state': 'direct_ok', 'started': False, 'probe': first,
                'first_probe': first, 'ensure': None, 'url': first['url'],
                'elapsed': round(time.time() - started_at, 2)}

    if not ensure:
        return {'ok': False, 'state': 'ensure_disabled', 'started': False, 'probe': first,
                'first_probe': first, 'ensure': None, 'url': first['url'],
                'elapsed': round(time.time() - started_at, 2)}

    ens = ensure_ready(timeout=ensure_timeout, port=port)
    if settle > 0:
        time.sleep(settle)
    # 复探走 probe_best(prefer='proxy'): FlClash 多为系统代理模式, 起来后 IPv4 直连仍被墙,
    # 先走 7890 既准又省一轮直连超时（实测省 ~5s）
    second = probe_best(url, probe_timeout, port=port, prefer='proxy')
    state = ('proxy_started' if ens.get('started') else 'proxy_ok') if second['ok'] else (
        'port_closed' if ens.get('reason') == 'port_closed' else 'unreachable')
    return {'ok': bool(second['ok']), 'state': state, 'started': bool(ens.get('started')),
            'probe': second, 'first_probe': first, 'ensure': ens, 'url': second['url'],
            'elapsed': round(time.time() - started_at, 2)}


def release(grace=STOP_GRACE):
    """优雅退出(`osascript quit app`) → 宽限 grace → `kill -TERM {pid}` 兜底。未运行则空操作。"""
    if not _is_darwin():
        return {'ok': True, 'stopped': False, 'reason': 'non_darwin'}
    if not is_running():
        return {'ok': True, 'stopped': False, 'reason': 'not_running'}

    _warn(f'[flclash] 释放: {" ".join(STOP_CMD)} (宽限 {grace:g}s)')
    try:
        _run(STOP_CMD, timeout=30)
    except Exception as exc:
        _warn(f'[flclash] 优雅退出命令异常: {exc}')

    deadline = time.time() + max(float(grace), 0.0)
    while is_running() and time.time() < deadline:
        time.sleep(1.0)

    force_issued = False
    pids = flclash_pids()
    if pids:
        force_issued = True
        _warn(f'[flclash] 优雅退出超时 {grace:g}s, kill -TERM: {" ".join(map(str, pids))}')
        try:
            _run(('kill', '-TERM', *[str(p) for p in pids]), timeout=10)
        except Exception as exc:
            _warn(f'[flclash] kill -TERM 异常: {exc}')
        time.sleep(TERM_WAIT)

    left = flclash_pids()
    if left:
        _warn(f'[flclash] ⚠️  仍在运行: {" ".join(map(str, left))}')
    else:
        _warn('[flclash] ✅ 已释放')
    return {'ok': not left, 'stopped': True, 'force_kill_issued': force_issued,
            'reason': 'released' if not left else 'still_running', 'pids': left}


def main(argv=None):
    parser = argparse.ArgumentParser(description='FlClash 代理生命周期单一真源')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_run = sub.add_parser('is-running', help='0=在跑 / 1=没跑')
    p_run.add_argument('--json', action='store_true')
    sub.add_parser('pids', help='打印 pid (空格分隔)')
    p_ensure = sub.add_parser('ensure', help='确保就绪 (未运行则拉起)')
    p_ensure.add_argument('--timeout', type=float, default=READY_TIMEOUT)
    p_ensure.add_argument('--port', type=int, default=READY_PORT)
    p_ensure.add_argument('--json', action='store_true')
    p_release = sub.add_parser('release', help='释放本应用 (优雅 → kill -TERM)')
    p_release.add_argument('--grace', type=float, default=STOP_GRACE)
    p_release.add_argument('--json', action='store_true')
    p_reach = sub.add_parser('reach', help='URL 可达性门 (直连优先, 不通按需拉起代理)')
    p_reach.add_argument('--url', default=None)
    p_reach.add_argument('--timeout', type=float, default=None, help=f'首探超时 (默认 {REACH_TIMEOUT:g}s)')
    p_reach.add_argument('--no-ensure', action='store_true', help='只探测, 不拉起代理')
    p_reach.add_argument('--json', action='store_true')

    args = parser.parse_args(argv)

    if args.cmd == 'is-running':
        running = is_running()
        if args.json:
            print(json.dumps({'running': running, 'pids': flclash_pids()}))
        else:
            print('running' if running else 'stopped')
        return 0 if running else 1

    if args.cmd == 'pids':
        print(' '.join(str(p) for p in flclash_pids()))
        return 0

    if args.cmd == 'ensure':
        res = ensure_ready(args.timeout, args.port)
        print(json.dumps(res, ensure_ascii=False) if args.json
              else ('ready' if res['ok'] else 'not-ready'))
        return 0 if res['ok'] else 1

    if args.cmd == 'release':
        res = release(args.grace)
        print(json.dumps(res, ensure_ascii=False) if args.json
              else ('released' if res['ok'] else 'still-running'))
        return 0 if res['ok'] else 1

    if args.cmd == 'reach':
        res = ensure_for_url(args.url, ensure=not args.no_ensure,
                             probe_timeout=args.timeout,
                             retry_timeout=None if args.no_ensure else REACH_RETRY_TIMEOUT)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            probe = res['probe']
            print(res['state'] if res['ok'] else f"{res['state']} ({probe['class']})")
        return 0 if res['ok'] else 1

    return 2


if __name__ == '__main__':
    # 唯一捕获点 (§11.1-1)：文案/退出码同源 cli_interrupt（§11.2），禁手抄第二份
    from cli_interrupt import emit  # 入口段内 import ⇒ 被 importlib 加载时零副作用

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('python3 scripts/flclash_proxy.py', sys.argv)
