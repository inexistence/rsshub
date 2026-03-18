---
name: rss-from-url
description: Turns a list-style webpage URL into RSS feed configuration (YAML). Fetches the page, infers item/title/link/date selectors, and outputs a config block. Use when the user wants to add a website as RSS source, "从链接生成配置", "把某网站配成 RSS", or provides a blog/list URL to turn into config.
---

# 从链接到 RSS 配置 (URL → Config)

将「任意列表页链接」沉淀为可复用的 RSS 配置：**抓取页面 → 推断选择器 → 写出 YAML → 检查验证**。

## 何时使用

- 用户给出**列表页 URL**（博客、新闻列表等），要求「配成 RSS」或「生成 config」
- 用户说「把某某网站加进 config」「从链接生成配置」「这个页面能做成 RSS 吗」

**输入**：必填 URL；可选 `output` 文件名、feed 的 `title` / `description`。

---

## 工作流

### 1. 抓取 + 推断（优先用脚本）

**运行环境**：脚本需 Python 3。若系统默认 `python` 为 2.7，请用 `python3` 或项目 `.venv/bin/python`。依赖在项目根执行 `pip install -r requirements.txt`（或先 `python3 -m venv .venv` 再在 venv 中安装），再运行下述命令。

在项目根目录执行本 skill 目录下的脚本：

```bash
.venv/bin/python .agent/skills/rss-from-url/infer_rss_config.py .agent/skills/rss-from-url/infer_rss_config.py "<URL>" [--output 文件名] [--title "标题"]
```

- 脚本会抓取 URL、推断 `item_selector` 与 `selectors`（title / link / published），并输出可追加到 config 的 YAML 片段。
- 本机 SSL 报错时加 `--no-verify`（输出中会带 `verify: false`）。
- 将输出核对后追加到 `scripts/config.yaml` 的 `feeds` 下，补全 `description` 等。
- **脚本失败时**：改用手动推断（见下），不确定页面结构可先看 **reference.md** 的快速检查脚本。

### 2. 写出配置

把脚本输出或手写配置写入 `scripts/config.yaml` 的 `feeds`。结构速查：

| 层级 | 字段 | 说明 |
|------|------|------|
| feed | title, description, link | 频道信息，link 可放 defaults |
| source | type: html, url | 必填 |
| source | item_selector | 每条列表项的容器 |
| source | selectors | title（必）, link, summary（可选，文章概要/描述）, published |
| source | verify | 可选，默认 true |

配置模板（条目必须有 `title`；无 `link` / `published` 可省略）：

```yaml
  - output: <如 feed.xml>
    feed:
      title: "<标题>"
      description: "<可选>"
      link: "<列表页 URL，建议与 source.url 一致>"
    source:
      type: html
      url: "<列表页 URL>"
      item_selector: "<条目容器 CSS 选择器>"
      selectors:
        title: "<标题选择器>"
        link: "<链接选择器，带 @href>"
        published: "<日期选择器，可选>"
        summary: "<可选，文章概要/描述选择器>"
      # verify: false   # 仅在本机 SSL 报错时加
```

### 3. 日期格式

若脚本 stderr 打印了「示例日期字符串」且 `generate_rss.parse_date` 尚未支持：在 `scripts/generate_rss.py` 的 `parse_date` 里往 `for fmt in (...)` 追加对应格式（如 `"%B %d, %Y"`、`"%b %d, %Y"`），naive datetime 用 `dt.replace(tzinfo=timezone.utc)`。更多格式见 **reference.md**。

### 4. 检查与验证（必须）

1. 在项目根执行：`python scripts/generate_rss.py`（或 `.venv/bin/python scripts/generate_rss.py`）。
2. 终端应有「已生成: rss/xxx.xml (N 条)」且 N ≥ 1；若为 0 则回到步骤 1/2 调整选择器或改用手动推断。
3. 打开 `rss/<output>.xml` 核对前几条的 title / link / pubDate。可选：用阅读器订阅一次。
4. **条数异常时**：若推断/生成条数明显偏少（如只有个位数），可能是选到了导航/侧栏而非正文列表。务必看 RSS 里前几条的 title 是否像「列表项」（如文章标题、公告标题），而不是菜单项；若不对，用下面「快速排查 DOM」重选 item_selector。

验证通过后才算完成。

---

## 经验与排查

- **快速排查 DOM**：脚本推断条数过少或不确定时，用 Python 对多种候选统计：对 `article`、`section`、`ol li`、`main ul li`、`[class*='item']` 等分别 `soup.select(sel)`，统计「匹配数、含 h2 数、含目标链接数」，选「匹配多且含 h2/链接多」的作为条目容器。

---

## 手动推断规则（脚本不可用或失败时）

- **条目容器**：按优先级尝试 `article[class*="ArticleList"]` → `article` → `[class*="card"]` → `[class*="post"]` → `ol li`（序号列表页）→ `[class*="item"]` → `main ul li`，选能匹配多条且每条内能区分标题/链接的。
- **标题**：容器内 `h1 a` / `h2 a` / `h3 a`（文本）或 `h1` / `h2` / `h3` / `[class*="title"]`，可用 `h2|h3`。
- **链接**：`h2 a@href`、`a[href*="/blog/"]@href` 等，href 需 `urljoin(base_url, href)` 转绝对地址。
- **日期**：`time@datetime` 或 `time` 文本，或 `[class*="date"]`、`[class*="__date"]`、`[fs-list-field="date"]`；记下页面格式在 `parse_date` 中追加（见步骤 3），格式对照见 **reference.md**。

选择器约定：`selector` 取文本，`selector@attr` 取属性（如 `a@href`），`a|b` 表示先试 a 再试 b。

---

## 示例（Claude Blog）

URL `https://claude.com/blog`，结构：`article.card_blog_list_wrap`，标题 `h3.card_blog_list_title`，链接 `a[href*='/blog/']`，日期 `div[fs-list-field=date]`（如 March 13, 2026）。对应配置（结构同上节模板）：

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

---

**参考**：同目录 **reference.md** — 选择器快速检查脚本、常见日期格式与 strftime 对照表。
