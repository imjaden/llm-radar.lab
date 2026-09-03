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

  阈值 STALE_HOURS 默认 7，可通过环境变量 LLM_RADAR_STALE_HOURS 覆盖（便于验收测试）。
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# ===== 阈值常量（默认 12h，可用 LLM_RADAR_STALE_HOURS 覆盖）=====
STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '12'))

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

    # 新鲜度检查（主）：超过阈值 → 硬告警 exit 1（REA-2 语义分离）
    if age > timedelta(hours=STALE_HOURS):
        hours = age.total_seconds() / 3600
        return 1, (f'llm-radar 数据过期: last_run_at={last_run_at} '
                   f'({hours:.1f}h 前) > {STALE_HOURS}h '
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
