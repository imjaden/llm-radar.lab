#!/bin/bash
# llm-radar twitter 采集 cron 包装 (CL-SEC19 D1A; 按需启停 2026-10-06)
# 生命周期: 检查 CDP 调试 Chrome (默认 9222) → 未就绪则拉起 (独立 profile, 复用登录态),
#           就绪则直接复用 → 轮询等 ready (最多 30s) → 采集 (stdout 透传, 退出码原样)
#           → 采集结束释放本脚本拉起的实例 (省 ~660MB 常驻内存)。
# 幂等/安全: 只关「本脚本本轮拉起的」或「上轮遗留(pidfile)的」调试 Chrome; 外部常驻实例不动。
# 环境变量:
#   TWITTER_CDP_PORT                调试端口 (默认 9222)
#   TWITTER_PROFILE_DIR             user-data-dir (默认 ~/chrome-twitter-cdp)
#   TWITTER_CHROME_BIN              Chrome 可执行文件 (默认 macOS 标准路径)
#   TWITTER_CHROME_LOG              拉起 Chrome 的 stdout/stderr (默认 /tmp/twitter-chrome.log)
#   TWITTER_CHROME_SHUTDOWN_TIMEOUT 优雅退出等待秒数, 超时 SIGKILL (默认 15)
#   TWITTER_CHROME_READY_TRIES      启动后就绪轮询次数, 每次 2s (默认 15 = ≤30s)
#   TWITTER_CHROME_KEEP=1           采集后不释放 (人工登录/调试时需要保留窗口)
set -u
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${TWITTER_CDP_PORT:-9222}"
PROFILE="${TWITTER_PROFILE_DIR:-$HOME/chrome-twitter-cdp}"
CHROME="${TWITTER_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
CHROME_LOG="${TWITTER_CHROME_LOG:-/tmp/twitter-chrome.log}"
SHUTDOWN_TIMEOUT="${TWITTER_CHROME_SHUTDOWN_TIMEOUT:-15}"
READY_TRIES="${TWITTER_CHROME_READY_TRIES:-15}"
PIDFILE="$PROJ_DIR/cache/pids/twitter-chrome-${PORT}.pid"
OWNED=0

cd "$PROJ_DIR" || exit 1
mkdir -p "$(dirname "$PIDFILE")"

is_ready() {
  curl -s --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

# 调试 Chrome 主进程 PID = 命令行含调试端口且非 Helper 子进程 (Helper 均带 --type=);
# 用 pgrep 取候选 (pgrep 不匹配自身), 再逐 pid 校验, 避免 ps 快照把 grep/awk 自身算进来
main_pids() {
  local p cmd
  for p in $(pgrep -f "remote-debugging-port=${PORT}" 2>/dev/null); do
    cmd="$(ps -o command= -p "$p" 2>/dev/null)" || continue
    [ -n "$cmd" ] || continue
    case "$cmd" in
      *--type=*) continue ;;
    esac
    printf '%s\n' "$p"
  done
}

# pidfile 里第一个仍存活的 pid (记录可能含已退出的 bootstrap 进程 → 逐个检查, 不复用单个 pid 的判据)
first_live_pid() {
  [ -f "$PIDFILE" ] || return 1
  local p
  for p in $(tr -dc '0-9 \n' < "$PIDFILE" 2>/dev/null); do
    if kill -0 "$p" 2>/dev/null; then
      printf '%s' "$p"
      return 0
    fi
  done
  return 1
}

shutdown_chrome() {
  local pids alive left
  pids="$(main_pids)"
  [ -n "$pids" ] || pids="$(first_live_pid || true)"
  if [ -z "$pids" ]; then
    rm -f "$PIDFILE"
    echo "[twitter-cron] 无需释放 (${PORT} 已无调试 Chrome)"
    return 0
  fi

  echo "[twitter-cron] 释放调试 Chrome (pid: $(printf '%s' "$pids" | tr '\n' ' '))"
  kill -TERM $pids 2>/dev/null
  for _ in $(seq 1 "$SHUTDOWN_TIMEOUT"); do
    sleep 1
    is_ready || break
  done

  alive="$(main_pids)"
  if [ -n "$alive" ]; then
    echo "[twitter-cron] ⚠️  优雅退出超时 ${SHUTDOWN_TIMEOUT}s, SIGKILL: $(printf '%s' "$alive" | tr '\n' ' ')"
    kill -KILL $alive 2>/dev/null
    sleep 2
  fi
  rm -f "$PIDFILE"

  left="$(main_pids | wc -l | tr -d ' ')"
  if [ "$left" = "0" ]; then
    echo "[twitter-cron] ✅ 已释放 (剩余调试 Chrome 进程: 0)"
  else
    echo "[twitter-cron] ⚠️  仍有 ${left} 个调试 Chrome 进程存活" >&2
  fi
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM HUP
  if [ "$OWNED" = "1" ] && [ "${TWITTER_CHROME_KEEP:-0}" != "1" ]; then
    shutdown_chrome
  elif [ "$OWNED" = "1" ]; then
    echo "[twitter-cron] TWITTER_CHROME_KEEP=1, 保留调试 Chrome (pidfile: ${PIDFILE})"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

if is_ready; then
  # pidfile 存在即视为本脚本的实例 (正常收尾会删除; 残留 = 上轮被强杀/遗留) → 本轮收编释放
  if [ -f "$PIDFILE" ]; then
    OWNED=1
    p="$(first_live_pid || true)"
    echo "[twitter-cron] ${PORT} 已就绪 (上轮遗留${p:+, pid ${p}}), 复用并在采集后释放"
  else
    echo "[twitter-cron] ${PORT} 已就绪 (外部常驻实例), 复用, 不释放"
  fi
else
  echo "[twitter-cron] ${PORT} 未就绪, 启动调试 Chrome (profile: ${PROFILE})"
  "$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" \
    >>"$CHROME_LOG" 2>&1 &
  OWNED=1
  for _ in $(seq 1 "$READY_TRIES"); do
    sleep 2
    is_ready && break
  done
fi

if ! is_ready; then
  echo "[twitter-cron] ❌ 调试 Chrome 启动失败 (见 ${CHROME_LOG}), 请手动检查" >&2
  exit 1
fi

if [ "$OWNED" = "1" ]; then
  main_pids > "$PIDFILE" 2>/dev/null || true
fi

python3 scripts/twitter-collector.py --attach
