#!/usr/bin/env bash
#
# LLM Radar 采集脚本 — 跨平台 launcher
# 自动识别 Mac / Linux，加载对应的 conda 环境与 API key
#
# 用法：
#   ./llm-radar-run.sh                    # 执行采集
#   ./llm-radar-run.sh crontab --status    # 透传参数给 collector
#
# 环境变量（按优先级）：
#   1. 脚本同目录下的 .env 文件
#   2. 系统环境变量 DEEPSEEK_API_KEY
#
# 路径说明（适配 Mac 与本 Linux 服务器）：
#   Mac:    ~/CodeSpace/llm-radar.jaden.tech
#   Linux:  /home/admin/codespace/llm-radar.lab

set -e

# ===== 自动识别项目根目录 =====
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ===== 加载 .env 文件（如有） =====
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ===== 检测操作系统，加载对应环境 =====
case "$(uname -s)" in
    Darwin)
        # macOS — 假设在当前 shell 环境中运行
        # conda 用户需先: conda activate llm-radar
        PYTHON="python3"
        ;;
    Linux)
        # 阿里云 Linux / CentOS — 使用 conda 环境
        if [ -f "/root/miniconda3/bin/activate" ]; then
            source /root/miniconda3/bin/activate llm-radar
            PYTHON="python"
        elif [ -f "/root/miniconda3/envs/llm-radar/bin/python" ]; then
            PYTHON="/root/miniconda3/envs/llm-radar/bin/python"
        else
            echo "❌ 未找到 conda 环境 (llm-radar)，请先: conda create -n llm-radar python=3.11"
            exit 1
        fi
        ;;
    *)
        echo "❌ 未知操作系统: $(uname -s)"
        exit 1
        ;;
esac

# ===== 检查 API key =====
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "❌ DEEPSEEK_API_KEY 未设置"
    echo "   请创建 .env 文件: echo 'DEEPSEEK_API_KEY=***' > .env"
    exit 1
fi

# ===== 执行 =====
if [ $# -eq 0 ]; then
    exec $PYTHON llm-radar-collector.py run
else
    exec $PYTHON llm-radar-collector.py "$@"
fi
