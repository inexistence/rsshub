"""Transform pipeline: registry, step resolution, and execution."""
from __future__ import annotations

from typing import Any

from .base import Transform, TransformContext
from .registry import REGISTRY, register
from . import translate  # noqa: F401 — register built-in transforms


def resolve_steps(
    spec: list[dict] | dict[str, Any] | None,
    pipelines: dict[str, list[dict]],
) -> list[dict]:
    """Resolve transforms spec (list, or {use, append}) into flat step list."""
    if not spec:
        return []
    if isinstance(spec, list):
        return _expand_steps(spec, pipelines)
    if isinstance(spec, dict):
        steps: list[dict] = []
        use = spec.get("use")
        if use:
            names = [use] if isinstance(use, str) else list(use)
            for name in names:
                if name not in pipelines:
                    raise ValueError(f"未定义的 pipeline: {name}")
                steps.extend(pipelines[name])
        append = spec.get("append") or []
        steps.extend(_expand_steps(append, pipelines))
        return steps
    raise ValueError(f"无效的 transforms 配置: {spec!r}")


def _expand_steps(steps: list[dict], pipelines: dict[str, list[dict]]) -> list[dict]:
    result: list[dict] = []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError(f"transform step 必须是 dict: {step!r}")
        if "pipeline" in step:
            name = step["pipeline"]
            if name not in pipelines:
                raise ValueError(f"未定义的 pipeline: {name}")
            result.extend(pipelines[name])
            continue
        nested = step.get("then")
        if nested is not None:
            head = {k: v for k, v in step.items() if k != "then"}
            if "type" in head:
                result.append(head)
            result.extend(_expand_steps(nested, pipelines))
            continue
        result.append(step)
    return result


def run_pipeline(ctx: TransformContext, steps: list[dict]) -> None:
    for step in steps:
        step_type = step.get("type")
        if not step_type:
            raise ValueError(f"transform step 缺少 type: {step!r}")
        transform = REGISTRY.get(step_type)
        if transform is None:
            raise ValueError(f"未知 transform 类型: {step_type}")
        transform.apply(ctx, step)
    ctx.entries = [e for e in ctx.entries if not e.pop("_skip", False)]


__all__ = [
    "TransformContext",
    "resolve_steps",
    "run_pipeline",
]
