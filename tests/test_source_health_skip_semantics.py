"""源健康语义: 跳过 ≠ 失败 + 降级冷却窗口 + 海外源按需拉起/释放代理。

背景（2026-10-09 实测）: 主采集把「被跳过的源」也记成 failure
  - 降级源: `_observe` 对 `{'success': False}` 累加 consecutive_fails ⇒ qbitai 累计 18 次仍被永久跳过
  - 海外源: FlClash 未运行时跳过 github-trending/huggingface, 同样按失败累加（fails 已 1/2/3…）
⇒ 任何一次环境类故障（代理没开 / chromedriver 版本不匹配 / 网络抖动）都会把源推进「永久降级」,
  只能人工 reset-health 复活（chromedriver 事故拖 9 天的同一根因）。

本文件锁住三条口径:
  1) 跳过: 不改 consecutive_fails / 不写 last_time（冷却计时以真实尝试为准）, 只留 last_skipped
  2) 真失败: 仍然累计（不得被上面这条改坏）
  3) 降级源超冷却窗口 → 放行重试一次; 海外源未就绪 → 本轮按需拉起代理, 采集后只释放自启的那个
"""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'llm-radar-collector.py'


def load_module():
    spec = importlib.util.spec_from_file_location('collector_src_health', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return load_module()


@pytest.fixture
def coll(mod, tmp_path, monkeypatch):
    """干净 collector: data_dir / fetch_cache 全在 tmp, 打印静音, 不碰网络与 git。"""
    c = mod.LLMRadarCollector()
    c.api_key = 'test-key'
    c._skip_push = True
    c.data_dir = tmp_path
    c.fetch_cache_path = tmp_path / 'fetch_cache.json'
    for name in ('_print_ok', '_print_err', '_print_info', '_print_warn'):
        monkeypatch.setattr(c, name, lambda *a, **k: None)
    monkeypatch.setattr(mod.time, 'sleep', lambda *a, **k: None)   # 免去每源 2s 节流
    return c


def write_health(tmp_path, health):
    (tmp_path / 'metrics.json').write_text(
        json.dumps({'source_health': health}, ensure_ascii=False), encoding='utf-8')


def read_health(tmp_path):
    return json.loads((tmp_path / 'metrics.json').read_text(encoding='utf-8'))


def iso(hours_ago=0.0):
    return (datetime.now() - timedelta(hours=hours_ago)).isoformat()


# ===== 1) 跳过 ≠ 失败 =====

def test_observe_skip_not_counted_and_rate_excludes_it(coll, tmp_path):
    """跳过源: consecutive_fails/last_time 不动, 记 last_skipped; 成功率分母只算真跑过的源。"""
    last_attempt = iso(30)
    write_health(tmp_path, {'qbitai': {'consecutive_fails': 18, 'last_result': 'fail',
                                       'last_time': last_attempt}})
    coll._observe(True, fetch_results={
        'qbitai': {'success': None, 'skipped': 'degraded'},
        'infoq': {'success': True},
        '_source_keys': ['qbitai', 'infoq'],
    })
    health = read_health(tmp_path)['source_health']
    assert health['qbitai']['consecutive_fails'] == 18, '跳过不得再加失败计数'
    assert health['qbitai']['last_result'] == 'fail', '旧的真实结果保留'
    assert health['qbitai']['last_skipped'] == 'degraded'
    assert health['qbitai']['last_time'] == last_attempt, \
        'last_time 只由真实尝试更新（否则降级冷却会被跳过顶开）'
    assert health['infoq']['consecutive_fails'] == 0 and health['infoq']['last_result'] == 'ok'
    assert read_health(tmp_path)['source_success_rate'] == 1.0, '跳过不计入分母'


def test_observe_real_failure_still_counts(coll, tmp_path):
    """真失败仍累计（防止上面的改动把失败识别也弄哑）。"""
    write_health(tmp_path, {'qbitai': {'consecutive_fails': 18, 'last_result': 'ok', 'last_time': iso(1)}})
    coll._observe(True, fetch_results={'qbitai': {'success': False}})
    health = read_health(tmp_path)['source_health']
    assert health['qbitai']['consecutive_fails'] == 19
    assert health['qbitai']['last_result'] == 'fail'
    assert read_health(tmp_path)['source_success_rate'] == 0.0


def test_observe_clears_skip_trace_after_real_attempt(coll, tmp_path):
    """本轮真跑过 → 清掉上一轮的 last_skipped 痕迹。"""
    write_health(tmp_path, {'github-trending': {'consecutive_fails': 1, 'last_result': 'fail',
                                                'last_time': iso(5),
                                                'last_skipped': 'no_flclash',
                                                'last_skipped_time': iso(5)}})
    coll._observe(True, fetch_results={'github-trending': {'success': True}})
    health = read_health(tmp_path)['source_health']['github-trending']
    assert 'last_skipped' not in health and 'last_skipped_time' not in health
    assert health['consecutive_fails'] == 0 and health['last_result'] == 'ok'


# ===== 2) 降级冷却窗口 =====

def test_degraded_in_cooldown_window(mod, coll):
    assert coll._degraded_in_cooldown(iso(0.5)) is True, '刚失败过 → 冷却中'
    assert coll._degraded_in_cooldown(iso(7)) is False, '超过窗口 → 放行重试'
    assert coll._degraded_in_cooldown(None) is False
    assert coll._degraded_in_cooldown('不是时间') is False


def test_degraded_window_disabled_means_always_skip(mod, coll, monkeypatch):
    monkeypatch.setattr(mod, 'DEGRADED_RETRY_HOURS', 0)
    assert coll._degraded_in_cooldown(iso(999)) is True


def test_fetch_all_skips_degraded_and_records_reason(mod, coll, tmp_path, monkeypatch):
    """全量扫描: 降级且在冷却窗口内 → 不抓取, 记 'degraded'（run() 据此标 success=None）。"""
    write_health(tmp_path, {'qbitai': {'consecutive_fails': 18, 'last_result': 'fail', 'last_time': iso(1)}})
    monkeypatch.setattr(mod, 'SOURCES', {'qbitai': {}, 'infoq': {}})
    seen = []
    monkeypatch.setattr(coll, 'fetch_source', lambda k: seen.append(k) or {'source': k, 'content': 'x'})
    coll.fetch_all()
    assert seen == ['infoq'], '降级源不得重抓'
    assert coll.fetch_skipped == {'qbitai': 'degraded'}


def test_explicit_source_bypasses_degraded_skip(coll, tmp_path, monkeypatch):
    """显式点名单源（诊断/补采）→ 放行重试，不被降级态挡住。"""
    write_health(tmp_path, {'qbitai': {'consecutive_fails': 18, 'last_result': 'fail', 'last_time': iso(1)}})
    seen = []
    monkeypatch.setattr(coll, 'fetch_source', lambda k: seen.append(k) or {'source': k, 'content': 'x'})
    coll.fetch_all(['qbitai'])
    assert seen == ['qbitai'], '点名抓取必须执行'
    assert coll.fetch_skipped == {}


def test_fetch_all_retries_degraded_after_window(coll, tmp_path, monkeypatch):
    """降级但已超冷却窗口 → 放行重试（环境类故障可自愈的关键）。"""
    write_health(tmp_path, {'qbitai': {'consecutive_fails': 18, 'last_result': 'fail', 'last_time': iso(7)}})
    seen = []
    monkeypatch.setattr(coll, 'fetch_source', lambda k: seen.append(k) or {'source': k, 'content': 'x'})
    coll.fetch_all(['qbitai'])
    assert seen == ['qbitai'], '超窗必须给一次重试机会'
    assert coll.fetch_skipped == {}


# ===== 3) 海外源按需拉起 / 释放代理（唯一真源） =====

def test_fetch_all_pulls_flclash_and_releases_when_owned(mod, coll, tmp_path, monkeypatch):
    """FlClash 未运行 → 本轮拉起（记 owned）→ 采集后在 run()/CLI 处释放。"""
    write_health(tmp_path, {})
    monkeypatch.setattr(coll, 'fetch_source', lambda k: {'source': k, 'content': 'x'})
    monkeypatch.setattr(mod, '_is_flclash_running', lambda: False)
    monkeypatch.setattr(mod, '_ensure_flclash_ready', lambda timeout=None: True)
    released = []
    monkeypatch.setattr(mod, '_release_flclash', lambda: released.append(1) or True)

    coll.fetch_all(['github-trending', 'infoq'])
    assert coll._flclash_owned is True
    assert coll.fetch_skipped == {}, '代理拉起来了就不该跳过海外源'
    assert coll.release_flclash_if_owned() is True
    assert released == [1], '自启的代理必须释放'
    assert coll.release_flclash_if_owned() is False, '释放幂等: 第二次不再动作'
    assert released == [1]


def test_fetch_all_skips_overseas_when_flclash_not_ready(mod, coll, tmp_path, monkeypatch):
    """代理起不来 → 跳过海外源并记 'no_flclash'（不计失败, 也不再是「FlClash 未运行」硬跳过）。"""
    write_health(tmp_path, {})
    seen = []
    monkeypatch.setattr(coll, 'fetch_source', lambda k: seen.append(k) or {'source': k, 'content': 'x'})
    monkeypatch.setattr(mod, '_is_flclash_running', lambda: False)
    monkeypatch.setattr(mod, '_ensure_flclash_ready', lambda timeout=None: False)

    coll.fetch_all(['github-trending', 'huggingface', 'infoq'])
    assert seen == ['infoq']
    assert coll.fetch_skipped == {'github-trending': 'no_flclash', 'huggingface': 'no_flclash'}
    assert coll._flclash_owned is False


def test_already_running_flclash_is_never_owned(mod, coll, tmp_path, monkeypatch):
    """原本就在运行的 FlClash: 不起、不关（不动别人的实例）。"""
    write_health(tmp_path, {})
    monkeypatch.setattr(coll, 'fetch_source', lambda k: {'source': k, 'content': 'x'})
    monkeypatch.setattr(mod, '_is_flclash_running', lambda: True)
    ensured, released = [], []
    monkeypatch.setattr(mod, '_ensure_flclash_ready', lambda timeout=None: ensured.append(1) or True)
    monkeypatch.setattr(mod, '_release_flclash', lambda: released.append(1) or True)

    coll.fetch_all(['github-trending'])
    assert ensured == [] and coll._flclash_owned is False
    assert coll.release_flclash_if_owned() is False
    assert released == []


# ===== 4) chromedriver 解析: 与驱动同名的 CLI wrapper 必须被判否 =====
# （2026-10-09 根因: ~/.local/bin/chromedriver = script-miner 的 chromedriver-manager wrapper,
#   旧实现 `shutil.which("chromedriver")` 命中它 ⇒ Selenium "Can not connect to the Service"
#   ⇒ qbitai 每轮失败、累计 18 次降级。修复前本组用例必红。）

def make_fake_binary(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/usr/bin/env bash\necho "{text}"\n', encoding='utf-8')
    path.chmod(0o755)
    return path


def test_driver_probe_rejects_cli_wrapper_shadowing_driver_name(mod, tmp_path):
    wrapper = make_fake_binary(tmp_path / 'chromedriver', '❌ 未知命令: --version\n📖 chromedriver v1.2(2026-09-25)')
    assert mod.LLMRadarCollector._driver_major_version(str(wrapper)) is None, 'CLI wrapper 不是驱动'
    real = make_fake_binary(tmp_path / 'chromedriver-real', 'ChromeDriver 154.0.8037.92 (refs/branch-heads/8037@{#1589})')
    assert mod.LLMRadarCollector._driver_major_version(str(real)) == 154, '真驱动必须被认出'


def test_resolve_chromedriver_prefers_real_binary_over_path_wrapper(mod, tmp_path, monkeypatch):
    """解析顺序: wdm 真驱动（主版本匹配 Chrome）优先于 PATH 上的同名 wrapper。"""
    wrapper = make_fake_binary(tmp_path / 'bin' / 'chromedriver', '❌ 未知命令')
    real = make_fake_binary(
        tmp_path / '.wdm' / 'drivers' / 'chromedriver' / 'mac-arm64' / '154.0.8037.92'
        / 'chromedriver-mac-arm64' / 'chromedriver',
        'ChromeDriver 154.0.8037.92 (ref)')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(mod.shutil, 'which', lambda name: str(wrapper) if name == 'chromedriver' else None)
    monkeypatch.setattr(mod.LLMRadarCollector, '_chrome_major_version',
                        classmethod(lambda cls: 154))
    assert mod.LLMRadarCollector._resolve_chromedriver() == str(real)


def test_resolve_chromedriver_none_when_only_wrapper_available(mod, tmp_path, monkeypatch):
    """只有 wrapper 时宁可返回 None（交由上层报错）, 也不把 wrapper 当驱动用。"""
    wrapper = make_fake_binary(tmp_path / 'bin' / 'chromedriver', '❌ 未知命令')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(mod.shutil, 'which', lambda name: str(wrapper) if name == 'chromedriver' else None)
    assert mod.LLMRadarCollector._resolve_chromedriver() is None
