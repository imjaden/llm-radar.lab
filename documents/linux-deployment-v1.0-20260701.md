# LLM-Radar Linux 服务器部署指南

> 阿里云 Linux (Alibaba Cloud Linux 3) 部署踩坑记录与解决方案。

---

## 1. 环境概览

```text
OS:     Alibaba Cloud Linux 3 (OpenAnolis Edition)
Python: conda env llm-radar (Python 3.11)
Chrome: google-chrome-stable 150.0.7871.46
Selenium: 4.45.0
```

## 2. 部署步骤

```bash
sudo su - 

# 1. 拉取代码
cd /home/admin/codespace/llm-radar.lab
git pull

# 2. 安装 Python 依赖
pip install openai selenium webdriver-manager requests beautifulsoup4 prettytable

# 3. 安装 Chrome（匹配 webdriver-manager 下载的 ChromeDriver 版本）
cat > /etc/yum.repos.d/google-chrome.repo << "REPO"
[google-chrome]
name=google-chrome
baseurl=https://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
REPO
yum install -y google-chrome-stable

# 4. 下载 ChromeDriver（自动匹配 Chrome 版本）
python3 -c "from webdriver_manager.chrome import ChromeDriverManager; print(ChromeDriverManager().install())"

# 5. 验证
bash llm-radar-run.sh selenium-check
```

## 3. 跨平台兼容改动

### 3.1 Chrome binary 路径自动检测

```python
# llm-radar-collector.py
@staticmethod
def _resolve_chrome_binary():
    """查找 Chrome/Chromium 路径（macOS / Linux）"""
    import os, shutil, sys as _sys
    if _sys.platform == "darwin":
        p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return p if os.path.exists(p) else None
    for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
        found = shutil.which(name)
        if found: return found
    return None
```

| 系统 | 检测路径 |
|:---|:---|
| macOS | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux | `which google-chrome` / `which chromium` |

### 3.2 ChromeDriver 路径自动检测

```python
@staticmethod
def _resolve_chromedriver():
    """查找 chromedriver 路径（优先 which，其次 ~/.wdm/ 缓存）"""
    found = shutil.which("chromedriver")
    if found: return found
    # 扫描 ~/.wdm/ 下最新的 chromedriver
    candidates = []
    for root, dirs, files in os.walk(os.path.expanduser("~/.wdm")):
        for f in files:
            if f == "chromedriver":
                candidates.append(os.path.join(root, f))
    if not candidates: return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]
```

### 3.3 版本号解析（修复 split() bug）

旧代码用 `chrome_ver.split()[-1]` 提取版本号，在 Linux 上 `"Chromium 133.0.6943.141 Fedora Project"` 会返回 `"Project"` 而不是版本号。

修复：用正则提取：

```python
import re
chrome_m = re.search(r"(\d+\.\d+\.\d+\.\d+)", chrome_ver)
chrome_num = chrome_m.group(1) if chrome_m else ""
```

### 3.4 浏览器启动测试（修复网络卡死）

旧代码导航到 `https://www.google.com`，在中国服务器上被墙导致 `net::ERR_CONNECTION_TIMED_OUT`。

修复：使用本地 data URL，无需网络：

```python
driver.get("data:text/html,<h1>Selenium OK</h1>")
```

## 4. 已知问题

| 问题 | 原因 | 状态 |
|:---|:---|:---|
| 量子位(qbitai) Selenium 超时 | 页面加载慢，当前 timeout 25s 不够 | ⏳ 待评估是否保留 |
| chrome 版本显示 "Project" | Chromium 版本输出带额外文本 | ✅ 已修复（regex 解析） |
| Google URL 被墙 | 阿里云服务器无法访问 google.com | ✅ 已修复（本地 data URL） |
| ChromeDriver 版本不匹配 | yum 安装的 Chromium 133 vs webdriver_manager 下载的 150 | ✅ 用 google-chrome-stable 统一版本 |

## 5. 运维命令

```bash
# 查看状态
python3 llm-radar-collector.py selenium-check

# 手动采集
bash llm-radar-run.sh run

# 查看日志
tail -f data/collector.log

# 清理残留 chromedriver 进程
pkill -9 -f chromedriver

# 更新代码
git pull
```


*版本: 1.0 | 创建: 2026-07-01*
