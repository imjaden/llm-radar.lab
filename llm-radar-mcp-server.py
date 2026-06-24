#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM-Radar MCP Server
=================================
MCP (Model Context Protocol) server for LLM-Radar.

Accepts 5-dimension entity data from Hermes Agent via stdio JSON-RPC 2.0,
validates quality, and merges into snapshot.json.

Protocol: MCP 2025-03-26
Transport: stdio (line-delimited JSON-RPC 2.0)

Tools:
  - submit_entities(api_key, providers, people, tools, llms, hotspots)
  - health_check(api_key)

Environment:
  LLM_RADAR_MCP_KEY  — API key for authentication (default: llm-radar-mcp-2026)
  LLM_RADAR_DIR      — project root (default: auto-detect from script location)

Version: 1.0(2026-06-23)
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = os.environ.get('LLM_RADAR_MCP_KEY', 'llm-radar-mcp-2026')
PROJECT_ROOT = Path(os.environ.get('LLM_RADAR_DIR', __file__)).resolve().parent
DATA_DIR = PROJECT_ROOT / 'data'
SNAPSHOT_PATH = DATA_DIR / 'snapshot.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger('mcp-llm-radar')

# ── Protocol Helpers ────────────────────────────────────────────────────

def send_msg(msg):
    """Send a JSON-RPC message to stdout (line-delimited)."""
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + '\n')
    sys.stdout.flush()

def send_result(req_id, result):
    send_msg({'jsonrpc': '2.0', 'id': req_id, 'result': result})

def send_error(req_id, code, message):
    send_msg({'jsonrpc': '2.0', 'id': req_id, 'error': {'code': code, 'message': message}})

def read_msg():
    """Read one JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    return json.loads(line)

# ── Auth ────────────────────────────────────────────────────────────────

def require_auth(params):
    """Validate API key in params. Returns error message or None."""
    key = params.get('api_key', '')
    if key != API_KEY:
        return f'无效的 API Key'
    return None

# ── Quality Gate ────────────────────────────────────────────────────────

def validate_entities(entities):
    """检查数据质量，返回 {accepted, rejected, rejected_reasons}"""
    accepted = {'providers': [], 'people': [], 'tools': [], 'llms': [], 'hotspots': []}
    rejected = {'providers': [], 'people': [], 'tools': [], 'llms': [], 'hotspots': []}
    reasons = []

    today = datetime.now().strftime('%Y-%m-%d')

    for dim, items in entities.items():
        if dim not in accepted:
            continue
        for item in (items or []):
            reason = None
            # 1. 必填字段（hotspots 用 title，其他用 name）
            name_field = 'name' if dim != 'hotspots' else 'title'
            if not item.get(name_field):
                reason = f'{name_field} 为空'
            # 2. 置信度过低
            elif item.get('confidence') == 'low':
                reason = 'confidence 为 low'
            # 3. 日期不合理
            elif dim == 'hotspots':
                d = item.get('date', '')
                if not d:
                    reason = '热点缺少 date'
                elif d > today:
                    reason = f'日期 {d} 在未来'
            else:
                for date_field in ['last_event_date', 'recent_activity_date', 'last_update_date']:
                    d = item.get(date_field, '')
                    if d and d > today:
                        reason = f'{date_field} {d} 在未来'
                        break

            if reason:
                rejected[dim].append(item)
                reasons.append({'id': item.get('id', '?'), 'dim': dim, 'reason': reason})
            else:
                accepted[dim].append(item)

    return accepted, rejected, reasons

# ── Merge ───────────────────────────────────────────────────────────────

def merge_entities(new_entities):
    """将新实体合并到 snapshot.json（复用 collector.py 相同的合并逻辑）"""
    snapshot = {'providers': [], 'people': [], 'tools': [], 'llms': [], 'hotspots': [],
                'changelog': [], 'stats': {}, 'generated_at': datetime.now().isoformat()}

    if SNAPSHOT_PATH.exists():
        try:
            snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
        except:
            pass

    today = datetime.now().strftime('%Y-%m-%d')
    changelog = []
    new_count = 0
    update_count = 0

    for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
        name_field = 'name' if dim != 'hotspots' else 'title'
        old_items = {e.get(name_field, ''): e for e in snapshot.get(dim, []) if e.get(name_field)}
        incoming = new_entities.get(dim, [])
        if not incoming:
            continue

        for item in incoming:
            name_field = 'name' if dim != 'hotspots' else 'title'
            name = item.get(name_field, '')
            if not name:
                continue
            if name in old_items:
                # 更新：保留历史数据，覆盖新字段
                existing = old_items[name]
                # 保留原 id，覆盖热度和事件
                existing['hot_score'] = item.get('hot_score', existing.get('hot_score', 0))
                existing['hot_level'] = item.get('hot_level', existing.get('hot_level', ''))
                for field in ['last_event', 'last_event_date', 'last_event_url',
                              'recent_activity', 'recent_activity_date',
                              'last_update', 'last_update_date']:
                    if item.get(field):
                        existing[field] = item[field]
                old_items[name] = existing
                update_count += 1
                changelog.append({
                    'type': 'update', 'dimension': dim,
                    'id': item.get('id', name), 'summary': f'{dim}: {name}',
                    'date': today,
                })
            else:
                old_items[name] = item
                new_count += 1
                changelog.append({
                    'type': 'new', 'dimension': dim,
                    'id': item.get('id', name), 'summary': f'{dim}: {name}',
                    'date': today,
                })

        snapshot[dim] = list(old_items.values())

    # 更新 changelog（保留最近 200 条）
    snapshot['changelog'] = (snapshot.get('changelog', []) + changelog)[-200:]

    # 更新 stats
    snapshot['stats'] = {
        'total_providers': len(snapshot.get('providers', [])),
        'total_people': len(snapshot.get('people', [])),
        'total_tools': len(snapshot.get('tools', [])),
        'total_llms': len(snapshot.get('llms', [])),
        'total_hotspots': len(snapshot.get('hotspots', [])),
        'new_this_period': new_count,
        'updated_this_period': update_count,
    }

    snapshot['generated_at'] = datetime.now().isoformat()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')

    return new_count, update_count, snapshot['stats']

# ── Tool Handlers ───────────────────────────────────────────────────────

def handle_submit_entities(params, req_id):
    """submit_entities tool implementation."""
    # Auth
    auth_err = require_auth(params)
    if auth_err:
        send_error(req_id, -32001, auth_err)
        return

    # 收集各维度数据
    entities = {}
    for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
        entities[dim] = params.get(dim, [])

    # 空提交检查
    total = sum(len(v) for v in entities.values())
    if total == 0:
        send_error(req_id, -32002, '提交数据为空')
        return

    # 质量检验
    accepted, rejected, reasons = validate_entities(entities)
    accepted_total = sum(len(v) for v in accepted.values())

    if accepted_total == 0:
        send_result(req_id, {
            'status': 'rejected',
            'accepted': {k: 0 for k in entities},
            'rejected': {k: len(entities[k]) for k in entities},
            'rejected_reasons': reasons,
            'merge_result': None,
            'snapshot_totals': None,
        })
        return

    # 合并到 snapshot
    new_c, upd_c, stats = merge_entities(accepted)

    # 返回结果
    result = {
        'status': 'accepted' if len(reasons) == 0 else 'partial',
        'accepted': {k: len(v) for k, v in accepted.items()},
        'rejected': {k: len(v) for k, v in rejected.items()},
        'rejected_reasons': reasons,
        'merge_result': {'new': new_c, 'updated': upd_c},
        'snapshot_totals': stats,
    }
    send_result(req_id, result)
    log.info(f'submit_entities: accepted={accepted_total}, rejected={len(reasons)}, new={new_c}, updated={upd_c}')


def handle_health_check(params, req_id):
    """health_check tool implementation."""
    auth_err = require_auth(params)
    if auth_err:
        send_error(req_id, -32001, auth_err)
        return

    stats = {}
    if SNAPSHOT_PATH.exists():
        try:
            snap = json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
            stats = snap.get('stats', {})
        except:
            pass

    send_result(req_id, {
        'status': 'ok',
        'version': '1.0',
        'snapshot': str(SNAPSHOT_PATH),
        'total_entities': sum(stats.get(k, 0) for k in
                               ['total_providers', 'total_people', 'total_tools', 'total_llms', 'total_hotspots']),
        'detail': stats,
        'last_updated': stats.get('generated_at', ''),
    })

# ── Main Loop ───────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    'submit_entities': {
        'fn': handle_submit_entities,
        'schema': {
            'name': 'submit_entities',
            'description': '向 LLM-Radar 提交 5 维度情报数据（厂商/人物/工具/大模型/热点），自动质量检验后合并到 snapshot.json',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'api_key': {'type': 'string', 'description': '鉴权密钥'},
                    'providers': {'type': 'array', 'items': {'type': 'object'}},
                    'people': {'type': 'array', 'items': {'type': 'object'}},
                    'tools': {'type': 'array', 'items': {'type': 'object'}},
                    'llms': {'type': 'array', 'items': {'type': 'object'}},
                    'hotspots': {'type': 'array', 'items': {'type': 'object'}},
                },
                'required': ['api_key'],
            },
        },
    },
    'health_check': {
        'fn': handle_health_check,
        'schema': {
            'name': 'health_check',
            'description': '检查 LLM-Radar MCP Server 运行状态和 snapshot 概况',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'api_key': {'type': 'string', 'description': '鉴权密钥'},
                },
                'required': ['api_key'],
            },
        },
    },
}


def main():
    """MCP Server main loop — reads JSON-RPC from stdin."""
    log.info(f'MCP Server started (PID={os.getpid()})')
    log.info(f'Project root: {PROJECT_ROOT}')
    log.info(f'Snapshot: {SNAPSHOT_PATH}')

    while True:
        try:
            msg = read_msg()
            if msg is None:
                break  # EOF

            req_id = msg.get('id')
            method = msg.get('method')
            params = msg.get('params', {})

            if method == 'initialize':
                send_result(req_id, {
                    'protocolVersion': '2025-03-26',
                    'capabilities': {
                        'tools': {},
                    },
                    'serverInfo': {
                        'name': 'llm-radar-mcp',
                        'version': '1.0',
                    },
                })
                log.info('Client initialized')

            elif method == 'notifications/initialized':
                # 无需响应
                pass

            elif method == 'tools/list':
                tools = [t['schema'] for t in TOOL_REGISTRY.values()]
                send_result(req_id, {'tools': tools})
                log.info(f'Listed {len(tools)} tools')

            elif method == 'tools/call':
                tool_name = params.get('name', '')
                tool_args = params.get('arguments', {})
                tool = TOOL_REGISTRY.get(tool_name)
                if tool:
                    tool['fn'](tool_args, req_id)
                else:
                    send_error(req_id, -32601, f'未知工具: {tool_name}')

            else:
                send_error(req_id, -32601, f'未知方法: {method}')

        except json.JSONDecodeError:
            send_error(0, -32700, 'JSON 解析错误')
        except Exception as e:
            log.exception('Unhandled error')
            send_error(0, -32603, f'服务器内部错误: {e}')


if __name__ == '__main__':
    main()
