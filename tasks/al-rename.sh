#!/bin/bash
# al-rename.sh — 一次性迁移 agent-loop 文件命名规范
# 用法: cd <项目根目录> && bash tasks/al-rename.sh
#
# 变更内容:
#   loop.md          → requirements.md
#   AUDITLOG.md      → audit-log.md (根目录 + 每个 task 目录)
#   feature.md       → features.md (每个 task 目录)
#   manifest.yaml    → task-manifest.yaml (每个 task 目录)
#   tasks/current    → tasks/active-task (symlink)
#   tasks/.lock      → tasks/.agent-loop.lock
#   tasks/task-*     → tasks/al-* (任务目录)
#   tasks/agent-loop-scanner.py → tasks/al-scanner.py
#   tasks/agent-loop-dev.sh     → tasks/al-dev.sh
#   tasks/agent-loop-review.sh  → tasks/al-review.sh
#   tasks/init-task.py          → tasks/al-init.py
#   tasks/news-radar.yaml       → tasks/agents-teamwork.yaml
#
set -e
BASE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE"
echo "工作目录: $BASE"
echo ""

# Phase 1: 根目录
echo "=== Phase 1: 根目录文件 ==="
[ -f loop.md ] && mv -v loop.md requirements.md || echo "  (loop.md 不存在，跳过)"
[ -f AUDITLOG.md ] && mv -v AUDITLOG.md audit-log.md || echo "  (AUDITLOG.md 不存在，跳过)"

# Phase 2: tasks/ 目录
echo ""
echo "=== Phase 2: tasks/ 目录 ==="
cd tasks

# 脚本文件
[ -f agent-loop-scanner.py ] && mv -v agent-loop-scanner.py al-scanner.py || true
[ -f agent-loop-dev.sh ] && mv -v agent-loop-dev.sh al-dev.sh || true
[ -f agent-loop-review.sh ] && mv -v agent-loop-review.sh al-review.sh || true
[ -f init-task.py ] && mv -v init-task.py al-init.py || true

# 锁文件
[ -f .lock ] && mv -v .lock .agent-loop.lock || echo "  (.lock 不存在，跳过)"

# 项目级状态
[ -f news-radar.yaml ] && mv -v news-radar.yaml agents-teamwork.yaml || echo "  (news-radar.yaml 不存在，跳过)"

# Symlink: current → active-task
SAVED_TARGET="$(readlink current 2>/dev/null || echo "")"
if [ -L current ]; then
  rm current
  if [ -n "$SAVED_TARGET" ]; then
    NEW_TARGET="${SAVED_TARGET/#task-/al-}"
    ln -s "$NEW_TARGET" active-task
    echo "  current -> active-task (target: $NEW_TARGET)"
  fi
else
  echo "  (current symlink 不存在，跳过)"
fi

# 任务目录: task-* → al-*
for dir in task-*/; do
  [ -d "$dir" ] || continue
  dir="${dir%/}"
  new_dir="al${dir#task}"
  mv -v "$dir" "$new_dir"
done

# 任务目录内部文件
for dir in al-*/; do
  [ -d "$dir" ] || continue
  dir="${dir%/}"
  [ -f "$dir/manifest.yaml" ] && mv -v "$dir/manifest.yaml" "$dir/task-manifest.yaml" || true
  [ -f "$dir/feature.md" ] && mv -v "$dir/feature.md" "$dir/features.md" || true
  [ -f "$dir/AUDITLOG.md" ] && mv -v "$dir/AUDITLOG.md" "$dir/audit-log.md" || true
done

# 更新 symlink 如果它指向旧 task- 目录
CUR_TARGET="$(readlink active-task 2>/dev/null || echo "")"
if echo "$CUR_TARGET" | grep -q "^task-" >/dev/null 2>&1; then
  NEW_TARGET="al${CUR_TARGET#task}"
  rm active-task
  ln -s "$NEW_TARGET" active-task
  echo "  symlink 更新: active-task -> $NEW_TARGET"
fi

# Phase 3: documents/
echo ""
echo "=== Phase 3: documents/ ==="
cd "$BASE/documents"
[ -f agent-loop-design-v1.0.md ] && mv -v agent-loop-design-v1.0.md agent-loop-design-v1.0-20260711.md || echo "  (无旧版 design doc，跳过)"

echo ""
echo "=== 完成! ==="
echo "请检查 git status 确认变更:"
git -C "$BASE" status --short | head -30
echo ""
echo "变更摘要:"
echo "  $(find "$BASE" -name 'requirements.md' -not -path '*/archive/*' | wc -l | tr -d ' ') 个 requirements.md"
echo "  $(find "$BASE" -name 'audit-log.md' -not -path '*/archive/*' | wc -l | tr -d ' ') 个 audit-log.md"
echo "  $(find "$BASE" -name 'features.md' -not -path '*/archive/*' | wc -l | tr -d ' ') 个 features.md"
echo "  $(find "$BASE" -name 'task-manifest.yaml' -not -path '*/archive/*' | wc -l | tr -d ' ') 个 task-manifest.yaml"
echo "  $(find "$BASE" -name 'active-task' -maxdepth 3 | wc -l | tr -d ' ') 个 active-task symlink"
