#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X (Twitter) 热点采集器 — llm-radar 独立采集脚本
================================================
设计: documents/solutions/x-hotspot-design-v1.1-20260825.md
  §3 采集器 (CLI/登录态/抓取/失败处理/反爬) / §4 数据 schema / §6 入库

CLI 签名 (§3.2):
  python3 scripts/twitter-collector.py            默认 = collect
  python3 scripts/twitter-collector.py --collect  显式采集 (等价默认)
  python3 scripts/twitter-collector.py --login    有头模式打开登录页, 人工登录一次
  python3 scripts/twitter-collector.py --dry-run  只解析配置+探测登录态, 不抓取不写盘

退出码 (§3.5):
  0 = 成功 (含部分成功: 写盘 + last_error)
  1 = 抓取失败 (全部失败不写盘, 保留上次) / 配置错误 / 未知参数
  2 = 登录态失效 (需人工重新登录)

环境变量:
  TWITTER_PROFILE_DIR  覆盖 Chrome profile 路径 (默认 cache/twitter-profile/)

依赖: PyYAML (twitter-targets.yaml 解析), selenium + Chrome (抓取)
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# ===== Constants =====
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / 'twitter-targets.yaml'
DATA_PATH = PROJECT_ROOT / 'data' / 'twitter.json'
DEFAULT_PROFILE_DIR = PROJECT_ROOT / 'cache' / 'twitter-profile'

WINDOW_HOURS = 36          # 36h 窗口 (§3.4 D4)
SCROLLS = 3                # 滚动次数 (保守, 防反爬 §3.6)
SCROLL_DELAY = 2.0         # 每次滚动间隔 (秒)
WAIT_TIMEOUT = 30          # 等待主时间线超时 (秒)
TOLERANCE_MINUTES = 5      # O-2: 36h 窗口过滤容差 (now+5min, 时钟偏差)
LOGIN_WAIT_SECONDS = 600   # --login 轮询上限 (10 分钟)

COMMIT_MSG = 'auto-push@llm-radar: update twitter ({} changes)'
LOGIN_HINT = '需要人工重新登录: python3 scripts/twitter-collector.py --login'

USAGE = """用法:
  python3 scripts/twitter-collector.py            默认 = collect (抓取 36h 窗口推文)
  python3 scripts/twitter-collector.py --collect  显式采集 (等价默认)
  python3 scripts/twitter-collector.py --login    有头模式打开登录页, 人工登录一次
  python3 scripts/twitter-collector.py --dry-run  只解析配置+探测登录态, 不抓取不写盘

退出码: 0=成功(含部分成功) / 1=抓取失败或配置错误 / 2=登录态失效"""


# ===== 配置解析 (§3.1) =====

class ConfigError(Exception):
    """twitter-targets.yaml 配置错误 (硬错误, 不静默跳过, exit 1)。"""


def parse_config(text):
    """解析 twitter-targets.yaml 文本 → 规范化 targets 列表 (纯函数, 可单测)。

    - name/handle/url 必填 (缺失/非字符串 → ConfigError)
    - enabled 默认 true, max_tweets 默认 20 (<=0 视为默认)
    - 空文件/空配置 → []
    """
    if yaml is None:
        raise ConfigError('PyYAML 未安装: pip3 install pyyaml')
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f'YAML 解析失败: {e}')
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ConfigError('配置根必须是对象 (含 targets 列表)')
    raw = data.get('targets', [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError('targets 必须是列表')
    targets = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ConfigError(f'targets[{i}] 必须是对象')
        name, handle, url = item.get('name'), item.get('handle'), item.get('url')
        missing = [k for k, v in (('name', name), ('handle', handle), ('url', url))
                   if not isinstance(v, str) or not v.strip()]
        if missing:
            raise ConfigError(f'targets[{i}] 缺少必填字段: {", ".join(missing)}')
        try:
            max_tweets = int(item.get('max_tweets') or 20)
        except (TypeError, ValueError):
            raise ConfigError(f'targets[{i}] max_tweets 必须是整数')
        if max_tweets <= 0:
            max_tweets = 20
        targets.append({
            'name': name.strip(),
            'handle': handle.strip(),
            'url': url.strip(),
            'enabled': bool(item.get('enabled', True)),
            'max_tweets': max_tweets,
        })
    return targets


def load_config(path=None):
    """读配置文件 → parse_config。读取失败 → ConfigError (exit 1)。

    path=None 时读模块全局 CONFIG_PATH (运行时取值, 便于测试 monkeypatch)。
    """
    p = Path(path) if path is not None else Path(CONFIG_PATH)
    try:
        text = p.read_text(encoding='utf-8')
    except OSError as e:
        raise ConfigError(f'读取配置失败: {p} ({e})')
    return parse_config(text)


# ===== 时间处理 (O-1: 统一 UTC Z 存储) =====

def _to_utc_dt(value):
    """ISO 时间值 (含 Z / 偏移) → 带时区 datetime (UTC); 解析失败 → None"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def utc_now_str():
    """当前 UTC 时间, schema Z 格式: 2026-08-25T01:00:00Z"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_posted_at(value):
    """time[datetime] ISO 值 → UTC Z 字符串; 解析失败 → None"""
    dt = _to_utc_dt(value)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ') if dt else None


# ===== 36h 窗口过滤 (§3.4 D4, O-2 容差) =====

def within_window(posted_at, now=None, window_hours=WINDOW_HOURS,
                  tolerance_minutes=TOLERANCE_MINUTES):
    """posted_at 是否在 [now - window_hours, now + tolerance] 窗口内。

    O-2: 允许未来 5 分钟 (时钟偏差); 更远的未来视为异常丢弃。
    边界: 恰好在窗口起点 (now - window_hours) 保留。
    """
    dt = _to_utc_dt(posted_at)
    if dt is None:
        return False
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    lower = now - timedelta(hours=window_hours)
    upper = now + timedelta(minutes=tolerance_minutes)
    return lower <= dt <= upper


def filter_window(tweets, now=None, window_hours=WINDOW_HOURS):
    """36h 窗口过滤: 保留窗口内推文 (含容差)。"""
    return [t for t in tweets
            if within_window(t.get('posted_at'), now=now, window_hours=window_hours)]


# ===== 去重 / 截断 (O-3) =====

def dedup_tweets(tweets):
    """单次抓取内 tweet id 去重 (O-3, 滚动防重复); 无 id 推文保留。"""
    seen = set()
    out = []
    for t in tweets:
        tid = t.get('id')
        if tid:
            if tid in seen:
                continue
            seen.add(tid)
        out.append(t)
    return out


def truncate_tweets(tweets, max_tweets=20):
    """max_tweets 截断: 时间倒序取前 N (posted_at 缺失排最后)。"""
    n = max(1, int(max_tweets or 20))

    def key(t):
        dt = _to_utc_dt(t.get('posted_at'))
        return dt.timestamp() if dt else -1.0

    return sorted(tweets, key=key, reverse=True)[:n]


# ===== DOM 解析 (纯函数, 供单测与实抓共用 §3.4) =====

RE_STATUS_ID = re.compile(r'/status/(\d+)')
RE_VIEWS = re.compile(r'([\d,]+)\s*(?:views|次查看)', re.I)
RE_REPLIES = re.compile(r'([\d,]+)\s*(?:repl\w+|回复)', re.I)
RE_RETWEETS = re.compile(r'([\d,]+)\s*(?:repost\w*|retweet\w*|转推|转帖)', re.I)
RE_LIKES = re.compile(r'([\d,]+)\s*(?:likes?|喜欢|赞)', re.I)


def _num_from_label(label, pattern):
    """从 aria-label 提取数字; 无匹配/非数字 → None"""
    if not label:
        return None
    m = pattern.search(label)
    if not m:
        return None
    digits = m.group(1).replace(',', '')
    if not digits.isdigit():
        return None
    return int(digits)


def parse_tweet_html(html, handle=''):
    """纯函数: 从 tweet article 的 outerHTML 提取字段 (§3.4)。

    字段缺失置 null (不省略键); 多级 fallback; 任何解析失败不抛异常。
    """
    tweet = {'id': None, 'text': None, 'posted_at': None, 'url': None,
             'views': None, 'replies': None, 'retweets': None, 'likes': None,
             'images': None}
    if not html:
        return tweet
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return tweet
    soup = BeautifulSoup(html, 'html.parser')

    # id + url: a[href*="/status/"] (规范化为 https://x.com/{handle}/status/{id})
    status_id = None
    for a in soup.select('a[href*="/status/"]'):
        m = RE_STATUS_ID.search(a.get('href') or '')
        if m:
            status_id = m.group(1)
            break
    if status_id:
        tweet['id'] = status_id
        h = (handle or '').strip().lstrip('@')
        if h:
            tweet['url'] = f'https://x.com/{h}/status/{status_id}'

    # text: [data-testid="tweetText"]; 无则整卡文本
    text_el = soup.select_one('[data-testid="tweetText"]')
    if text_el is not None:
        tweet['text'] = text_el.get_text(' ', strip=True)
    else:
        card_text = soup.get_text(' ', strip=True)
        tweet['text'] = card_text[:500] if card_text else None

    # posted_at: time[datetime]
    t = soup.select_one('time[datetime]')
    if t is not None:
        tweet['posted_at'] = parse_posted_at(t.get('datetime'))

    # views: 任意 aria-label 匹配 "N views" / "N 次查看" (英文优先, 中文兜底)
    for el in soup.select('[aria-label]'):
        v = _num_from_label(el.get('aria-label'), RE_VIEWS)
        if v is not None:
            tweet['views'] = v
            break

    # replies / retweets / likes: 底部按钮 aria-label (逐项正则, 中文兜底)
    for sel, key, pat in (('[data-testid="reply"]', 'replies', RE_REPLIES),
                          ('[data-testid="retweet"]', 'retweets', RE_RETWEETS),
                          ('[data-testid="like"]', 'likes', RE_LIKES)):
        el = soup.select_one(sel)
        if el is not None:
            tweet[key] = _num_from_label(el.get('aria-label'), pat)

    # images: img[src*="pbs.twimg.com/media/"]
    imgs = [img.get('src') for img in soup.select('img[src*="pbs.twimg.com/media/"]')
            if img.get('src')]
    tweet['images'] = imgs or None

    return tweet


# ===== 结果判定 (§3.5 RIG-1 四场景) =====

def build_last_error(failed_results):
    """部分成功: last_error = 'name: reason; ...' 或 None (无失败时清空)。"""
    parts = []
    for r in failed_results:
        tgt = r.get('target') or {}
        name = tgt.get('name') or tgt.get('handle') or '?'
        parts.append(f'{name}: {r.get("error") or "未知错误"}')
    return '; '.join(parts) if parts else None


def evaluate_results(results, login_wall=False):
    """纯函数: 各 target 结果 → (write, last_error, exit_code) (§3.5)。

    results: [{'target': {...}, 'tweets': [...], 'error': str|None}]
    全部成功(≥1 target 有数据) → 写盘 + last_error 清空 + 0
    部分成功               → 写盘(含成功 target) + last_error + 0
    全部失败 / 全部无数据   → 不写盘(保留上次) + 1
    登录态失效             → 不写盘 + 2
    """
    if login_wall:
        return (False, None, 2)
    ok = [r for r in results if r.get('tweets')]
    failed = [r for r in results if r.get('error')]
    if ok:
        return (True, build_last_error(failed), 0)
    return (False, None, 1)


# ===== Schema / 写盘 (§4) =====

def build_document(targets, window_hours=WINDOW_HOURS, last_error=None,
                   generated_at=None):
    """构造 twitter.json 文档: 缺失键用 null, 不省略 (前端渲染稳定)。"""
    return {
        'generated_at': generated_at or utc_now_str(),
        'window_hours': window_hours,
        'targets': targets,
        'last_error': last_error,
    }


def target_doc(target, tweets):
    """成功 target → schema 中的 target 对象"""
    return {'name': target['name'], 'handle': target['handle'],
            'url': target['url'], 'tweets': tweets}


def write_document(doc, path=DATA_PATH):
    """原子写盘 twitter.json (tmp + os.replace)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n',
                   encoding='utf-8')
    os.replace(tmp, path)


# ===== 入库 (§6 REA-1, X-REV-2) =====

def _git_run(*args, timeout=60):
    """git 子进程封装 (list-form, 禁 shell=True)。返回 CompletedProcess 不抛异常。"""
    try:
        return subprocess.run(['git', *args], cwd=str(PROJECT_ROOT),
                              capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        return subprocess.CompletedProcess(['git', *args], 125, '', str(e))


def commit_and_push(tweet_count):
    """采集成功后自带 commit + push (REA-1)。

    X-REV-2: git add 范围限定 data/twitter.json (勿 git add -A 顺带);
    push 失败仅记 stderr/cron 日志 (last_error 仅在写盘时更新, 不自相矛盾),
    不重试轰炸, 下一轮自动再试。
    """
    msg = COMMIT_MSG.format(tweet_count)
    r = _git_run('add', str(DATA_PATH))
    if r.returncode != 0:
        print(f'[twitter-collector] ❌ git add 失败: {(r.stderr or "").strip()[:200]}',
              file=sys.stderr)
        return False
    r = _git_run('commit', '-m', msg)
    if r.returncode != 0:
        err = (r.stderr or '').strip()
        if 'nothing to commit' in err:
            print('[twitter-collector] ℹ️  twitter.json 无变更, 跳过 push')
        else:
            print(f'[twitter-collector] ❌ git commit 失败: {err[:200]}',
                  file=sys.stderr)
        return False
    print(f'[twitter-collector] ✅ commit: {msg}')
    r = _git_run('push')
    if r.returncode != 0:
        print(f'[twitter-collector] ⚠️  push 失败 (下轮自动重试): '
              f'{(r.stderr or "").strip()[:200]}', file=sys.stderr)
        return False
    print('[twitter-collector] ✅ push 成功')
    return True


# ===== Profile 互斥锁 (O-5: --login 与 cron 并发保护) =====

class ProfileLock:
    """cache/twitter-profile/.collector.lock pidfile 互斥 (防双 Chrome 实例)。"""

    def __init__(self, profile_dir):
        self.path = Path(profile_dir) / '.collector.lock'

    def acquire(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                try:
                    pid = int(self.path.read_text().strip())
                    os.kill(pid, 0)  # 存活检查; 进程不存在 → ProcessLookupError
                    print(f'[twitter-collector] ❌ 另一个采集/登录进程正在运行 '
                          f'(pid={pid}), 退出', file=sys.stderr)
                    return False
                except (ValueError, ProcessLookupError):
                    pass  # 残留锁, 覆盖
            self.path.write_text(str(os.getpid()))
            return True
        except OSError:
            return True  # 锁失败 best-effort, 不阻断

    def release(self):
        try:
            if self.path.exists() and self.path.read_text().strip() == str(os.getpid()):
                self.path.unlink()
        except OSError:
            pass


# ===== Selenium 层 (§3.3/3.4/3.6) =====

class LoginWallError(Exception):
    """登录态失效 (exit 2)"""


class ChallengeError(Exception):
    """验证挑战 (cf-challenge / Something went wrong, 跳过本轮)"""


class FetchError(Exception):
    """抓取失败 (单 target)"""


def start_driver(profile_dir, headed=False):
    """启动 Chrome (持久化 profile + headless=new / 有头)。selenium 惰性导入。"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_argument(f'--user-data-dir={Path(profile_dir)}')
    if not headed:
        opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--window-size=1280,900')
    opts.add_argument('--blink-settings=imagesEnabled=false')
    opts.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    return webdriver.Chrome(options=opts)


def detect_login_wall(driver):
    """登录墙检测 (§3.3): URL 重定向 /login 或页面出现登录入口。

    异常 → True (fail-safe, 宁可不抓也不反复撞墙)。
    """
    try:
        url = driver.current_url or ''
        if re.search(r'/(?:login|i/flow/login)', url):
            return True
        if driver.find_elements('css selector',
                                'a[href="/login"], [data-testid="loginButton"]'):
            return True
    except Exception:
        return True
    return False


def detect_challenge(driver):
    """验证挑战检测 (§3.6): cf-challenge / Something went wrong → 跳过本轮。"""
    try:
        html = driver.page_source or ''
        return any(m in html for m in ('cf-challenge', 'Something went wrong',
                                       'Request failed'))
    except Exception:
        return False


def fetch_target(driver, target, window_hours=WINDOW_HOURS, scrolls=SCROLLS,
                 scroll_delay=SCROLL_DELAY, wait_timeout=WAIT_TIMEOUT, now=None):
    """抓取单个 target 36h 窗口内推文 (§3.4)。

    返回 tweets (窗口过滤 + 去重 + max_tweets 截断)。
    登录墙 → LoginWallError; 验证挑战 → ChallengeError; 超时/无元素 → FetchError。
    """
    driver.get(target['url'])
    articles = []
    deadline = time.monotonic() + wait_timeout
    while time.monotonic() < deadline:
        if detect_login_wall(driver):
            raise LoginWallError('登录墙')
        if detect_challenge(driver):
            raise ChallengeError('验证挑战 (cf-challenge / Something went wrong)')
        articles = driver.find_elements('css selector', 'article[data-testid="tweet"]')
        if articles:
            break
        time.sleep(2)
    if not articles:
        raise FetchError('未找到 tweet 元素 (可能页面结构变化或登录态异常)')

    # 滚动加载 (保守 3 次 × 2s, 防反爬 §3.6)
    for _ in range(scrolls):
        try:
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        except Exception:
            pass
        time.sleep(scroll_delay)
    articles = driver.find_elements('css selector', 'article[data-testid="tweet"]')
    if detect_challenge(driver):
        raise ChallengeError('验证挑战 (cf-challenge / Something went wrong)')

    tweets = []
    for el in articles:
        try:
            html = el.get_attribute('outerHTML') or ''
        except Exception:
            continue
        tweets.append(parse_tweet_html(html, target['handle']))
    tweets = dedup_tweets(tweets)
    tweets = filter_window(tweets, now=now, window_hours=window_hours)
    tweets = truncate_tweets(tweets, target.get('max_tweets', 20))
    return tweets


# ===== 命令实现 =====

def cmd_login(profile_dir):
    """--login: 有头模式打开登录页, 人工登录一次 (O-11)。

    完成判定: 轮询 auth_token cookie (每 2s, 上限 10 分钟);
    用户提前关窗 → 视为完成, 用 headless 校验登录态。
    """
    lock = ProfileLock(profile_dir)
    if not lock.acquire():
        return 1
    driver = None
    try:
        driver = start_driver(profile_dir, headed=True)
        driver.get('https://x.com/login')
        print('[twitter-collector] 请在浏览器中登录 X; 完成后本程序自动检测并退出')
        deadline = time.monotonic() + LOGIN_WAIT_SECONDS
        confirmed = False
        while time.monotonic() < deadline:
            time.sleep(2)
            try:
                cookies = driver.get_cookies()
            except Exception:
                break  # 用户关闭窗口 → 交由下方 headless 校验
            if any(c.get('name') == 'auth_token' for c in cookies):
                confirmed = True
                print('[twitter-collector] ✅ 检测到登录 cookie, 登录完成')
                break
        if not confirmed:
            try:
                driver.quit()
            except Exception:
                pass
            driver = None
            print('[twitter-collector] 未在窗口内确认, 校验登录态...')
            driver = start_driver(profile_dir, headed=False)
            driver.get('https://x.com/home')
            time.sleep(4)
            if detect_login_wall(driver):
                print(f'[twitter-collector] ❌ 未检测到登录态: {LOGIN_HINT}',
                      file=sys.stderr)
                return 1
            print('[twitter-collector] ✅ 登录态校验通过')
        return 0
    except Exception as e:
        print(f'[twitter-collector] ❌ --login 失败: {e}', file=sys.stderr)
        return 1
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        lock.release()


def cmd_dry_run(targets, profile_dir):
    """--dry-run: 只解析配置 + 探测登录态, 不抓取不写盘。exit 0/1/2。"""
    print(f'[twitter-collector] 配置解析成功: {len(targets)} 个启用目标')
    for t in targets:
        print(f'  - {t["name"]} (@{t["handle"]}) {t["url"]}  max_tweets={t["max_tweets"]}')
    lock = ProfileLock(profile_dir)
    if not lock.acquire():
        return 1
    try:
        driver = start_driver(profile_dir, headed=False)
        try:
            probe_url = targets[0]['url']
            print(f'[twitter-collector] 探测登录态: {probe_url}')
            driver.get(probe_url)
            time.sleep(4)
            if detect_login_wall(driver):
                print(f'[twitter-collector] ❌ 登录态失效: {LOGIN_HINT}',
                      file=sys.stderr)
                return 2
            if detect_challenge(driver):
                print('[twitter-collector] ⚠️  登录态有效, 但页面出现验证挑战 '
                      '(采集可能受限)')
            else:
                print('[twitter-collector] ✅ 登录态有效')
            return 0
        finally:
            try:
                driver.quit()
            except Exception:
                pass
    except Exception as e:
        print(f'[twitter-collector] ❌ 登录态探测失败: {e}', file=sys.stderr)
        return 1
    finally:
        lock.release()


def cmd_collect(targets, profile_dir):
    """--collect (默认): 抓取 → 判定 → 写盘 → commit+push。"""
    lock = ProfileLock(profile_dir)
    if not lock.acquire():
        return 1
    driver = None
    try:
        driver = start_driver(profile_dir, headed=False)
        results = []
        login_wall = False
        for t in targets:
            print(f'[twitter-collector] 抓取: {t["name"]} (@{t["handle"]})')
            try:
                tweets = fetch_target(driver, t)
                print(f'[twitter-collector]   → {len(tweets)} 条 36h 窗口内推文')
                results.append({'target': t, 'tweets': tweets, 'error': None})
            except LoginWallError:
                login_wall = True
                print('[twitter-collector] ❌ 登录态失效', file=sys.stderr)
                break
            except ChallengeError as e:
                print(f'[twitter-collector] ⚠️  {e}, 跳过本轮', file=sys.stderr)
                results.append({'target': t, 'tweets': [], 'error': str(e)})
            except Exception as e:
                print(f'[twitter-collector] ⚠️  抓取失败: {e}', file=sys.stderr)
                results.append({'target': t, 'tweets': [], 'error': str(e)})

        write, last_error, code = evaluate_results(results, login_wall=login_wall)
        if code == 2:
            print(f'[twitter-collector] ❌ {LOGIN_HINT}', file=sys.stderr)
            return 2
        if not write:
            fails = [f'{r["target"].get("name")}: {r.get("error") or "无 36h 窗口内推文"}'
                     for r in results if r.get('error')]
            reason = '; '.join(fails) if fails else '全部 target 均无 36h 窗口内推文'
            print(f'[twitter-collector] ❌ 本轮无可用数据, 不写盘 '
                  f'(保留上次 twitter.json): {reason}', file=sys.stderr)
            return 1

        ok_results = [r for r in results if r.get('tweets')]
        docs = [target_doc(r['target'], r['tweets']) for r in ok_results]
        total = sum(len(r['tweets']) for r in ok_results)
        doc = build_document(docs, last_error=last_error)
        write_document(doc)
        print(f'[twitter-collector] ✅ 写盘 data/twitter.json ({total} 条推文)')
        if last_error:
            print(f'[twitter-collector] ⚠️  last_error: {last_error}')
        commit_and_push(total)
        return 0
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        lock.release()


# ===== CLI (RIG-2) =====

def parse_args(argv):
    """CLI 解析: 默认 collect; 未知参数/多余参数 → 打印用法并 SystemExit(1)。"""
    if not argv:
        return {'mode': 'collect'}
    arg = argv[0]
    if arg in ('-h', '--help'):
        print(USAGE)
        raise SystemExit(0)
    if arg == '--collect':
        mode = 'collect'
    elif arg == '--login':
        mode = 'login'
    elif arg == '--dry-run':
        mode = 'dry-run'
    else:
        print(USAGE, file=sys.stderr)
        raise SystemExit(1)
    if len(argv) > 1:
        print(USAGE, file=sys.stderr)
        raise SystemExit(1)
    return {'mode': mode}


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return e.code if e.code is not None else 0

    profile_dir = Path(os.environ.get('TWITTER_PROFILE_DIR') or DEFAULT_PROFILE_DIR)
    mode = args['mode']

    if mode == 'login':
        return cmd_login(profile_dir)

    try:
        targets = load_config()
    except ConfigError as e:
        print(f'[twitter-collector] ❌ 配置错误: {e} (exit 1)', file=sys.stderr)
        return 1

    enabled = [t for t in targets if t['enabled']]
    if mode == 'dry-run':
        if not enabled:
            print('[twitter-collector] ❌ 无启用目标 (twitter-targets.yaml)',
                  file=sys.stderr)
            return 1
        return cmd_dry_run(enabled, profile_dir)

    if not enabled:
        # O-12: 空 targets/全 disabled → 写空文件 exit 0 + 提示
        write_document(build_document([]))
        print('[twitter-collector] ⚠️  twitter-targets.yaml 无启用目标, '
              '已写空 data/twitter.json')
        commit_and_push(0)
        return 0
    return cmd_collect(enabled, profile_dir)


if __name__ == '__main__':
    sys.exit(main())
