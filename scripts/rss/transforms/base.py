"""Transform pipeline core types and field helpers."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class TransformContext:
    feed: dict
    entries: list[dict]
    source: dict
    meta: dict = field(default_factory=dict)

    def copy(self) -> TransformContext:
        return TransformContext(
            feed=self.feed.copy(),
            entries=[entry.copy() for entry in self.entries],
            source=self.source,
            meta=copy.copy(self.meta),
        )


def iter_entry_fields(
    ctx: TransformContext, fields: list[str]
) -> Iterator[tuple[int, str, str]]:
    for index, entry in enumerate(ctx.entries):
        for name in fields:
            value = entry.get(name)
            if isinstance(value, str) and value.strip():
                yield index, name, value


def iter_feed_fields(
    ctx: TransformContext, fields: list[str]
) -> Iterator[tuple[str, str]]:
    for name in fields:
        value = ctx.feed.get(name)
        if isinstance(value, str) and value.strip():
            yield name, value


def set_entry_field(ctx: TransformContext, index: int, name: str, value: str) -> None:
    ctx.entries[index][name] = value


def set_feed_field(ctx: TransformContext, name: str, value: str) -> None:
    ctx.feed[name] = value


class Transform:
    type: str

    def apply(self, ctx: TransformContext, config: dict[str, Any]) -> None:
        raise NotImplementedError


def handle_field_error(config: dict[str, Any], exc: Exception) -> str:
    """Return on_error mode: keep | skip | fail."""
    mode = config.get("on_error", "keep")
    if mode == "fail":
        raise exc
    return mode
