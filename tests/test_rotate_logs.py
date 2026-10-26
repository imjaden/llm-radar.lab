#!/usr/bin/env python3
"""`scripts/rotate-logs.sh` 的钉子：copytruncate 语义 + 阈值/跨天触发 + 保留份数。

为什么钉「inode 不变」：写入方每轮重新 open 追加，但长跑进程可能持有 fd；rename 会让新行写进旧 inode，
表现为「日志突然不再增长」。copytruncate（cp + `: >`）必须保持原路径原 inode。
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts' / 'rotate-logs.sh'


def _run(tmp_path, *args, max_bytes=100, keep=7):
    env = dict(os.environ, ROTATE_STATE=str(tmp_path / 'state.json'))
    return subprocess.run(['bash', str(SCRIPT), '--dir', str(tmp_path / 'logs'),
                           '--max-bytes', str(max_bytes), '--keep', str(keep), *args],
                          capture_output=True, text=True, env=env)


def _seed(tmp_path, name='a.log', content='line1\nline2\n'):
    d = tmp_path / 'logs'
    d.mkdir(exist_ok=True)
    f = d / name
    f.write_text(content, encoding='utf-8')
    return f


def test_truncates_in_place_and_gzips(tmp_path):
    f = _seed(tmp_path)
    inode = f.stat().st_ino
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f.exists() and f.stat().st_size == 0, '原文件必须被原地清零'
    assert f.stat().st_ino == inode, 'inode 变了 ⇒ 等价于 rename, 会丢写'
    gz = list(f.parent.glob('a.log.*.gz'))
    assert len(gz) == 1
    import gzip
    assert gzip.open(gz[0], 'rt', encoding='utf-8').read() == 'line1\nline2\n'


def test_second_run_same_day_is_noop(tmp_path):
    _seed(tmp_path)
    assert _run(tmp_path).returncode == 0
    r = _run(tmp_path)                      # 当天已轮转过, 且新文件 0 字节
    assert '无需轮转' in r.stdout, r.stdout
    assert len(list((tmp_path / 'logs').glob('a.log.*.gz'))) == 1


def test_size_threshold_triggers_again_same_day(tmp_path):
    f = _seed(tmp_path)
    assert _run(tmp_path, max_bytes=10).returncode == 0
    f.write_text('y' * 50, encoding='utf-8')
    r = _run(tmp_path, max_bytes=10)        # 超阈值 ⇒ 即使当天已轮转也要再轮转
    assert r.returncode == 0
    assert len(list(f.parent.glob('a.log.*.gz'))) == 2, r.stdout


def test_keep_n_prunes_old_archives(tmp_path):
    f = _seed(tmp_path)
    for _ in range(4):
        f.write_text('z\n', encoding='utf-8')
        assert _run(tmp_path, max_bytes=1, keep=2).returncode == 0
    assert len(list(f.parent.glob('a.log.*.gz'))) == 2, '必须只保留最近 2 份'


def test_dry_run_touches_nothing(tmp_path):
    f = _seed(tmp_path)
    r = _run(tmp_path, '--dry-run')
    assert r.returncode == 0 and '[dry-run]' in r.stdout
    assert f.stat().st_size == 12, 'dry-run 不得截断'
    assert not list(f.parent.glob('a.log.*.gz'))


def test_empty_file_is_skipped(tmp_path):
    f = _seed(tmp_path, content='')
    r = _run(tmp_path)
    assert r.returncode == 0
    assert not list(f.parent.glob('a.log.*.gz')), '空文件不该制造空档'
