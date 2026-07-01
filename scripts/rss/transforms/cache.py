"""File cache for transform outputs keyed by content + config."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..constants import REPO_ROOT

CACHE_DIR = REPO_ROOT / ".cache" / "transforms"


def _config_hash(config: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in config.items()
        if key not in ("on_error", "fields", "feed_fields")
    }
    raw = json.dumps(stable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_key(
    transform_type: str,
    config: dict[str, Any],
    scope: str,
    field: str,
    text: str,
) -> str:
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{transform_type}:{_config_hash(config)}:{scope}:{field}:{text_hash}"


def get(key: str) -> str | None:
    path = CACHE_DIR / f"{key}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def set(key: str, value: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.txt"
    path.write_text(value, encoding="utf-8")
