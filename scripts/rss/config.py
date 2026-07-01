"""Load feed configuration from config.yaml."""
import os

import yaml

from .constants import CONFIG_FILE


def load_config() -> list[dict]:
    """
    加载 config.yaml。
    返回 list[dict]，每项: { output, feed, source }。config 中必须有 feeds 列表。
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
        defaults["defaults"]["feed"].update(
            data.get("defaults", {}).get("feed", {})
        )
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
