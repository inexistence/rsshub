"""Fetch RSS entries from Next.js _next/data JSON API."""
import hashlib
import re
from urllib.parse import urlparse

import requests

from ..constants import DEFAULT_HEADERS, REPO_ROOT

BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')
CACHE_DIR = REPO_ROOT / ".cache" / "next_json"
JSON_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json, text/plain, */*",
}


def _get_json_field(obj: dict, spec: str):
    """从 JSON 对象按字段名取值，支持 a|b 优先取第一个非空."""
    if not spec or not obj:
        return None
    for part in spec.split("|"):
        val = obj.get(part.strip())
        if val:
            return val.strip() if isinstance(val, str) else val
    return None


def _cache_key(bootstrap_url: str, page_path: str) -> str:
    digest = hashlib.sha256(f"{bootstrap_url}|{page_path}".encode()).hexdigest()
    return digest[:16]


def _read_cached_build_id(cache_key: str) -> str | None:
    path = CACHE_DIR / f"{cache_key}.txt"
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _write_cached_build_id(cache_key: str, build_id: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{cache_key}.txt").write_text(build_id, encoding="utf-8")


def _fetch_build_id_from_html(
    bootstrap_url: str, headers: dict, verify: bool
) -> str:
    r = requests.get(bootstrap_url, headers=headers, timeout=30, verify=verify)
    r.raise_for_status()
    m = BUILD_ID_RE.search(r.text)
    if not m:
        raise ValueError(f"未在 {bootstrap_url} 中找到 Next.js buildId")
    return m.group(1)


def _resolve_build_id(
    source: dict, bootstrap_url: str, headers: dict, verify: bool
) -> tuple[str, str]:
    """返回 (build_id, source_kind)。source_kind: config | cache | bootstrap."""
    cache_key = _cache_key(bootstrap_url, source["page_path"])

    if source.get("build_id"):
        return str(source["build_id"]), "config"

    cached = _read_cached_build_id(cache_key)
    if cached:
        return cached, "cache"

    build_id = _fetch_build_id_from_html(bootstrap_url, headers, verify)
    _write_cached_build_id(cache_key, build_id)
    return build_id, "bootstrap"


def _fetch_posts(
    base: str,
    build_id: str,
    page_path: str,
    items_key: str,
    headers: dict,
    verify: bool,
) -> list:
    json_url = f"{base}/_next/data/{build_id}{page_path}.json"
    r = requests.get(json_url, headers=headers, timeout=30, verify=verify)
    r.raise_for_status()
    return (r.json().get("pageProps") or {}).get(items_key) or []


def fetch_entries_from_next_json(source: dict) -> list[dict]:
    """从 Next.js _next/data JSON API 解析条目（绕过部分站点的 HTML 反爬）."""
    bootstrap_url = source.get("bootstrap_url") or source.get("url")
    page_path = source.get("page_path")
    selectors = source.get("selectors") or {}
    items_key = source.get("items_key", "posts")
    link_prefix = source.get("link_prefix", "")
    if not bootstrap_url or not page_path or not selectors:
        return []

    html_headers = {**DEFAULT_HEADERS, **(source.get("headers") or {})}
    json_headers = {**JSON_HEADERS, **(source.get("headers") or {})}
    verify = source.get("verify", True)
    base = f"{urlparse(bootstrap_url).scheme}://{urlparse(bootstrap_url).netloc}"
    cache_key = _cache_key(bootstrap_url, page_path)

    build_id, build_source = _resolve_build_id(
        source, bootstrap_url, html_headers, verify
    )
    try:
        posts = _fetch_posts(
            base, build_id, page_path, items_key, json_headers, verify
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404 and build_source != "bootstrap":
            build_id = _fetch_build_id_from_html(
                bootstrap_url, html_headers, verify
            )
            _write_cached_build_id(cache_key, build_id)
            posts = _fetch_posts(
                base, build_id, page_path, items_key, json_headers, verify
            )
        else:
            raise

    _write_cached_build_id(cache_key, build_id)

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
