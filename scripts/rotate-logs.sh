#!/bin/bash
# 日志轮转（copytruncate 语义）—— 2026-10-26
#
# 为什么是 copytruncate 而不是 rename/mv：
#   写入方（crontab `>>` 重定向、wrapper、launchd）每轮重新 open 追加，但长跑进程（tail/grep 巡检、
#   采集器继承的 stdout）可能仍持有 fd ⇒ rename 后新行继续写进旧 inode，表现为「日志突然不再增长」。
#   这里 `cp -p` 出一份 → `: >` 原文件清零，路径不变、inode 不变，无人丢行（极端情况下可能丢正在写的一行）。
#
# 触发条件（满足其一）：
#   · 文件 ≥ --max-bytes（默认 5 MB）
#   · 当天还没轮转过（跨天；cron 每天 06:10 跑 ⇒ 等价于按日归档，保证「最近 N 天」这个语义可靠）
# 保留：最近 --keep 份（默认 7）压缩档，其余删除。
#
# 用法:
#   bash scripts/rotate-logs.sh [--dry-run] [--force] [--dir DIR]... [--max-bytes N] [--keep N]
# 退出码: 0 正常（含无事可做） / 1 至少一个文件轮转失败
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="${ROTATE_STATE:-$ROOT/cache/records/rotate-logs-state.json}"
MAX_BYTES="${ROTATE_MAX_BYTES:-5242880}"
KEEP="${ROTATE_KEEP:-7}"
DRY=0
FORCE=0
DIRS=("$ROOT/cache/logs" "$HOME/Library/Logs/llm-radar")

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --force) FORCE=1 ;;
    --dir) DIRS=("$2"); shift ;;
    --max-bytes) MAX_BYTES="$2"; shift ;;
    --keep) KEEP="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

TODAY="$(date +%Y-%m-%d)"
NOW="$(date +%Y%m%d-%H%M%S)"

# 当天是否已轮转过（读状态文件里的 last 日期）
LAST=""
if [ -f "$STATE" ]; then
  LAST="$(sed -n 's/.*"last"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$STATE" | head -1)"
fi

rotated=0
failed=0

for base in "${DIRS[@]}"; do
  [ -d "$base" ] || continue
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    sz=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
    [ "$sz" -eq 0 ] && continue                      # 空文件不轮转（避免制造一堆空档）
    if [ "$FORCE" -eq 0 ] && [ "$LAST" = "$TODAY" ] && [ "$sz" -lt "$MAX_BYTES" ]; then
      continue                                       # 今天已轮转过且未超阈值
    fi
    if [ "$DRY" -eq 1 ]; then
      echo "[dry-run] $f (${sz}B) → $(basename "$f").$NOW.gz"
      rotated=$((rotated + 1))
      continue
    fi
    # 同一秒内连续轮转同名会覆盖 ⇒ 加序号后缀保证唯一（测试与手工演练常见）
    tag="$NOW"; n=1
    while [ -e "$f.$tag" ] || [ -e "$f.$tag.gz" ]; do tag="$NOW-$n"; n=$((n + 1)); done
    cp -p "$f" "$f.$tag" || { echo "❌ cp 失败: $f" >&2; failed=$((failed + 1)); continue; }
    : > "$f" || { echo "❌ 截断失败: $f" >&2; failed=$((failed + 1)); continue; }
    if gzip -f "$f.$tag"; then
      echo "🔄 已轮转: $f (${sz}B) → $(basename "$f").$tag.gz"
    else
      echo "❌ gzip 失败: $f.$tag" >&2
      failed=$((failed + 1))
    fi
    rotated=$((rotated + 1))
    # 保留最近 KEEP 份（按名字排序 = 按时间排序）。BSD head 不支持负计数 ⇒ 显式算超额份数
    total=$(ls -1 "$f".*.gz 2>/dev/null | wc -l | tr -d ' ')
    excess=$((total - KEEP))
    if [ "$excess" -gt 0 ]; then
      ls -1 "$f".*.gz 2>/dev/null | sort | head -n "$excess" | while IFS= read -r old; do
        rm -f "$old" && echo "🧹 清理: $(basename "$old")"
      done
    fi
  done < <(find "$base" -maxdepth 2 -type f -name '*.log' 2>/dev/null)
done

if [ "$DRY" -eq 0 ]; then
  mkdir -p "$(dirname "$STATE")"
  printf '{"last": "%s", "ts": "%s", "rotated": %d, "failed": %d}\n' \
    "$TODAY" "$NOW" "$rotated" "$failed" > "$STATE"
fi

[ "$rotated" -eq 0 ] && echo "无需轮转（今天已处理且未超 ${MAX_BYTES}B）"
[ "$failed" -gt 0 ] && exit 1
exit 0
