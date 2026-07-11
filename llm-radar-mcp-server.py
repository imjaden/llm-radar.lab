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
import secrets
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = os.environ.get('LLM_RADAR_MCP_KEY', '')
if not API_KEY:
    API_KEY = secrets.token_hex(32)  # 64-char random hex
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stderr,
    )
    log = logging.getLogger('mcp-llm-radar')
    log.warning('=' * 60)
    log.warning('⚠️  LLM_RADAR_MCP_KEY 未设置，已生成临时随机 key')
    log.warning(f'   本次会话 key: {API_KEY[:8]}...{API_KEY[-4:]}')
    log.warning('   建议: export LLM_RADAR_MCP_KEY=<your-secure-key>')
    log.warning('=' * 60)
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stderr,
    )
    log = logging.getLogger('mcp-llm-radar')
PROJECT_ROOT = Path(os.environ.get('LLM_RADAR_DIR', __file__)).resolve().parent
DATA_DIR = PROJECT_ROOT / 'data'
SNAPSHOT_PATH = DATA_DIR / 'snapshot.json'

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
                if "id" not in item or not item.get("id"):
                    item["id"] = name.lower().replace(" ", "-").replace("/", "-")[:40]
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

    # Data retention: max 100 per dimension + 15-day sliding window (same as Agent Loop)
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
    for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
        items = snapshot.get(dim, [])
        if len(items) <= 100:
            continue
        # Remove items without recent events
        date_fields = {'hotspots': 'date', 'providers': 'last_event_date',
                       'people': 'recent_activity_date', 'tools': 'last_update_date',
                       'llms': 'last_event_date'}
        df = date_fields.get(dim, 'last_event_date')
        recent = [e for e in items if e.get(df, '') >= cutoff]
        if len(recent) > 100:
            recent.sort(key=lambda e: e.get(df, ''), reverse=True)
            recent = recent[:100]
        snapshot[dim] = recent if recent else items[:100]

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
    """CLI entry point with lifecycle commands."""
    import argparse

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE = DATA_DIR / 'mcp-server.pid'
    LOG_FILE = DATA_DIR / 'mcp-server.log'
    DEFAULT_PORT = 8901

    def _read_pid():
        """Read PID file. Returns (pid, port) or (None, None)."""
        if PID_FILE.exists():
            try:
                data = json.loads(PID_FILE.read_text())
                pid = data.get('pid')
                port = data.get('port', 0)
                # Verify process is alive
                if pid:
                    os.kill(pid, 0)
                    return pid, port
            except (ProcessLookupError, json.JSONDecodeError, OSError):
                PID_FILE.unlink(missing_ok=True)
        return None, None

    def _write_pid(pid, port=0):
        """Write PID file."""
        PID_FILE.write_text(json.dumps({'pid': pid, 'port': port, 'started_at': datetime.now().isoformat()}))

    def _get_status():
        """Return dict with full server status."""
        pid, port = _read_pid()
        stats = {}
        if SNAPSHOT_PATH.exists():
            try:
                snap = json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
                stats = snap.get('stats', {})
            except:
                pass
        return {
            'running': pid is not None,
            'pid': pid,
            'port': port if pid else None,
            'mode': 'http' if port and pid else ('stdio' if pid else 'stopped'),
            'log': str(LOG_FILE) if LOG_FILE.exists() else None,
            'pid_file': str(PID_FILE),
            'snapshot': str(SNAPSHOT_PATH),
            'total_entities': sum(stats.get(k, 0) for k in
                                   ['total_providers', 'total_people', 'total_tools', 'total_llms', 'total_hotspots']),
            'detail': stats,
        }

    def cmd_start(args):
        """Start MCP server (stdio or HTTP)."""
        # 管道模式：输入来自 pipe（echo | python3 ...），不检查 PID 直接处理消息
        if not sys.stdin.isatty():
            main()
            return

        pid, port = _read_pid()
        if pid:
            status = _get_status()
            mode = 'HTTP' if status['port'] else 'stdio'
            print(f'⚠️  MCP Server 已在运行 (PID={pid}, 模式={mode})')
            print(f'   使用 `{sys.argv[0]} status` 查看详情')
            return

        if args.port:
            # HTTP mode — launch as daemon or foreground
            if args.daemon:
                import subprocess
                log_fd = open(LOG_FILE, 'a')
                # Spawn child process directly running HTTP server, not via 'start'
                child_code = f'''import sys; sys.path.insert(0, {repr(str(PROJECT_ROOT))})
import json, os; os.environ['MCP_HTTP_MODE'] = '1'
os.chdir({repr(str(PROJECT_ROOT))})
from http.server import HTTPServer, BaseHTTPRequestHandler
# Inline minimal HTTP server (same as run_http_server)
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, d, c=200):
        self.send_response(c); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
        self.wfile.write(json.dumps(d, ensure_ascii=False).encode())
    def do_GET(self):
        if self.path=='/health': self._j({{'status':'ok','version':'1.0'}})
        elif self.path=='/api/status':
            import json as j2
            s={{}};
            try: s=j2.loads(open({repr(str(SNAPSHOT_PATH))}).read()).get('stats',{{}})
            except: pass
            self._j({{'running':True,'port':{args.port},'total_entities':sum(s.get(k,0) for k in ['total_providers','total_people','total_tools','total_llms','total_hotspots']),'detail':s}})
        else: self._j({{'error':'not found'}},404)
    def do_POST(self):
        if self.path=='/api/submit':
            import sys as _s, json as _j; _s.path.insert(0, {repr(str(PROJECT_ROOT))})
            from llm_radar_mcp_server import require_auth, validate_entities, merge_entities
            l=int(self.headers.get('Content-Length',0))
            p=_j.loads(self.rfile.read(l))
            ae=require_auth(p)
            if ae: self._j({{'error':ae}},401); return
            es={{}};
            for d in ['providers','people','tools','llms','hotspots']: es[d]=p.get(d,[])
            if sum(len(v) for v in es.values())==0: self._j({{'error':'empty'}},400); return
            ac,re,rz=validate_entities(es)
            if sum(len(v) for v in ac.values())==0: self._j({{'status':'rejected'}}); return
            n,u,s=merge_entities(ac)
            self._j({{'status':'accepted','accepted':{{k:len(v) for k,v in ac.items()}},'merge_result':{{'new':n,'updated':u}}}})
        else: self._j({{'error':'not found'}},404)
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
HTTPServer(('0.0.0.0',{args.port}),H).serve_forever()'''
                proc = subprocess.Popen([sys.executable, '-c', child_code],
                                        stdout=log_fd, stderr=log_fd, close_fds=True)
                _write_pid(proc.pid, args.port)
                import time; time.sleep(1)
                # Verify it started
                if proc.poll() is not None:
                    print(f'❌ MCP Server 启动失败，请检查日志: {LOG_FILE}')
                    PID_FILE.unlink(missing_ok=True)
                else:
                    print(f'✅ MCP Server 已启动 (PID={proc.pid}, 端口={args.port})')
                    print(f'   日志: {LOG_FILE}')
                    if args.open:
                        import webbrowser
                        webbrowser.open(f'http://localhost:{args.port}')
            else:
                # Foreground HTTP server
                os.environ['MCP_HTTP_MODE'] = '1'
                _write_pid(os.getpid(), args.port)
                print(f'✅ MCP Server 已启动 (PID={os.getpid()}, 端口={args.port})')
                print(f'   按 Ctrl+C 停止')
                run_http_server(args.port)
        else:
            # Stdio mode (default, for Hermes Agent)
            _write_pid(os.getpid(), 0)
            main()

    def cmd_stop(args):
        """Stop MCP server."""
        pid, port = _read_pid()
        if not pid:
            print('ℹ️  MCP Server 未在运行')
            return
        try:
            os.kill(pid, 15)  # SIGTERM
            import time
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)  # SIGKILL if still alive
            except ProcessLookupError:
                pass
            PID_FILE.unlink(missing_ok=True)
            print(f'✅ MCP Server 已停止 (PID={pid})')
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
            print(f'ℹ️  MCP Server (PID={pid}) 已不存在')

    def cmd_status(args):
        """Show MCP server status."""
        status = _get_status()
        if args.json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return

        if status['running']:
            mode_str = f"🌐 {status['mode'].upper()}"
            port_str = f", 端口={status['port']}" if status['port'] else ''
            print(f'✅ MCP Server  运行中')
            print(f'   PID: {status["pid"]}  {mode_str}{port_str}')
            print(f'   实体数: {status["total_entities"]}')
            if status['log']:
                print(f'   日志: {status["log"]}')
            print(f'   PID 文件: {status["pid_file"]}')
        else:
            print('⏹️  MCP Server  未运行')

    def cmd_restart(args):
        """Restart MCP server."""
        cmd_stop(args)
        cmd_start(args)

    def cmd_help(args):
        """Show usage information."""
        print(f'''
╔══════════════════════════════════════════════╗
║         LLM-Radar MCP Server v1.0            ║
╚══════════════════════════════════════════════╝

 Usage:
   {sys.argv[0]} <command> [options]

 Commands:

   start      启动 MCP Server
     --port PORT     HTTP 端口（默认 0 = stdio 模式，供 Hermes Agent 对接）
     --daemon       后台运行（仅 HTTP 模式）
     --open         自动打开浏览器（仅 HTTP 模式）

   status     查看运行状态
     --json         JSON 格式输出

   stop       停止 MCP Server

   restart    重启 MCP Server

   help       显示本帮助

 Examples:
   # Stdio 模式（对接 Hermes Agent，默认）
   {sys.argv[0]} start

   # HTTP 模式（前台运行）
   {sys.argv[0]} start --port 8901

   # HTTP 模式（后台运行）
   {sys.argv[0]} start --port 8901 --daemon --open

   # 查看状态
   {sys.argv[0]} status
   {sys.argv[0]} status --json

   # 停止
   {sys.argv[0]} stop

 Environment:
   LLM_RADAR_MCP_KEY    API Key（默认: llm-radar-mcp-2026）
   LLM_RADAR_DIR        项目根目录

 Data Files:
   data/mcp-server.pid  PID 文件
   data/mcp-server.log  运行日志
   data/snapshot.json   数据快照
''')

    # ── HTTP Server ──────────────────────────────────────────────────────

    def run_http_server(port):
        """Run HTTP server wrapping MCP tools."""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class MCPHTTPHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                logging.info(f'HTTP {args[0]} {args[1]} - {args[2]}')

            def _send_json(self, data, code=200):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

            def do_GET(self):
                if self.path == '/health':
                    status = _get_status()
                    self._send_json({'status': 'ok', 'version': '1.0', 'server': 'llm-radar-mcp',
                                     'running': status['running'], 'total_entities': status['total_entities']})
                elif self.path == '/api/status':
                    self._send_json(_get_status())
                else:
                    self._send_json({'error': 'not found'}, 404)

            def do_POST(self):
                if self.path == '/api/submit':
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length)
                    try:
                        params = json.loads(body)
                    except json.JSONDecodeError:
                        self._send_json({'error': 'invalid JSON'}, 400)
                        return
                    # Auth
                    auth_err = require_auth(params)
                    if auth_err:
                        self._send_json({'error': auth_err}, 401)
                        return
                    # Process
                    entities = {}
                    for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
                        entities[dim] = params.get(dim, [])
                    total = sum(len(v) for v in entities.values())
                    if total == 0:
                        self._send_json({'error': 'empty submission'}, 400)
                        return
                    accepted, rejected, reasons = validate_entities(entities)
                    if sum(len(v) for v in accepted.values()) == 0:
                        self._send_json({'status': 'rejected', 'accepted': {}, 'rejected_reasons': reasons}, 200)
                        return
                    new_c, upd_c, stats = merge_entities(accepted)
                    self._send_json({
                        'status': 'accepted' if len(reasons) == 0 else 'partial',
                        'accepted': {k: len(v) for k, v in accepted.items()},
                        'rejected': {k: len(v) for k, v in rejected.items()},
                        'rejected_reasons': reasons,
                        'merge_result': {'new': new_c, 'updated': upd_c},
                        'snapshot_totals': stats,
                    })
                else:
                    self._send_json({'error': 'not found'}, 404)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

        server = HTTPServer(('0.0.0.0', port), MCPHTTPHandler)
        print(f'🔗  HTTP Server: http://localhost:{port}')
        print(f'   GET  /health       — 健康检查')
        print(f'   GET  /api/status   — 状态详情')
        print(f'   POST /api/submit   — 提交实体数据')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\n⏹️  服务器已停止')
            server.server_close()

    # ── CLI Dispatch ─────────────────────────────────────────────────────

    parser = argparse.ArgumentParser(description='LLM-Radar MCP Server', add_help=False)
    parser.add_argument('command', nargs='?', default='start', choices=['start', 'stop', 'status', 'restart', 'help'])
    parser.add_argument('--port', type=int, default=0, help=f'HTTP port (default: 0 = stdio mode)')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (HTTP mode only)')
    parser.add_argument('--open', action='store_true', help='Open browser (HTTP mode only)')
    parser.add_argument('--json', action='store_true', help='JSON output (status only)')

    args = parser.parse_args()
    cmd_map = {'start': cmd_start, 'stop': cmd_stop, 'status': cmd_status,
               'restart': cmd_restart, 'help': cmd_help}
    cmd_map[args.command](args)
