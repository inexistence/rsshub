"""Regression tests for invalid responses, fallback, and translation deadlines."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rss.transforms import TransformContext, cache, run_pipeline, translate


DEEPL_NOTICE = (
    "You're using an older version of DeepL. Please update.\n"
    "您使用的是旧版 DeepL，请更新到最新版本。"
)
TRANSLATE_STEP = {"type": "translate", "target": "zh-CN", "on_error": "keep"}


def send_one_then_block(output, engines, queries, target):
    with output:
        output.send((0, "有效译文"))
        time.sleep(5)


class TranslateTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cache_dir = patch.object(cache, "CACHE_DIR", Path(directory.name))
        cache_dir.start()
        self.addCleanup(cache_dir.stop)

    def test_provider_falls_back_after_multilingual_error_message(self):
        client = Mock()
        client.translate_with_translator.side_effect = [
            {"status": "success", "translated_text": DEEPL_NOTICE},
            {"status": "success", "translated_text": "代理记忆的组成部分"},
        ]
        engines = [{"id": "deepl"}, {"id": "google"}]
        result = translate._translate_with_fallback(
            client, engines, "The components of agent memory", "zh-CN", "en", {}
        )
        self.assertEqual(result, "代理记忆的组成部分")
        self.assertEqual(
            [call.args[0]["id"] for call in client.translate_with_translator.call_args_list],
            ["deepl", "google"],
        )

    def test_provider_does_not_repeat_failing_engine_throughout_batch(self):
        client = Mock()
        client.translate_with_translator.side_effect = [
            OSError("offline"),
            {"status": "success", "translated_text": "译文一"},
            {"status": "error"},
            {"status": "success", "translated_text": "译文二"},
            {"status": "success", "translated_text": "译文三"},
        ]
        engines = [{"id": "first"}, {"id": "second"}]
        failures = {}
        for i, expected in enumerate(("译文一", "译文二", "译文三")):
            self.assertEqual(
                translate._translate_with_fallback(
                    client, engines, f"Title {i}", "zh-CN", "en", failures
                ),
                expected,
            )
        self.assertEqual(
            [call.args[0]["id"] for call in client.translate_with_translator.call_args_list],
            ["first", "second", "first", "second", "second"],
        )

    def test_invalid_cached_results_are_retried_and_replaced(self):
        old_key = cache.cache_key("translate", TRANSLATE_STEP, "entry", "title", "Old title")
        good_key = cache.cache_key("translate", TRANSLATE_STEP, "entry", "title", "Good title")
        cache.set(old_key, DEEPL_NOTICE)
        cache.set(good_key, "有效缓存")
        ctx = TransformContext({}, [{"title": "Old title"}, {"title": "Good title"}], {})
        provider = Mock(**{"translate_many.return_value": ["新的译文"]})
        with patch.object(translate, "get_provider", return_value=provider):
            run_pipeline(ctx, [TRANSLATE_STEP])
        provider.translate_many.assert_called_once_with([("Old title", "en")], target="zh-CN")
        self.assertEqual([entry["title"] for entry in ctx.entries], ["新的译文", "有效缓存"])
        self.assertEqual(cache.get(old_key), "新的译文")

    def test_exhausted_provider_preserves_original_and_discards_poisoned_cache(self):
        key = cache.cache_key("translate", TRANSLATE_STEP, "entry", "title", "Original")
        cache.set(key, DEEPL_NOTICE)
        ctx = TransformContext({}, [{"title": "Original"}], {})
        provider = Mock(**{"translate_many.return_value": [None]})
        with patch.object(translate, "get_provider", return_value=provider):
            with self.assertLogs("rss.transforms.translate", level="WARNING"):
                run_pipeline(ctx, [TRANSLATE_STEP])
        self.assertEqual(ctx.entries, [{"title": "Original"}])
        self.assertIsNone(cache.get(key))

    def test_exhausted_provider_also_respects_skip_and_fail(self):
        provider = Mock(**{"translate_many.return_value": [None]})
        with patch.object(translate, "get_provider", return_value=provider):
            ctx = TransformContext({}, [{"title": "Original"}], {})
            with self.assertLogs("rss.transforms.translate", level="WARNING"):
                run_pipeline(ctx, [{**TRANSLATE_STEP, "on_error": "skip"}])
            self.assertEqual(ctx.entries, [])
            ctx = TransformContext({}, [{"title": "Original"}], {})
            with self.assertRaisesRegex(RuntimeError, "翻译服务未返回有效译文"):
                run_pipeline(ctx, [{**TRANSLATE_STEP, "on_error": "fail"}])

    def test_deadline_does_not_wait_for_stuck_worker_or_discard_completed_results(self):
        provider = translate.EasyTranslatorProvider()
        with (
            patch.object(translate, "_translate_worker", send_one_then_block),
            patch.object(translate, "BATCH_TIMEOUT_SECONDS", 0.8),
            self.assertLogs("rss.transforms.translate", level="WARNING"),
        ):
            before = time.monotonic()
            values = provider.translate_many([("One", "en"), ("Two", "en")], target="zh-CN")
            elapsed = time.monotonic() - before
        self.assertEqual(values, ["有效译文", None])
        self.assertLess(elapsed, 2.5)


if __name__ == "__main__":
    unittest.main()
