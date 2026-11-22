"""Translate transform using easytranslator (default) or other providers."""
from __future__ import annotations

import logging
import multiprocessing
import re
import time
from typing import Any

from .registry import register
from .base import (
    Transform,
    TransformContext,
    handle_field_error,
    iter_entry_fields,
    iter_feed_fields,
    set_entry_field,
    set_feed_field,
)
from . import cache as transform_cache

LANG_MAP = {
    "zh-CN": "Chinese Simplified",
    "zh-TW": "Chinese Traditional",
    "zh": "Chinese Simplified",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "ru": "Russian",
}

# 仅使用现有的免凭证引擎，按优先级尝试，不再轮询全部引擎。
EASYTRANSLATOR_ENGINES = (
    {"id": "google", "name": "Google", "priority": 1},
    {"id": "bing", "name": "Bing", "priority": 2},
    {"id": "cloudTranslation", "name": "Cloud Translation", "priority": 3},
)
REQUEST_TIMEOUT_SECONDS = 7
BATCH_TIMEOUT_SECONDS = 45
MAX_CONSECUTIVE_ENGINE_FAILURES = 2
_PROVIDER_PAGE_PATTERN = re.compile(r"<(?:!doctype\s+html|html\b|body\b)", re.I)
logger = logging.getLogger(__name__)


def _resolve_dest_lang(target: str) -> str:
    return LANG_MAP.get(target, target)


def _target_requires_chinese(target: str) -> bool:
    normalized = target.lower().replace("_", "-")
    return normalized in ("zh", "zh-cn", "zh-tw")


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _predominantly_chinese(text: str) -> bool:
    """文本以中文为主时无需再译成中文。"""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return cjk >= 2 and cjk / len(chars) >= 0.3


def _resolve_source_lang(text: str, target: str, configured: str) -> str:
    """避免 auto 把英文误判为中文，触发 zh→zh 引擎报错。"""
    if configured != "auto":
        return configured
    if _target_requires_chinese(target) and not _contains_chinese(text):
        return "en"
    return configured


def _validate_translation(text: object, target: str) -> str:
    """Reject provider errors even when their localized notices contain Hanzi."""
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("翻译结果为空")
    if (
        "older version of deepl" in " ".join(text.casefold().split())
        or _PROVIDER_PAGE_PATTERN.search(text)
    ):
        raise RuntimeError("翻译服务返回了错误页面")
    if _target_requires_chinese(target) and not _contains_chinese(text):
        raise RuntimeError(f"翻译结果无效（目标 {target} 无中文）")
    return text.strip()


def _translate_with_fallback(client, engines, text, target, source, failures):
    """Validate the response before accepting it or trying the next engine."""
    for engine in engines:
        engine_id = engine["id"]
        if failures.get(engine_id, 0) >= MAX_CONSECUTIVE_ENGINE_FAILURES:
            continue
        try:
            # easytranslator mutates priority in-place; its ranking should not
            # affect fallback order for this batch or mutate shared configuration.
            result = client.translate_with_translator(
                engine.copy(), text, _resolve_dest_lang(target), source
            )
            if result.get("status") != "success":
                raise RuntimeError("引擎请求失败")
            translated = _validate_translation(result.get("translated_text"), target)
        except Exception:
            failures[engine_id] = failures.get(engine_id, 0) + 1
        else:
            failures[engine_id] = 0
            return translated
    return None


def _translate_worker(output, engines, queries, target):
    """Send per-field results so a deadline does not lose partial progress."""
    with output:
        try:
            from easytranslator import EasyTranslator

            client = EasyTranslator(translators=[engine.copy() for engine in engines])
            client.TIMEOUT = REQUEST_TIMEOUT_SECONDS
        except Exception:
            logger.warning("无法初始化翻译服务", exc_info=True)
            return
        failures = {}
        for index, (text, source) in enumerate(queries):
            result = _translate_with_fallback(client, engines, text, target, source, failures)
            output.send((index, result))


class EasyTranslatorProvider:
    def __init__(self, engines: list[dict] | None = None) -> None:
        self._engines = sorted(
            engines or EASYTRANSLATOR_ENGINES, key=lambda engine: engine["priority"]
        )

    def translate_many(self, queries: list[tuple[str, str]], *, target: str) -> list[str | None]:
        if not queries:
            return []
        results: list[str | None] = [None] * len(queries)
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        worker = context.Process(
            target=_translate_worker, args=(sender, self._engines, queries, target), daemon=True
        )
        deadline = time.monotonic() + BATCH_TIMEOUT_SECONDS
        try:
            worker.start()
            sender.close()
            for _ in queries:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not receiver.poll(remaining):
                    logger.warning("翻译超时，停止等待剩余字段")
                    break
                try:
                    index, text = receiver.recv()
                except EOFError:
                    break
                results[index] = text
        except OSError:
            logger.warning("无法启动或读取翻译进程", exc_info=True)
        finally:
            receiver.close()
            sender.close()
            if worker.pid is not None:
                worker.join(timeout=0.1)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=0.2)
                if worker.is_alive():
                    worker.kill()
                    worker.join(timeout=0.2)
            if not worker.is_alive():
                worker.close()
        return results


_PROVIDERS: dict[str, type] = {
    "easytranslator": EasyTranslatorProvider,
}


def get_provider(name: str, *, engines: list[dict] | None = None) -> EasyTranslatorProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"未知 translate provider: {name}")
    return cls(engines=engines)


@register
class TranslateTransform(Transform):
    type = "translate"

    def apply(self, ctx: TransformContext, config: dict[str, Any]) -> None:
        provider_name = config.get("provider", "easytranslator")
        engines = config.get("engines")
        provider = get_provider(provider_name, engines=engines)
        target = config.get("target")
        if not target:
            raise ValueError("translate transform 需要 target 字段")

        src_lang = config.get("source", "auto")
        entry_fields = config.get("fields") or ["title", "summary"]
        feed_fields = config.get("feed_fields") or []

        fields = [
            ("entry", index, name, text)
            for index, name, text in iter_entry_fields(ctx, entry_fields)
        ] + [
            ("feed", None, name, text)
            for name, text in iter_feed_fields(ctx, feed_fields)
        ]

        def apply_result(scope, index, name, value):
            if scope == "entry":
                set_entry_field(ctx, index, name, value)
            else:
                set_feed_field(ctx, name, value)

        pending = []
        for scope, index, name, text in fields:
            key = transform_cache.cache_key(self.type, config, scope, name, text)
            cached = transform_cache.get(key)
            if cached is not None:
                try:
                    cached = _validate_translation(cached, target)
                except RuntimeError:
                    transform_cache.discard(key)
                else:
                    apply_result(scope, index, name, cached)
                    continue

            if _target_requires_chinese(target) and _predominantly_chinese(text):
                continue
            pending.append((scope, index, name, text, key))

        queries = [
            (text, _resolve_source_lang(text, target, src_lang))
            for _, _, _, text, _ in pending
        ]
        translated = provider.translate_many(queries, target=target) if queries else []
        failures = 0
        for (scope, index, name, _, key), value in zip(pending, translated, strict=True):
            try:
                value = _validate_translation(value, target)
            except RuntimeError:
                failures += 1
                exc = RuntimeError("翻译服务未返回有效译文")
                mode = handle_field_error(config, exc)
                if mode == "skip" and scope == "entry":
                    ctx.entries[index]["_skip"] = True
            else:
                transform_cache.set(key, value)
                apply_result(scope, index, name, value)
        if failures:
            logger.warning(
                "%d/%d 个字段未译成，按 on_error=%s 处理",
                failures, len(pending), config.get("on_error", "keep"),
            )
