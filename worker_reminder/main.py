"""打工人周历 CLI 编排入口.

用法:
    uv run python -m worker_reminder.main               # 推送当天卡片（默认 Image API 整卡 PNG）
    uv run python -m worker_reminder.main --api canvas  # 用 Canvas API DSL
    uv run python -m worker_reminder.main --day 周一    # 指定周几（调试）
    uv run python -m worker_reminder.main --meme-mode fixed  # 表情包固定单日文件（默认分组随机）
    uv run python -m worker_reminder.main --dry-run     # 只打印 payload 不推送
    uv run python -m worker_reminder.main --preview     # 渲染设计样式预览图
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

from .config import load_config
from .dot_push import DotPushError, push_canvas, push_image
from .holidays import footer_text, year_progress_dots
from .image_utils import ImageError, meme_data_uri, pick_meme_src, process_meme
from .layout import build_canvas_payload, build_image_payload
from .render_card import render_card_png
from .slogans import WEEKDAY_NAMES, slogan_for, weekday_name
from .timeutil import beijing_today

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIC_DIR = PROJECT_ROOT / "pic"

WEEKDAY_TO_NAME = {w: name for w, name in enumerate(WEEKDAY_NAMES)}
NAME_TO_WEEKDAY = {name: w for w, name in WEEKDAY_TO_NAME.items()}


def parse_day(s: str) -> int:
    """接受 0-6 或 周一..周日 → weekday() 索引。"""
    if s in NAME_TO_WEEKDAY:
        return NAME_TO_WEEKDAY[s]
    try:
        w = int(s)
        if 0 <= w <= 6:
            return w
    except ValueError:
        pass
    print(f"[ERROR] --day 参数非法: {s}（接受 0-6 或 周一~周日）", file=sys.stderr)
    sys.exit(1)


def _meme_uri_or_error(weekday: int, treatment: str, mode: str) -> tuple[str | None, str | None]:
    """返回 (meme_uri, error_message)；失败时 error_message 非空。"""
    try:
        return meme_data_uri(weekday, PIC_DIR, treatment, mode), None
    except ImageError as e:
        return None, str(e)


def _render_image_data_uri(weekday: int, treatment: str, meme_mode: str,
                           dots: list[bool], progress_label: str, footer: str,
                           ) -> tuple[str | None, str | None]:
    """Image 模式：渲染整卡 296×152 PNG → data URI。失败返回 (None, error)。"""
    try:
        line1, line2 = slogan_for(weekday)
        meme = process_meme(pick_meme_src(weekday, PIC_DIR, meme_mode), treatment=treatment)
        card = render_card_png(line1, line2, meme, dots=dots,
                               progress_label=progress_label, footer=footer, scale=1)
        buf = io.BytesIO()
        card.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), None
    except ImageError as e:
        return None, str(e)


def _build_and_push(args, config) -> int:
    today = beijing_today()
    weekday = parse_day(args.day) if args.day else today.weekday()
    treatment = args.treatment or config.treatment
    meme_mode = args.meme_mode or config.meme_mode
    mode = args.api or config.push_mode
    if mode == "image" and treatment == "4level":
        # 4level 是预览对比专用灰阶，Image API + ditherType NONE 推到 1-bit
        # 设备会渲染异常，推送场景强制回退 bw
        print(f"[WARN] image 模式不支持 treatment=4level（仅预览用），已回退 bw")
        treatment = "bw"
    line1, line2 = slogan_for(weekday)
    name = weekday_name(weekday)
    dots = year_progress_dots(today)
    progress_label = f"{today.year}年进度："
    footer = footer_text(today)

    print(f"[{name}] {line1} / {line2}  mode={mode} meme={meme_mode} treatment={treatment}")
    print(f"  {progress_label}{sum(dots)}/12  footer={footer}")

    if mode == "image":
        uri, err = _render_image_data_uri(weekday, treatment, meme_mode,
                                          dots, progress_label, footer)
        if err:
            payload = build_image_payload(png_data_uri="", error_message=err)
            _emit(payload, args, "错误卡（image）")
            return 0 if args.dry_run else _push(payload, config)
        payload = build_image_payload(png_data_uri=uri)
        _emit(payload, args, f"Image API 整卡（{line1}/{line2}）")
    else:
        meme_uri, err = _meme_uri_or_error(weekday, treatment, meme_mode)
        if err:
            payload = build_canvas_payload(line1="", line2="", meme_uri="", error_message=err)
            _emit(payload, args, "错误卡（canvas）")
            return 0 if args.dry_run else _push(payload, config)
        payload = build_canvas_payload(line1=line1, line2=line2, meme_uri=meme_uri,
                                       dots=dots, progress_label=progress_label, footer=footer)
        _emit(payload, args, f"Canvas API（{line1}/{line2}）")

    return 0 if args.dry_run else _push(payload, config)


def _emit(payload: dict, args, label: str) -> None:
    if args.dry_run or args.verbose:
        print(f"--- payload: {label} ---")
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _push(payload: dict, config) -> int:
    """按 payload 内容选端点：含 image 键 → Image API，否则 Canvas API。

    （错误卡 payload 是 canvas DSL，无论模式都走 push_canvas；
     --api canvas + .env PUSH_MODE=image 也不会再把 DSL 发到 /image。）
    """
    try:
        if "image" in payload:
            msg = push_image(config.dot_api_key, config.dot_device_id, payload)
        else:
            msg = push_canvas(config.dot_api_key, config.dot_device_id, payload)
    except DotPushError as e:
        print(f"[ERROR] 推送失败: {e}")
        return 1
    print(f"✓ 推送成功: {msg}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="打工人周历 — 推送当天卡片到 Dot Quote/0")
    parser.add_argument("--api", choices=["canvas", "image"], default=None,
                        help="推送模式，覆盖 .env PUSH_MODE（默认 image）")
    parser.add_argument("--day", default=None, help="指定周几（0-6 或 周一~周日），默认今天")
    parser.add_argument("--treatment", choices=["bw", "fs", "4level"], default=None,
                        help="表情包二值化方式，覆盖 .env TREATMENT（默认 bw 硬阈值）")
    parser.add_argument("--meme-mode", choices=["fixed", "random"], default=None,
                        help="表情包来源：random=按周几从分组文件夹随机（默认）| fixed=顶层单日文件")
    parser.add_argument("--dry-run", action="store_true", help="只打印 payload 不推送")
    parser.add_argument("--verbose", action="store_true", help="打印 payload")
    parser.add_argument("--preview", action="store_true", help="渲染设计样式预览图后退出")
    args = parser.parse_args()

    if args.preview:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        from render_preview import main as preview_main

        # render_preview 的 parser 不认识 --preview，剥掉后再转发其余参数（如 --scale 4）
        sys.argv = [a for a in sys.argv if a != "--preview"]
        return preview_main()

    config = load_config(require_keys=not args.dry_run)
    return _build_and_push(args, config)


if __name__ == "__main__":
    sys.exit(main())
