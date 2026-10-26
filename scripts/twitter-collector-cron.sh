#!/bin/bash
# llm-radar twitter 采集 cron 包装 (CL-SEC19 D1A; 按需启停 2026-10-06; 节流+代理生命周期 2026-10-09)
#
# 生命周期 (按序):
#   0) 节流: twitter.json 生成 < TWITTER_THROTTLE_HOURS 则跳过 (`--force` 绕过) —— 支持 cron 每小时尝试,
#      任意一次唤醒都能补上被休眠错过的槽位 (固定 09:20/21:20 会整槽丢失: 2026-10-07~09 实测断 3 天)。
#   1) FlClash 代理 (X 必需): 未运行 → 拉起 + 等 7890 LISTEN (≤180s) → 采集后释放;
#      原本就在运行 → 先验端口 (不通 ⇒ 短预算 10s 后判未就绪, 不重复拉起) → 采集后保持运行不动。
#      **探测/就绪/起停唯一真源 = scripts/flclash_proxy.py** (本脚本只编排, 不自持 pgrep/osascript/nc);
#      命令与阈值对齐声明层真源 script-miner/projects/macosx/macosx-service-policy.json
#      (services[FlClash].restart: stop=`osascript -e 'quit app "FlClash"'` / grace 20s /
#       force_fallback=`kill -TERM {pid}` / start=`open -g -a FlClash` / verify.ports=[7890])。
#   2) 调试 Chrome (默认 9222): 未就绪则拉起 (独立 profile, 复用登录态) → 采集 → 释放本脚本拉起的实例。
# 幂等/安全: 只关「本脚本拉起的」「上轮遗留(pidfile)的」调试 Chrome 与 FlClash; 外部常驻实例一律不动。
#
# 环境变量:
#   TWITTER_THROTTLE_HOURS          数据新鲜度节流阈值 h (默认 5; 0 = 关闭节流)
#   TWITTER_FLCLASH_ENSURE          1=管理 FlClash 起停 (默认), 0=不管理生命周期 (采集器只探测不拉起)
#   TWITTER_FLCLASH_PORT            就绪判据端口 (默认 7890)
#   TWITTER_FLCLASH_READY_TIMEOUT   启动后等就绪秒数 (默认 180)
#   TWITTER_FLCLASH_GRACE           优雅退出宽限秒数 (默认 20)
#   TWITTER_CHROMEDRIVER           chromedriver 可执行文件（默认由 scripts/chromedriver_bootstrap.py 给出已验证兼容路径）
#   TWITTER_CDP_PORT                调试端口 (默认 9222)
#   TWITTER_PROFILE_DIR             user-data-dir (默认 ~/chrome-twitter-cdp)
#   TWITTER_CHROME_BIN              Chrome 可执行文件 (默认 macOS 标准路径)
#   TWITTER_CHROME_LOG              拉起 Chrome 的 stdout/stderr (默认 /tmp/twitter-chrome.log)
#   TWITTER_CHROME_SHUTDOWN_TIMEOUT 优雅退出等待秒数, 超时 SIGKILL (默认 15)
#   TWITTER_CHROME_READY_TRIES      启动后就绪轮询次数, 每次 2s (默认 15 = ≤30s)
#   TWITTER_WINDOW_POS              采集 Chrome 窗口左上角 x,y (默认 -1900,-297 = 本机副屏左上)
#   TWITTER_WINDOW_SIZE             采集 Chrome 窗口 w,h (默认 880,1000)
#   TWITTER_DISPLAY_COUNT           覆盖「副屏探测」结果 (测试用; 未设则 system_profiler 实测)
#   TWITTER_CHROME_KEEP=1           采集后不释放任何本脚本拉起的资源 (人工登录/调试用)
#
# 用法: bash scripts/twitter-collector-cron.sh [--force]
set -u
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${TWITTER_CDP_PORT:-9222}"
PROFILE="${TWITTER_PROFILE_DIR:-$HOME/chrome-twitter-cdp}"
CHROME="${TWITTER_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
CHROME_LOG="${TWITTER_CHROME_LOG:-/tmp/twitter-chrome.log}"
SHUTDOWN_TIMEOUT="${TWITTER_CHROME_SHUTDOWN_TIMEOUT:-15}"
READY_TRIES="${TWITTER_CHROME_READY_TRIES:-15}"
WIN_POS="${TWITTER_WINDOW_POS:--1900,-297}"
WIN_SIZE="${TWITTER_WINDOW_SIZE:-880,1000}"
THROTTLE_HOURS="${TWITTER_THROTTLE_HOURS:-5}"
FLCLASH_ENSURE="${TWITTER_FLCLASH_ENSURE:-1}"
FLCLASH_PORT="${TWITTER_FLCLASH_PORT:-7890}"
FLCLASH_READY_TIMEOUT="${TWITTER_FLCLASH_READY_TIMEOUT:-180}"
FLCLASH_GRACE="${TWITTER_FLCLASH_GRACE:-20}"
PIDFILE="$PROJ_DIR/cache/pids/twitter-chrome-${PORT}.pid"
OWNED=0
OWNED_FLCLASH=0

cd "$PROJ_DIR" || exit 1
mkdir -p "$(dirname "$PIDFILE")"

is_ready() {
  curl -s --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

# ── 窗口摆位: 采集 Chrome 必须保持 visible ────────────────────────────────────
# 实测 (2026-10-21, Chrome 155 + 9210px 测试页): 窗口最小化/隐藏 ⇒ document.visibilityState=hidden,
# scrollTo 执行成功但 **scroll 事件 0 次派发、IntersectionObserver 0 次、DOM 0 增长**;
# 同一页面 visible 下滚 3 次 = scroll 172 次 / DOM +172 项。X 时间线靠滚动加载 ⇒
# 最小化会让采集静默少数据 (不报错, 只是拿不到)。故摆到副屏小窗: 保持 visible, 且不 activate 抢前台。
# 单屏 / 坐标非法 / 探测不到副屏 → 不传坐标 (退化为 Chrome 默认位, 仍 visible)。
# 默认坐标 (-1900,-297, 880x1000) 实测标定: 起窗后 rect=(-1900,-297,880,1000), 页面内
# screen.availLeft/Top=[-1920,-297] 与之一致 (WindowServer 把副屏放在主屏上方 → y 为负)。
# 注意: Chrome 会把窗口夹进所在屏, 超出部分被推回 (曾传 y=240/727 均被夹到 -297 附近)。
display_count() {
  if [ -n "${TWITTER_DISPLAY_COUNT:-}" ]; then printf '%s' "$TWITTER_DISPLAY_COUNT"; return 0; fi
  local n
  n="$(system_profiler SPDisplaysDataType 2>/dev/null | grep -c 'Resolution:')"
  printf '%s' "${n:-0}"
}

window_args() {
  local n
  case "${WIN_POS}${WIN_SIZE}" in
    *[!0-9,.-]*) echo "[twitter-cron] ⚠️  窗口坐标非法 (${WIN_POS} / ${WIN_SIZE}), 不传窗口参数" >&2; return 0 ;;
  esac
  n="$(display_count)"
  case "$n" in ''|*[!0-9]*) n=0 ;; esac
  if [ "$n" -lt 2 ]; then
    echo "[twitter-cron] 未检出副屏 (display_count=${n}), 不传窗口参数 (Chrome 默认位)" >&2
    return 0
  fi
  printf '%s' "--window-position=${WIN_POS} --window-size=${WIN_SIZE}"
}

# 调试 Chrome 主进程 PID = 命令行含调试端口 ∧ 非 Helper 子进程 (Helper 均带 --type=) ∧ 是 Chrome 程序本身。
# 加「是 Chrome 程序」这条是为了不误伤仅"提到"该端口的旁观进程 (监视脚本/编辑器/我的巡检命令都曾中招);
# 用 pgrep 取候选 (pgrep 不匹配自身), 再逐 pid 校验, 避免 ps 快照把 grep/awk 自身算进来
CHROME_NAME="$(basename "$CHROME")"
main_pids() {
  local p cmd
  for p in $(pgrep -f "remote-debugging-port=${PORT}" 2>/dev/null); do
    cmd="$(ps -o command= -p "$p" 2>/dev/null)" || continue
    [ -n "$cmd" ] || continue
    case "$cmd" in
      *--type=*) continue ;;
    esac
    case "$cmd" in
      *"$CHROME_NAME"*|*"Google Chrome"*) ;;
      *) continue ;;
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

# ===== FlClash 代理 (X 必需) =====
# 唯一真源 = scripts/flclash_proxy.py: 探测(精确名 ∪ 应用路径双判据) / 就绪(端口 LISTEN) / 起停 / 通知。
# 本脚本只做编排: 消假阳性(单一 `pgrep -f` + 应用名的老口径会被 `osascript -e 'quit app "FlClash"'` 这类
# 命令行含 FlClash 的进程自身命中)与阈值口径都在 helper 里, 勿在此重写。
FLCLASH_PY="$PROJ_DIR/scripts/flclash_proxy.py"

flclash_pids() { python3 "$FLCLASH_PY" pids 2>/dev/null; }

flclash_running() { python3 "$FLCLASH_PY" is-running >/dev/null 2>&1; }

ensure_flclash() {
  local was_running=0
  if flclash_running; then
    was_running=1
    echo "[twitter-cron] FlClash 已在运行 (pid: $(flclash_pids | tr '\n' ' ')) ⇒ 验 ${FLCLASH_PORT} 后复用, 采集后保持运行"
  else
    echo "[twitter-cron] FlClash 未运行, 启动 (open -g -a FlClash; 就绪判据 ${FLCLASH_PORT} LISTEN ≤${FLCLASH_READY_TIMEOUT}s)"
  fi
  # Q-1: 「进程在」≠「代理通」⇒ 无论是否在运行都走 ensure（已在运行且端口通时即时返回, 不会重复拉起）
  if python3 "$FLCLASH_PY" ensure --timeout "$FLCLASH_READY_TIMEOUT" --port "$FLCLASH_PORT" >/dev/null; then
    if [ "$was_running" = "0" ]; then
      OWNED_FLCLASH=1
      echo "[twitter-cron] FlClash 就绪 (${FLCLASH_PORT} LISTEN), 采集后释放"
    else
      echo "[twitter-cron] FlClash 就绪 (${FLCLASH_PORT} LISTEN), 沿用外部实例"
    fi
    return 0
  fi
  if [ "$was_running" = "1" ]; then
    echo "[twitter-cron] ⏸️  FlClash 在运行但 ${FLCLASH_PORT} 不可达, 本轮跳过 (不计失败; CL151/Q-1)" >&2
  else
    echo "[twitter-cron] ⏸️  FlClash 启动后 ${FLCLASH_READY_TIMEOUT}s 内 ${FLCLASH_PORT} 未 LISTEN, 本轮跳过 (不计失败; CL151)" >&2
  fi
  return 1
}

release_flclash() {
  echo "[twitter-cron] 释放 FlClash (真源 helper: osascript quit → 宽限 ${FLCLASH_GRACE}s → kill -TERM 兜底)"
  if python3 "$FLCLASH_PY" release --grace "$FLCLASH_GRACE" >/dev/null; then
    echo "[twitter-cron] ✅ FlClash 已释放"
  else
    echo "[twitter-cron] ⚠️  FlClash 仍在运行 (pid: $(flclash_pids | tr '\n' ' '))" >&2
  fi
}

# 数据新鲜度 (h); 无法判定 → 退出码非 0 (不跳过, 交给采集器自己报错)
twitter_age_hours() {
  python3 - "$THROTTLE_HOURS" <<'PY'
import datetime, json, sys
try:
    gen = datetime.datetime.strptime(json.load(open('data/twitter.json'))['generated_at'],
                                     '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
except Exception:
    print('?')
    raise SystemExit(1)
now = datetime.datetime.now(datetime.timezone.utc)
print(f'{(now - gen).total_seconds() / 3600.0:.1f}')
raise SystemExit(0)
PY
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM HUP
  if [ "${TWITTER_CHROME_KEEP:-0}" = "1" ]; then
    [ "$OWNED" = "1" ] && echo "[twitter-cron] TWITTER_CHROME_KEEP=1, 保留调试 Chrome (pidfile: ${PIDFILE})"
    [ "$OWNED_FLCLASH" = "1" ] && echo "[twitter-cron] TWITTER_CHROME_KEEP=1, 保留 FlClash"
  else
    [ "$OWNED" = "1" ] && shutdown_chrome
    [ "$OWNED_FLCLASH" = "1" ] && release_flclash
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

FORCE=0
for a in "$@"; do
  case "$a" in
    --force|--no-throttle) FORCE=1 ;;
  esac
done

# ===== 0) 节流 =====
if [ "$FORCE" != "1" ] && [ "$THROTTLE_HOURS" != "0" ]; then
  if age="$(twitter_age_hours)" && [ -n "$age" ] && [ "$age" != "?" ]; then
    if python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)" "$age" "$THROTTLE_HOURS"; then
      echo "[twitter-cron] 跳过: twitter.json 生成于 ${age}h 前 (< 节流阈值 ${THROTTLE_HOURS}h; --force 绕过)"
      exit 0
    fi
    echo "[twitter-cron] 距上次采集 ${age}h (≥ ${THROTTLE_HOURS}h), 执行采集"
  fi
fi

# ===== 1) FlClash 代理 =====
# 端口两侧同源 (Q-1 后端口是硬门禁): 采集器子进程按同一 TWITTER_FLCLASH_PORT 探测;
# 否则本脚本验 A 端口通过、采集器再验真源默认 7890 失败 ⇒ 每轮静默跳到「未就绪」。
export TWITTER_FLCLASH_PORT="$FLCLASH_PORT"
if [ "$FLCLASH_ENSURE" = "1" ]; then
  # CL151: 就绪失败 ⇒ 本轮静默跳过（跳过 ≠ 失败: 不计连败、不告警、不发通知）
  if ! ensure_flclash; then
    echo "[twitter-cron] ⏸️  跳过本轮: FlClash 代理未就绪 (非异常, 不计失败; CL151)"
    exit 0
  fi
else
  echo "[twitter-cron] TWITTER_FLCLASH_ENSURE=0, 不管理 FlClash 生命周期"
  # Q-2: 关掉生命周期管理时, 采集器只允许探测、不得自行拉起（否则可能被拉起后常驻）
  export TWITTER_PROXY_NO_ENSURE=1
fi

# ===== 2) 调试 Chrome =====
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
  WINDOW_ARGS="$(window_args)"
  # shellcheck disable=SC2086  # WINDOW_ARGS 是受控的 `--k=v --k=v`; 不用数组: macOS /bin/bash 3.2 + set -u 下空数组展开会报 unbound variable
  "$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" $WINDOW_ARGS \
    >>"$CHROME_LOG" 2>&1 &
  OWNED=1
  if [ -n "$WINDOW_ARGS" ]; then
    echo "[twitter-cron] 窗口摆位 (保持 visible, 不抢前台): ${WINDOW_ARGS}"
  fi
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

# ── chromedriver 版本守卫（Chrome 自动升级后自动跟随; 无 chromedriver-manager 的平台自动跳过）──
if [ -z "${TWITTER_CHROMEDRIVER:-}" ] && [ -f "scripts/chromedriver_bootstrap.py" ]; then
  # OBS-6: 单次调用（就绪即返回, 不就绪按 60s 预算跟随）
  _drv="$(python3 scripts/chromedriver_bootstrap.py --resolve --deadline 60 2>/dev/null || true)"
  if [ -n "$_drv" ]; then
    export TWITTER_CHROMEDRIVER="$_drv"
    echo "[twitter-cron] chromedriver: $_drv"
  else
    echo "[twitter-cron] chromedriver 未就绪（已按 60s 预算尝试跟随）⇒ 回退既有扫描逻辑"
  fi
fi

python3 scripts/twitter-collector.py --attach
