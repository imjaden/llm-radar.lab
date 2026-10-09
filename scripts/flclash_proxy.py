#!/usr/bin/env python3
"""FlClash 代理生命周期单一真源: 探测 / 就绪 / 起停 / 通知。

本模块是**唯一实现**——`llm-radar-collector.py`、`scripts/twitter-collector.py`(探测) 与
`scripts/twitter-collector-cron.sh`(起停编排, 经 CLI 子命令) 都必须走这里, 不得各自 pgrep/osascript。

命令与阈值口径对齐**声明层真源**(跨项目只读引用, 不在本仓另立一套):
  /Users/jadenli/CodeSpace/script-miner/projects/macosx/macosx-service-policy.json
  `services[FlClash].restart` = stop `osascript -e 'quit app "FlClash"'` / grace 20s /
  force_fallback `kill -TERM {pid}` / start `open -a FlClash` / verify `{ports:[7890], wait:180s}`。

检测口径(勿改回单一 `pgrep -f` + 应用名): 形如 `osascript -e 'quit app "FlClash"'` 的进程
命令行里同样出现 "FlClash" ⇒ `-f` 会把它自己命中, 产生**假阳性**(判"在跑"却没跑)。
真源用「精确名 `pgrep -x FlClash` ∪ 应用路径 `pgrep -f /Applications/FlClash.app`」双判据,
对上述形态不命中; 反例回归见 tests/test_flclash_proxy.py。

CLI:
  python3 scripts/flclash_proxy.py is-running [--json]   # 退出码 0=在跑 / 1=没跑
  python3 scripts/flclash_proxy.py pids                  # 空格分隔 pid (无则空行)
  python3 scripts/flclash_proxy.py ensure [--timeout 180] [--port 7890] [--json]   # 0=就绪 / 1=未就绪
  python3 scripts/flclash_proxy.py release [--grace 20] [--json]                   # 0=已释放 / 1=仍存活
  python3 scripts/flclash_proxy.py notify                # best-effort 通知, 失败静默返回 1

stdout = 机器可读单值(status word / JSON); 动作细节走 stderr(人类可读, 便于 cron 日志留痕)。
"""
from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import time

APP_NAME = 'FlClash'
APP_PATH = '/Applications/FlClash.app'
START_CMD = ('open', '-a', APP_NAME)
STOP_CMD = ('osascript', '-e', 'quit app "FlClash"')
NOTIFY_CMD = ('osascript', '-e',
              'display notification "采集 X 数据需启动 flClash 应用" with title "llm-radar"')
READY_PORT = 7890          # 对齐 policy services[FlClash].restart.verify.ports
READY_TIMEOUT = 180.0      # 对齐 policy ...verify.wait
STOP_GRACE = 20.0          # 对齐 policy ...restart.grace
POLL_INTERVAL = 2.0
PROBE_TIMEOUT = 2.0
TERM_WAIT = 3.0


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


def ensure_ready(timeout=READY_TIMEOUT, port=READY_PORT):
    """未运行 → `open -a FlClash` + 轮询等端口 LISTEN; 已在运行 → 直接复用, 不做任何动作。"""
    if not _is_darwin():
        return {'ok': True, 'started': False, 'reason': 'non_darwin', 'pids': []}
    if is_running():
        return {'ok': True, 'started': False, 'reason': 'already_running', 'pids': flclash_pids()}

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


def notify_required():
    """macOS 本地通知(提示启动 FlClash); 非 Darwin 直接 False; 失败静默。"""
    if not _is_darwin():
        return False
    try:
        _run(NOTIFY_CMD, timeout=3)
        return True
    except Exception:
        return False


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
    sub.add_parser('notify', help='本地通知 (best-effort)')

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

    if args.cmd == 'notify':
        return 0 if notify_required() else 1

    return 2


if __name__ == '__main__':
    sys.exit(main())
