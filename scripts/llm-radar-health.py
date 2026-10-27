#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""llm-radar 线上数据新鲜度探针 (health watchdog)

独立探针脚本，不修改 llm-radar-collector.py。请求线上 timestamp.json 健康检查端点，
端到端验证「采集 → push → GitHub Pages 部署 → CDN」链路是否产出新鲜数据。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三态退出契约 (O-1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  exit 1 + 非空 stdout  = 硬告警：数据过期 (now - last_run_at > STALE_HOURS)
                          或 网络失败 / JSON 解析失败 / 字段缺失 / 时间戳无法解析
  exit 0 + 非空 stdout  = 软告警：最近一轮质量门禁失败 (last_run_status != 'success'，
                          但数据仍新鲜) —— 不阻断，避免把「质量失败」误报为「数据过期」
  exit 0 + 空 stdout    = 健康：数据新鲜且质量门禁通过，静默

no_agent watchdog 语义：空 stdout → 静默不投递；非空 stdout → 作为消息投递；
非零退出码 → 错误警报（防止看门狗自身损坏无人知晓）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
时区契约 (O-2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  last_run_at 由采集器以 datetime.now().isoformat() 写盘，为采集机本地时间
  (naive，无时区后缀)。服务器 (Linux) 与本机 (macOS) 均运行于 +08:00 时区，
  探针以「本机 now」直接与 fromisoformat(last_run_at) 相减。
  若任一端未来变更时区，此契约即失效，需同步调整本脚本。

  阈值 STALE_HOURS 默认 12，可通过环境变量 LLM_RADAR_STALE_HOURS 覆盖（便于验收测试）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
判定点口径 (crossrepo-llm-radar-staleness / DAILY-CHECKER-CL191)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  夜间 22:00–08:00 合盖不采 ⇒ 纯绝对小时数必在早晨误报, 故与 `lr status` 统一为:
    判定点 = 今天已有成功采集 ? 该时刻 + 30min : 当日 09:40 + 30min (=10:10)
    now < 判定点 ⇒ 不判陈旧（静默/仅质量告警）
    age > 48h ⇒ 例外, 不受判定点保护
  本探针只拿到线上 timestamp.json（无 run_history）, 故用 last_run_at 近似「今日成功时刻」——
  比 `lr status` 更宽松（不会多报）; 等价性由 tests/test_health_staleness.py 钉住。
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# ===== 阈值常量（默认 12h，可用 LLM_RADAR_STALE_HOURS 覆盖）=====
def _env_int(name, default, lo=None):
    """env 整数安全解析（CL151 §3 坑位: 空串/非数字不得在 import 期 traceback）。"""
    try:
        n = int(str(os.environ.get(name, '') or default).strip())
    except (TypeError, ValueError):
        return default
    return default if (lo is not None and n < lo) else n


STALE_HOURS = _env_int('LLM_RADAR_STALE_HOURS', 12, lo=1)
CRITICAL_HOURS = _env_int('LLM_RADAR_CRITICAL_HOURS', 48, lo=1)

# ===== 陈旧度「判定点」口径（与 llm-radar-collector.py::staleness_judge_point 同源）=====
# 夜间 22:00–08:00 用户合盖不采 ⇒ 纯绝对小时数必然在早晨误报。
# 判定点 = 今天已有成功采集 ? 该时刻+宽限 : 当日应到时刻(默认 09:40)+宽限(=10:10)。
# 与 `lr status` 的唯一差别: 本探针只拿到线上 timestamp.json（没有 run_history），
# 因此用 last_run_at 当「今日成功时刻」的近似（更宽松, 不会错报）；等价性由
# tests/test_health_staleness.py::test_parity_with_collector 钉住。
FIRST_SLOT_TODAY = (os.environ.get('LLM_RADAR_FIRST_SLOT') or '09:40').strip() or '09:40'
STALENESS_GRACE_MIN = _env_int('LLM_RADAR_STALENESS_GRACE_MIN', 30, lo=0)


def _parse_hhmm(value):
    """'09:40' → (9, 40)；非法/越界 → None。"""
    try:
        hh, mm = str(value).split(':')
        h, m = int(hh), int(mm)
    except (AttributeError, ValueError):
        return None
    return (h, m) if (0 <= h <= 23 and 0 <= m <= 59) else None


def staleness_judge_point(now, last_dt=None, last_status=None):
    """陈旧度判定点（本地时区）。

    今天已有成功采集 ⇒ `last_dt + 宽限`；否则 ⇒ `当日 09:40 + 宽限`。
    """
    if last_dt is not None and last_status == 'success' and last_dt.date() == now.date():
        return last_dt + timedelta(minutes=STALENESS_GRACE_MIN)
    hh, mm = _parse_hhmm(FIRST_SLOT_TODAY) or (9, 40)
    expect = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return expect + timedelta(minutes=STALENESS_GRACE_MIN)


def staleness_verdict(now, last_dt, last_status=None):
    """→ (is_stale, judged, judge_at)。

    `judged` 在这里的含义是「判定点是否已过」（消息里用它区分是判定点触发还是 >48h 兜底）；
    与 collector 的 `judged`（陈旧度判据是否生效）在 >48h 兜底这一格语义不同，故消息侧只按
    `now >= judge_at` 判读。
    """
    judge_at = staleness_judge_point(now, last_dt, last_status)
    if last_dt is None:
        return True, True, judge_at
    hours = max(0.0, (now - last_dt).total_seconds() / 3600)   # 未来时间戳(时钟偏移)当 0
    if hours > CRITICAL_HOURS:
        return True, now >= judge_at, judge_at        # >48h 不受判定点保护
    if now < judge_at:
        return False, False, judge_at
    return hours > STALE_HOURS, True, judge_at

# 线上健康检查端点（自有域名，HTTPS）
ENDPOINT = 'https://llm-radar.lab.jaden.tech/timestamp.json'
TIMEOUT = 15


def fetch():
    """请求线上 timestamp.json，加 ?t=<epoch> cache-busting 绕过 CDN 陈旧副本 (RIG-2)。"""
    url = f'{ENDPOINT}?t={int(time.time())}'
    req = urllib.request.Request(url, headers={'User-Agent': 'llm-radar-health/1.0'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def check(data, now=None):
    """评估新鲜度与质量，返回 (exit_code, message)。

    message 为空字符串表示健康静默。now 参数用于测试注入。
    """
    now = now or datetime.now()

    last_run_at = data.get('last_run_at')
    status = data.get('last_run_status')
    last_news_date = data.get('last_news_date', '')

    if not last_run_at:
        return 1, f'llm-radar 探针错误: timestamp.json 缺少 last_run_at 字段'

    try:
        last_dt = datetime.fromisoformat(last_run_at)
    except (ValueError, TypeError):
        return 1, f'llm-radar 探针错误: last_run_at 无法解析: {last_run_at!r}'

    age = now - last_dt
    hours = max(0.0, age.total_seconds() / 3600)
    is_stale, judged, judge_at = staleness_verdict(now, last_dt, status)

    # 新鲜度检查（主）：判定点之后且超阈值 → 硬告警 exit 1（REA-2 语义分离）
    if is_stale:
        if not judged:
            reason = f'>{CRITICAL_HOURS}h 兜底判定'
        else:
            reason = f'判定点 {judge_at:%H:%M} 已过'
        return 1, (f'llm-radar 数据过期: last_run_at={last_run_at} '
                   f'({hours:.1f}h 前) > {STALE_HOURS}h [{reason}] '
                   f'(last_news_date={last_news_date}, status={status})')

    # 质量检查（辅）：status != success 但数据新鲜 → 软告警 exit 0，不阻断
    if status != 'success':
        return 0, (f'llm-radar 质量告警: 最近一轮质量门禁失败 '
                   f'(last_run_status={status}, 数据仍新鲜)')

    # 健康 → 静默 exit 0
    return 0, ''


def main():
    try:
        data = fetch()
    except Exception as e:
        # 网络失败 / JSON 解析失败 → 错误告警 exit 1（而非静默）
        print(f'llm-radar 探针错误: 无法获取或解析 timestamp.json: {e}')
        return 1

    code, msg = check(data)
    if msg:
        print(msg)
    return code


if __name__ == '__main__':
    sys.exit(main())
