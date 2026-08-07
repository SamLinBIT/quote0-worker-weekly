"""北京时区日期工具.

系统时区可能是 UTC，直接 date.today() 会取错"今天"（北京时间
0:00–7:59 之间会拿到昨天）。所有"当天"语义统一走这里，
wrapper 里的 export TZ 保留作兜底。
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

_BEIJING = ZoneInfo("Asia/Shanghai")


def beijing_today() -> date:
    """返回北京时间今天的日期（卡片文案/取图/进度共用）。"""
    return datetime.now(_BEIJING).date()
