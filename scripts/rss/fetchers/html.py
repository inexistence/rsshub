"""Fetch RSS entries by parsing HTML with CSS selectors."""
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..constants import DEFAULT_HEADERS


def _select_one(parent, spec: str, base_url: str):
    """
    在 parent (BeautifulSoup 节点) 内按 spec 取值。
    spec: "selector" 取文本；"selector@attr" 取属性；支持多个候选用 | 分隔。
    """
    if not spec or not parent:
        return None
    spec = spec.strip()
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


def _fix_github_trending_links(entries: list, url: str, base_url: str) -> None:
    """GitHub Trending：未登录时链接为 login?return_to= 或 /sponsors/，改为直链仓库。"""
    if "github.com" not in url or "trending" not in url or not base_url:
        return
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
            repo_path = title.replace(" ", "").strip()
            if repo_path.count("/") == 1:
                e["link"] = f"{base_url}/{repo_path}"


def fetch_entries_from_html(source: dict) -> list[dict]:
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

    headers = {**DEFAULT_HEADERS, **(source.get("headers") or {})}
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

    _fix_github_trending_links(entries, url, base_url)
    return entries
