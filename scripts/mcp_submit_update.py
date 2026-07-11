#!/usr/bin/env python3
"""
通过 MCP 协议提交 LLM-Radar 数据更新。
1. 启动 MCP 服务器子进程
2. 执行 initialize 握手
3. 调用 submit_entities
4. git add + commit
"""
import subprocess, json, os, sys, signal
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER = str(_PROJECT_ROOT / 'llm-radar-mcp-server.py')
API_KEY=os.environ.get('LLM_RADAR_MCP_KEY', '')
if not API_KEY:
    print('ERROR: LLM_RADAR_MCP_KEY 环境变量未设置', file=sys.stderr)
    print('  export LLM_RADAR_MCP_KEY=<your-secure-key>', file=sys.stderr)
    sys.exit(1)
PROJECT_DIR = str(_PROJECT_ROOT)

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
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                buf += line
                try:
                    return json.loads(buf)
                except json.JSONDecodeError:
                    continue
    finally:
        signal.alarm(0)

def main():
    """MCP 提交主流程"""
    print('启动 MCP 服务器...')
    proc = subprocess.Popen(
        [sys.executable, SERVER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, 'LLM_RADAR_MCP_KEY': API_KEY},
    )

    # 初始化
    init_resp = send(proc, {
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {'protocolVersion': '2025-03-26', 'clientInfo': {'name': 'submit-script'}},
    })
    init_result = recv(proc)
    if not init_result or 'result' not in init_result:
        print(f'初始化失败: {init_result}', file=sys.stderr)
        proc.kill()
        sys.exit(1)
    print(f'  MCP 版本: {init_result["result"].get("protocolVersion", "?")}')
    print(f'  服务器: {init_result["result"].get("serverInfo", {}).get("name", "?")}')

    # 检查命令行参数
    if len(sys.argv) < 2:
        print('Usage: python3 scripts/mcp_submit_update.py <json_file_or_json_string>')
        proc.kill()
        sys.exit(1)

    # 读取实体数据
    entity_input = sys.argv[1]
    if os.path.isfile(entity_input):
        with open(entity_input) as f:
            entities = json.load(f)
    else:
        try:
            entities = json.loads(entity_input)
        except json.JSONDecodeError as e:
            print(f'JSON 解析失败: {e}', file=sys.stderr)
            proc.kill()
            sys.exit(1)

    # 提交
    send(proc, {
        'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': 'submit_entities', 'arguments': {'entities': entities, 'api_key': API_KEY}},
    })
    result = recv(proc)
    if not result:
        print('无响应', file=sys.stderr)
        proc.kill()
        sys.exit(1)

    if 'error' in result:
        print(f'提交失败: {result["error"]}', file=sys.stderr)
        proc.kill()
        sys.exit(1)

    submit_result = result.get('result', {})
    stats = submit_result.get('stats', {})
    print(f'✅ 提交成功: 新增 {stats.get("new", 0)} / 更新 {stats.get("updated", 0)} / 拒绝 {stats.get("rejected", 0)}')

    # Git commit
    try:
        subprocess.run(['git', 'add', '-A'], cwd=PROJECT_DIR, check=True, capture_output=True)
        msg = f'mcp@llm-radar: submit update ({stats.get("new", 0)} new, {stats.get("updated", 0)} updated)'
        r = subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT_DIR, capture_output=True, text=True)
        if r.returncode == 0:
            print('✅ Git commit 完成')
        elif 'nothing to commit' in (r.stdout + r.stderr):
            print('ℹ️ 无变更，跳过 commit')
        else:
            print(f'⚠️ Git commit 失败: {r.stderr[:200]}')
    except Exception as e:
        print(f'⚠️ Git 操作失败: {e}')

    proc.stdin.close()
    proc.wait()

if __name__ == '__main__':
    main()
