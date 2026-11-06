"""collector 进程内 `.env` 加载（GOV-1 收口，2026-11-06）。

背景: wrapper（`cache/system-command/lr-wrapper.sh`）是 gitignored 生成物，
`install.py --force` 重生成会丢掉手工补的 `.env` 段 ⇒ `lr run` 报「DEEPSEEK_API_KEY 未配置」。
这与「key 失效」形似但根因完全不同（2026-11-04 踩过：一边查 key 一边其实是 wrapper 缺段）。
把加载下沉到 `main()` 入口后，任何入口（lr / 直跑 python / cron）都能拿到 key，
wrapper 那段降级为冗余保险。

钉子:
  1) 能读到 .env 并写进 os.environ
  2) **不覆盖**既有 env（cron / wrapper / 调用方优先）
  3) 引号、`export ` 前缀、注释、空行、无 `=` 行都要正确处理
  4) 文件缺失 → 返回 False 且不动 env（不抛异常）
  5) main() 入口确实调用了 _load_dotenv（接线）
"""
import os

import pytest

from conftest import import_collector


@pytest.fixture
def mod():
    return import_collector()


class TestLoadDotenv:
    def test_reads_key_from_file(self, mod, tmp_path, monkeypatch):
        monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
        p = tmp_path / '.env'
        p.write_text('DEEPSEEK_API_KEY=sk-dotenv-test\n', encoding='utf-8')
        assert mod._load_dotenv(p) is True
        assert os.environ['DEEPSEEK_API_KEY'] == 'sk-dotenv-test'

    def test_existing_env_wins(self, mod, tmp_path, monkeypatch):
        """shell / cron 已给的 key 不能被 .env 里的旧值顶掉。"""
        monkeypatch.setenv('DEEPSEEK_API_KEY', 'from-shell')
        p = tmp_path / '.env'
        p.write_text('DEEPSEEK_API_KEY=from-file\n', encoding='utf-8')
        mod._load_dotenv(p)
        assert os.environ['DEEPSEEK_API_KEY'] == 'from-shell'

    def test_quotes_export_and_junk(self, mod, tmp_path, monkeypatch):
        for k in ('DOTENV_A', 'DOTENV_B', 'DOTENV_EMPTY'):
            monkeypatch.delenv(k, raising=False)
        p = tmp_path / '.env'
        p.write_text(
            '# 注释行\n'
            '\n'
            'export DOTENV_A="v1"\n'
            "DOTENV_B='v2'\n"
            'DOTENV_EMPTY=\n'
            '这一行没有等号\n',
            encoding='utf-8')
        assert mod._load_dotenv(p) is True
        assert os.environ['DOTENV_A'] == 'v1'
        assert os.environ['DOTENV_B'] == 'v2'
        assert os.environ['DOTENV_EMPTY'] == ''

    def test_missing_file_is_noop(self, mod, tmp_path, monkeypatch):
        monkeypatch.setenv('DEEPSEEK_API_KEY', 'untouched')
        assert mod._load_dotenv(tmp_path / 'nope.env') is False
        assert os.environ['DEEPSEEK_API_KEY'] == 'untouched'

    def test_tolerates_spaces_around_equals(self, mod, tmp_path, monkeypatch):
        monkeypatch.delenv('DOTENV_SPACED', raising=False)
        p = tmp_path / '.env'
        p.write_text('DOTENV_SPACED =  value with space  \n', encoding='utf-8')
        mod._load_dotenv(p)
        assert os.environ['DOTENV_SPACED'] == 'value with space'


class TestMainWiring:
    def test_main_loads_dotenv_first(self, mod, monkeypatch, capsys):
        called = []
        monkeypatch.setattr(mod, '_load_dotenv', lambda *a, **k: called.append(1) or True)
        monkeypatch.setattr(mod.sys, 'argv', ['llm-radar-collector.py', 'help'])
        with pytest.raises(SystemExit):
            mod.main()
        assert called == [1], 'main() 入口必须先加载 .env（GOV-1）'
