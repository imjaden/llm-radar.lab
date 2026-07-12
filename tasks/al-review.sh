#!/bin/bash
# al-review.sh — reviewer-executor context script
#
# 在 cron job 的 agent mode 中运行, 将当前 task 的评审上下文注入。

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

echo "=== demand.md (原始需求) ==="
cat "tasks/$TASK_DIR/demand.md" 2>/dev/null || echo "(空)"

echo "=== features.md (实现清单) ==="
cat "tasks/$TASK_DIR/features.md" 2>/dev/null || echo "(空)"

echo "=== git log ==="
git log --oneline -10 2>/dev/null || echo "(无 git 历史)"
