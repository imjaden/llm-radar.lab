#!/bin/bash
# CDP Chrome 常驻守护入口（launchd ProgramArguments 调它，2026-11-12 CL017）
#
# 背景（实测事故）：plist 直接 `exec Chrome … https://x.com/home` + `KeepAlive=true` 时，
# 如果已有**别的** Chrome 占用同一 user-data-dir（Chrome 自更新会以 --no-startup-window
# 自重启并带上 --remote-allow-origins=*），每次 spawn 都会被现有实例「转发 URL 后退出 0」
# ⇒ launchd 每 ThrottleInterval(30s) 再 spawn 一次 ⇒ **每 30 秒多一个 https://x.com/home 页签**
# （实测 runs 477、16+ 页签，日志刷 `Opening in existing browser session.`）。
#
# 本脚本的契约（幂等）：
#   ① 端口已在监听 ⇒ 不再起 Chrome：补一次 page target（0 页才补）后 **exit 0**
#      —— 配合 plist 的 `KeepAlive = { SuccessfulExit = false }`，正常退出不再重启 ⇒ 无循环
#   ② 端口空闲 ⇒ exec Chrome（成为唯一实例，launchd 视其为本 job 的进程）
#   ③ Chrome 异常退出 ⇒ 非 0 退出码 ⇒ launchd 按 KeepAlive 重启（保留守护语义）
#
# 用法: bash scripts/twitter-chrome-agent.sh [--dry-run]
# env: TWITTER_CDP_PORT / TWITTER_PROFILE_DIR / TWITTER_CDP_PAGE_URL /
#      TWITTER_CHROME_BIN / TWITTER_WINDOW_POS / TWITTER_WINDOW_SIZE
set -u

PORT="${TWITTER_CDP_PORT:-9222}"
PROFILE="${TWITTER_PROFILE_DIR:-$HOME/chrome-twitter-cdp}"
URL="${TWITTER_CDP_PAGE_URL:-https://x.com/home}"
CHROME="${TWITTER_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
POS="${TWITTER_WINDOW_POS:--1900,-297}"
SIZE="${TWITTER_WINDOW_SIZE:-880,1000}"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

port_open() {
  # 不依赖 lsof（launchd 的最小 PATH 里 lsof 在 /usr/sbin，但 /dev/tcp 零依赖）
  (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null && { exec 3>&- 2>/dev/null; return 0; }
  return 1
}

page_count() {
  # 只认 /json/list 里 "type": "page"；取不到（非 2xx / 空）返回空串 ⇒ 调用方不做任何写动作
  local body n
  body="$(curl -s --max-time 3 "http://127.0.0.1:${PORT}/json/list" 2>/dev/null)" || return 1
  [ -n "$body" ] || return 1
  n="$(printf '%s' "$body" | grep -o '"type": *"page"' | wc -l | tr -d ' ')"
  printf '%s' "${n:-0}"
}

ensure_page() {
  local n
  n="$(page_count)" || { echo "[chrome-agent] /json/list 不可读，跳过补页"; return 0; }
  if [ "${n:-0}" -gt 0 ]; then
    echo "[chrome-agent] page targets=${n}，无需补页"
    return 0
  fi
  echo "[chrome-agent] page targets=0 ⇒ 补页 ${URL}"
  [ "$DRY" = "1" ] && return 0
  curl -s -X PUT --max-time 5 "http://127.0.0.1:${PORT}/json/new?${URL}" >/dev/null 2>&1 || true
}

if port_open; then
  echo "[chrome-agent] 127.0.0.1:${PORT} 已在监听（外部实例）⇒ 不重复启动，exit 0（KeepAlive 不再重启）"
  ensure_page
  exit 0
fi

echo "[chrome-agent] 127.0.0.1:${PORT} 空闲 ⇒ 启动调试 Chrome（profile=${PROFILE}）"
[ -x "$CHROME" ] || { echo "[chrome-agent] ❌ 找不到 Chrome: ${CHROME}" >&2; exit 1; }
if [ "$DRY" = "1" ]; then
  echo "[chrome-agent] dry-run: ${CHROME} --remote-debugging-port=${PORT} --user-data-dir=${PROFILE} --window-position=${POS} --window-size=${SIZE} ${URL}"
  exit 0
fi
exec "$CHROME" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE}" \
  --window-position="${POS}" \
  --window-size="${SIZE}" \
  "${URL}"
