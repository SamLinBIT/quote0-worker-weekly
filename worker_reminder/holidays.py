"""法定假期表 + 全年进度圆点.

假期日期以国务院办公厅年度放假安排为准，手工维护：
- 元旦(1/1) / 劳动节(5/1) / 国庆(10/1) 是固定公历节日，代码自动生成，无需入表；
- 春节/清明/端午/中秋 按公告逐年填入 FESTIVALS（跨年后需人工补充）。

缺下一年手工表时 next_holiday 只告警一次：固定节日倒计时仍可用，
农历节日停用、footer 只显示日期。每年用 tools/update_holidays.py
生成骨架后按公告补填即可（国务院安排通常前一年 11 月发布）。
"""

from __future__ import annotations

from datetime import date

# 固定公历节日（法定日期，不随年度安排变化）
_FIXED_SOLAR_HOLIDAYS: tuple[tuple[str, int, int], ...] = (
    ("元旦", 1, 1),
    ("劳动节", 5, 1),
    ("国庆", 10, 1),
)

# 农历/节气节日（年份 → [(名称, (月, 日)), ...]，按日期升序，手工按公告维护）。
# 口径：记录"放假第一天"（与国务院通知一致，如 2026 春节 2/15、清明 4/4）
FESTIVALS: dict[int, list[tuple[str, tuple[int, int]]]] = {
    2026: [
        ("春节", (2, 15)),
        ("清明", (4, 4)),
        ("端午", (6, 19)),
        ("中秋", (9, 25)),
    ],
}


def year_holidays(year: int) -> list[tuple[str, tuple[int, int]]]:
    """当年全部假期（固定公历 + 手工表），按日期升序。"""
    fixed = [(name, (month, day)) for name, month, day in _FIXED_SOLAR_HOLIDAYS]
    return sorted(fixed + FESTIVALS.get(year, []), key=lambda item: item[1])


def year_progress_dots(today: date) -> list[bool]:
    """12 个月进度圆点：已过的月份（含当前月）实心 True，未来空心 False。"""
    return [m <= today.month for m in range(1, 13)]


_warned_missing_year = False


def next_holiday(today: date) -> tuple[str, int] | None:
    """返回 (下一个法定假期名称, 距离天数)。年内没有则查下一年（需有表）。"""
    global _warned_missing_year
    if today.year + 1 not in FESTIVALS and not _warned_missing_year:
        _warned_missing_year = True
        print(f"[WARN] holidays.py 缺少 {today.year + 1} 年的手工假期表，"
              "春节/清明/端午/中秋 倒计时停用"
              "（用 tools/update_holidays.py 生成骨架后按国务院安排补填）")
    for year in (today.year, today.year + 1):
        for name, (month, day) in year_holidays(year):
            h = date(year, month, day)
            if h >= today:
                return name, (h - today).days
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
