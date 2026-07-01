"""Load feed configuration from config.yaml."""
import os
from pathlib import Path

import yaml

from .constants import CONFIG_FILE
from .transforms import resolve_steps


def load_config() -> list[dict]:
    """
    加载 config.yaml，返回 feed 组列表。

    每组共享 source（只 fetch 一次），包含多个 output：
    { source, outputs: [{ output, feed, transforms }] }

    支持顶层 pipelines、feeds[].variants、transforms.use/append。
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
        "pipelines": {},
    }
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        defaults["defaults"]["feed"].update(
            data.get("defaults", {}).get("feed", {})
        )
        defaults["feeds"] = data.get("feeds") or []
        defaults["pipelines"] = data.get("pipelines") or {}

    pipelines = defaults["pipelines"]
    groups: list[dict] = []

    for item in defaults["feeds"]:
        base_feed = defaults["defaults"]["feed"].copy()
        base_feed.update(item.get("feed") or {})
        source = item.get("source")
        outputs = _build_outputs(item, base_feed, pipelines)
        _resolve_output_paths(item, outputs)
        groups.append({"source": source, "outputs": outputs})

    return groups


def _build_outputs(
    item: dict,
    base_feed: dict,
    pipelines: dict[str, list[dict]],
) -> list[dict]:
    outputs: list[dict] = []

    main_output = {
        "output": item.get("output", "rss.xml"),
        "feed": base_feed,
        "transforms": resolve_steps(item.get("transforms"), pipelines),
    }
    outputs.append(main_output)

    for variant in item.get("variants") or []:
        variant_feed = base_feed.copy()
        variant_feed.update(variant.get("feed") or {})
        outputs.append({
            "output": variant["output"],
            "feed": variant_feed,
            "transforms": resolve_steps(variant.get("transforms"), pipelines),
        })

    return outputs


def _resolve_output_paths(item: dict, outputs: list[dict]) -> None:
    """有 variants 时，将同组 output 放入 rss/{dir}/ 子目录。"""
    if not item.get("variants"):
        return

    folder = item.get("dir") or Path(item.get("output", "rss.xml")).stem
    for out in outputs:
        filename = Path(out["output"]).name
        out["output"] = f"{folder}/{filename}"

