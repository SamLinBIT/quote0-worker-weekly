"""payload 结构 / 端点选择 / 文案种子 / 假期 / 二值化 的核心测试.

重点回归 H1/H2：image 模式的 payload 必须含 image 键（走 push_image），
canvas 模式与错误卡 payload 必须含 windowData（走 push_canvas），
不能把 DSL 发到 /image 端点。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from worker_reminder.config import Config
from worker_reminder.holidays import footer_text, year_progress_dots
from worker_reminder.layout import build_canvas_payload, build_image_payload
from worker_reminder.main import _push
from worker_reminder.slogans import DAY_PHRASES, WEEKDAY_NAMES, slogan_for

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXED_MEME = PROJECT_ROOT / "pic" / "周一.GIF"

HAS_MEME = FIXED_MEME.is_file()

_CFG = Config(dot_api_key="test-key", dot_device_id="test-device")


# --- payload 结构 ----------------------------------------------------

def test_image_payload_has_image_key() -> None:
    payload = build_image_payload(png_data_uri="data:image/png;base64,AAAA")
    assert payload["image"].startswith("data:image/png;base64,")
    assert payload["ditherType"] == "NONE"
    assert "windowData" not in payload  # Image API 不收 DSL


def test_canvas_payload_has_window_data() -> None:
    payload = build_canvas_payload(line1="周一周一", line2="奄奄一息",
                                   meme_uri="data:image/png;base64,AAAA")
    assert "windowData" in payload
    assert payload["taskAlias"] == "打工人周历"
    assert "image" not in payload


def test_error_payload_is_canvas_dsl() -> None:
    # 错误卡（image 或 canvas 模式）都是 canvas DSL → 走 push_canvas
    for payload in (
        build_image_payload(png_data_uri="", error_message="boom"),
        build_canvas_payload(line1="", line2="", meme_uri="", error_message="boom"),
    ):
        assert "windowData" in payload
        assert "image" not in payload


# --- H1/H2 回归：payload 类型 → 端点 ---------------------------------

def test_push_image_payload_goes_to_push_image(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("worker_reminder.main.push_image",
                        lambda *a: calls.append("image") or "ok")
    monkeypatch.setattr("worker_reminder.main.push_canvas",
                        lambda *a: calls.append("canvas") or "ok")
    payload = build_image_payload(png_data_uri="data:image/png;base64,AAAA")
    assert _push(payload, _CFG) == 0
    assert calls == ["image"]


@pytest.mark.parametrize("payload", [
    build_canvas_payload(line1="周一周一", line2="奄奄一息",
                         meme_uri="data:image/png;base64,AAAA"),
    build_image_payload(png_data_uri="", error_message="boom"),  # 错误卡也是 canvas DSL
])
def test_canvas_payload_goes_to_push_canvas(monkeypatch, payload) -> None:
    calls: list[str] = []
    monkeypatch.setattr("worker_reminder.main.push_image",
                        lambda *a: calls.append("image") or "ok")
    monkeypatch.setattr("worker_reminder.main.push_canvas",
                        lambda *a: calls.append("canvas") or "ok")
    assert _push(payload, _CFG) == 0
    assert calls == ["canvas"]


# --- 文案 -------------------------------------------------------------

def test_slogan_seed_stable_same_day() -> None:
    assert slogan_for(2) == slogan_for(2)


def test_slogan_weekday_names_and_phrase_pools() -> None:
    for w in range(7):
        line1, line2 = slogan_for(w)
        assert line1 == WEEKDAY_NAMES[w] * 2
        assert line2 in DAY_PHRASES[w]


# --- 假期与进度 -------------------------------------------------------

def test_year_progress_dots() -> None:
    assert year_progress_dots(date(2026, 8, 7)) == [True] * 8 + [False] * 4


def test_footer_text_countdown() -> None:
    # 2026 中秋 9/25：9/1 → 24 天后
    assert footer_text(date(2026, 9, 1)) == "2026-09-01 · 距中秋还有24天"


def test_footer_text_today_is_holiday() -> None:
    assert footer_text(date(2026, 1, 1)) == "2026-01-01 · 今天元旦!"


def test_holiday_dates_match_state_council_2026() -> None:
    # 口径=放假第一天，与国办发明电〔2025〕7号一致：春节 2/15（非正月初一 2/17）、清明 4/4（非 4/5）
    from worker_reminder.holidays import FESTIVALS

    assert dict(FESTIVALS[2026]) == {"春节": (2, 15), "清明": (4, 4),
                                     "端午": (6, 19), "中秋": (9, 25)}
    assert footer_text(date(2026, 2, 10)) == "2026-02-10 · 距春节还有5天"


def test_fixed_solar_holidays_auto_generated() -> None:
    # 元旦/劳动节/国庆 固定公历节日无需入表，2026 表里没有也要能倒计时
    from worker_reminder.holidays import FESTIVALS

    assert ("劳动节", (5, 1)) not in FESTIVALS[2026]
    assert footer_text(date(2026, 5, 1)) == "2026-05-01 · 今天劳动节!"


def test_holidays_table_sorted_and_valid() -> None:
    from worker_reminder import holidays

    for year, entries in holidays.FESTIVALS.items():
        for name, (month, day) in entries:
            date(year, month, day)  # 非法日期会抛 ValueError
        dates = [d for _, d in entries]
        assert dates == sorted(dates), f"{year} 未按日期升序"
        assert len(dates) == len(set(dates)), f"{year} 有重复日期"


def test_next_holiday_cross_year_missing_table(monkeypatch, capsys) -> None:
    from worker_reminder import holidays

    monkeypatch.setattr(holidays, "_warned_missing_year", False)
    # 2026 年内手工节日已过完 → 固定节日元旦顶上；2027 无手工表 → 告警一次
    assert holidays.next_holiday(date(2026, 12, 31)) == ("元旦", 1)
    assert footer_text(date(2026, 12, 31)) == "2026-12-31 · 距元旦还有1天"
    out = capsys.readouterr().out
    assert "缺少 2027" in out
    assert "WARN" in out


def test_next_holiday_without_manual_table() -> None:
    # 2027 只有固定节日：1/2 → 下一个是劳动节
    assert footer_text(date(2027, 1, 2)) == "2027-01-02 · 距劳动节还有119天"


def test_next_holiday_after_last_holiday_within_year() -> None:
    # 国庆后 → 下一年元旦顶上（10/2 → 2027-01-01 共 91 天）
    from worker_reminder.holidays import next_holiday

    assert next_holiday(date(2026, 10, 2)) == ("元旦", 91)


# --- 二值化 -----------------------------------------------------------

@pytest.mark.skipif(not HAS_MEME, reason="pic/周一.GIF 素材缺失")
def test_process_meme_bw_is_strict_binary() -> None:
    from worker_reminder.image_utils import process_meme

    im = process_meme(FIXED_MEME, treatment="bw")
    assert set(im.tobytes()) <= {0, 255}


@pytest.mark.skipif(not HAS_MEME, reason="pic/周一.GIF 素材缺失")
def test_process_meme_4level_differs_from_bw() -> None:
    from worker_reminder.image_utils import process_meme

    bw = process_meme(FIXED_MEME, treatment="bw")
    four = process_meme(FIXED_MEME, treatment="4level")
    assert set(four.tobytes()) <= {0, 85, 170, 255}
    assert bw.tobytes() != four.tobytes()
