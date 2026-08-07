"""表情包图片管线：GIF → 黑白二值 PNG → base64 data URI.

素材特征（已实测）：pic/ 下 240×240 单帧静态图、P 调色板模式、
透明背景（transparency 索引各异）的黑白调贴纸表情包。

取图模式：
  random — 按周几从分组文件夹（周一周二/周三/周四/周五周六周日）按当天日期确定性随机抽一张
  fixed  — 固定顶层单日文件 pic/周一.GIF（旧行为）
"""

from __future__ import annotations

import base64
import io
import random
from pathlib import Path

from PIL import Image, ImageOps

from .slogans import weekday_name
from .timeutil import beijing_today

# 贴到屏幕上的目标尺寸（与 layout.py / render_card.py 保持一致）
MEME_SIZE = 112

# 二值化阈值（bw 硬阈值与 fs/归一化共用同一边界，灰值 127 以下为黑）
THRESHOLD = 127

# 周几 → 分组文件夹（random 模式）：周一/周二共用一个文件夹，以此类推
MEME_GROUP_DIRS = {
    0: "周一周二",
    1: "周一周二",
    2: "周三",
    3: "周四",
    4: "周五周六周日",
    5: "周五周六周日",
    6: "周五周六周日",
}
_MEME_EXTS = {".gif", ".png", ".jpg", ".jpeg"}


class ImageError(Exception):
    """表情包加载/处理失败。"""


def process_meme(src: Path, size: int = MEME_SIZE, treatment: str = "bw") -> Image.Image:
    """把表情包 GIF 处理成贴到白底上的黑白图。

    treatment:
      bw  — 硬阈值二值化（默认）
      fs  — Floyd-Steinberg 抖动（convert("1")，Pillow 确定性算法）
      4level — 四级灰阶映射（名义灰阶，真机渲染为二进制，仅供对比）
    """
    try:
        im = Image.open(src)
    except (OSError, ValueError) as e:
        raise ImageError(f"无法打开表情包 {src}: {e}") from e

    im = im.convert("RGBA")

    # 透明背景合成到白底（设备屏幕是白底黑字）
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert("L")
    im = ImageOps.autocontrast(im, cutoff=1)

    # 目标尺寸缩小（先缩放再二值化，保留细节）
    im = im.resize((size, size), Image.LANCZOS)

    if treatment == "bw":
        im = im.point(lambda x: 255 if x > THRESHOLD else 0)
    elif treatment == "4level":
        # 真四级灰阶 {0,85,170,255}（仅预览对比用，真机 1-bit 渲染为二进制）
        im = im.point(lambda x: (0, 85, 170, 255)[min(x * 4 // 255, 3)])
    else:  # fs
        im = im.convert("1")

    # bw/fs 归一化到严格 0/255 灰度（设备 img-levels-2 无歧义显示）；
    # 4level 保留四级灰阶供对比图展示
    if treatment in ("bw", "fs"):
        im = im.convert("L").point(lambda x: 255 if x > THRESHOLD else 0)
    return im


def pick_meme_src(weekday: int, pic_dir: Path = Path("pic"), mode: str = "random") -> Path:
    """按模式挑表情包源文件路径。

    random — 从分组文件夹（周一周二/周三/周四/周五周六周日）抽一张：
             以当天日期 + 周几为随机种子（同一天内结果稳定，便于 dry-run 对比），
             文件夹缺失/为空时回退 fixed。
    fixed  — 固定顶层单日文件 pic/周一.GIF。
    """
    if mode == "random":
        group = pic_dir / MEME_GROUP_DIRS[weekday]
        try:
            files = sorted(p for p in group.iterdir() if p.suffix.lower() in _MEME_EXTS)
        except OSError:
            files = []
        if files:
            rng = random.Random(f"{beijing_today().isoformat()}-{weekday}")
            return rng.choice(files)
    return pic_dir / f"{weekday_name(weekday)}.GIF"


def meme_png_bytes(weekday: int, pic_dir: Path = Path("pic"), treatment: str = "bw",
                   mode: str = "random") -> bytes:
    """返回某周几表情包的 PNG bytes（已二值化）。"""
    im = process_meme(pick_meme_src(weekday, pic_dir, mode), treatment=treatment)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def meme_data_uri(weekday: int, pic_dir: Path = Path("pic"), treatment: str = "bw",
                  mode: str = "random") -> str:
    """返回 data:image/png;base64,... URI（Canvas 模式 img src）。"""
    return "data:image/png;base64," + base64.b64encode(
        meme_png_bytes(weekday, pic_dir, treatment, mode)
    ).decode("ascii")
