"""Transform type registry."""
from __future__ import annotations

from .base import Transform

REGISTRY: dict[str, Transform] = {}


def register(cls: type[Transform]) -> type[Transform]:
    instance = cls()
    REGISTRY[cls.type] = instance
    return cls
