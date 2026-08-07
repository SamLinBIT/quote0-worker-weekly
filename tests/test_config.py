""".env 解析与配置加载测试."""

from __future__ import annotations

import pytest

from worker_reminder.config import _load_env_file, _parse_env_line


@pytest.mark.parametrize("line,expected", [
    ("DOT_API_KEY=abc", ("DOT_API_KEY", "abc")),
    ("export DOT_API_KEY=abc", ("DOT_API_KEY", "abc")),
    ("export  DOT_API_KEY = abc", ("DOT_API_KEY", "abc")),
    ("DOT_API_KEY = abc # 行尾注释", ("DOT_API_KEY", "abc")),
    ("KEY=\"v # 引号内不算注释\"", ("KEY", "v # 引号内不算注释")),
    ("A=b # c", ("A", "b")),
    ("# 整行注释", None),
    ("", None),
    ("NOVALUE", None),
    ("=value", None),
])
def test_parse_env_line(line: str, expected) -> None:
    assert _parse_env_line(line) == expected


def test_load_env_file_parses_and_does_not_override(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        'LR_A=1\nexport LR_B=2 # x\nLR_C="3" # y\n# 注释\n\nLR_D=4\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("LR_A", "existing")
    _load_env_file(env)
    assert __import__("os").environ["LR_A"] == "existing"
    assert __import__("os").environ["LR_B"] == "2"
    assert __import__("os").environ["LR_C"] == "3"
    assert __import__("os").environ["LR_D"] == "4"


def test_load_env_file_missing_is_noop(tmp_path) -> None:
    _load_env_file(tmp_path / "not-exists.env")  # 不应抛异常
