#!/bin/bash
# al-dev.sh — dev-executor context script
#
# 在 cron job 的 agent mode 中运行, 将当前 task 的上下文注入到 agent 的 prompt 中。
# stdout 被 cron 系统作为 script context 使用。
# stderr 用于进度提示（>/dev/stderr）。

BASE="$HOME/CodeSpace/llm-radar.jaden.tech"
cd "$BASE" || exit 1

TASK_DIR="$(readlink tasks/active-task 2>/dev/null || echo "")"
if [ -z "$TASK_DIR" ]; then
  echo "=== 无活跃 task ===" > /dev/stderr
  exit 0
fi

echo "=== 当前任务 ===" > /dev/stderr
echo "任务目录: tasks/$TASK_DIR"

echo "=== task-manifest.yaml ==="
cat "tasks/$TASK_DIR/task-manifest.yaml" 2>/dev/null || echo "(不存在)"

echo "=== demand.md ==="
cat "tasks/$TASK_DIR/demand.md" 2>/dev/null || echo "(空)"

echo "=== audit-log.md ==="
cat "tasks/$TASK_DIR/audit-log.md" 2>/dev/null || echo "(无评审记录)"
