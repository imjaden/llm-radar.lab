"""auto-push 独立通道（2026-11-06）：采集被 6h 防抖跳过时，仍推送本地待推 commit。

动机: auto-push 挂在 run() 的采集尾巴上 ⇒ 采集被防抖跳过时，手工/半自动产生的 commit
会被压在本地最多 6h，期间 `lr status` 恒「待推」。这里只推**已提交**内容，不产数据。

钉子:
  1) 仅「pending_push（ahead>0 且 behind==0）」才推；已同步/落后/真分叉一律不碰
  2) `_skip_push`（测试/降级）时绝不推
  3) run() 被 _think 否决时必须调用这条通道，且仍返回 False（不伪装成采集成功）
  4) 真 git 环境（本地 repo + bare origin）端到端可推上去
"""
import subprocess

import pytest

from conftest import import_collector


def _proc(code, stdout='', stderr=''):
    return subprocess.CompletedProcess(['git'], code, stdout, stderr)


def _quiet(c):
    for m in ('_print_ok', '_print_err', '_print_info', '_print_warn'):
        setattr(c, m, lambda msg: None)
    return c


class TestPushAheadOnSkip:
    def _collector(self, ahead=2, behind=0, skip_push=False):
        c = _quiet(import_collector().LLMRadarCollector())
        c._skip_push = skip_push
        if ahead and not behind:
            state = 'pending_push'
        elif ahead == 0 and behind == 0:
            state = 'ok'
        else:
            state = 'warning'
        c._git_divergence = lambda: (ahead, behind, state)
        c._git_run = lambda *a, **k: _proc(0, stdout='abc1234 fix@cli: 示例提交\n')
        pushed = []
        c._push_with_recovery = lambda changelog, msg: pushed.append((changelog, msg))
        return c, pushed

    def test_pushes_when_ahead(self):
        c, pushed = self._collector(ahead=2)
        assert c._push_ahead_on_skip() is True
        assert len(pushed) == 1
        assert pushed[0][0] == [], '不得给死信通道塞假 changelog'
        assert '2 笔' in pushed[0][1]

    def test_noop_when_in_sync(self):
        c, pushed = self._collector(ahead=0, behind=0)
        assert c._push_ahead_on_skip() is False
        assert pushed == []

    @pytest.mark.parametrize('ahead,behind', [(0, 1), (1, 1)])
    def test_noop_when_behind_or_forked(self, ahead, behind):
        """落后/真分叉交给 _sync_remote 处理，这条通道不许抢跑。"""
        c, pushed = self._collector(ahead=ahead, behind=behind)
        assert c._push_ahead_on_skip() is False
        assert pushed == []

    def test_skip_push_guard(self):
        c, pushed = self._collector(ahead=3, skip_push=True)
        assert c._push_ahead_on_skip() is False
        assert pushed == []


class TestRunSkipWiring:
    def test_run_calls_push_channel_when_throttled(self, tmp_path):
        c = _quiet(import_collector().LLMRadarCollector())
        c.data_dir = tmp_path
        c.project_root = tmp_path
        c._sync_remote = lambda: None
        c._think = lambda force=False: False
        called = []
        c._push_ahead_on_skip = lambda: called.append(1)
        assert c.run() is False, '被防抖跳过时 run 仍返回 False'
        assert called == [1], '跳过分支必须走独立推送通道'

    def test_run_does_not_call_channel_when_thinking_true(self, tmp_path, monkeypatch):
        """_think 通过时不得提前调用（推送由采集尾巴的 auto-push 负责）。"""
        c = _quiet(import_collector().LLMRadarCollector())
        c.data_dir = tmp_path
        c.project_root = tmp_path
        c._sync_remote = lambda: None
        c._think = lambda force=False: True
        called = []
        c._push_ahead_on_skip = lambda: called.append(1)
        monkeypatch.setattr(c, 'fetch_all', lambda keys: (_ for _ in ()).throw(RuntimeError('停在这里')))
        try:
            c.run()
        except RuntimeError:
            pass
        assert called == []


class TestRealGitRoundTrip:
    """端到端: 真 repo + bare origin，验证「已提交未推」确实被推上去。"""

    def _build(self, tmp_path):
        origin = tmp_path / 'origin.git'
        work = tmp_path / 'work'
        subprocess.run(['git', 'init', '--bare', '-q', '-b', 'main', str(origin)], check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(work)], check=True)
        for kv in (('user.name', 't'), ('user.email', 't@example.com')):
            subprocess.run(['git', 'config', *kv], cwd=work, check=True)
        subprocess.run(['git', 'remote', 'add', 'origin', str(origin)], cwd=work, check=True)
        (work / 'a.txt').write_text('1')
        subprocess.run(['git', 'add', '-A'], cwd=work, check=True)
        subprocess.run(['git', 'commit', '-qm', 'c1'], cwd=work, check=True)
        subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=work, check=True)
        return origin, work

    def test_pushes_pending_commit_to_origin(self, tmp_path):
        origin, work = self._build(tmp_path)
        (work / 'b.txt').write_text('2')
        subprocess.run(['git', 'add', '-A'], cwd=work, check=True)
        subprocess.run(['git', 'commit', '-qm', 'c2 待推'], cwd=work, check=True)
        local_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=work, check=True,
                                    capture_output=True, text=True).stdout.strip()
        remote_before = subprocess.run(['git', '--git-dir', str(origin), 'rev-parse', 'main'],
                                       check=True, capture_output=True, text=True).stdout.strip()
        assert local_head != remote_before, '前提: 应有一笔未推提交'

        c = _quiet(import_collector().LLMRadarCollector())
        c.project_root = work
        c._skip_push = False
        assert c._push_ahead_on_skip() is True

        remote_after = subprocess.run(['git', '--git-dir', str(origin), 'rev-parse', 'main'],
                                      check=True, capture_output=True, text=True).stdout.strip()
        assert remote_after == local_head, '待推提交必须到达 origin'

    def test_synced_repo_is_untouched(self, tmp_path):
        origin, work = self._build(tmp_path)
        before = subprocess.run(['git', '--git-dir', str(origin), 'rev-parse', 'main'],
                                check=True, capture_output=True, text=True).stdout.strip()
        c = _quiet(import_collector().LLMRadarCollector())
        c.project_root = work
        c._skip_push = False
        assert c._push_ahead_on_skip() is False
        after = subprocess.run(['git', '--git-dir', str(origin), 'rev-parse', 'main'],
                               check=True, capture_output=True, text=True).stdout.strip()
        assert before == after
