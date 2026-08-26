#!/bin/bash
# llm-radar twitter 采集 cron 包装 (CL-SEC19, D1A)
# 1) 检查 CDP 调试 Chrome (默认 9222); 无则自动拉起 (独立 profile, 复用登录态)
# 2) 轮询等 ready (最多 30s)
# 3) exec --attach 采集 (stdout 透传, 退出码原样)
set -u
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${TWITTER_CDP_PORT:-9222}"
PROFILE="$HOME/chrome-twitter-cdp"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

is_ready() {
  curl -s --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

if ! is_ready; then
  echo "[twitter-cron] ${PORT} 未就绪, 启动调试 Chrome (profile: ${PROFILE})"
  "$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" \
    >/tmp/twitter-chrome.log 2>&1 &
  for _ in $(seq 1 15); do
    sleep 2
    is_ready && break
  done
fi

if ! is_ready; then
  echo "[twitter-cron] ❌ 调试 Chrome 启动失败 (见 /tmp/twitter-chrome.log), 请手动检查" >&2
  exit 1
fi

cd "$PROJ_DIR" || exit 1
exec python3 scripts/twitter-collector.py --attach
