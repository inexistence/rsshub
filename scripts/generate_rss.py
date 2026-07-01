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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rss import (  # noqa: E402
    RSS_OUTPUT_DIR,
    TransformContext,
    build_feed,
    fetch_entries_for_source,
    load_config,
    run_pipeline,
)


def _write_feed(output_path: Path, feed_cfg: dict, entries: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fg = build_feed(feed_cfg, entries)
    fg.rss_file(str(output_path), encoding="utf-8")
    print(f"已生成: {output_path} ({len(entries)} 条)", file=sys.stderr)


def _generate_output(
    output_spec: dict,
    entries: list[dict],
    source: dict,
) -> bool:
    """Run transforms and write one output file. Returns True on success."""
    output_path = RSS_OUTPUT_DIR / output_spec["output"]

    ctx = TransformContext(
        feed=output_spec["feed"].copy(),
        entries=[entry.copy() for entry in entries],
        source=source,
    )
    try:
        run_pipeline(ctx, output_spec.get("transforms") or [])
    except Exception as e:
        if output_path.exists():
            print(
                f"转换失败，保留已有: {output_path} ({e})",
                file=sys.stderr,
            )
            return False
        raise

    _write_feed(output_path, ctx.feed, ctx.entries)
    return True


def main():
    feed_groups = load_config()
    RSS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for group in feed_groups:
        source = group["source"]
        outputs = group["outputs"]

        try:
            entries = fetch_entries_for_source(source)
        except Exception as e:
            for output_spec in outputs:
                output_path = RSS_OUTPUT_DIR / output_spec["output"]
                if output_path.exists():
                    print(
                        f"抓取失败，保留已有: {output_path} ({e})",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"抓取失败，跳过: {output_path} ({e})",
                        file=sys.stderr,
                    )
            if not any(
                (RSS_OUTPUT_DIR / o["output"]).exists() for o in outputs
            ):
                raise
            continue

        for output_spec in outputs:
            _generate_output(output_spec, entries, source)


if __name__ == "__main__":
    main()
