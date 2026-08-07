#!/usr/bin/env python3
"""假期表维护工具：校验现有表 / 抓取国务院安排 / 生成骨架.

假期以国务院办公厅年度放假安排为准。数据源为 GitHub 开源项目
NateScarlet/holiday-cn（自动每日抓取国务院公告，数据带 papers 官方原文
链接可溯源）：元旦/劳动节/国庆为固定公历节日（自动生成，无需入表）；
春节/清明/端午/中秋 按公告补填 FESTIVALS。

用法:
    uv run python tools/update_holidays.py                      # 校验 + 打印缺失年份骨架
    uv run python tools/update_holidays.py --check              # 只校验
    uv run python tools/update_holidays.py --fetch              # 抓取下一年国务院安排并打印
    uv run python tools/update_holidays.py --fetch --year 2026  # 抓取指定年份
    uv run python tools/update_holidays.py --fetch --apply      # 抓取并直接写入 holidays.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from worker_reminder import holidays  # noqa: E402

# 需维护的节日（按国务院公告补填），与 FESTIVALS 注释一致
_MANUAL_FESTIVALS = ("春节", "清明", "端午", "中秋")

# holiday-cn 数据里的节日名 → 项目表里的名字
_HOLIDAY_CN_NAMES = {
    "春节": "春节",
    "清明节": "清明",
    "端午节": "端午",
    "中秋节": "中秋",
}

# 固定公历节日（sanity 校验用）：数据里应有且首日固定
_FIXED_SOLAR_STARTS = {"元旦": (1, 1), "劳动节": (5, 1), "国庆节": (10, 1)}

_CDN_URL = "https://fastly.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json"

_HOLIDAYS_PY = PROJECT_ROOT / "worker_reminder" / "holidays.py"


def _validate() -> int:
    errors = 0
    for year, entries in holidays.FESTIVALS.items():
        for name, (month, day) in entries:
            try:
                date(year, month, day)
            except ValueError as e:
                print(f"[ERROR] {year} {name}: {e}")
                errors += 1
        dates = [d for _, d in entries]
        if dates != sorted(dates):
            print(f"[ERROR] {year} 假期表未按日期升序")
            errors += 1
        if len(dates) != len(set(dates)):
            print(f"[ERROR] {year} 假期表有重复日期")
            errors += 1
    if errors:
        print(f"共 {errors} 处错误")
        return 1
    print(f"[OK] 现有假期表校验通过（{len(holidays.FESTIVALS)} 年）")
    return 0


def _skeleton(year: int) -> str:
    lines = [f"    {year}: ["]
    for name in _MANUAL_FESTIVALS:
        lines.append(f'        ("{name}", (?, ?)),  # TODO: 按国务院安排补填')
    lines.append("    ],")
    return "\n".join(lines)


def extract_holiday_starts(days: list[dict]) -> dict[str, tuple[int, int]]:
    """从 holiday-cn days 提取各节日放假第一天（isOffDay=true 的最早日期）。

    补班日（name 含"上班"）isOffDay=false 会被自然排除；返回项目表
    用名 → (月, 日)，按日期升序。固定节日也一并返回供 sanity 校验。
    """
    starts: dict[str, date] = {}
    for item in days:
        if not item.get("isOffDay"):
            continue
        name = item.get("name", "")
        if not name or "上班" in name:
            continue
        try:
            day = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if name not in starts or day < starts[name]:
            starts[name] = day
    return {n: (d.month, d.day) for n, d in sorted(starts.items(), key=lambda kv: kv[1])}


def fetch_holiday_days(year: int, timeout: float = 15.0) -> dict:
    """抓取 holiday-cn 某年 JSON（含 papers/days）。失败抛 OSError/ValueError。"""
    url = _CDN_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": "quote0-worker-weekly/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _entries_block(year: int, entries: list[tuple[str, tuple[int, int]]]) -> str:
    lines = [f"    {year}: ["]
    for name, (month, day) in entries:
        lines.append(f'        ("{name}", ({month}, {day})),')
    lines.append("    ],")
    return "\n".join(lines)


def write_festivals_entry(holidays_py: Path, year: int,
                          entries: list[tuple[str, tuple[int, int]]]) -> None:
    """把某年的 FESTIVALS 条目写入 holidays.py（已存在则替换，否则追加到表尾）。"""
    text = holidays_py.read_text(encoding="utf-8")
    block = _entries_block(year, entries)
    pattern = re.compile(rf"^    {year}: \[\n.*?\n    \],$", re.MULTILINE | re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text, count=1)
    else:
        idx = text.rfind("\n}")
        if idx == -1:
            raise SystemExit("[ERROR] 找不到 FESTIVALS 表尾，未写入（请手工粘贴）")
        text = text[:idx] + "\n" + block + text[idx:]
    holidays_py.write_text(text, encoding="utf-8")


def _do_fetch(args) -> int:
    year = args.year or max(holidays.FESTIVALS) + 1
    print(f"抓取 {year} 年国务院安排（{_CDN_URL.format(year=year)}）...")
    try:
        data = fetch_holiday_days(year)
    except (OSError, ValueError) as e:
        print(f"[ERROR] 抓取失败: {e}")
        return 1

    if not data.get("days"):
        print(f"[INFO] {year} 年官方安排尚未发布（holiday-cn 数据为空），"
              "通常前一年 11 月发布，到时重试即可。")
        return 0

    starts = extract_holiday_starts(data["days"])

    missing = [cn for cn in _HOLIDAY_CN_NAMES if cn not in starts]
    if missing:
        print(f"[WARN] 数据里缺少节日首日: {missing}（可稍后重试或手工补填）")

    for cn_name, fixed in _FIXED_SOLAR_STARTS.items():
        got = starts.get(cn_name)
        if got != fixed:
            print(f"[WARN] 固定节日 {cn_name} 首日应为 {fixed}，数据给出 {got}，请人工核对")

    entries = [(name, starts[cn]) for cn, name in _HOLIDAY_CN_NAMES.items()
               if (starts.get(cn)) is not None]
    print()
    print(f"{year} 年国务院安排（放假第一天）：")
    print(_entries_block(year, entries))
    for paper in data.get("papers", []):
        print(f"  官方原文: {paper}")

    if args.apply:
        write_festivals_entry(_HOLIDAYS_PY, year, entries)
        print(f"[OK] 已写入 {_HOLIDAYS_PY}，运行 --check 验证")
    else:
        print()
        print("加 --apply 直接写入 holidays.py；或手工粘贴后跑 --check 验证。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="假期表维护：校验 / 抓取 / 生成骨架")
    parser.add_argument("--year", type=int, default=None,
                        help="年份（默认：现有表中最大年份的下一年）")
    parser.add_argument("--check", action="store_true", help="只校验，不打印")
    parser.add_argument("--fetch", action="store_true",
                        help="抓取 holiday-cn（自动每日抓国务院公告）的该年数据")
    parser.add_argument("--apply", action="store_true",
                        help="配合 --fetch：把抓到的条目直接写入 holidays.py")
    args = parser.parse_args()

    if _validate() != 0:
        return 1
    if args.fetch:
        return _do_fetch(args)
    if args.check:
        return 0

    year = args.year or max(holidays.FESTIVALS) + 1
    print()
    print(f"为 {year} 年生成骨架（元旦/劳动节/国庆自动生效，勿重复填入）：")
    print(_skeleton(year))
    print()
    print(f"把骨架填入 holidays.py FESTIVALS（替换 (?, ?)）后，{year} 年的"
          "春节/清明/端午/中秋 倒计时即恢复；或直接 --fetch 抓取国务院安排。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
