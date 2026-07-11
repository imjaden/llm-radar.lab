#!/usr/bin/env python3
"""
通过 MCP 协议提交 LLM-Radar 数据更新。
1. 启动 MCP 服务器子进程
2. 执行 initialize 握手
3. 调用 submit_entities
4. git add + commit
"""
import subprocess, json, os, sys, signal

SERVER = '/Users/jadenli/CodeSpace/llm-radar.jaden.tech/llm-radar-mcp-server.py'
API_KEY = 'llm-radar-mcp-2026'
PROJECT_DIR = '/Users/jadenli/CodeSpace/llm-radar.jaden.tech'

def send(proc, msg):
    line = json.dumps(msg, ensure_ascii=False)
    proc.stdin.write(line + '\n')
    proc.stdin.flush()

def recv(proc, timeout=30):
    def handler(signum, frame):
        raise TimeoutError('MCP 无响应')
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        buf = ''
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            buf += line
            try:
                resp = json.loads(buf.strip())
                if 'jsonrpc' in resp:
                    return resp
            except json.JSONDecodeError:
                continue
    except TimeoutError:
        return {'error': f'超时 {timeout}s'}
    finally:
        signal.alarm(0)

# 启动 MCP 服务
env = os.environ.copy()
env['LLM_RADAR_MCP_KEY'] = API_KEY
proc = subprocess.Popen(
    ['python3', SERVER],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    env=env, text=True
)

try:
    # Step 1: Initialize
    print('[1/4] 初始化 MCP 连接...', flush=True)
    send(proc, {
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {
            'protocolVersion': '2025-03-26',
            'capabilities': {},
            'clientInfo': {'name': 'hermes-research', 'version': '1.0'}
        }
    })
    resp = recv(proc)
    if resp.get('error'):
        print(f'  ❌ 初始化失败: {resp["error"]}', flush=True)
        sys.exit(1)
    print(f'  ✅ MCP Server: {resp["result"]["serverInfo"]["name"]}')

    # Step 2: Initialized notification
    print('[2/4] 发送初始化确认...', flush=True)
    send(proc, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    # Step 3: Health check
    print('[3/4] 健康检查...', flush=True)
    send(proc, {
        'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {
            'name': 'health_check',
            'arguments': {'api_key': API_KEY}
        }
    })
    resp = recv(proc)
    if resp.get('result'):
        r = resp['result']
        print(f'  状态: {r["status"]}')
        print(f'  实体总数: {r["total_entities"]}')
    else:
        print(f'  ⚠️ health_check 异常: {resp}')

    # Step 4: Submit updated entities (fix key issues found in review)
    print('[4/4] 提交数据更新...', flush=True)

    # Fix: 空URL provider 补充
    fix_providers = [
        # 特斯拉
        {
            'id': 'tesla', 'name': '特斯拉', 'country': '美国',
            'hot_score': 55, 'hot_level': '温热',
            'last_event': '马斯克盯上AI基建，特斯拉将卖算力积木，新商标已曝光',
            'last_event_date': '2026-06-23',
            'last_event_url': 'https://36kr.com/p/3855730629899523',
            'key_people': ['埃隆·马斯克'],
            'focus_areas': ['AI基础设施', '自动驾驶'],
            'confidence': 'high',
        },
    ]

    payload = {
        'api_key': API_KEY,
        'providers': fix_providers,
        'people': [],
        'tools': [],
        'llms': [],
        'hotspots': [],
    }

    send(proc, {
        'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
        'params': {
            'name': 'submit_entities',
            'arguments': payload,
        }
    })
    resp = recv(proc, timeout=60)
    if resp.get('result'):
        r = resp['result']
        status = '✅' if r['status'] in ('accepted','partial') else '❌'
        print(f'  {status} 状态: {r["status"]}')
        print(f'  接受: {r["accepted"]}')
        if r.get('rejected_reasons'):
            print(f'  拒绝: {r["rejected_reasons"]}')
        if r.get('merge_result'):
            m = r['merge_result']
            print(f'  合并结果: 新增={m["new"]}, 更新={m["updated"]}')
        if r.get('snapshot_totals'):
            print(f'  最新总数: {r["snapshot_totals"]}')
    else:
        print(f'  ❌ submit_entities 失败: {resp}')

finally:
    proc.stdin.close()
    try: proc.wait(timeout=5)
    except: proc.kill()

print()
print('=== Git Commit ===')
os.chdir(PROJECT_DIR)
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'status'], check=True)
print()
result = subprocess.run(
    ['git', 'commit', '-m', 'feat@audit: 提交数据质量评审报告; 通过MCP修复空URL'],
    capture_output=True, text=True
)
print(result.stdout)
if result.returncode == 0:
    subprocess.run(['git', 'push'], check=True)
    print('✅ 已推送')
else:
    print('⚠️ 无变更或提交失败')
