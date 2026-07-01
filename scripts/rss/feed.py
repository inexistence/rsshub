"""Build RSS feed from configuration and parsed entries."""
from feedgen.feed import FeedGenerator

from .dates import parse_date, parse_date_from_title, stable_date_from_entries


def build_feed(feed_cfg: dict, entries: list) -> FeedGenerator:
    """根据 feed 配置和条目生成 FeedGenerator。
    lastBuildDate 使用最新条目的发布日期，这样内容未变时时间戳稳定，不会触发无意义更新。
    条目的描述来自 selectors.summary（文章概要，可选）。
    """
    fg = FeedGenerator()
    fg.title(feed_cfg.get("title", "RSS"))
    fg.link(href=feed_cfg.get("link", ""), rel="alternate")
    fg.description(feed_cfg.get("description", ""))
    fg.language(feed_cfg.get("language", "zh-CN"))

    pub_dates = []
    for e in entries:
        fe = fg.add_entry()
        fe.title(e.get("title", ""))
        if e.get("link"):
            fe.link(href=e["link"])
        if e.get("summary"):
            fe.description(e["summary"])
        dt = parse_date(e["published"]) if e.get("published") else None
        if not dt and e.get("title"):
            dt = parse_date_from_title(e["title"])
        if dt:
            fe.published(dt)
            pub_dates.append(dt)

    if pub_dates:
        fg.updated(max(pub_dates))
    elif entries:
        stable = stable_date_from_entries(entries)
        if stable:
            fg.updated(stable)

    return fg
