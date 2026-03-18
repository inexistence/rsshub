#!/usr/bin/env python3
"""
从多个网页数据源（HTML 解析）生成多份 rss.xml。
配置见 config.yaml 的 feeds，每个 source 为 type: html。
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import yaml
    from feedgen.feed import FeedGenerator
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print("请安装依赖: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(1) from e

REPO_ROOT = Path(__file__).resolve().parent.parent
RSS_OUTPUT_DIR = REPO_ROOT / "rss"  # 生成的 RSS 文件统一输出到此目录
CONFIG_FILE = Path(__file__).parent / "config.yaml"


def load_config():
    """
    加载 config.yaml。
    返回 list[dict]，每项: { output, feed, source }。必须有 feeds 列表。
    """
    defaults = {
        "defaults": {
            "feed": {
                "title": os.getenv("RSS_TITLE", "我的 RSS"),
                "link": os.getenv("RSS_LINK", "https://github.com"),
                "description": os.getenv("RSS_DESCRIPTION", "自动生成的 RSS"),
                "language": "zh-CN",
            }
        },
        "feeds": [],
    }
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        defaults["defaults"]["feed"].update(data.get("defaults", {}).get("feed", {}))
        defaults["feeds"] = data.get("feeds") or []

    result = []
    for item in defaults["feeds"]:
        feed_cfg = defaults["defaults"]["feed"].copy()
        feed_cfg.update(item.get("feed") or {})
        result.append({
            "output": item.get("output", "rss.xml"),
            "feed": feed_cfg,
            "source": item.get("source"),
        })
    return result


def _select_one(parent, spec: str, base_url: str):
    """
    在 parent (BeautifulSoup 节点) 内按 spec 取值。
    spec: "selector" 取文本；"selector@attr" 取属性；支持多个候选用 | 分隔。
    """
    if not spec or not parent:
        return None
    spec = spec.strip()
    # 支持 "a|b" 表示优先 a，没有再 b
    for part in spec.split("|"):
        part = part.strip()
        if "@" in part:
            sel, attr = part.split("@", 1)
            sel, attr = sel.strip(), attr.strip()
            node = parent.select_one(sel)
            if node and attr:
                val = node.get(attr)
                if val and attr == "href" and base_url:
                    val = urljoin(base_url, val)
                return val.strip() if isinstance(val, str) else val
        else:
            node = parent.select_one(part)
            if node:
                return node.get_text(strip=True)
    return None


def fetch_entries_from_html(source: dict):
    """从网页 HTML 用 CSS 选择器解析条目."""
    if not source or source.get("type") != "html":
        return []
    url = source.get("url")
    if not url:
        return []
    item_selector = source.get("item_selector")
    selectors = source.get("selectors") or source.get("item_map") or {}
    if not item_selector or not selectors:
        return []

    headers = source.get("headers") or {}
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; RSSHub/1.0)")
    verify = source.get("verify", True)
    r = requests.get(url, headers=headers, timeout=30, verify=verify)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    items = soup.select(item_selector)[:50]
    entries = []
    for el in items:
        entry = {}
        for rss_key, sel_spec in selectors.items():
            if isinstance(sel_spec, str):
                val = _select_one(el, sel_spec, base_url)
            else:
                val = None
            if val:
                entry[rss_key] = val
        if entry.get("title"):
            entries.append(entry)
    # GitHub Trending：未登录时链接为 login?return_to= 或 /sponsors/，改为直链仓库
    if "github.com" in url and "trending" in url and base_url:
        for e in entries:
            link = e.get("link") or ""
            title = (e.get("title") or "").strip()
            if "github.com/login?return_to=" in link:
                try:
                    parsed = urlparse(link)
                    qs = parse_qs(parsed.query)
                    return_to = (qs.get("return_to") or [None])[0]
                    if return_to:
                        path = return_to.lstrip("/")
                        if path and "/" in path and " " not in path:
                            e["link"] = f"{base_url}/{path}"
                except Exception:
                    pass
            elif "/sponsors/" in link and title and "/" in title:
                # title 形如 "owner /repo"，转为 https://github.com/owner/repo
                repo_path = title.replace(" ", "").strip()
                if repo_path.count("/") == 1:
                    e["link"] = f"{base_url}/{repo_path}"
    return entries


def fetch_entries_for_source(source: dict):
    """从 source（type: html）解析条目，返回列表."""
    if not source or source.get("type") != "html":
        return []
    return fetch_entries_from_html(source)


def parse_date(s):
    """简单解析常见日期格式."""
    if not s:
        return None
    s = s.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",  # March 13, 2026
        "%b %d, %Y",  # Feb 05, 2026
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

    # 收集所有条目的发布日期，用于最后设置 feed 的 updated/lastBuildDate
    pub_dates = []
    for e in entries:
        fe = fg.add_entry()
        fe.title(e.get("title", ""))
        if e.get("link"):
            fe.link(href=e["link"])
        if e.get("summary"):
            fe.description(e["summary"])
        if e.get("published"):
            dt = parse_date(e["published"])
            if dt:
                fe.published(dt)
                pub_dates.append(dt)

    # 用最新条目的发布日期作为 lastBuildDate，内容不变则时间戳不变
    if pub_dates:
        fg.updated(max(pub_dates))
    # 无条目时 feedgen 会使用当前时间，保持默认行为即可

    return fg


def main():
    feeds_config = load_config()
    RSS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []

    for item in feeds_config:
        output_path = RSS_OUTPUT_DIR / item["output"]
        feed_cfg = item["feed"]
        source = item["source"]

        entries = fetch_entries_for_source(source)
        fg = build_feed(feed_cfg, entries)
        fg.rss_file(str(output_path), encoding="utf-8")
        generated.append(output_path)
        print(f"已生成: {output_path} ({len(entries)} 条)", file=sys.stderr)


if __name__ == "__main__":
    main()
