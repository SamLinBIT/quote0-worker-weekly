"""tools/update_holidays.py 的解析与写入逻辑测试（不联网）."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
spec = importlib.util.spec_from_file_location("update_holidays", TOOLS / "update_holidays.py")
assert spec and spec.loader
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


# --- extract_holiday_starts -------------------------------------------------

_DAYS_2026 = [
    {"name": "元旦", "date": "2026-01-01", "isOffDay": True},
    {"name": "元旦", "date": "2026-01-02", "isOffDay": True},
    {"name": "上班(补元旦假期)", "date": "2026-01-04", "isOffDay": False},
    {"name": "春节", "date": "2026-02-14", "isOffDay": False},  # 补班日
    {"name": "春节", "date": "2026-02-15", "isOffDay": True},
    {"name": "春节", "date": "2026-02-16", "isOffDay": True},
    {"name": "清明节", "date": "2026-04-04", "isOffDay": True},
    {"name": "劳动节", "date": "2026-05-01", "isOffDay": True},
    {"name": "端午节", "date": "2026-06-19", "isOffDay": True},
    {"name": "中秋节", "date": "2026-09-25", "isOffDay": True},
    {"name": "国庆节", "date": "2026-10-01", "isOffDay": True},
]


def test_extract_holiday_starts_first_off_day() -> None:
    starts = MOD.extract_holiday_starts(_DAYS_2026)
    # 春节取 2/15（补班 2/14 排除）；多天假期取第一天
    assert starts["春节"] == (2, 15)
    assert starts["清明节"] == (4, 4)
    assert starts["端午节"] == (6, 19)
    assert starts["中秋节"] == (9, 25)
    # 固定节日也可供 sanity 校验
    assert starts["元旦"] == (1, 1)
    assert starts["劳动节"] == (5, 1)
    assert starts["国庆节"] == (10, 1)


def test_extract_holiday_starts_ignores_malformed() -> None:
    days = [
        {"name": "春节", "date": "2026-02-15", "isOffDay": True},
        {"name": "春节", "date": "bad-date", "isOffDay": True},
        {"name": "春节", "date": "2026-02-16", "isOffDay": False},  # 非休息日排除
        {"name": "", "date": "2026-03-01", "isOffDay": True},       # 无名
        {"name": "上班(补春节假期)", "date": "2026-02-14", "isOffDay": True},  # 防御
    ]
    assert MOD.extract_holiday_starts(days) == {"春节": (2, 15)}


# --- write_festivals_entry --------------------------------------------------

_FESTIVALS_TEXT = (
    "FESTIVALS: dict[int, list[tuple[str, tuple[int, int]]]] = {\n"
    "    2026: [\n"
    '        ("春节", (2, 15)),\n'
    "    ],\n"
    "}\n"
)


def test_write_festivals_entry_replaces_existing(tmp_path) -> None:
    f = tmp_path / "holidays.py"
    f.write_text(_FESTIVALS_TEXT, encoding="utf-8")
    MOD.write_festivals_entry(f, 2026, [("春节", (2, 15)), ("清明", (4, 4)),
                                        ("端午", (6, 19)), ("中秋", (9, 25))])
    text = f.read_text(encoding="utf-8")
    assert '("春节", (2, 15)),' in text
    assert '("中秋", (9, 25)),' in text
    assert text.count("2026: [") == 1


def test_write_festivals_entry_appends_new_year(tmp_path) -> None:
    f = tmp_path / "holidays.py"
    f.write_text(_FESTIVALS_TEXT, encoding="utf-8")
    MOD.write_festivals_entry(f, 2027, [("春节", (2, 6))])
    text = f.read_text(encoding="utf-8")
    assert "2027: [" in text
    assert '("春节", (2, 6)),' in text
    assert text.index("2026: [") < text.index("2027: [")
    # 表尾结构未被破坏
    assert text.endswith("    ],\n}\n")
