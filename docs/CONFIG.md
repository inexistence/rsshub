# config.yaml 配置说明

`scripts/config.yaml` 控制所有 RSS 源的抓取、转换与输出，**随仓库提交**。复制 `scripts/config.example.yaml` 为起点，或直接向现有 `feeds` 追加。

```bash
cp scripts/config.example.yaml scripts/config.yaml
python scripts/generate_rss.py
```

---

## 文件结构概览

```yaml
defaults:       # 可选，全局 feed 默认值
  feed: { ... }

pipelines:      # 可选，可复用的转换管道
  to_zh: [ ... ]

feeds:          # 必填，数据源列表
  - output: ...
    feed: { ... }
    source: { ... }
    transforms: ...    # 可选
    variants: [ ... ]  # 可选
```

---

## 顶层字段

### `defaults.feed`

所有 feed 共用的频道默认值。每个 `feeds[]` 项里的 `feed` 会**覆盖**同名字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 频道标题 |
| `description` | string | 频道描述 |
| `link` | string | 频道链接（建议与列表页 URL 一致） |
| `language` | string | RSS language，如 `zh-CN`、`en` |

也可用环境变量作为兜底（config 未写时）：`RSS_TITLE`、`RSS_LINK`、`RSS_DESCRIPTION`。

### `pipelines`

命名转换管道，供 `transforms.use` 或 step 里的 `pipeline:` 引用。

```yaml
pipelines:
  to_zh:
    - type: translate
      target: zh-CN
      fields: [title, summary]
      on_error: keep
```

### `feeds`

数据源与输出列表，每项为一个 **feed group**（共享 `source`，可产生多个 XML）。

---

## feeds[] 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `output` | 是 | 输出文件名，如 `blog.xml` 或 `feed.xml` |
| `dir` | 否 | 有 `variants` 时作为子目录名；省略则用 `output` 的文件名（不含扩展名） |
| `feed` | 否 | 频道元数据，字段见上表 |
| `source` | 是 | 数据源，见下文 |
| `transforms` | 否 | 主输出（原文）的转换管道 |
| `variants` | 否 | 变体输出列表，结构与下表相同（无 `source`） |

### variants[] 每项

| 字段 | 必填 | 说明 |
|------|------|------|
| `output` | 是 | 文件名，如 `zh.xml`（有 variants 时只写文件名即可） |
| `feed` | 否 | 覆盖频道元数据（合并自主 feed + 本项） |
| `transforms` | 否 | 该变体的转换管道 |

---

## 输出路径规则

| 情况 | 生成路径 | 示例 |
|------|----------|------|
| 无 `variants` | `rss/<output>` | `rss/blog.xml` |
| 有 `variants` | `rss/<dir>/<output>` | `rss/claude/feed.xml`、`rss/claude/zh.xml` |

有 `variants` 时，**同组只 fetch 一次** `source`，每个 output 独立跑 transforms 并写 XML。

---

## source 配置

### type: html

从列表页 HTML 用 CSS 选择器解析条目。

```yaml
source:
  type: html
  url: "https://example.com/blog"
  item_selector: "article.post"    # 每条目的容器
  selectors:
    title: "h2 a"                  # 必填
    link: "h2 a@href"              # 可选，自动补全为绝对 URL
    summary: ".excerpt"            # 可选 → RSS <description>
    published: "time@datetime"     # 可选 → pubDate
  verify: true                     # 可选，默认 true；本机 SSL 报错时设 false
  headers:                         # 可选，合并到默认 User-Agent
    Cookie: "..."
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `type` | 是 | `html` |
| `url` | 是 | 列表页 URL |
| `item_selector` | 是 | 条目容器 CSS 选择器 |
| `selectors` | 是 | 字段映射，至少含 `title` |
| `verify` | 否 | HTTPS 证书校验，默认 `true` |
| `headers` | 否 | 额外 HTTP 请求头 |

**选择器约定**

- `selector` — 取节点文本
- `selector@attr` — 取属性（如 `a@href`、`time@datetime`）
- `a|b` — 优先 `a`，没有再试 `b`
- 兼容旧字段名 `item_map`（同 `selectors`）

条目无 `title` 会被丢弃；最多抓取 50 条。

### type: next_json

从 Next.js `_next/data/{buildId}{path}.json` 解析（适合 CI 上 HTML 被 403 的站点）。

```yaml
source:
  type: next_json
  bootstrap_url: "https://www.example.com/the-batch"
  build_id: "abc123"               # 可选，CI 上 HTML 被 403 时建议填写
  page_path: "/the-batch/tag/letters"
  link_prefix: "https://www.example.com/the-batch"
  items_key: posts                 # 可选，默认 posts
  selectors:
    title: "title"
    link: "slug"                   # 与 link_prefix 拼绝对 URL
    published: "published_at"
    summary: "custom_excerpt|excerpt"
  verify: true
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `bootstrap_url` | 是* | 用于拼 JSON 域名；无 `build_id` 时也从该页 HTML 提取 buildId |
| `build_id` | 否 | Next.js buildId；填写后跳过 HTML 抓取（适合 GitHub Actions 等 CI） |
| `page_path` | 是 | JSON 路径，如 `/the-batch/tag/letters` |
| `link_prefix` | 否 | `link` 为 slug 时的 URL 前缀 |
| `items_key` | 否 | `pageProps` 下数组字段名，默认 `posts` |
| `selectors` | 是 | JSON 字段名映射；支持 `a|b` 优先 |

*`url` 可代替 `bootstrap_url`。

**buildId 获取顺序**：`build_id` 配置 → `.cache/next_json/` 缓存 → 抓取 `bootstrap_url` HTML。站点重新部署后若 JSON 返回 404，本地重新抓取可更新缓存，或手动改 `build_id`（在 HTML 源码中搜 `"buildId"`）。

### type: email

通过 IMAP 从邮箱拉取邮件，适合订阅邮件列表、Newsletter 等。

```yaml
source:
  type: email
  host_env: EMAIL_163_HOST
  user_env: EMAIL_163_USER
  password_env: EMAIL_163_PASSWORD
  folder: RSS                        # 可选，默认 INBOX
  limit: 15                          # 可选，最多条数，默认 50
  since_days: 30                     # 可选，只拉最近 N 天
  from_filter: newsletter@example.com  # 可选，发件人过滤
  subject_filter: "Weekly Digest"    # 可选，主题过滤
  link_from_body: true               # 可选，从正文提取首个 URL 作为 link
  summary_max_chars: 500             # 可选，摘要最大长度
  body_format: plain                 # 可选，plain | html
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `type` | 是 | `email` |
| `host_env` | 是 | IMAP 服务器对应的环境变量名，如 `EMAIL_163_HOST` |
| `user_env` | 是 | 邮箱账号对应的环境变量名 |
| `password_env` | 是 | 授权码/应用密码对应的环境变量名 |
| `folder` / `mailbox` | 否 | 邮箱文件夹，默认 `INBOX` |
| `port` | 否 | 默认 `993` |
| `ssl` | 否 | 默认 `true` |
| `since_days` | 否 | 只拉最近 N 天邮件 |
| `from_filter` | 否 | IMAP FROM 过滤 |
| `subject_filter` | 否 | IMAP SUBJECT 过滤 |
| `criteria` | 否 | 自定义 IMAP 搜索条件，覆盖上述过滤 |
| `link_from_body` | 否 | 从正文提取首个 `http(s)` 链接，默认 `true` |
| `summary_max_chars` | 否 | 摘要截断长度，默认 `500` |
| `body_format` | 否 | 摘要优先 `plain` 或 `html`，默认 `plain` |
| `limit` | 否 | 最多条目数，默认 `50` |
| `imap_id` | 否 | 强制发送 IMAP `ID`；网易系域名默认开启 |

**凭证**：`host`、`user`、密码**均不写入** `config.yaml`，只在 config 里写环境变量名，实际值放在 `.env`（本地）或 GitHub Secrets（CI）。

#### 本地：`.env`

```bash
cp .env.example .env
# 编辑 .env，填入 EMAIL_163_HOST / EMAIL_163_USER / EMAIL_163_PASSWORD
python scripts/generate_rss.py
```

`.env` 位于仓库根目录，已被 `.gitignore`；`generate_rss.py` 启动时会自动加载。

#### GitHub Actions：Secrets

凭证可放在 **Repository secrets** 或 **Environment secrets**（推荐按邮箱单独建 Environment，如 `EMAIL_163`）。

**方式 A：Environment secrets（推荐）**

1. **Settings** → **Environments** → 新建或打开 `EMAIL_163`
2. 在 **Environment secrets** 中添加（名称须与 config 里 `*_env` 一致）：

| Secret 名称 | 示例值 | 说明 |
|-------------|--------|------|
| `EMAIL_163_HOST` | `imap.163.com` | IMAP 服务器 |
| `EMAIL_163_USER` | `you@163.com` | 邮箱账号 |
| `EMAIL_163_PASSWORD` | `xxxx` | 163 授权码（非登录密码） |

3. workflow 的 job 需声明 `environment: EMAIL_163`（见 `.github/workflows/generate-rss.yml`），否则读不到 Environment secrets。

**方式 B：Repository secrets**

在 **Settings** → **Secrets and variables** → **Actions** → **Repository secrets** 添加上表同名 Secret；workflow 里 `env:` 引用方式相同，可去掉 job 上的 `environment:`。

workflow 中 `Generate RSS` 步骤通过 `env` 注入变量；Secret 名称必须与 `config.yaml` 里的 `host_env` / `user_env` / `password_env` 字符串**完全一致**。

Gmail 等需开启 IMAP 并使用[应用专用密码](https://support.google.com/accounts/answer/185833)。

**网易邮箱（163 / 126 / yeah）**：登录后需发送 IMAP `ID` 命令，代码已对 `*.163.com` 等域名自动处理；其他服务商若遇 `SELECT` 失败可设 `imap_id: true`。

**条目映射**：`Subject` → `title`；`Date` → `published`；正文 → `summary`；正文首个 URL → `link`（可关）。

---

## transforms 配置

转换在 fetch 之后、写 XML 之前执行。支持三种写法。

### 1. 直接写 step 列表

```yaml
transforms:
  - type: translate
    target: zh-CN
    fields: [title, summary]
    on_error: keep
```

### 2. 引用 pipeline + 追加

```yaml
transforms:
  use: to_zh              # 字符串，或列表 [to_zh, other]
  append:
    - type: summarize     # 未来
      fields: [summary]
```

### 3. 步骤内引用 / 嵌套

```yaml
transforms:
  - pipeline: to_zh       # 展开命名管道
  - type: translate
    target: ja
    fields: [title]
    then:                 # 本步之后执行的子管道
      - type: summarize
        fields: [summary]
```

---

## transform: translate

| 字段 | 默认 | 说明 |
|------|------|------|
| `type` | — | 固定 `translate` |
| `target` | — | 目标语言，如 `zh-CN`、`zh-TW`、`en` |
| `fields` | `[title, summary]` | 要翻译的**条目**字段 |
| `feed_fields` | `[]` | 要翻译的**频道**字段，如 `[title, description]` |
| `source` | `auto` | 源语言 |
| `provider` | `easytranslator` | 翻译后端 |
| `engines` | 代码内默认 | 覆盖 easytranslator 引擎优先级列表 |
| `on_error` | `keep` | 失败策略，见下 |

**`on_error`**

| 值 | 行为 |
|----|------|
| `keep` | 该字段保留原文（推荐） |
| `skip` | 丢弃整条 entry |
| `fail` | 抛错；若目标 XML 已存在则 CI 保留旧文件 |

**中文版 variant 推荐写法**

- `pipelines.to_zh` 只译条目（`fields`）
- variant 的 `feed.title` / `feed.description` **手写中文**
- 若也要机器翻译频道信息，在 step 里加 `feed_fields: [title, description]`（且 feed 元数据保持外文）

**翻译缓存**：原文 + 配置不变时复用 `.cache/transforms/`；CI 经 `actions/cache` 跨 run 持久化。

**中文校验**：目标为 `zh-CN` 等时，译文必须含汉字；否则视为失败，保留英文且不缓存乱码。

---

## 完整示例

### 单文件 HTML 源

```yaml
defaults:
  feed:
    link: "https://your-name.github.io/rsshub"
    language: "zh-CN"

feeds:
  - output: blog.xml
    feed:
      title: "某站博客"
      description: "列表页 RSS"
      link: "https://example.com/blog"
    source:
      type: html
      url: "https://example.com/blog"
      item_selector: "article.post"
      selectors:
        title: "h2"
        link: "a@href"
        summary: ".excerpt"
        published: "time@datetime"
```

→ `rss/blog.xml`

### 一源多输出（原文 + 中文）

```yaml
pipelines:
  to_zh:
    - type: translate
      target: zh-CN
      fields: [title, summary]
      on_error: keep

feeds:
  - dir: example
    output: feed.xml
    feed:
      title: "Example Blog"
      language: en
      link: "https://example.com/blog"
    source:
      type: html
      url: "https://example.com/blog"
      item_selector: "article.post"
      selectors:
        title: "h2"
        link: "a@href"
    variants:
      - output: zh.xml
        feed:
          title: "示例博客"
          description: "中文版"
          language: zh-CN
        transforms:
          use: to_zh
```

→ `rss/example/feed.xml`、`rss/example/zh.xml`

### Next.js JSON 源 + 中文 variant

```yaml
feeds:
  - dir: letters
    output: feed.xml
    feed:
      title: "Letters"
      link: "https://www.example.com/letters"
    source:
      type: next_json
      bootstrap_url: "https://www.example.com/app"
      page_path: "/letters"
      link_prefix: "https://www.example.com"
      selectors:
        title: "title"
        link: "slug"
        published: "published_at"
        summary: "excerpt"
    variants:
      - output: zh.xml
        feed:
          title: "来信（中文）"
        transforms:
          use: to_zh
```

---

## 日期格式

若页面日期无法解析，在 `scripts/rss/dates.py` 的 `parse_date` 中追加 strftime 格式。常见格式见 `.agent/skills/rss-from-url/reference.md`。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 代码结构、CI、扩展 transform |
| [AGENTS.md](../AGENTS.md) | AI 协作入口 |
| [config.example.yaml](../scripts/config.example.yaml) | 可复制模板 |
| [rss-from-url SKILL](../.agent/skills/rss-from-url/SKILL.md) | 从 URL 推断 HTML 源配置 |
