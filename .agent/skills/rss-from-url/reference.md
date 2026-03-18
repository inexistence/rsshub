# 选择器发现参考

## 快速检查脚本思路

当不确定页面结构时，可用临时脚本打印「条目数 + 前几条的 title/link/date」：

```python
from bs4 import BeautifulSoup
import requests
url = "列表页 URL"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(r.text, "html.parser")
for sel in ["article", "[class*='card']", "[class*='post']"]:
    items = soup.select(sel)
    if len(items) >= 3:
        print("item_selector 候选:", sel, "数量:", len(items))
        el = items[0]
        print("  title 候选:", el.select_one("h1, h2, h3") and el.select_one("h1, h2, h3").get_text(strip=True)[:50])
        print("  link 候选:", el.select_one("a[href]") and el.select_one("a[href]").get("href"))
        print("  date 候选:", el.select_one("time") or el.select_one("[class*='date']"))
        break
```

根据输出调整 `item_selector` 与 `selectors`，再写进 config。

## 常见日期格式与 strftime

| 页面示例 | strftime 格式 |
|----------|----------------|
| 2026-03-13 | %Y-%m-%d |
| March 13, 2026 | %B %d, %Y |
| 13 Mar 2026 | %d %b %Y |
| Wed, 18 Mar 2026 | %a, %d %b %Y |

未支持时在 `parse_date` 的 `for fmt in (...)` 中追加，并保证返回的 datetime 带 tzinfo（如 `timezone.utc`）。
