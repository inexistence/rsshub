"""Fetch RSS entries from Next.js _next/data JSON API."""
import re
from urllib.parse import urlparse

import requests

from ..constants import DEFAULT_HEADERS

BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')


def _get_json_field(obj: dict, spec: str):
    """从 JSON 对象按字段名取值，支持 a|b 优先取第一个非空."""
    if not spec or not obj:
        return None
    for part in spec.split("|"):
        val = obj.get(part.strip())
        if val:
            return val.strip() if isinstance(val, str) else val
    return None


def fetch_entries_from_next_json(source: dict) -> list[dict]:
    """从 Next.js _next/data JSON API 解析条目（绕过部分站点的 HTML 反爬）."""
    bootstrap_url = source.get("bootstrap_url") or source.get("url")
    page_path = source.get("page_path")
    selectors = source.get("selectors") or {}
    items_key = source.get("items_key", "posts")
    link_prefix = source.get("link_prefix", "")
    if not bootstrap_url or not page_path or not selectors:
        return []

    headers = {**DEFAULT_HEADERS, **(source.get("headers") or {})}
    verify = source.get("verify", True)
    r = requests.get(bootstrap_url, headers=headers, timeout=30, verify=verify)
    r.raise_for_status()
    m = BUILD_ID_RE.search(r.text)
    if not m:
        raise ValueError(f"未在 {bootstrap_url} 中找到 Next.js buildId")
    build_id = m.group(1)

    base = f"{urlparse(bootstrap_url).scheme}://{urlparse(bootstrap_url).netloc}"
    json_url = f"{base}/_next/data/{build_id}{page_path}.json"
    r = requests.get(json_url, headers=headers, timeout=30, verify=verify)
    r.raise_for_status()
    posts = (r.json().get("pageProps") or {}).get(items_key) or []

    entries = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        entry = {}
        for rss_key, field_spec in selectors.items():
            val = _get_json_field(post, field_spec)
            if rss_key == "link" and val and link_prefix and not str(val).startswith("http"):
                val = f"{link_prefix.rstrip('/')}/{str(val).lstrip('/')}"
            if val:
                entry[rss_key] = val
        if entry.get("title"):
            entries.append(entry)
    return entries[:50]
