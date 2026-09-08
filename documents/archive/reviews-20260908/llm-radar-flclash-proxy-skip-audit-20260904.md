# FlClash 代理跳过海外源审计 — review报告 v1.0

- **日期**: 2026-09-04
- **审查者**: Security Reviewer (review profile)
- **范围**: commit d73188b `feat@llm-radar: skip github/huggingface when FlClash proxy down`
- **项目**: llm-radar.lab
- **级别**: L2 (scripts, git ops, 无 auth)
- **结论**: PASS — 100/100 (A)

## 背景

FlClash 代理未运行时, github-trending / huggingface 两个海外源会超时拖慢采集。本 commit 在采集前检测 FlClash 进程, 未运行时跳过海外源; X 采集器同理, 代理未运行时提前 exit 1, 避免无谓的 Chrome 启动与登录态探测。

## 审计要点逐项验证

### 1. 改动范围 ✅

`git show d73188b --stat`: 2 files changed, 44 insertions(+), 0 deletions(-)

- `llm-radar-collector.py` (+22)
- `scripts/twitter-collector.py` (+22)

无新增文件, 无依赖变更, 无测试改动。工作区干净 (测试后已还原 3 个数据文件, 无残留脏文件)。

### 2. FlClash 检测逻辑 ✅

**文件**: `llm-radar-collector.py:42-54` / `scripts/twitter-collector.py:43-55`

```python
def _is_flclash_running():
    if platform.system() != 'Darwin':
        return True  # 非 macOS 跳过检测
    try:
        result = subprocess.run(['pgrep', '-f', 'FlClash'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False
```

- 非 Darwin → 返回 True (跳过检测), 与 docstring「非 macOS 跳过检测」一致, 不误伤 Linux/CI ✅
- `subprocess.run` 用 list 形式, 无 `shell=True` / 字符串拼接 → 无 shell 注入 ✅
- `timeout=5` + `except Exception → False` (fail-closed: 检测异常时保守跳过海外源) ✅
- 依赖 `import platform` / `import subprocess` 均已就位 (collector L33/L32 已存在; twitter 新增 L34 `platform`, `subprocess` 已在 L34 之前) ✅

### 3. fetch_all 跳过海外源逻辑 ✅

**文件**: `llm-radar-collector.py:678-684`

```python
NEEDS_FLCLASH = {'github-trending', 'huggingface'}
if not _is_flclash_running():
    blocked = [k for k in source_keys if k in NEEDS_FLCLASH]
    ...
```

- 源 key 与 `SOURCES` 字典一致 (L97 `github-trending` / L103 `huggingface`) ✅
- TechCrunch 已移除 (L96 注释), 无遗漏海外源 ✅
- 单源运行 (`run <source>` / `fetch <source>`) 时仅当该源 ∈ NEEDS_FLCLASH 才跳过, 不误伤中文源 ✅
- 与既有 degraded-source 跳过机制 (≥3 consecutive_fails) 并列, 无冲突 ✅

### 4. twitter-collector 提前 exit 1 ✅

**文件**: `scripts/twitter-collector.py:891-895`

- 位置正确: 在 login / dry-run / 空 targets 分支之后、`cmd_collect` 之前 ✅
- `login` / `dry-run` 无需访问 X, 正确绕过检测 ✅
- 空 targets → 写空文件 exit 0, 正确绕过 ✅
- 仅 `collect` / `attach` 需要代理, 提前 exit 1 避免无谓 Chrome 启动 ✅

## 数据验证

- 全量测试: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 222 passed, 2 deselected ✅
- diff 最小性: 2 files changed, 44 insertions(+), 0 deletions(-)
- 实测 FlClash 运行态: `pgrep -f FlClash` → PID 77742/77746 命中 (本机 FlClash 运行中, 检测返回 True, 无跳过) ✅
- 测试后已 `git checkout --` 还原 timestamp.json / overview.json / data/snapshot.json, 工作区干净 ✅

## 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| (无) | — | — | — |

## 观察 (ℹ️ 不计分)

- OBS-1: `_is_flclash_running()` 在两个脚本中重复实现 (符合项目「无 package 布局, 单脚本」设计, 非缺陷)
- OBS-2: 新增 FlClash 跳过路径无独立单元测试 (CI/Linux 平台返回 True 不触发; 启发式检测 + degraded-source 兜底, 低风险)

## 评分

- 基础分: 100
- 扣分: 0
- 最终: 100/100 (A) → PASS

## 结论

改动最小且正确。subprocess 用 list 形式无注入风险, 非 Darwin 跳过检测不误伤 CI/Linux, 跳过逻辑仅命中两个海外源 key, X 采集器提前 exit 1 位置正确。全量回归 222 passed, 工作区干净。可安全 push。
