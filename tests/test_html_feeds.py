"""Regression tests for the Claude and Anthropic HTML feed rules."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rss.config import load_config
from rss.fetchers.html import fetch_entries_from_html


class HtmlFeedRulesTest(unittest.TestCase):
    def parse(self, directory, html):
        source = next(
            group["source"]
            for group in load_config()
            if group["outputs"][0]["output"] == f"{directory}/feed.xml"
        )
        response = Mock(text=html, encoding="utf-8")
        with patch("rss.fetchers.html.requests.get", return_value=response):
            return fetch_entries_from_html(source)

    def test_claude_reads_links_on_the_article_cards(self):
        entries = self.parse("claude", """
            <a href="/resources/articles/featured"><h3>Featured</h3></a>
            <div class="ResourcesIndex-module-scss-module__hash__grid">
              <a href="/resources/articles/building-always-on-agents">
                <span class="ResourceCard-module-scss-module__hash__meta">Nov 13, 2026</span>
                <h3>Building always-on agents</h3>
              </a>
              <a href="https://claude.dev/blog/verification/">
                <span class="ResourceCard-module-scss-module__hash__meta">Nov 16, 2026</span>
                <h3>Verification</h3>
              </a>
            </div>
        """)
        self.assertEqual(entries, [
            {
                "title": "Building always-on agents",
                "link": "https://claude.com/resources/articles/building-always-on-agents",
                "published": "Nov 13, 2026",
            },
            {
                "title": "Verification",
                "link": "https://claude.dev/blog/verification/",
                "published": "Nov 16, 2026",
            },
        ])

    def test_anthropic_uses_article_title_link_not_the_engineering_category(self):
        entries = self.parse("anthropic-engineering", """
            <article><h3><a href="/company">Unrelated</a></h3></article>
            <article class="hash_article" data-listing-row="story">
              <header><a href="/engineering">Engineering</a><time>Nov 6, 2026</time></header>
              <h3><a href="/research/components-of-agent-memory">The components of agent memory</a></h3>
            </article>
        """)
        self.assertEqual(entries, [{
            "title": "The components of agent memory",
            "link": "https://www.anthropic.com/research/components-of-agent-memory",
            "published": "Nov 6, 2026",
        }])
