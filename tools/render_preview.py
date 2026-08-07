#!/usr/bin/env python3
"""渲染 7 张设计样式预览图（4× 放大）+ 周一三种二值化 treatment 对比图.

用法:
    uv run python tools/render_preview.py                # 全部默认
    uv run python tools/render_preview.py --treatment bw # 硬阈值处理
    uv run python tools/render_preview.py --meme-mode fixed  # 表情包固定单日文件（默认分组随机）
    uv run python tools/render_preview.py --scale 4      # 放大 4× 查看（默认 1×=屏幕分辨率）
输出: preview/周一.png ~ 周日.png（默认 296×152 设备分辨率）; preview/_对比_周一.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image  # noqa: E402

from laborer_reminder.holidays import footer_text, year_progress_dots  # noqa: E402
from laborer_reminder.image_utils import pick_meme_src, process_meme  # noqa: E402
from laborer_reminder.render_card import CARD_H, CARD_W, render_card_png  # noqa: E402
from laborer_reminder.slogans import slogan_for, weekday_name  # noqa: E402
from laborer_reminder.timeutil import beijing_today  # noqa: E402

SCALE = 1  # 默认设备原生分辨率 296×152；--scale 4 可放大查看
OUT_DIR = PROJECT_ROOT / "preview"
PIC_DIR = PROJECT_ROOT / "pic"


def render_all(treatment: str, scale: int, meme_mode: str = "random") -> None:
    today = beijing_today()
    dots = year_progress_dots(today)
    progress_label = f"{today.year}年进度："
    footer = footer_text(today)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for weekday in range(7):
        line1, line2 = slogan_for(weekday)
        meme = process_meme(pick_meme_src(weekday, PIC_DIR, meme_mode), treatment=treatment)
        card = render_card_png(line1, line2, meme, dots=dots,
                               progress_label=progress_label, footer=footer, scale=scale)
        out = OUT_DIR / f"{weekday_name(weekday)}.png"
        card.save(out)
        print(f"  {out}  ({CARD_W * scale}x{CARD_H * scale})  {line1} / {line2}")


def render_treatment_compare(weekday: int = 0, meme_mode: str = "random") -> None:
    """周一表情包三种处理并排对比（fs / bw / 4level），各 240×240 间隔 12。"""
    line1, line2 = slogan_for(weekday)
    name = weekday_name(weekday)
    labels = ("fs Floyd-Steinberg", "bw 硬阈值", "4level 四级灰阶")
    cell = 240
    gap = 12
    total = cell * 3 + gap * 4
    strip = Image.new("L", (total, cell + 30), 255)
    from PIL import ImageDraw, ImageFont

    from laborer_reminder.render_card import load_font
    draw = ImageDraw.Draw(strip)
    font = load_font(20)
    for i, (t, label) in enumerate(zip(("fs", "bw", "4level"), labels)):
        meme = process_meme(pick_meme_src(weekday, PIC_DIR, meme_mode), size=cell, treatment=t)
        strip.paste(meme, (gap + i * (cell + gap), 0))
        draw.text((gap + i * (cell + gap), cell + 4), label, font=font, fill=0)
    out = OUT_DIR / f"_对比_{name}.png"
    strip.save(out)
    print(f"  {out}  (三 treatment 对比: {line1} / {line2})")


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染打工人周历设计样式预览图")
    parser.add_argument("--treatment", choices=["fs", "bw", "4level"], default="bw",
                        help="表情包二值化方式 (默认 bw 硬阈值)")
    parser.add_argument("--meme-mode", choices=["fixed", "random"], default="random",
                        help="表情包来源 (默认 random 分组随机)")
    parser.add_argument("--scale", type=int, default=SCALE, help="放大倍数 (默认 1=设备分辨率)")
    parser.add_argument("--no-compare", action="store_true", help="跳过周一对比图")
    args = parser.parse_args()
    if args.scale <= 0:
        print(f"[ERROR] --scale 必须为正整数（收到 {args.scale}）", file=sys.stderr)
        return 1

    print(f"渲染 {args.treatment} × {args.meme_mode} × {args.scale}x ...")
    render_all(args.treatment, args.scale, args.meme_mode)
    if not args.no_compare:
        render_treatment_compare(meme_mode=args.meme_mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
