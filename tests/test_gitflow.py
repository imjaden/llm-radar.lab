"""Test git flow: _sync_remote, _push_with_recovery, _clean_conflict_file,
_union_snapshot / _merge_semantic (D1) and _converge_fork (D2, CL006 v1.1-r2)."""
import json
import subprocess

# helpers ----------------------------------------------------------------


def _proc(code, stderr='', stdout=''):
    return subprocess.CompletedProcess(['git'], code, stdout, stderr)


class _GitFake:
    """Stateful _git_run fake: routes on ('fetch', ...), ('rev-parse', ...) etc."""

    def __init__(self, routes=None):
        self.routes = routes or {}  # key: tuple of first tokens; value: CompletedProcess or callable
        self.calls = []

    def __call__(self, *args, timeout=60):
        self.calls.append(args)
        for key, val in self.routes.items():
            if isinstance(key, tuple):
                if args[:len(key)] == key:
                    return val(*args) if callable(val) else val
            else:
                if args[0] == key:
                    return val(*args) if callable(val) else val
        return _proc(0)


def _no(*a, **k):
    return None


# _sync_remote ------------------------------------------------------------


class TestSyncRemote:
    def test_fast_forward(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'merge-base':
                return _proc(0)  # is-ancestor → 可快进
            if args[0] == 'merge':
                return _proc(0)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._sync_remote()
        assert ('fetch', 'origin', 'main') in calls
        assert ('merge', '--ff-only', 'origin/main') in calls

    def test_diverged_calls_converge(self, collector, monkeypatch):
        """CL006: 分叉 → _sync_remote 调 _converge_fork（而非仅本地优先）。"""
        calls = []
        converged = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'merge-base':
                return _proc(1)  # 分叉
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_converge_fork', lambda: converged.append(1) or True)
        collector._sync_remote()
        assert converged == [1]
        # 分叉时 ff merge 不应发生
        assert not any(c[0] == 'merge' for c in calls)

    def test_diverged_converge_fail_local_priority(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'merge-base':
                return _proc(1)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_converge_fork', lambda: False)
        collector._sync_remote()  # 收敛失败 → 不抛异常（本地优先兜底）
        assert not any(c[0] == 'merge' for c in calls)

    def test_fetch_fail_local_priority(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'fetch':
                return _proc(1, 'network error')
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._sync_remote()
        assert not any(c[0] == 'merge-base' for c in calls)

    def test_aborts_residual_rebase_first(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_has_rebase_state', lambda: True)
        collector._sync_remote()
        assert calls[0] == ('rebase', '--abort')


# _push_with_recovery -------------------------------------------------------


class TestPushRecovery:
    def test_push_success(self, collector, monkeypatch):
        monkeypatch.setattr(collector, '_git_run', lambda *a, timeout=60: _proc(0))
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._push_with_recovery([{'type': 'new'}], 'msg')

    def test_rebase_success_plain_push_no_force(self, collector, monkeypatch):
        """CL006: rebase 成功后普通 push（删除 force-with-lease）。"""
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push':
                return _proc(1, 'rejected') if args == ('push', 'origin', 'main') and len(calls) == 1 else _proc(0)
            if args[0] == 'pull':
                return _proc(0)  # rebase 成功
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        assert not any('--force-with-lease' in a for a in calls)
        assert not any('--force' in a for a in calls)
        # 普通 push 发生两次（初次 rejected + rebase 后成功）
        assert sum(1 for a in calls if a == ('push', 'origin', 'main')) == 2

    def test_rebase_conflict_converge_success(self, collector, monkeypatch):
        """CL006: rebase 冲突 → _converge_fork 成功 → 普通 push 成功。"""
        calls = []
        pushes = {'n': 0}

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push':
                pushes['n'] += 1
                # 初次 push rejected；收敛后 push 成功
                return _proc(1, 'rejected') if pushes['n'] == 1 else _proc(0)
            if args[0] == 'pull':
                return _proc(1, 'CONFLICT')
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_converge_fork', lambda: True)
        wrote = {}
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: wrote.setdefault('err', e))
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        assert not any('--force' in a for a in calls)
        assert 'err' not in wrote  # 收敛成功不写 dead-letter
        assert pushes['n'] == 2

    def test_rebase_conflict_converge_fail_dead_letter(self, collector, monkeypatch):
        """CL006: rebase 冲突且收敛失败 → dead-letter 提示人工 merge（无 force）。"""
        calls = []
        wrote = {}

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push':
                return _proc(1, 'rejected')
            if args[0] == 'pull':
                return _proc(1, 'CONFLICT')
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_converge_fork', lambda: False)
        monkeypatch.setattr(collector, '_write_dead_letter',
                            lambda c, e: wrote.setdefault('err', e))
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        assert not any('--force' in a for a in calls)
        assert '语义收敛失败' in wrote.get('err', '')

    def test_no_exception_when_all_fail(self, collector, monkeypatch):
        monkeypatch.setattr(collector, '_git_run',
                            lambda *a, timeout=60: _proc(1, 'fail'))
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: None)
        monkeypatch.setattr(collector, '_converge_fork', lambda: False)
        collector._push_with_recovery([{'type': 'new'}], 'msg')


# D1 semantic union ----------------------------------------------------------


class TestMergeSemantic:
    def test_empty_fill(self, collector):
        a = {'id': 'x', 'name': 'X', 'desc': ''}
        b = {'id': 'x', 'name': 'X', 'desc': 'desc-here'}
        merged = collector._merge_semantic(a, b)
        assert merged['desc'] == 'desc-here'

    def test_time_newer_wins(self, collector):
        a = {'id': 'x', 'summary': 'old', 'last_event_date': '2026-09-01'}
        b = {'id': 'x', 'summary': 'new', 'last_event_date': '2026-09-05'}
        merged = collector._merge_semantic(a, b)
        assert merged['summary'] == 'new'
        # 对称：参数交换结果一致
        assert collector._merge_semantic(b, a) == merged

    def test_multi_time_field_priority(self, collector):
        """RIG-9: last_event_date > updated_at——last_event_date 判新侧胜出，不交叉比较。"""
        a = {'id': 'x', 'summary': 'from-a', 'last_event_date': '2026-09-05', 'updated_at': '2026-09-01T00:00:00'}
        b = {'id': 'x', 'summary': 'from-b', 'last_event_date': '2026-09-01', 'updated_at': '2026-09-05T00:00:00'}
        merged = collector._merge_semantic(a, b)
        assert merged['summary'] == 'from-a'  # a 的 last_event_date 较新
        assert collector._merge_semantic(b, a) == merged

    def test_tie_lexicographic(self, collector):
        """无时间字段平局 → 字典序较大值（跨机确定）。"""
        a = {'id': 'x', 'tag': 'alpha'}
        b = {'id': 'x', 'tag': 'beta'}
        merged = collector._merge_semantic(a, b)
        assert merged['tag'] == 'beta'
        assert collector._merge_semantic(b, a) == merged


class TestUnionSnapshot:
    def _snap(self, generated_at, dims, hotspots=None, changelog=None, stats=None, extra=None):
        s = {'version': '1.0', 'generated_at': generated_at, 'period': 'p',
             'execution_mode': 'auto'}
        for dim in ('providers', 'people', 'tools', 'llms'):
            s[dim] = dims.get(dim, [])
        s['hotspots'] = hotspots or []
        s['changelog'] = changelog or []
        s['stats'] = stats or {}
        if extra:
            s.update(extra)
        return s

    def test_union_counts_no_loss(self, collector):
        local = self._snap('2026-09-06T10:00:00', {
            'providers': [{'id': 'a'}, {'id': 'b'}],
            'people': [{'id': 'p1'}],
            'tools': [], 'llms': [],
        }, stats={'total_providers': 2, 'total_people': 1})
        remote = self._snap('2026-09-06T12:00:00', {
            'providers': [{'id': 'b', 'note': 'server'}, {'id': 'c'}],
            'people': [], 'tools': [{'id': 't1'}], 'llms': [{'id': 'l1'}],
        }, stats={'total_providers': 2, 'total_tools': 1, 'total_llms': 1})
        merged = collector._union_snapshot(local, remote)
        ids = {p['id'] for p in merged['providers']}
        assert ids == {'a', 'b', 'c'}  # 并集不丢任一端
        # b 合并：remote 侧 note 保留（local 无），remote generated_at 较新
        b = next(p for p in merged['providers'] if p['id'] == 'b')
        assert b.get('note') == 'server'
        assert len(merged['people']) == 1 and len(merged['tools']) == 1 and len(merged['llms']) == 1
        assert merged['stats']['total_providers'] == 3
        assert merged['generated_at'] == '2026-09-06T12:00:00'  # 较新侧

    def test_union_symmetric(self, collector):
        local = self._snap('2026-09-06T10:00:00', {
            'providers': [{'id': 'a', 'x': '1'}, {'id': 'b', 'last_event_date': '2026-09-02'}],
            'people': [{'id': 'p'}], 'tools': [], 'llms': [],
        }, hotspots=[{'id': 'h1', 'date': '2026-09-05'}],
           changelog=[{'type': 'new', 'dimension': 'providers', 'id': 'a', 'time': '10:00'}],
           stats={'total_providers': 2, 'new_this_period': 1})
        remote = self._snap('2026-09-06T12:00:00', {
            'providers': [{'id': 'a', 'x': '9'}, {'id': 'c'}],
            'people': [], 'tools': [], 'llms': [],
        }, hotspots=[{'id': 'h2', 'date': '2026-09-06'}],
           changelog=[{'type': 'new', 'dimension': 'providers', 'id': 'c', 'time': '12:00'}],
           stats={'total_providers': 1})
        m1 = collector._union_snapshot(local, remote)
        m2 = collector._union_snapshot(remote, local)
        assert m1 == m2  # 跨机确定性

    def test_hotspot_cap_max(self, collector):
        local_hs = [{'id': f'l{i}', 'date': f'2026-09-0{i}'} for i in range(1, 5)]  # 4
        remote_hs = [{'id': f'r{i}', 'date': f'2026-09-0{i}'} for i in range(6, 10)]  # 4
        local = self._snap('2026-09-06T10:00:00', {'providers': [], 'people': [], 'tools': [], 'llms': []},
                           hotspots=local_hs)
        remote = self._snap('2026-09-06T12:00:00', {'providers': [], 'people': [], 'tools': [], 'llms': []},
                            hotspots=remote_hs)
        merged = collector._union_snapshot(local, remote)
        assert len(merged['hotspots']) == 4  # max(4,4) 截断
        dates = [h['date'] for h in merged['hotspots']]
        assert dates == sorted(dates, reverse=True)  # date 降序

    def test_changelog_newer_time(self, collector):
        local = self._snap('2026-09-06T10:00:00', {'providers': [], 'people': [], 'tools': [], 'llms': []},
                           changelog=[{'type': 'update', 'dimension': 'tools', 'id': 't', 'time': '10:00', 'v': 'old'}])
        remote = self._snap('2026-09-06T12:00:00', {'providers': [], 'people': [], 'tools': [], 'llms': []},
                            changelog=[{'type': 'update', 'dimension': 'tools', 'id': 't', 'time': '12:00', 'v': 'new'}])
        merged = collector._union_snapshot(local, remote)
        assert merged['changelog'][0]['v'] == 'new'  # 同键取较新 time

    def test_real_data_regression(self, collector):
        """真实数据回归：origin/main 与本地 snapshot 并集，4 维度 = id 集合并集，计数 ≥ 两侧。"""
        import subprocess as sp
        r1 = sp.run(['git', 'show', 'HEAD:data/snapshot.json'], capture_output=True, text=True, cwd=collector.project_root)
        r2 = sp.run(['git', 'show', 'origin/main:data/snapshot.json'], capture_output=True, text=True, cwd=collector.project_root)
        if r1.returncode != 0 or r2.returncode != 0:
            import pytest
            pytest.skip('git blob 不可用（HEAD/origin/main snapshot 缺失）')
        local = json.loads(r1.stdout)
        remote = json.loads(r2.stdout)
        merged = collector._union_snapshot(local, remote)
        for dim in ('providers', 'people', 'tools', 'llms'):
            ids_m = {x.get('id') for x in merged[dim]}
            ids_l = {x.get('id') for x in local.get(dim, [])}
            ids_r = {x.get('id') for x in remote.get(dim, [])}
            assert ids_m == (ids_l | ids_r), f'{dim} union 不等于 id 并集'
            assert len(merged[dim]) >= max(len(ids_l), len(ids_r))


# D2 _converge_fork ------------------------------------------------------------


class TestConvergeFork:
    def _enable(self, collector):
        collector._skip_push = False

    def test_equal_noop(self, collector, monkeypatch):
        self._enable(collector)
        fake = _GitFake({
            ('fetch', 'origin', 'main'): _proc(0),
            ('rev-parse', 'HEAD'): _proc(0, stdout='abc\n'),
            ('rev-parse', 'origin/main'): _proc(0, stdout='abc\n'),
        })
        monkeypatch.setattr(collector, '_git_run', fake)
        assert collector._converge_fork() is True
        assert not any(c[0] == 'merge' for c in fake.calls)

    def test_ff_path(self, collector, monkeypatch):
        self._enable(collector)
        fake = _GitFake({
            ('fetch', 'origin', 'main'): _proc(0),
            ('rev-parse', 'HEAD'): _proc(0, stdout='a\n'),
            ('rev-parse', 'origin/main'): _proc(0, stdout='b\n'),
            ('merge-base', '--is-ancestor', 'HEAD', 'origin/main'): _proc(0),
            ('merge', '--ff-only', 'origin/main'): _proc(0),
        })
        monkeypatch.setattr(collector, '_git_run', fake)
        assert collector._converge_fork() is True
        assert ('merge', '--ff-only', 'origin/main') in fake.calls

    def test_dirty_guard(self, collector, monkeypatch):
        self._enable(collector)
        fake = _GitFake({
            ('fetch', 'origin', 'main'): _proc(0),
            ('rev-parse', 'HEAD'): _proc(0, stdout='a\n'),
            ('rev-parse', 'origin/main'): _proc(0, stdout='b\n'),
            ('merge-base', '--is-ancestor', 'HEAD', 'origin/main'): _proc(1),
            ('status', '--porcelain'): _proc(0, stdout=' M data/snapshot.json\n'),
        })
        monkeypatch.setattr(collector, '_git_run', fake)
        assert collector._converge_fork() is False
        assert not any(c[0] == 'merge' and '--no-commit' in c for c in fake.calls)

    def test_fork_semantic_success(self, collector, monkeypatch):
        self._enable(collector)
        seen = {'unmerged': ['data/snapshot.json', 'overview.json', 'timestamp.json']}

        def route(*args, **kw):
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'rev-parse':
                return _proc(0, stdout='a\n' if args[1] == 'HEAD' else 'b\n')
            if args[0] == 'merge-base':
                return _proc(1)
            if args[0] == 'status':
                return _proc(0, stdout='')
            if args[0] == 'merge' and '--no-commit' in args:
                return _proc(1, 'conflict')  # 有冲突
            if args[0] == 'diff' and args[1] == '--name-only':
                return _proc(0, stdout='\n'.join(seen['unmerged']) + '\n' if seen['unmerged'] else '')
            if args[0] == 'commit':
                seen['committed'] = args
                return _proc(0)
            if args[0] == 'push':
                seen['pushed'] = True
                return _proc(0)
            if args[0] == 'add':
                return _proc(0)
            if args[0] == 'merge' and '--abort' in args:
                return _proc(0)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', route)
        monkeypatch.setattr(collector, '_resolve_converge_file', lambda rel: True)
        # 第二次 diff (解决后复查) 返回空
        orig = collector._git_run
        calls = {'n': 0}

        def routed2(*a, timeout=60):
            if a[0] == 'diff' and a[1] == '--name-only':
                calls['n'] += 1
                if calls['n'] >= 2:
                    return _proc(0, stdout='')
            return route(*a, timeout=timeout)

        monkeypatch.setattr(collector, '_git_run', routed2)
        monkeypatch.setattr(collector, '_in_merge_state', lambda: False)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        assert collector._converge_fork() is True
        assert seen.get('pushed') is True
        assert seen['committed'][2] == collector._CONVERGE_MSG

    def test_nonwhitelist_conflict_aborts(self, collector, monkeypatch):
        self._enable(collector)
        wrote = {}
        git_calls = []

        def route(*args, timeout=60):
            git_calls.append(args)
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'rev-parse':
                return _proc(0, stdout='a\n' if args[1] == 'HEAD' else 'b\n')
            if args[0] == 'merge-base':
                return _proc(1)
            if args[0] == 'status':
                return _proc(0, stdout='')
            if args[0] == 'merge' and '--no-commit' in args:
                return _proc(1, 'conflict')
            if args[0] == 'diff':
                return _proc(0, stdout='llm-radar-collector.py\n')
            if args[0] == 'commit':
                return _proc(0)
            if args[0] == 'merge' and '--abort' in args:
                return _proc(0)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', route)
        monkeypatch.setattr(collector, '_in_merge_state', lambda: False)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: wrote.setdefault('err', e))
        assert collector._converge_fork() is False
        assert '白名单外冲突' in wrote.get('err', '')
        assert not any(c[0] == 'commit' for c in git_calls)
        assert not any(c[0] == 'push' for c in git_calls)
        assert ('merge', '--abort') in git_calls

    def test_clean_automerge_commit_push(self, collector, monkeypatch):
        self._enable(collector)

        def route(*args, timeout=60):
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'rev-parse':
                return _proc(0, stdout='a\n' if args[1] == 'HEAD' else 'b\n')
            if args[0] == 'merge-base':
                return _proc(1)
            if args[0] == 'status':
                return _proc(0, stdout='')
            if args[0] == 'merge' and '--no-commit' in args:
                return _proc(0)  # 无冲突自动合并
            if args[0] == 'commit':
                return _proc(0)
            if args[0] == 'push':
                return _proc(0)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', route)
        monkeypatch.setattr(collector, '_in_merge_state', lambda: False)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        assert collector._converge_fork() is True

    def test_finally_aborts_residual_merge(self, collector, monkeypatch):
        self._enable(collector)
        aborted = []

        def route(*args, timeout=60):
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'rev-parse':
                return _proc(0, stdout='a\n' if args[1] == 'HEAD' else 'b\n')
            if args[0] == 'merge-base':
                return _proc(1)
            if args[0] == 'status':
                return _proc(1, 'err')
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', route)
        monkeypatch.setattr(collector, '_in_merge_state', lambda: True)
        monkeypatch.setattr(collector, '_abort_rebase',
                            lambda: aborted.append(1))
        collector._converge_fork()
        assert aborted  # finally 清理

    def test_skip_push_guard(self, collector, monkeypatch):
        # fixture 默认 _skip_push=True → 直接跳过
        called = []
        monkeypatch.setattr(collector, '_git_run', lambda *a, timeout=60: called.append(a) or _proc(0))
        assert collector._converge_fork() is False
        assert not called


# _clean_conflict_file ------------------------------------------------------------


class TestCleanConflictFile:
    def test_no_marker_noop(self, collector, tmp_path):
        p = tmp_path / 'f.json'
        p.write_text('{"a": 1}')
        collector._clean_conflict_file(p)
        assert p.read_text() == '{"a": 1}'

    def test_conflict_tracked_checkout_theirs(self, collector, tmp_path, monkeypatch):
        p = tmp_path / 'f.json'
        p.write_text('<<<<<<< HEAD\n=======\n>>>>>>>')
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'ls-files':
                return _proc(0)  # tracked
            if args[0] == 'checkout':
                return _proc(0)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        collector._clean_conflict_file(p)
        assert any(c[0] == 'checkout' and c[1] == '--theirs' for c in calls)

    def test_conflict_untracked_remove(self, collector, tmp_path, monkeypatch):
        p = tmp_path / 'f.json'
        p.write_text('<<<<<<< HEAD\n=======\n>>>>>>>')

        def fake_git(*args, timeout=60):
            if args[0] == 'ls-files':
                return _proc(1)  # untracked
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        collector._clean_conflict_file(p)
        assert not p.exists()  # 已删除，由写盘重建

    def test_save_snapshot_cleans_markers(self, temp_snapshot, monkeypatch):
        temp_snapshot.snapshot_path.write_text('<<<<<<< HEAD\n=======\n>>>>>>>')

        def fake_git(*args, timeout=60):
            return _proc(1)  # untracked → os.remove

        monkeypatch.setattr(temp_snapshot, '_git_run', fake_git)
        snapshot = {
            'providers': [], 'people': [], 'tools': [], 'llms': [],
            'hotspots': [], 'generated_at': '2026-08-12T00:00:00',
        }
        temp_snapshot._save_snapshot(snapshot)
        text = temp_snapshot.snapshot_path.read_text()
        assert '<<<<<<<' not in text
        data = json.loads(text)  # 合法 JSON
        assert data['generated_at'] == '2026-08-12T00:00:00'


# D3 partial branch converge ------------------------------------------------------


class TestPartialConverge:
    def test_partial_push_fail_converge_success(self, collector, monkeypatch):
        collector._skip_push = False
        calls = {'checkout': [], 'converge': 0}

        def fake_run(cmd, **kw):
            # git add/commit 返回假成功（不触碰真实仓库）；push 抛 CalledProcessError
            if isinstance(cmd, list) and cmd[:1] == ['git']:
                if cmd[1] == 'push':
                    raise subprocess.CalledProcessError(1, cmd, output='rejected')
                return subprocess.CompletedProcess(cmd, 0)
            raise AssertionError('unexpected subprocess.run')

        monkeypatch.setattr(subprocess, 'run', fake_run)

        def fake_git(*args, timeout=60):
            if args[0] == 'checkout':
                calls['checkout'].append(args)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_converge_fork',
                            lambda: calls.__setitem__('converge', calls['converge'] + 1) or True)
        collector._auto_push([], partial=True)
        assert calls['checkout'] == [('checkout', '--', 'data/snapshot.json'),
                                     ('checkout', '--', 'overview.json')]
        assert calls['converge'] == 1

    def test_partial_push_fail_converge_fail_dead_letter(self, collector, monkeypatch):
        collector._skip_push = False
        wrote = {}

        def fake_run(cmd, **kw):
            if isinstance(cmd, list) and cmd[:1] == ['git']:
                if cmd[1] == 'push':
                    raise subprocess.CalledProcessError(1, cmd, output='rejected')
                return subprocess.CompletedProcess(cmd, 0)
            raise AssertionError('unexpected subprocess.run')

        monkeypatch.setattr(subprocess, 'run', fake_run)
        monkeypatch.setattr(collector, '_git_run', lambda *a, timeout=60: _proc(0))
        monkeypatch.setattr(collector, '_converge_fork', lambda: False)
        monkeypatch.setattr(collector, '_write_dead_letter',
                            lambda c, e: wrote.setdefault('err', e))
        collector._auto_push([], partial=True)
        assert 'partial' in wrote.get('err', '')
