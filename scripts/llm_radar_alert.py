#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""llm-radar 告警分流（CL009，2026-11-12）。

设计铁律（都在 tests/test_alert_dispatch.py 里钉住）：
1. **只对状态跃迁发声**：某类问题首次出现 / 升级为 critical / 恢复时各一条；
   同 kind 在 DEDUPE_HOURS 内不重复（默认 24h，天然不会刷屏）。
2. **事实源只有 metrics/ts 产物**，不重新探网、不重新跑采集（可以被任意时刻安全调用）。
3. **best-effort**：通知发不出去也返回 0，绝不影响采集退出码；`--json` 模式下人类行一律 stderr。
4. **默认本地通道**（osascript，与 X 登录墙同一条 `title=llm-radar` 通道），
   `--channel feishu` 才走网关；无凭据依赖。

用法:
    python3 scripts/llm_radar_alert.py check [--dry-run] [--channel local|feishu|none] [--json]
    python3 scripts/llm_radar_alert.py classify [--json]      # 只看当前判据，不写状态、不发通知
env:
    LLM_RADAR_ALERT_STALE_HOURS   数据陈旧阈值（默认 6.5）
    LLM_RADAR_ALERT_DEDUPE_HOURS  同 kind 去重窗口（默认 24）
    LLM_RADAR_ALERT_STATE        状态文件路径（默认 cache/state/alert-state.json）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / 'data'
STATE_PATH = Path(os.environ.get('LLM_RADAR_ALERT_STATE')
                  or REPO_ROOT / 'cache' / 'state' / 'alert-state.json')

STALE_HOURS = float(os.environ.get('LLM_RADAR_ALERT_STALE_HOURS') or 6.5)
DEDUPE_HOURS = float(os.environ.get('LLM_RADAR_ALERT_DEDUPE_HOURS') or 24.0)
# 连败门槛: 凭据类一次性确定（1 次即报）；可自愈类给足重试余量（避免抖动）
RETRY_GATE = {'model': 2, 'quota': 2, 'network': 3, 'other': 3}
DEGRADED_FAILS = 3
X_HEALTH_PATH = REPO_ROOT / 'cache' / 'state' / 'x-health.json'


def _parse_ts(value):
    """ISO 字符串 / datetime → datetime；解析不了返回 None（判据宁缺勿噪）。"""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return {}


def classify(metrics=None, ts_data=None, now=None, x_health=None, stale_hours=None):
    """当前应报的问题清单（纯函数，不读写状态、不发通知）。

    返回 [{level, kind, text, fix}]；level ∈ {critical, warning}。
    """
    now = now or datetime.now()
    stale_hours = STALE_HOURS if stale_hours is None else stale_hours
    metrics = metrics if isinstance(metrics, dict) else _load_json(DATA_DIR / 'metrics.json')
    ts_data = ts_data if isinstance(ts_data, dict) else _load_json(REPO_ROOT / 'timestamp.json')
    if x_health is None:
        x_health = _load_json(X_HEALTH_PATH)

    alerts = []
    consec = int(metrics.get('consecutive_fails') or 0)
    _raw_err = metrics.get('last_error')
    err = _raw_err if isinstance(_raw_err, dict) else {}
    kind = str(err.get('kind') or '').strip()

    # —— 外部依赖（凭据类 1 次即报，其余按连败门槛）
    dep = {
        'auth_missing': ('critical', 'DeepSeek 凭据缺失（DEEPSEEK_API_KEY 未配置）',
                         '在 .env 填 DEEPSEEK_API_KEY 后: lr run --force'),
        'auth': ('critical', 'DeepSeek 鉴权失败（401/403）',
                 '核对 .env 的 DEEPSEEK_API_KEY 是否有效: lr run --force'),
        'model': ('warning', 'DeepSeek 模型不可用',
                  '换用可用模型或稍后重试: lr run --force'),
        'quota': ('warning', 'DeepSeek 额度/限流',
                  '等待窗口恢复或换 key: lr run --force'),
        'network': ('warning', 'DeepSeek 网络不可达',
                    '检查网络/代理后: lr fetch qbitai'),
        'other': ('warning', '采集失败（未分类）',
                  '看 cache/logs/llm-radar-collector/collector.log 尾部'),
    }
    if kind in dep:
        level, text, fix = dep[kind]
        gate = RETRY_GATE.get(kind, 1)
        if consec >= gate:
            alerts.append({'level': level, 'kind': kind,
                           'text': f'{text}（连败 {consec} 轮）', 'fix': fix})

    # —— 数据陈旧（比 last_error 更根本：采集器没跑起来时只有它能说话）
    last_run = _parse_ts(ts_data.get('last_run_at'))
    if last_run:
        age_h = (now - last_run).total_seconds() / 3600.0
        if age_h > stale_hours:
            alerts.append({
                'level': 'critical', 'kind': 'stale',
                'text': f'数据陈旧 {age_h:.1f}h（阈值 {stale_hours:g}h，最近一轮 '
                        f'{last_run.strftime("%m-%d %H:%M")}）',
                'fix': 'lr status；crontab -l | grep llm-radar；./llm-radar-run.sh run',
            })

    # —— 降级源（连续失败 ≥3 被跳过，静默降级会让人以为「今天没新闻」）
    _raw_sh = metrics.get('source_health')
    sh = _raw_sh if isinstance(_raw_sh, dict) else {}
    degraded = sorted(k for k, h in sh.items()
                      if isinstance(h, dict) and int(h.get('consecutive_fails') or 0) >= DEGRADED_FAILS)
    if degraded:
        alerts.append({
            'level': 'warning', 'kind': 'source_degraded',
            'text': f'源已降级跳过: {", ".join(degraded)}（连败 ≥{DEGRADED_FAILS}）',
            'fix': f'lr fetch {degraded[0]} 单源排查',
        })

    # —— X 采集链路（登录墙 / page target=0 的静默故障，由巡检写入 sidecar）
    if isinstance(x_health, dict) and x_health.get('status') and x_health['status'] != 'ok':
        at = _parse_ts(x_health.get('at'))
        fresh = (now - at) < timedelta(hours=12) if at else True
        if fresh:
            alerts.append({
                'level': 'critical', 'kind': 'x_health',
                'text': f'X 采集链路异常: {x_health.get("detail") or x_health["status"]}',
                'fix': 'lr chrome --wait；lr chrome --status',
            })
    return alerts


def decide(alerts, state=None, now=None, dedupe_hours=None):
    """(要发的消息, 新状态)。跃迁式：首次 / 升级 / 恢复 才发；同级去重 dedupe_hours。"""
    now = now or datetime.now()
    dedupe_hours = DEDUPE_HOURS if dedupe_hours is None else dedupe_hours
    state = dict(state or {})
    out = []
    seen = set()
    for a in alerts:
        kind = a['kind']
        seen.add(kind)
        prev = state.get(kind) if isinstance(state.get(kind), dict) else None
        send = False
        if prev is None:
            send = True
        elif a['level'] == 'critical' and prev.get('level') != 'critical':
            send = True
        else:
            last = _parse_ts(prev.get('last_sent_at'))
            if last is None or (now - last) >= timedelta(hours=dedupe_hours):
                send = True
        if send:
            out.append({'level': a['level'], 'kind': kind,
                        'title': 'llm-radar 告警' if a['level'] == 'critical'
                                 else 'llm-radar 提示',
                        'text': f"{a['text']} ⇒ {a['fix']}"})
            state[kind] = {'level': a['level'], 'last_sent_at': now.isoformat(),
                           'text': a['text']}
    # 恢复回执（必须发一条，否则「还在报吗」无从判断）
    for kind in list(state):
        if kind not in seen:
            out.append({'level': 'info', 'kind': kind, 'title': 'llm-radar 恢复',
                        'text': f'已恢复: {kind}'})
            state.pop(kind, None)
    return out, state


def deliver(messages, channel='local', dry_run=False):
    """发送。返回成功条数；任何失败都静默（best-effort）。"""
    if dry_run or channel == 'none':
        for m in messages:
            print(f"[dry-run] {m['title']}: {m['text']}", file=sys.stderr)
        return 0
    ok = 0
    for m in messages:
        try:
            if channel == 'feishu':
                cmd = ['hermes', 'send', '--to', os.environ.get('LLM_RADAR_ALERT_TO', 'feishu'),
                       f"{m['title']}: {m['text']}"]
                r = subprocess.run(cmd, capture_output=True, timeout=20)
            else:  # local: 与 X 登录墙同一条 osascript 通道
                if sys.platform != 'darwin':
                    return ok
                safe = m['text'].replace('"', '\\"')
                r = subprocess.run(
                    ['osascript', '-e',
                     f'display notification "{safe}" with title "{m["title"]}"'],
                    capture_output=True, timeout=10)
            ok += 1 if r.returncode == 0 else 0
        except Exception:
            continue
    return ok


def check(repo_root=None, channel='local', dry_run=False, now=None, state_path=None,
          quiet=False, metrics=None, ts_data=None, x_health=None):
    """一轮告警判定 + 发送 + 状态落盘。返回 {alerts, sent, state}。"""
    state_path = Path(state_path or STATE_PATH)
    alerts = classify(metrics, ts_data, now=now, x_health=x_health)
    state = _load_json(state_path) if state_path.exists() else {}
    state = state.get('kinds', state) if isinstance(state, dict) else {}
    msgs, new_state = decide(alerts, state, now=now)
    if not quiet:
        for m in msgs:
            print(f"[alert] {m['title']}: {m['text']}", file=sys.stderr)
    sent = deliver(msgs, channel=channel, dry_run=dry_run)
    if not dry_run:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({'kinds': new_state}, ensure_ascii=False,
                                             indent=2), encoding='utf-8')
        except Exception:
            pass
    return {'alerts': alerts, 'messages': msgs, 'sent': sent, 'state': new_state}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv and not argv[0].startswith('-') else 'check'
    json_out = '--json' in argv
    dry = '--dry-run' in argv
    channel = 'local'
    for i, a in enumerate(argv):
        if a == '--channel' and i + 1 < len(argv):
            channel = argv[i + 1]
    if cmd == 'classify':
        res = {'alerts': classify()}
    else:
        res = check(channel=channel, dry_run=dry, quiet=json_out)
    if json_out:
        print(json.dumps({'status': 'success', 'data': res, 'error': None},
                         ensure_ascii=False))
    else:
        n = len(res.get('alerts') or [])
        print(f"[alert] 判据 {n} 条 / 待发 {len(res.get('messages') or [])} 条"
              f" / 已发 {res.get('sent', 0)} 条", file=sys.stderr)
    return 0


if __name__ == '__main__':
    # 唯一捕获点（§11.1-1）：文案/退出码同源 cli_interrupt，禁手抄第二份
    from cli_interrupt import emit  # 入口段内 import ⇒ 被 importlib 加载时零副作用

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('python3 scripts/llm_radar_alert.py', sys.argv)
