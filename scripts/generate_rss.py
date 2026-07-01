#!/usr/bin/env python3
"""
从多个网页数据源（HTML 解析）生成多份 rss.xml。
配置见 config.yaml 的 feeds，每个 source 为 type: html。
"""
import sys
from pathlib import Path

try:
    import yaml  # noqa: F401 — 依赖检查
    from feedgen.feed import FeedGenerator  # noqa: F401
    import requests  # noqa: F401
    from bs4 import BeautifulSoup  # noqa: F401
except ImportError as e:
    print("请安装依赖: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(1) from e

# 允许以 `python scripts/generate_rss.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rss import (  # noqa: E402
    RSS_OUTPUT_DIR,
    build_feed,
    fetch_entries_for_source,
    load_config,
)


def main():
    feeds_config = load_config()
    RSS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for item in feeds_config:
        output_path = RSS_OUTPUT_DIR / item["output"]
        feed_cfg = item["feed"]
        source = item["source"]

        try:
            entries = fetch_entries_for_source(source)
        except Exception as e:
            if output_path.exists():
                print(
                    f"抓取失败，保留已有: {output_path} ({e})",
                    file=sys.stderr,
                )
                continue
            raise

        fg = build_feed(feed_cfg, entries)
        fg.rss_file(str(output_path), encoding="utf-8")
        print(f"已生成: {output_path} ({len(entries)} 条)", file=sys.stderr)


if __name__ == "__main__":
    main()
