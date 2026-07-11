#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM-Radar MCP Protocol 手工测试验证脚本

模拟 Hermes Agent 通过 stdio JSON-RPC 2.0 调用 MCP Server。
测试用例：
  1. health_check — 验证服务器运行状态
  2. submit_entities (有效数据) — 验证正常写入
  3. submit_entities (低置信度) — 验证质量门禁拒绝
  4. submit_entities (空提交) — 验证空数据拒绝
  5. submit_entities (错误 API Key) — 验证鉴权拒绝

用法：
  python3 scripts/mcp-protocol-demo.py

依赖：
  - llm-radar-mcp-server.py 在项目根目录

流程:
scripts/mcp-protocol-demo.py
    │
    ├─ subprocess.Popen → python3 llm-radar-mcp-server.py（自动启动）
    │
    ├─ 发 JSON-RPC 请求 → stdin pipe
    ├─ 收 JSON-RPC 响应 ← stdout pipe
    │
    ├─ 测试 5 个用例（health_check / submit / reject / empty / auth）
    │
    └─ 子进程退出（pipe 关闭 → EOF）

  每次运行都是独立的、一次性的 stdio 会话。不需要也不依赖手工启动的 MCP Server 实例。
"""

import subprocess
import json
import sys
import os
import secrets
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MCP_SERVER = PROJECT_ROOT / 'llm-radar-mcp-server.py'
API_KEY = os.environ.get('LLM_RADAR_MCP_KEY', '')
if not API_KEY:
    API_KEY = secrets.token_hex(32)
    print(f'WARN  LLM_RADAR_MCP_KEY not set, generated temp key: {API_KEY[:8]}...{API_KEY[-4:]}',
          file=sys.stderr)
WRONG_KEY = 'wrong-key'


def send_request(proc, method, params=None):
    """发送 JSON-RPC 请求到 MCP Server，返回响应。"""
    req = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': method,
        'params': params or {},
    }
    line = json.dumps(req, ensure_ascii=False) + '\n'
    proc.stdin.write(line)
    proc.stdin.flush()

    resp_line = proc.stdout.readline()
    if resp_line:
        return json.loads(resp_line.strip())
    return None


def run_test(name, func):
    """运行一个测试用例"""
    print(f'\n=== {name} ===')
    try:
        func()
        print(f'  ✅ PASS')
    except Exception as e:
        print(f'  ❌ FAIL: {e}')


def test_health_check(proc):
    """TC1: health_check"""
    resp = send_request(proc, 'tools/call', {
        'name': 'health_check',
        'arguments': {'api_key': API_KEY},
    })
    assert resp, '无响应'
    assert 'result' in resp, f'无 result: {resp.get("error")}'
    r = resp['result']
    assert r['status'] == 'ok', f'status 应为 ok: {r}'
    print(f'  status=ok, version={r["version"]}, total={r["total_entities"]}')


def test_submit_valid(proc):
    """TC2: submit_entities — 有效数据"""
    entities = {
        'api_key': API_KEY,
        'providers': [{
            'id': 'test-company',
            'name': '测试公司',
            'country': '中国',
            'hot_score': 60,
            'hot_level': '高热',
            'last_event': '发布测试产品',
            'last_event_date': '2026-06-23',
            'confidence': 'high',
        }],
        'hotspots': [{
            'id': 'test-event',
            'title': '测试热点事件',
            'summary': '用于验证 MCP 协议的热点事件',
            'date': '2026-06-23',
            'source': 'MCP Test',
            'url': '',
            'confidence': 'high',
        }],
    }
    resp = send_request(proc, 'tools/call', {
        'name': 'submit_entities',
        'arguments': entities,
    })
    assert resp, '无响应'
    assert 'result' in resp, f'无 result: {resp.get("error")}'
    r = resp['result']
    assert r['status'] in ('accepted', 'partial'), f'应为 accepted: {r}'
    assert r['accepted']['providers'] == 1, f'应接受 1 厂商: {r}'
    assert r['accepted']['hotspots'] == 1, f'应接受 1 热点: {r}'
    print(f'  状态: {r["status"]}')
    print(f'  接受: providers={r["accepted"]["providers"]}, hotspots={r["accepted"]["hotspots"]}')
    print(f'  合并: new={r["merge_result"]["new"]}, updated={r["merge_result"]["updated"]}')


def test_submit_low_confidence(proc):
    """TC3: submit_entities — 低置信度（应被拒绝）"""
    entities = {
        'api_key': API_KEY,
        'providers': [{
            'id': 'dubious-inc',
            'name': '可疑公司',
            'country': '未知',
            'hot_score': 10,
            'confidence': 'low',  # ← 应被拒绝
        }],
    }
    resp = send_request(proc, 'tools/call', {
        'name': 'submit_entities',
        'arguments': entities,
    })
    assert resp, '无响应'
    r = resp.get('result', resp)
    assert r['rejected']['providers'] == 1, f'应拒绝低置信度: {r}'
    print(f'  拒绝: providers={r["rejected"]["providers"]}')
    for rr in r['rejected_reasons']:
        print(f'  原因: [{rr["dim"]}] {rr["id"]} → {rr["reason"]}')


def test_submit_empty(proc):
    """TC4: submit_entities — 空提交（应返回 error）"""
    entities = {'api_key': API_KEY}
    resp = send_request(proc, 'tools/call', {
        'name': 'submit_entities',
        'arguments': entities,
    })
    assert resp, '无响应'
    assert 'error' in resp, f'空提交应返回 error: {resp}'
    print(f'  错误: code={resp["error"]["code"]}, message={resp["error"]["message"]}')


def test_submit_wrong_key(proc):
    """TC5: submit_entities — 错误 API Key（应返回鉴权错误）"""
    entities = {
        'api_key': WRONG_KEY,
        'hotspots': [{'id': 'x', 'title': 'x', 'date': '2026-06-23', 'confidence': 'high'}],
    }
    resp = send_request(proc, 'tools/call', {
        'name': 'submit_entities',
        'arguments': entities,
    })
    assert resp, '无响应'
    assert 'error' in resp, f'错误 key 应返回 error: {resp}'
    print(f'  鉴权拒绝: code={resp["error"]["code"]}, message={resp["error"]["message"]}')


def main():
    """启动 MCP Server 子进程，执行所有测试用例"""
    print('=== LLM-Radar MCP 协议测试 ===')
    print(f'Server: {MCP_SERVER}')
    print(f'API Key: {API_KEY}')

    # 启动 MCP Server
    proc = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, 'LLM_RADAR_MCP_KEY': API_KEY},
    )

    # 初始化
    init_resp = send_request(proc, 'initialize', {
        'protocolVersion': '2025-03-26',
        'capabilities': {},
        'clientInfo': {'name': 'mcp-test-client', 'version': '1.0'},
    })
    assert init_resp and 'result' in init_resp, f'初始化失败: {init_resp}'
    print(f'  Server: {init_resp["result"]["serverInfo"]["name"]} v{init_resp["result"]["serverInfo"]["version"]}')
    print(f'  Protocol: {init_resp["result"]["protocolVersion"]}')

    # List tools
    list_resp = send_request(proc, 'tools/list')
    assert list_resp and 'result' in list_resp
    tools = [t['name'] for t in list_resp['result']['tools']]
    print(f'  Tools: {", ".join(tools)}')

    # 运行测试
    run_test('TC1: health_check', lambda: test_health_check(proc))
    run_test('TC2: submit_entities (有效数据)', lambda: test_submit_valid(proc))
    run_test('TC3: submit_entities (低置信度)', lambda: test_submit_low_confidence(proc))
    run_test('TC4: submit_entities (空提交)', lambda: test_submit_empty(proc))
    run_test('TC5: submit_entities (错误 Key)', lambda: test_submit_wrong_key(proc))

    # 关闭服务器
    proc.stdin.close()
    proc.wait(timeout=5)
    print(f'\n=== 测试完成 (exit code: {proc.returncode}) ===')


if __name__ == '__main__':
    main()
