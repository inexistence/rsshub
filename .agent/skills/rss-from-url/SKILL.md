---
name: rss-from-url
description: Turns a list-style webpage URL into RSS feed configuration (YAML). Fetches the page, infers item/title/link/date selectors, and outputs a config block. Use when the user wants to add a website as RSS source, "从链接生成配置", "把某网站配成 RSS", or provides a blog/list URL to turn into config.
---

# 从链接到 RSS 配置 (URL → Config)

将「任意列表页链接」沉淀为可复用的 RSS 配置：抓取页面 → 推断选择器 → 写出 YAML。

## 何时使用

- 用户给出一个**列表页 URL**（博客、新闻列表等），要求「配成 RSS」或「生成 config」
- 用户说「把某某网站加进 config」「从链接生成配置」「这个页面能做成 RSS 吗」

## 输入

- **必填**：列表页 URL（如 `https://example.com/blog`）
- **可选**：`output` 文件名（如 `claude.xml`）、feed 的 `title` / `description`

## 工作流

### 1. 抓取页面

- 用 `requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)` 拉取 HTML。
- 若报错 `CERTIFICATE_VERIFY_FAILED`：在生成的 `source` 下加 `verify: false`，并在脚本里支持 `verify = source.get("verify", True)` 传给 `requests.get(..., verify=verify)`。

### 2. 推断结构（BeautifulSoup）

用脚本或内联代码完成：

- **条目容器 (item_selector)**：按优先级尝试  
  `article` → `[class*="card"]` → `[class*="post"]` → `[class*="item"]` → `main ul li`。  
  选能匹配到多条、且每条内能唯一区分标题/链接的容器。
- **标题 (title)**：在每条容器内找  
  `h1 a` / `h2 a` / `h3 a`（取文本）；若无 `a`，则 `h1` / `h2` / `h3` 或 `[class*="title"]`（取文本）。
- **链接 (link)**：  
  `h1 a@href` / `h2 a@href` / `h3 a@href`，或 `a[href*="/blog/"]@href`、`a[href*="/news/"]@href` 等（取 `href`，需用 `urljoin(base_url, href)` 转绝对地址）。
- **日期 (published)**：  
  `time@datetime` 或 `time`（文本）；若无 `time`，再找 `[class*="date"]`、`[fs-list-field="date"]` 等。  
  记下实际日期字符串格式（如 `March 13, 2026` → `%B %d, %Y`）。

选择器规范（与 generate_rss 一致）：

- `selector`：取该节点**文本**。
- `selector@attr`：取该节点**属性**（如 `a@href`）。
- `a|b`：先试 `a`，没有再试 `b`。

### 3. 写出配置

在项目的 `config.yaml` 的 `feeds` 下追加一段：

```yaml
  - output: <文件名，如 claude.xml>
    feed:
      title: "<feed 标题>"
      description: "<可选>"
    source:
      type: html
      url: "<列表页 URL>"
      item_selector: "<条目容器 CSS 选择器>"
      selectors:
        title: "<标题选择器>"
        link: "<链接选择器，带 @href>"
        published: "<日期选择器，可选>"
      # verify: false   # 仅在本机 SSL 报错时加
```

条目必须有 `title`；若没有 `link` 或 `published`，可省略对应字段。

### 4. 日期格式与脚本

若页面日期格式在 `generate_rss.parse_date` 中尚未支持（例如 `March 13, 2026`），在 `generate_rss.py` 的 `parse_date` 里：

- 在 `for fmt in (...)` 中加入对应格式（如 `"%B %d, %Y"`）。
- 若 `datetime.strptime` 得到的是 naive datetime，用 `dt.replace(tzinfo=timezone.utc)` 再返回，以满足 feedgen 的 `published` 要求。

### 5. 验证

运行项目的 RSS 生成命令（如 `python3 scripts/generate_rss.py`），确认生成的 XML 里出现预期条目；若条目为 0，回到步骤 2 调整 `item_selector` 或各 `selectors`。

## 配置结构速查

| 层级 | 字段 | 说明 |
|------|------|------|
| feed | title, description, link | 频道信息，link 可放在 defaults |
| source | type: html, url | 必填 |
| source | item_selector | 每条列表项的容器 |
| source | selectors | title（必）, link, description, published |
| source | verify | 可选，默认 true |

## 示例（Claude Blog）

- URL: `https://claude.com/blog`
- 实际结构：`article.card_blog_list_wrap`，标题在 `h3.card_blog_list_title`（无内嵌 a），链接在 `a[href*='/blog/']`，日期在 `div[fs-list-field=date]`（文本如 March 13, 2026）。

对应配置：

```yaml
  - output: claude.xml
    feed:
      title: "Claude Blog"
      description: "Product news and best practices for teams building with Claude"
    source:
      type: html
      url: "https://claude.com/blog"
      item_selector: "article.card_blog_list_wrap"
      selectors:
        title: "h3.card_blog_list_title"
        link: "a[href*='/blog/']@href"
        published: "div[fs-list-field=date]"
```

并在 `parse_date` 中增加 `"%B %d, %Y"`，且对 naive 日期补 `timezone.utc`。
