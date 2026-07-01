"""Date parsing and stable timestamps for feeds without published dates."""
import hashlib
import re
from datetime import datetime, timedelta, timezone


def parse_date(s: str | None) -> datetime | None:
    """简单解析常见日期格式."""
    if not s:
        return None
    s = s.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",  # 2026-06-26T07:30:05.000-07:00
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",  # March 13, 2026
        "%b %d, %Y",  # Feb 05, 2026
        "%B %Y",  # June 2017（标题中常见）
        "%b %Y",  # Jun 2017
        "%a, %d %b %Y %H:%M:%S %z",
    ):
        try:
            dt = datetime.strptime(s.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def parse_date_from_title(title: str) -> datetime | None:
    """从标题中尝试解析日期（如 "Policy announcement: June 2017" / "January 28, 2020"），用于无 published 的源。"""
    if not title or not title.strip():
        return None
    for pattern, fmt in (
        (
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}",
            "%B %d, %Y",
        ),
        (
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4}",
            "%b %d, %Y",
        ),
        (
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
            "%B %Y",
        ),
        (
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
            "%b %Y",
        ),
    ):
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            dt = parse_date(m.group(0).strip())
            if dt:
                return dt
    return None


def stable_date_from_entries(entries: list) -> datetime | None:
    """无日期源（如 GitHub Trending）：用条目内容哈希生成稳定时间戳，内容不变则不变。"""
    if not entries:
        return None
    raw = "\n".join(
        f"{e.get('title', '')}|{e.get('link', '')}" for e in entries
    )
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    days_offset = int(h[:8], 16) % 3650  # 约 10 年内某天
    return datetime(2020, 1, 1, tzinfo=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=days_offset)
