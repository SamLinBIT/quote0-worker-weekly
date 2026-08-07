"""周几文案表 — 打工人精神状态一览.

前半句固定为"周X周X"（当天周几），后半句从当天文案池随机抽一句
（以当天日期+周几为种子，同一天内稳定，便于 dry-run 对比）。
"""

from __future__ import annotations

import random

from .timeutil import beijing_today

# index = date.weekday(), 0 = 周一
WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 每天的后半句池（原 A/B 两版合并，按周几分池）
DAY_PHRASES: dict[int, tuple[str, ...]] = {
    0: ("奄奄一息", "惨惨戚戚", "呆若木鸡"),
    1: ("命剩一半", "苦忧参半", "魂散一半"),
    2: ("三座大山", "续命上班", "心情一般", "两眼一翻"),
    3: ("重见天日", "差点逝世", "逐渐放肆"),
    4: ("眉飞色舞", "敲锣打鼓", "生龙活虎"),
    5: ("假装很秀"),
    6: ("死期将至", "悲伤度日"),
}


def slogan_for(weekday: int) -> tuple[str, str]:
    """返回 (第一行, 第二行)：前半句"周X周X"，后半句从当天池子随机抽（同日稳定）。"""
    rng = random.Random(f"{beijing_today().isoformat()}-slogan-{weekday}")
    return WEEKDAY_NAMES[weekday] * 2, rng.choice(DAY_PHRASES[weekday])


def weekday_name(weekday: int) -> str:
    """周几汉字名（用于 pic 文件夹 / 预览文件名）。"""
    return WEEKDAY_NAMES[weekday]
