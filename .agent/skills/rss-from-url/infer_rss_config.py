#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从列表页 URL 抓取 HTML，推断条目容器与 title/link/published 选择器，输出可追加到 config.yaml 的配置片段。
用法（在项目根目录）: python .agent/skills/rss-from-url/infer_rss_config.py <URL> [--output 文件名] [--title "标题"]
与 rss-from-url skill 配合：抓取与推断由此脚本完成，人工或 AI 将输出写入 config 后运行 generate_rss.py 做验证。
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请安装依赖（在项目根目录）: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# 脚本位于 .agent/skills/rss-from-url/，向上四级为仓库根（供后续扩展用）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 条目容器候选：能匹配到多条且每条内可解析出标题和链接
ITEM_SELECTOR_CANDIDATES = [
    "article[class*='ArticleList']",
    "article[class*='card']",
    "article[class*='post']",
    "article",
    "[class*='card'][class*='blog']",
    "[class*='card']",
    "[class*='post']",
    "[class*='item']",
    "main ul li",
]

# 标题：取文本
TITLE_SPECS = [
    "h1 a",
    "h2 a",
    "h3 a",
    "h1",
    "h2",
    "h3",
    "h4",
    "[class*='title']",
    "a[href*='/']",  # 用链接文本兜底
]

# 日期：先属性再文本；需与 generate_rss.parse_date 已支持格式一致
DATE_SELECTOR_CANDIDATES = [
    ("time@datetime", "attr"),
    ("time", "text"),
    ("[datetime]@datetime", "attr"),
    ("div[class*='__date']", "text"),
    ("div[class*='date']", "text"),
    ("span[class*='date']", "text"),
    "[fs-list-field=date]",
]


def fetch_soup(url: str, verify: bool = True) -> Tuple[BeautifulSoup, str, bool]:
    """抓取 URL，返回 (soup, base_url, ssl_ok)。若 SSL 失败则 ssl_ok=False."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSHub/1.0)"}
    try:
        r = requests.get(url, headers=headers, timeout=30, verify=verify)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return BeautifulSoup(r.text, "html.parser"), base, True
    except requests.exceptions.SSLError:
        if verify:
            try:
                r = requests.get(url, headers=headers, timeout=30, verify=False)
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                parsed = urlparse(url)
                base = f"{parsed.scheme}://{parsed.netloc}"
                return BeautifulSoup(r.text, "html.parser"), base, False
            except Exception as e:
                print(f"抓取失败: {e}", file=sys.stderr)
                raise SystemExit(1) from e
        raise
    except Exception as e:
        print(f"抓取失败: {e}", file=sys.stderr)
        raise SystemExit(1) from e


def get_path_segment(url: str) -> str:
    """从 URL 取路径第一段，用于 link 选择器，如 /blog、/engineering。"""
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    return "/" + path.split("/")[0]


def _select_text(parent, spec: str) -> Optional[str]:
    if not parent or not spec:
        return None
    node = parent.select_one(spec.strip())
    return node.get_text(strip=True) if node else None


def _select_attr(parent, spec: str, base_url: str) -> Optional[str]:
    if not parent or not spec or "@" not in spec:
        return None
    sel, attr = spec.split("@", 1)
    sel, attr = sel.strip(), attr.strip()
    node = parent.select_one(sel)
    if not node or not attr:
        return None
    val = node.get(attr)
    if val and attr == "href" and base_url:
        val = urljoin(base_url, val)
    return val.strip() if isinstance(val, str) else val


def try_entries(soup: BeautifulSoup, base_url: str, item_sel: str, path_segment: str):
    """
    在 soup 中用 item_sel 取条目，逐条尝试 title/link/date 候选，返回
    (entries_count, title_spec, link_spec, published_spec, sample_date_str)。
    """
    items = soup.select(item_sel)
    if len(items) < 2 or len(items) > 150:
        return 0, None, None, None, None

    # 确定链接选择器：优先指向同站列表路径的 a 标签
    link_path = path_segment or "/"
    link_spec_candidates = [
        f"a[href*='{link_path}']@href",
        "a[href*='/']@href",
        "h2 a@href",
        "h3 a@href",
        "h1 a@href",
        "a@href",
    ]

    best_title = best_link = best_published = None
    sample_date = None
    ok_count = 0

    for el in items:
        title_val = None
        for spec in TITLE_SPECS:
            title_val = _select_text(el, spec)
            if title_val and len(title_val) > 2 and len(title_val) < 300:
                if best_title is None:
                    best_title = spec
                break
        if not title_val:
            continue

        link_val = None
        for spec in link_spec_candidates:
            link_val = _select_attr(el, spec, base_url)
            if link_val and base_url in link_val and link_val != base_url + "/" and link_val != base_url:
                if best_link is None:
                    best_link = spec
                break
        if not link_val:
            # 允许无 link，但优先有 link
            if best_link is None and best_title:
                best_link = ""

        date_val = None
        for spec in DATE_SELECTOR_CANDIDATES:
            if isinstance(spec, tuple):
                sel, kind = spec
                date_val = _select_attr(el, sel, base_url) if kind == "attr" else _select_text(el, sel)
            else:
                date_val = _select_text(el, spec)
            if date_val and re.search(r"\d{4}", date_val) and len(date_val) < 50:
                if best_published is None:
                    best_published = spec if isinstance(spec, str) else spec[0]
                    sample_date = date_val.strip()
                break

        ok_count += 1

    if ok_count < 2:
        return 0, None, None, None, None
    return ok_count, best_title or "h2|h3", best_link or "a[href*='/']@href", best_published, sample_date


def infer_config(url: str, verify: bool = True) -> Optional[dict]:
    """
    抓取 url，推断 item_selector 与 selectors，返回建议配置 dict（不含 output/title 等由调用方填的字段）。
    若推断失败返回 None。
    """
    soup, base_url, ssl_ok = fetch_soup(url, verify=verify)
    path_segment = get_path_segment(url)

    for item_sel in ITEM_SELECTOR_CANDIDATES:
        count, title_spec, link_spec, published_spec, sample_date = try_entries(
            soup, base_url, item_sel, path_segment
        )
        if count >= 2 and title_spec and link_spec is not None:
            source = {
                "type": "html",
                "url": url,
                "item_selector": item_sel,
                "selectors": {
                    "title": title_spec,
                    "link": link_spec or "a[href*='/']@href",
                },
            }
            if published_spec:
                source["selectors"]["published"] = published_spec
            if not ssl_ok:
                source["verify"] = False
            return {
                "source": source,
                "sample_date": sample_date,
                "entry_count": count,
            }
    return None


def main():
    parser = argparse.ArgumentParser(description="从列表页 URL 推断 RSS 配置（抓取 + 选择器推断）")
    parser.add_argument("url", help="列表页 URL")
    parser.add_argument("--output", "-o", default="", help="建议的 output 文件名，如 feed.xml")
    parser.add_argument("--title", "-t", default="", help="建议的 feed 标题")
    parser.add_argument("--no-verify", action="store_true", help="请求时关闭 SSL 验证")
    args = parser.parse_args()

    result = infer_config(args.url, verify=not args.no_verify)
    if not result:
        print("未能推断出有效配置（未找到符合条件的条目容器或选择器）", file=sys.stderr)
        sys.exit(1)

    source = result["source"]
    entry_count = result["entry_count"]
    sample_date = result.get("sample_date")

    # 生成可追加到 config.yaml 的 YAML 片段
    output_name = args.output or "rss.xml"
    title = args.title or "RSS Feed"
    feed_link = source["url"]

    lines = [
        "  # 以下为 infer_rss_config.py 推断结果，请核对后放入 config.yaml 的 feeds 下",
        "  - output: " + output_name,
        "    feed:",
        "      title: \"" + title.replace('"', '\\"') + "\"",
        "      description: \"\"  # 可选",
        "      link: \"" + feed_link.replace('"', '\\"') + "\"",
        "    source:",
        "      type: html",
        "      url: \"" + source["url"].replace('"', '\\"') + "\"",
        "      item_selector: \"" + source["item_selector"].replace('"', '\\"') + "\"",
        "      selectors:",
        "        title: \"" + source["selectors"]["title"].replace('"', '\\"') + "\"",
        "        link: \"" + source["selectors"]["link"].replace('"', '\\"') + "\"",
    ]
    if "published" in source["selectors"]:
        lines.append("        published: \"" + source["selectors"]["published"].replace('"', '\\"') + "\"")
    if source.get("verify") is False:
        lines.append("      verify: false")

    print("\n".join(lines))
    print("", file=sys.stderr)
    print(f"推断条目数: {entry_count}", file=sys.stderr)
    if sample_date:
        print(f"示例日期字符串: {sample_date!r} → 若 generate_rss.parse_date 不支持，需在 parse_date 中增加对应格式", file=sys.stderr)
    config_rel = "scripts/config.yaml"
    print(f"请将上述 YAML 追加到 {config_rel} 的 feeds 下，然后运行: python scripts/generate_rss.py 做验证。", file=sys.stderr)


if __name__ == "__main__":
    main()
