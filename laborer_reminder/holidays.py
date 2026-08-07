"""法定假期表 + 全年进度圆点.

假期为公历日期（节日当天），以国务院办公厅年度安排为准；
农历节日日期按年份手工维护，跨年后需补充新的一年。
"""

from __future__ import annotations

from datetime import date

# 年份 → [(名称, (月, 日)), ...]（按日期升序）
HOLIDAYS: dict[int, list[tuple[str, tuple[int, int]]]] = {
    2026: [
        ("元旦", (1, 1)),
        ("春节", (2, 17)),
        ("清明", (4, 5)),
        ("劳动节", (5, 1)),
        ("端午", (6, 19)),
        ("中秋", (9, 25)),
        ("国庆", (10, 1)),
    ],
}


def year_progress_dots(today: date) -> list[bool]:
    """12 个月进度圆点：已过的月份（含当前月）实心 True，未来空心 False。"""
    return [m <= today.month for m in range(1, 13)]


_warned_missing_year = False


def next_holiday(today: date) -> tuple[str, int] | None:
    """返回 (下一个法定假期名称, 距离天数)。年内没有则查下一年（需有表）。"""
    for year in (today.year, today.year + 1):
        for name, (month, day) in HOLIDAYS.get(year, []):
            h = date(year, month, day)
            if h >= today:
                return name, (h - today).days
    global _warned_missing_year
    if today.year + 1 not in HOLIDAYS and not _warned_missing_year:
        _warned_missing_year = True
        print(f"[WARN] holidays.py 缺少 {today.year + 1} 年的假期表，"
              "假期倒计时已停用（每年需按国务院安排补充）")
    return None


def footer_text(today: date) -> str:
    """底部信息行：如 '2026-08-06 · 距中秋还有50天'。"""
    date_part = f"{today:%Y-%m-%d}"
    holiday = next_holiday(today)
    if holiday is None:
        return date_part
    name, days = holiday
    if days == 0:
        return f"{date_part} · 今天{name}!"
    return f"{date_part} · 距{name}还有{days}天"
