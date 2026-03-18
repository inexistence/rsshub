# 选择器发现参考

## 快速检查脚本思路

当不确定页面结构时，可用临时脚本打印「条目数 + 前几条的 title/link/date/summary」：

```python
from bs4 import BeautifulSoup
import requests
url = "列表页 URL"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(r.text, "html.parser")
for sel in ["article", "[class*='card']", "[class*='post']", "li[class*='announcement']"]:
    items = soup.select(sel)
    if len(items) >= 3:
        print("item_selector 候选:", sel, "数量:", len(items))
        el = items[0]
        print("  title 候选:", el.select_one("h1, h2, h3") and el.select_one("h1, h2, h3").get_text(strip=True)[:50])
        print("  link 候选:", el.select_one("a[href]") and el.select_one("a[href]").get("href"))
        print("  date 候选:", el.select_one("time") or el.select_one("[class*='date']"))
        # summary：见下节「概要/描述」常见 class
        for sum_sel in ["[class*='post-body']", "[class*='excerpt']", "[class*='summary']", "[class*='body']", "p"]:
            p = el.select_one(sum_sel)
            if p:
                t = p.get_text(strip=True)
                if len(t) > 20:
                    print("  summary 候选", sum_sel, ":", (t[:80] + "..." if len(t) > 80 else t))
                    break
        break
```

根据输出调整 `item_selector` 与 `selectors`（含可选的 summary），再写进 config。

## 概要/描述（summary）

- **作用**：config 里 `source.selectors.summary` 对应「条目描述」，会输出为 RSS 每条 `<item>` 的 `<description>`。不配则该项为空。
- **常见选择器**（按优先级尝试）：
  - `[class*='post-body']`、`[class*='announcement__post-body']`：列表项正文块（如 Google Help 公告）
  - `[class*='excerpt']`、`[class*='summary']`、`[class*='description']`、`[class*='desc']`
  - `[class*='body']`、`[class*='content']`：正文/内容容器
  - `p`：首段（注意排除导航/按钮等短文本）
- **手动排查**：若推断脚本未给出 summary，在条目容器内找「一段 20～800 字、像摘要」的文本所在节点，看其 class 是否含 `body`/`content`/`excerpt`/`summary`，对应写成 `summary: "div.xxx"` 追加到 config 的 selectors。
- **长度**：推断脚本只接受约 20～800 字符的文本作为 summary；过长可能被当成正文而忽略，过短可能是按钮/标签。若页面摘要更长，可放宽 `infer_rss_config.py` 的 `SUMMARY_MAX_LEN` 或直接手写 summary 选择器。

## 常见日期格式与 strftime

| 页面示例 | strftime 格式 |
|----------|----------------|
| 2026-03-13 | %Y-%m-%d |
| March 13, 2026 | %B %d, %Y |
| 13 Mar 2026 | %d %b %Y |
| Wed, 18 Mar 2026 | %a, %d %b %Y |

未支持时在 `parse_date` 的 `for fmt in (...)` 中追加，并保证返回的 datetime 带 tzinfo（如 `timezone.utc`）。
