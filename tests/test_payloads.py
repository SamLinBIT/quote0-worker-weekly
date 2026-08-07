"""payload 结构 / 端点选择 / 文案种子 / 假期 / 二值化 的核心测试.

重点回归 H1/H2：image 模式的 payload 必须含 image 键（走 push_image），
canvas 模式与错误卡 payload 必须含 windowData（走 push_canvas），
不能把 DSL 发到 /image 端点。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from laborer_reminder.config import Config
from laborer_reminder.holidays import footer_text, year_progress_dots
from laborer_reminder.layout import build_canvas_payload, build_image_payload
from laborer_reminder.main import _push
from laborer_reminder.slogans import DAY_PHRASES, WEEKDAY_NAMES, slogan_for

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
    assert payload["taskAlias"] == "打工人每周提醒"
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
    monkeypatch.setattr("laborer_reminder.main.push_image",
                        lambda *a: calls.append("image") or "ok")
    monkeypatch.setattr("laborer_reminder.main.push_canvas",
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
    monkeypatch.setattr("laborer_reminder.main.push_image",
                        lambda *a: calls.append("image") or "ok")
    monkeypatch.setattr("laborer_reminder.main.push_canvas",
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


# --- 二值化 -----------------------------------------------------------

@pytest.mark.skipif(not HAS_MEME, reason="pic/周一.GIF 素材缺失")
def test_process_meme_bw_is_strict_binary() -> None:
    from laborer_reminder.image_utils import process_meme

    im = process_meme(FIXED_MEME, treatment="bw")
    assert set(im.tobytes()) <= {0, 255}


@pytest.mark.skipif(not HAS_MEME, reason="pic/周一.GIF 素材缺失")
def test_process_meme_4level_differs_from_bw() -> None:
    from laborer_reminder.image_utils import process_meme

    bw = process_meme(FIXED_MEME, treatment="bw")
    four = process_meme(FIXED_MEME, treatment="4level")
    assert set(four.tobytes()) <= {0, 85, 170, 255}
    assert bw.tobytes() != four.tobytes()
