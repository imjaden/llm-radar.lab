#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CL012 — twitter.json 写盘合并语义钉子。

背景（2026-11-09 实测事故）：force 轮 9/10 账号遇 cf-challenge，旧实现只把**成功**的
target 写进文档 ⇒ `data/twitter.json` 从 10 账号/300 条掉到 1 账号/30 条，并被 auto-push
推到线上（当日已 `git revert`）。

判据（每条都能独立变红）:
1. 本轮失败的账号 ⇒ 保留上轮 tweets 且标 `stale: True`，顶层 `stale_targets` 列其 handle；
2. 本轮成功的账号 ⇒ 一律以新数据为准（不保留旧数据，不会出现 stale 标记）；
3. 顺序沿用上轮（防前端顺序抖动），上轮没有的新账号追加在后；
4. 上轮该账号本来就是空数组 ⇒ 不保留、不进 stale_targets（不留空壳）；
5. 无上轮文档（首跑 / 文件损坏）⇒ 原样返回，不抛异常；
6. 静态回归：采集循环里不得再出现「连续 2 账号挑战 ⇒ break」（事故放大器）。
"""
import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'scripts' / 'twitter-collector.py'


def load_module():
    spec = importlib.util.spec_from_file_location('twitter_collector_cl012', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _doc(targets, last_error=None, stale=None):
    doc = {
        'generated_at': '2026-11-09T08:30:54Z',
        'retention': '30/24h',
        'targets': targets,
        'last_error': last_error,
    }
    if stale:
        doc['stale_targets'] = stale
    return doc


def _tgt(handle, n=1, name=None):
    return {
        'name': name or handle.upper(),
        'handle': handle,
        'url': f'https://x.com/{handle}',
        'tweets': [{'id': f'{handle}-{i}', 'text': 'x'} for i in range(n)],
    }


def test_failed_target_keeps_previous_tweets():
    tc = load_module()
    old = _doc([_tgt('a', 3), _tgt('b', 2)])
    new = _doc([_tgt('a', 1)])              # 本轮只抓到 a

    merged = tc.merge_document(new, old)

    by_handle = {t['handle']: t for t in merged['targets']}
    assert len(merged['targets']) == 2, '失败的 b 不能被丢掉'
    assert len(by_handle['a']['tweets']) == 1, '成功的 a 必须用新数据'
    assert len(by_handle['b']['tweets']) == 2, 'b 保留上轮 2 条'
    assert by_handle['b'].get('stale') is True, '保留项必须标 stale'
    assert merged['stale_targets'] == ['b']
    assert 'stale' not in by_handle['a']


def test_success_overrides_previous_data():
    tc = load_module()
    old = _doc([_tgt('a', 5)])
    new = _doc([_tgt('a', 30)])

    merged = tc.merge_document(new, old)

    assert len(merged['targets']) == 1
    assert len(merged['targets'][0]['tweets']) == 30, '不得混入旧推文'
    assert 'stale_targets' not in merged
    assert merged['targets'][0].get('stale') is None


def test_order_follows_previous_doc_and_appends_new():
    tc = load_module()
    old = _doc([_tgt('a', 1), _tgt('b', 1)])
    new = _doc([_tgt('c', 1), _tgt('a', 1)])   # 新账号 + 已存在账号，顺序故意反着

    merged = tc.merge_document(new, old)

    assert [t['handle'] for t in merged['targets']] == ['a', 'b', 'c']
    assert merged['stale_targets'] == ['b']


def test_empty_previous_tweets_are_not_kept():
    tc = load_module()
    old = _doc([_tgt('a', 0), _tgt('b', 2)])
    new = _doc([_tgt('c', 1)])

    merged = tc.merge_document(new, old)

    handles = [t['handle'] for t in merged['targets']]
    assert handles == ['b', 'c'], f'空数组不保留: {handles}'
    assert merged['stale_targets'] == ['b']


def test_no_previous_document_returns_new_doc():
    tc = load_module()
    new = _doc([_tgt('a', 2)])

    assert tc.merge_document(new, None) is new
    assert tc.merge_document(new, {}) is new


def test_load_previous_document_handles_missing_and_corrupt(tmp_path):
    tc = load_module()

    assert tc._load_previous_document(tmp_path / 'nope.json') is None

    bad = tmp_path / 'bad.json'
    bad.write_text('{not json', encoding='utf-8')
    assert tc._load_previous_document(bad) is None

    good = tmp_path / 'ok.json'
    good.write_text(json.dumps({'targets': []}), encoding='utf-8')
    assert tc._load_previous_document(good) == {'targets': []}


def test_collect_path_gone():  # 静态回归：事故放大器不得复活
    src = SCRIPT.read_text(encoding='utf-8')
    assert '提前终止本轮' not in src, 'CL012: 连续挑战不得提前终止（会丢余下账号）'
    assert 'challenge_streak >= 2' in src, '连击计数仍应保留（用于退避与告警）'
    assert 'CHALLENGE_BACKOFF_SEC' in src and 'time.sleep(backoff)' in src
    assert 'merge_document(doc, _load_previous_document())' in src, '写盘前必须合并上轮数据'
