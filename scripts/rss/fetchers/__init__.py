"""Dispatch entry fetching to source-type-specific fetchers."""
from .html import fetch_entries_from_html
from .next_json import fetch_entries_from_next_json


def fetch_entries_for_source(source: dict) -> list[dict]:
    """从 source 解析条目，返回列表."""
    if not source:
        return []
    source_type = source.get("type")
    if source_type == "html":
        return fetch_entries_from_html(source)
    if source_type == "next_json":
        return fetch_entries_from_next_json(source)
    return []
