#!/bin/bash
# wrapper 中断钉子（CL007 P3 / SEC-1）—— 判 `lr` bash 包装层在 --json 模式下中断时
# 是否仍然「人类提示走 stderr、stdout 只剩信封」。
#
# 为什么必须 `set -m`：非交互 shell 的后台作业继承 SIGINT=SIG_IGN，不加作业控制时
# `kill -INT` 对子进程无效（实测 7/7 rc=0 且任务跑完，2026-11-03 review LR-CLI-005）。
#
# 用法: bash scripts/wrapper-interrupt-probe.sh [--json|--human] [秒数]
# 输出: 机器可读一行 `RESULT rc=<n> stdout=<n>B stderr=<n>B` + 两侧内容抽样
set -u

MODE="${1:---json}"
DELAY="${2:-1.2}"
LR="$HOME/.local/bin/lr"
[ -x "$LR" ] || { echo "RESULT skip reason=no-wrapper path=$LR"; exit 0; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

case "$MODE" in
  --json)  ARGS=(fetch qbitai --json) ;;
  --human) ARGS=(fetch qbitai) ;;
  *) echo "RESULT skip reason=bad-mode mode=$MODE"; exit 0 ;;
esac

set -m
"$LR" "${ARGS[@]}" >"$TMP/out" 2>"$TMP/err" &
PID=$!
sleep "$DELAY"
kill -INT "$PID" 2>/dev/null
wait "$PID"
RC=$?

OUT_B=$(wc -c <"$TMP/out" | tr -d ' ')
ERR_B=$(wc -c <"$TMP/err" | tr -d ' ')
echo "RESULT rc=$RC stdout=${OUT_B}B stderr=${ERR_B}B mode=$MODE"
echo "--- stdout ---"; head -c 400 "$TMP/out"; echo
echo "--- stderr ---"; head -c 400 "$TMP/err"; echo
