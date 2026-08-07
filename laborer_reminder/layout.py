"""Canvas API windowData JSON builder for 296x152 e-ink screen.

基于参考项目 quote0-deepseek-balance/deepseek_balance/layout.py 的
_element() DSL 与 payload 结构，改为打工人周历卡片：
垂直三段式 — 顶部 12 个月进度圆点 / 中部左表情包右两行大字 / 底部日期假期小字。

上下边距各 8px（px-[4px] py-[8px]）；表情包保持 112 不变：
顶行 -mb-[2px]、底行 -mt-[2px] 把文字少量叠进表情包上下空白，
两处小字用 leading-[1] 固定行高（与 render_card.py 的 PAD_Y/TOP_PULL/BOTTOM_PULL 对应）。
顶行带 zIndex 置顶，文字画在表情包上层（Pillow 侧对应"先贴表情包、后画顶部行"）。
"""

from __future__ import annotations

from typing import Any

TASK_ALIAS = "打工人周历"


def _element(
    el_type: str,
    tw: str = "",
    style: dict[str, Any] | None = None,
    children: Any = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build a Canvas element dict."""
    props: dict[str, Any] = {}
    if tw:
        props["tw"] = tw
    if style:
        props["style"] = style
    if children is not None:
        props["children"] = children
    props.update(extra)
    return {"type": el_type, "props": props}


def _dot_element(filled: bool) -> dict[str, Any]:
    """一个月进度圆点：实心黑 / 空心白底黑描边（style 静态 CSS 保证支持）。"""
    style = {"width": "8px", "height": "8px", "borderRadius": "50%"}
    if filled:
        style["backgroundColor"] = "black"
    else:
        style["backgroundColor"] = "white"
        style["border"] = "1px solid black"
    return _element("div", style=style)


def build_canvas_payload(
    *,
    line1: str,
    line2: str,
    meme_uri: str,
    dots: list[bool] | None = None,
    progress_label: str = "",
    footer: str = "",
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build the complete Canvas API request payload for a laborer card.

    line1/line2: 两行大字；meme_uri: 表情包 data URI；
    dots: 12 个月进度圆点；progress_label: 顶部标签；footer: 底部信息行。
    """
    if error_message:
        return _build_error_payload(error_message)

    right_children = [
        _element("div",
            tw="text-32-chillksans leading-[1]",
            style={
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            children=line1,
        ),
        _element("div",
            tw="text-32-chillksans leading-[1]",
            style={
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            children=line2,
        ),
    ]

    window_data = {
        "default": [
            _element("div",
                tw="flex flex-col w-full h-full min-w-0 min-h-0 bg-white text-black",
                children=[
                    # Top: progress label + 12 month dots (whole row centered)
                    # -mb-[2px] 与 render_card TOP_PULL 对应：文字下探进表情包上空白；
                    # zIndex 置顶 → 文字画在表情包上层（不被表情包盖住）
                    _element("div",
                        tw="flex flex-row items-center justify-center gap-[4px] shrink-0 -mb-[2px]",
                        style={"zIndex": 1},
                        children=[
                            _element("span", tw="text-14-chillksans leading-[1]", children=progress_label),
                            *[_dot_element(f) for f in (dots if dots else [])],
                        ],
                    ),
                    # Middle: meme + two big lines
                    _element("div",
                        tw="flex flex-row flex-1 min-h-0 gap-[6px]",
                        children=[
                            _element("div",
                                tw="flex flex-col items-center justify-center w-[112px] h-full shrink-0",
                                children=[
                                    _element("img",
                                        tw="w-[112px] h-[112px] img-dither-none img-levels-2",
                                        src=meme_uri,
                                    ),
                                ],
                            ),
                            _element("div",
                                tw="flex flex-col flex-1 min-w-0 justify-center gap-[2px]",
                                children=right_children,
                            ),
                        ],
                    ),
                    # Bottom: date + next holiday info (centered)
                    # -mt-[2px] 与 render_card BOTTOM_PULL 对应：footer 上探进表情包下空白
                    _element("div",
                        tw="text-14-chillksans leading-[1] shrink-0 w-full -mt-[2px]",
                        style={
                            "textAlign": "center",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        },
                        children=footer,
                    ),
                ],
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": TASK_ALIAS,
        "border": 0,
        "link": "https://www.mindreset.tech/",
        "layoutFull": {"tw": "px-[4px] py-[8px]"},
        "windowData": window_data,
    }


def build_image_payload(
    *,
    png_data_uri: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build the Image API request payload (整卡 296×152 PNG 直推).

    ditherType: NONE — 本地已做严格 0/255 二值化，设备端不再抖动保锐利。
    """
    if error_message:
        # Image API 没有 DSL，错误态直接复用 canvas 错误卡
        return build_canvas_payload(line1="", line2="", meme_uri="", error_message=error_message)

    return {
        "refreshNow": True,
        "image": png_data_uri,
        "taskAlias": TASK_ALIAS,
        "border": 0,
        "ditherType": "NONE",
    }


def _build_error_payload(error_message: str) -> dict[str, Any]:
    """Build an error-state Canvas payload to show on the device."""
    window_data = {
        "default": [
            _element("div",
                tw="flex flex-col w-full h-full min-w-0 min-h-0 bg-white text-black justify-center p-[12px] gap-[4px]",
                children=[
                    _element("div",
                        tw="text-18-chillksans font-bold",
                        children="✗ 打工人周历 出错了",
                    ),
                    _element("div",
                        tw="text-14-chillksans",
                        style={
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "pre-wrap",
                            "wordBreak": "break-word",
                            "lineClamp": 4,
                        },
                        children=error_message,
                    ),
                ],
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": TASK_ALIAS,
        "border": 0,
        "link": "https://www.mindreset.tech/",
        "layoutFull": {"tw": "p-[4px]"},
        "windowData": window_data,
    }
