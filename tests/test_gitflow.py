"""Test git flow fix: _sync_remote, _push_with_recovery, _clean_conflict_file."""
import json
import subprocess


def _proc(code, stderr='', stdout=''):
    return subprocess.CompletedProcess(['git'], code, stdout, stderr)


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

    def test_diverged_local_priority(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'fetch':
                return _proc(0)
            if args[0] == 'merge-base':
                return _proc(1)  # 分叉
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._sync_remote()
        # 分叉时不 merge，本地优先
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
        # fetch 失败后直接返回，不调用 merge-base
        assert not any(c[0] == 'merge-base' for c in calls)

    def test_aborts_residual_rebase_first(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_has_rebase_state', lambda: True)
        collector._sync_remote()
        # 残留 rebase 时先 abort
        assert calls[0] == ('rebase', '--abort')


class TestPushRecovery:
    def test_push_success(self, collector, monkeypatch):
        monkeypatch.setattr(collector, '_git_run', lambda *a, timeout=60: _proc(0))
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        collector._push_with_recovery([{'type': 'new'}], 'msg')

    def test_rejected_rebase_force_lease(self, collector, monkeypatch):
        calls = []

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push' and '--force-with-lease' not in args:
                return _proc(1, 'rejected')
            if args[0] == 'pull':
                return _proc(0)  # rebase 成功
            return _proc(0)  # force-with-lease 成功

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: None)
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        assert ('push', '--force-with-lease', 'origin', 'main') in calls

    def test_rejected_rebase_conflict_dead_letter(self, collector, monkeypatch):
        """v1.3: rebase 冲突 → force-with-lease 失败 → dead-letter (旧行为: 冲突直接 dead-letter 已更新)"""
        wrote = {}

        def fake_git(*args, timeout=60):
            if args[0] == 'push' and '--force-with-lease' not in args:
                return _proc(1, 'rejected')
            if args[0] == 'pull':
                return _proc(1, 'CONFLICT')  # rebase 冲突
            if args[0] == 'push' and '--force-with-lease' in args:
                return _proc(1, 'lease fail')  # force 也失败
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)

        def fake_dead(changelog, err):
            wrote['err'] = err

        monkeypatch.setattr(collector, '_write_dead_letter', fake_dead)
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        assert wrote.get('err') == 'rejected'

    def test_no_exception_when_all_fail(self, collector, monkeypatch):
        monkeypatch.setattr(collector, '_git_run',
                            lambda *a, timeout=60: _proc(1, 'fail'))
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: None)
        # 全部失败也不应抛异常
        collector._push_with_recovery([{'type': 'new'}], 'msg')

    def test_rebase_conflict_then_force_lease_success(self, collector, monkeypatch):
        """v1.3: rebase 冲突 → abort 后尝试 force-with-lease → 收敛完成 (不写 dead-letter)"""
        calls = []
        wrote = {}

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push' and '--force-with-lease' not in args:
                return _proc(1, 'rejected')
            if args[0] == 'pull':
                return _proc(1, 'CONFLICT')  # rebase 冲突
            return _proc(0)  # force-with-lease 成功

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: wrote.setdefault('err', e))
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        # force-with-lease 被调用且成功
        assert ('push', '--force-with-lease', 'origin', 'main') in calls
        assert calls.count(('push', '--force-with-lease', 'origin', 'main')) >= 1
        # 收敛成功 → 不写 dead-letter
        assert 'err' not in wrote

    def test_rebase_conflict_force_lease_fail_dead_letter(self, collector, monkeypatch):
        """v1.3: rebase 冲突 → force-with-lease 也失败 → dead-letter (不抛异常)"""
        calls = []
        wrote = {}

        def fake_git(*args, timeout=60):
            calls.append(args)
            if args[0] == 'push' and '--force-with-lease' not in args:
                return _proc(1, 'rejected')
            if args[0] == 'pull':
                return _proc(1, 'CONFLICT')  # rebase 冲突
            if args[0] == 'push' and '--force-with-lease' in args:
                return _proc(1, 'lease fail')  # force 也失败
            return _proc(0)

        monkeypatch.setattr(collector, '_git_run', fake_git)
        monkeypatch.setattr(collector, '_abort_rebase', lambda: None)
        monkeypatch.setattr(collector, '_write_dead_letter', lambda c, e: wrote.setdefault('err', e))
        collector._push_with_recovery([{'type': 'new'}], 'msg')
        # force-with-lease 被尝试
        assert ('push', '--force-with-lease', 'origin', 'main') in calls
        # 全失败 → dead-letter 记录 rejected
        assert wrote.get('err') == 'rejected'


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
        # 写冲突标记到 snapshot_path
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
