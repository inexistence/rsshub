"""Translate transform using easytranslator (default) or other providers."""
from __future__ import annotations

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

# easytranslator 引擎优先级（数字越小越优先）
EASYTRANSLATOR_ENGINES = [
    {"id": "alibaba", "name": "Alibaba", "priority": 10},
    {"id": "baidu", "name": "Baidu", "priority": 10},
    {"id": "modernMt", "name": "ModernMT", "priority": 20},
    {"id": "iciba", "name": "Iciba", "priority": 15},
    {"id": "google", "name": "Google", "priority": 4},
    {"id": "bing", "name": "Bing", "priority": 5},
    {"id": "lingvanex", "name": "Lingvanex", "priority": 20},
    {"id": "itranslate", "name": "Itranslate", "priority": 20},
    {"id": "sysTran", "name": "SysTran", "priority": 20},
    {"id": "argos", "name": "ArgoS", "priority": 20},
    {"id": "reverso", "name": "Reverso", "priority": 20},
    {"id": "deepl", "name": "DeepL", "priority": 5},
    {"id": "cloudTranslation", "name": "Cloud Translation", "priority": 3},
    {"id": "qqTranSmart", "name": "QQ Translate Smart", "priority": 5},
    {"id": "translateCom", "name": "Translate Com", "priority": 15},
    {"id": "sogou", "name": "Sogou", "priority": 5},
    {"id": "qqFanyi", "name": "QQ Fanyi", "priority": 10},
    {"id": "papago", "name": "Papago", "priority": 15},
    {"id": "youdao", "name": "Youdao", "priority": 15},
    {"id": "iflyrec", "name": "iFlyrec", "priority": 30},
    {"id": "caiyun", "name": "Caiyun", "priority": 15},
]


def _resolve_dest_lang(target: str) -> str:
    return LANG_MAP.get(target, target)


def _target_requires_chinese(target: str) -> bool:
    normalized = target.lower().replace("_", "-")
    return normalized in ("zh", "zh-cn", "zh-tw")


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _validate_translation(text: str, target: str) -> None:
    """中文目标语言必须含汉字，否则视为翻译失败（如 API 返回乱码）。"""
    if _target_requires_chinese(target) and not _contains_chinese(text):
        raise RuntimeError(f"翻译结果无效（目标 {target} 无中文）: {text[:80]!r}")


class EasyTranslatorProvider:
    def __init__(self, engines: list[dict] | None = None) -> None:
        try:
            from easytranslator import EasyTranslator
        except ImportError as exc:
            raise ImportError(
                "translate transform 需要 easytranslator: pip install easytranslator"
            ) from exc
        self._client = EasyTranslator(translators=engines or EASYTRANSLATOR_ENGINES)

    def translate(self, text: str, *, target: str, source: str = "auto") -> str:
        result = self._client.translate(
            text=text,
            dest_lang=_resolve_dest_lang(target),
            src_lang=source,
            proxies=[],
        )
        if result.get("status") != "success":
            raise RuntimeError(f"翻译失败: {result}")
        translated = result.get("translated_text")
        if not translated:
            raise RuntimeError(f"翻译结果为空: {result}")
        return translated


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

        self._translate_scope(
            ctx,
            config,
            provider,
            target,
            src_lang,
            scope="entry",
            fields=entry_fields,
            iter_fields=lambda: iter_entry_fields(ctx, entry_fields),
            apply_result=lambda idx, name, val: set_entry_field(ctx, idx, name, val),
        )
        self._translate_scope(
            ctx,
            config,
            provider,
            target,
            src_lang,
            scope="feed",
            fields=feed_fields,
            iter_fields=lambda: (
                (name, text) for name, text in iter_feed_fields(ctx, feed_fields)
            ),
            apply_result=lambda _idx, name, val: set_feed_field(ctx, name, val),
        )

    def _translate_scope(
        self,
        ctx: TransformContext,
        config: dict[str, Any],
        provider: EasyTranslatorProvider,
        target: str,
        src_lang: str,
        *,
        scope: str,
        fields: list[str],
        iter_fields,
        apply_result,
    ) -> None:
        if not fields:
            return

        for item in iter_fields():
            if scope == "entry":
                index, name, text = item
            else:
                name, text = item
                index = None

            key = transform_cache.cache_key(self.type, config, scope, name, text)
            cached = transform_cache.get(key)
            if cached is not None:
                try:
                    _validate_translation(cached, target)
                    apply_result(index, name, cached)
                    continue
                except RuntimeError:
                    pass

            try:
                translated = provider.translate(
                    text, target=target, source=src_lang
                )
                _validate_translation(translated, target)
                transform_cache.set(key, translated)
                apply_result(index, name, translated)
            except Exception as exc:
                mode = handle_field_error(config, exc)
                if mode == "skip" and scope == "entry" and index is not None:
                    ctx.entries[index]["_skip"] = True
