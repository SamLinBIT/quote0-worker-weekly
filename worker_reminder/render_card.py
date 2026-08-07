"""整卡渲染：296×152 黑白卡片 PNG（Image API 模式 + 本地预览共用).

垂直三段式布局（与 layout.py 的 Canvas payload 严格对应）：

    顶部：12 个月进度圆点（实心=已过含当前月，空心=未来）
    中部：左表情包 + 右两行大字（垂直居中于核心区）
    底部：一行 12px 小字（日期 · 下一个法定假期还有 N 天）

上下边距各 8px；表情包保持 112 不变，
顶部/底部文字行通过负 margin（-mb/-mt 2px）少量叠进表情包上下空白。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CARD_W = 296
CARD_H = 152
PAD_X = 4
PAD_Y = 8  # 上下边距；左右保持 4

# --- 垂直分配（核心区 112 不压缩，表情包不变）---
# PAD_Y(8) + 顶行净占 12(14-2) + CORE_H(112) + 底行净占 12(14-2) + PAD_Y(8) = 152
TOP_ROW_H = 14     # 顶行 box（canvas leading-[1] 后 14px）
TOP_PULL = 2       # 顶行 -mb-[2px]：文字/圆点少量下探进表情包上空白
BOTTOM_ROW_H = 14
BOTTOM_PULL = 2    # 底行 -mt-[2px]：footer 少量上探进表情包下空白
CORE_Y0 = PAD_Y + TOP_ROW_H - TOP_PULL                       # = 20（表情包位置不变）
CORE_H = CARD_H - 2 * PAD_Y - (TOP_ROW_H - TOP_PULL) - (BOTTOM_ROW_H - BOTTOM_PULL)  # = 112

# --- 顶部：进度标签 + 12 个月圆点（水平居中）---
DOT_R = 4                # 圆点半径
DOT_GAP = 4              # 点间距
DOTS_W = 12 * 2 * DOT_R + 11 * DOT_GAP     # = 140
LABEL_SIZE = 14
DOTS_Y = PAD_Y + (TOP_ROW_H - 2 * DOT_R) // 2    # = 11（圆点与文字垂直居中）

# --- 底部：信息小字（水平居中）---
FOOTER_SIZE = 14
FOOTER_Y = CORE_Y0 + CORE_H - BOTTOM_PULL          # = 130（少量叠在表情包下空白）

# --- 中部核心区 ---
MEME_X = PAD_X
MEME_SIZE = 112
MEME_Y = CORE_Y0                                 # = 20（112 填满核心区）
RIGHT_X = MEME_X + MEME_SIZE + 6                # = 122
TEXT_SIZE = 32
TEXT_STROKE = 0  # 细字：与设备端 text-32（无 font-bold）保持一致
LINE_GAP = 2
BLOCK_H = TEXT_SIZE * 2 + LINE_GAP             # 两行文字块总高 66
LINE1_Y = CORE_Y0 + (CORE_H - BLOCK_H) // 2   # = 43
LINE2_Y = LINE1_Y + TEXT_SIZE + LINE_GAP      # = 77

_FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "ChillKSans.otf"


def load_font(size: int = TEXT_SIZE) -> ImageFont.FreeTypeFont:
    """加载 Chill K Sans（系统无中文字体，中文渲染必须用它）。"""
    return ImageFont.truetype(str(_FONT_PATH), size)


def _draw_dots(draw: ImageDraw.ImageDraw, dots: list[bool], x0: int, y0: int) -> None:
    """12 个月进度圆点：实心黑 / 空心白底黑描边。x0/y0 为第一点左上角。"""
    for i, filled in enumerate(dots):
        cx = x0 + i * (2 * DOT_R + DOT_GAP) + DOT_R
        box = (cx - DOT_R, y0, cx + DOT_R, y0 + 2 * DOT_R)
        if filled:
            draw.ellipse(box, fill=0)
        else:
            draw.ellipse(box, fill=255, outline=0, width=1)


def _draw_top_row(draw: ImageDraw.ImageDraw, label: str, dots: list[bool]) -> None:
    """顶部行：'2026年进度：' + 12 圆点，整行水平居中（dots 为空时只画 label）。"""
    label_font = load_font(LABEL_SIZE)
    label_w = int(draw.textlength(label, font=label_font)) if label else 0
    gap = 4 if label else 0
    dots_w = DOTS_W if dots else 0
    total_w = label_w + gap + dots_w
    x0 = (CARD_W - total_w) // 2
    if label:
        draw.text((x0, PAD_Y), label, font=label_font, fill=0)
    if dots:
        _draw_dots(draw, dots, x0 + label_w + gap, DOTS_Y)


def render_card_png(
    line1: str,
    line2: str,
    meme: Image.Image,
    dots: list[bool] | None = None,
    progress_label: str = "",
    footer: str = "",
    scale: int = 1,
) -> Image.Image:
    """渲染一张 296×152 黑白卡片，scale 放大（预览用，NEAREST 保持像素锐利）。

    dots: 12 个月进度圆点（True=实心）；progress_label: 顶部标签如 "2026年进度："；
    footer: 底部信息行（水平居中）。
    """
    card = Image.new("L", (CARD_W, CARD_H), 255)
    draw = ImageDraw.Draw(card)
    font = load_font(TEXT_SIZE)

    # 中部：左表情包 + 右两行大字（先贴表情包）
    card.paste(meme, (MEME_X, MEME_Y))
    draw.text((RIGHT_X, LINE1_Y), line1, font=font, fill=0,
              stroke_width=TEXT_STROKE, stroke_fill=0)
    draw.text((RIGHT_X, LINE2_Y), line2, font=font, fill=0,
              stroke_width=TEXT_STROKE, stroke_fill=0)

    # 顶部：进度标签 + 圆点（后画 → 叠在表情包上空白的上层，不被表情包盖住）
    _draw_top_row(draw, progress_label, dots if dots else [])

    # 底部：信息小字（居中，同样后画叠在表情包下空白）
    if footer:
        footer_font = load_font(FOOTER_SIZE)
        footer_w = int(draw.textlength(footer, font=footer_font))
        draw.text(((CARD_W - footer_w) // 2, FOOTER_Y), footer, font=footer_font, fill=0)

    if scale != 1:
        card = card.resize((CARD_W * scale, CARD_H * scale), Image.NEAREST)
    return card
