# RSS 自动生成（GitHub Actions + GitHub Pages）

通过 GitHub Actions 定时从**多个网页**解析数据，生成**多份** RSS 并提交回仓库，由 GitHub Pages 提供订阅。

```
网页列表页（HTML）
       ↓
GitHub Actions 定时跑脚本（网页解析）
       ↓
生成多份 RSS（如 blog.xml、news.xml）
       ↓
commit 到 repo
       ↓
GitHub Pages 提供订阅
```

## 功能

- **多源多 RSS**：在 `config.yaml` 里配置多个 `feeds`，每个源对应一个输出文件。
- **网页解析**：用 CSS 选择器解析列表页，`item_selector` 选块，`selectors` 里配置 title/link/description/published，支持 `选择器@属性`（如 `a@href`、`time@datetime`）。
- **转换管道**：可选 transforms（如翻译），支持 `pipelines` 复用、`variants` 一源多输出（如中文版）。
- **自带 rss-from-url 技能**：在 Cursor 等支持 Agent Skills 的环境下，本项目包含 **rss-from-url** 技能。直接对 Agent 说「把某链接配成 RSS」「从链接生成配置」并给出列表页 URL，会按「抓取页面 → 推断选择器 → 写出 config → 检查验证」的流程处理。抓取与推断由 `.agent/skills/rss-from-url/infer_rss_config.py` 完成，验证则通过运行 `generate_rss.py` 并检查生成的 XML。技能定义见 `.agent/skills/rss-from-url/SKILL.md`。

> **开发者 / AI**：配置见 [docs/CONFIG.md](docs/CONFIG.md)，架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 快速开始

### 1. 推送到 GitHub

```bash
git init
git add .
git commit -m "feat: add RSS generator workflow"
git remote add origin https://github.com/<你的用户名>/rsshub.git
git push -u origin main
```

### 2. 设置工作流程权限（必选）

要让 Actions 把生成的 RSS 自动提交回仓库，需要开启写入权限：

- 仓库 **Settings** → **Actions** → **General**
- 在 **Workflow permissions** 中选择 **Read and write permissions**
- 点击 **Save**

（无需单独配置 `GITHUB_TOKEN`，也无需勾选「Allow GitHub Actions to create and approve pull requests」。）

### 3. 配置多数据源

```bash
cp scripts/config.example.yaml scripts/config.yaml
```

编辑 `scripts/config.yaml`（字段说明见 **[docs/CONFIG.md](docs/CONFIG.md)**）：

- **defaults.feed**：所有 feed 共用的默认值（如 link、language）。每个 feed 里只写要覆盖或各自不同的字段（如 title、description）。
- **feeds**：列表，每项包含 **output**（生成文件名）、**feed**（该订阅的 title/link/description）、**source**（`html`、`next_json` 或 `email`）。见 `config.example.yaml`。
- **邮箱源凭证**：在 config 里只写 `host_env` / `user_env` / `password_env` 变量名；本地复制 `.env.example` 为 `.env` 填入实际值，详见 [CONFIG.md](docs/CONFIG.md)。

注意：`config.yaml` **可提交**（只写环境变量名，不含密码）；`.env` 含真实凭证，**勿提交**。CI 跑邮箱源时在 GitHub **Secrets** 配置同名变量（见 [CONFIG.md — GitHub Actions](docs/CONFIG.md#github-actionsrepository-secrets)）。

### 4. 开启 GitHub Pages

- 仓库 **Settings** → **Pages**
- **Source** 选 **Deploy from a branch**
- **Branch** 选 `main`，目录选 **/ (root)**，Save

订阅地址示例（多份 RSS，文件在 `rss/` 目录下）：

```
https://<你的用户名>.github.io/rsshub/rss/blog.xml
https://<你的用户名>.github.io/rsshub/rss/deeplearning-letters/feed.xml
https://<你的用户名>.github.io/rsshub/rss/deeplearning-letters/zh.xml
```

### 5. 可选：Repo 变量与 Secrets

- **Variables**（`RSS_TITLE`、`RSS_LINK`、`RSS_DESCRIPTION`）：未在 config 里写死的 feed 默认值。
- **Secrets**（邮箱源）：`EMAIL_163_HOST`、`EMAIL_163_USER`、`EMAIL_163_PASSWORD` 等，名称须与 config 里 `*_env` 一致。配置步骤见 **[docs/CONFIG.md](docs/CONFIG.md)**。

## 定时与触发

- **定时**：默认每天 UTC 0:00、8:00、16:00 各跑一次，可在 `.github/workflows/generate-rss.yml` 里改 `schedule`。
- **手动**：Actions 页选择 **Generate RSS** → **Run workflow**。
- **推送**：修改 `scripts/` 或该 workflow 并推送到 `main` 时也会跑一次。

## 项目结构

```
rsshub/
├── AGENTS.md                            # AI 协作入口
├── docs/
│   ├── CONFIG.md                        # config.yaml 完整配置说明
│   └── ARCHITECTURE.md                  # 架构、CI、扩展 transform
├── .agent/skills/rss-from-url/          # 自带技能：从链接生成 config
│   └── SKILL.md
├── .github/workflows/generate-rss.yml   # 定时 + 生成 + 提交 rss/
├── scripts/
│   ├── config.example.yaml              # 多源示例（含 variants / pipelines）
│   ├── config.yaml                      # feed 配置（提交）；密钥见 .env
│   ├── generate_rss.py                  # CLI 入口
│   └── rss/                             # 生成逻辑（fetchers、transforms 等）
├── rss/                                 # 生成的 RSS（由 Actions 提交）
├── requirements.txt
└── README.md
```

## 网页解析配置说明

`type: html` 的 source 示例：

```yaml
source:
  type: html
  url: "https://example.com/blog"
  item_selector: "article.post"    # 每个条目的容器
  selectors:
    title: "h2 a"                 # 文本
    link: "h2 a@href"             # 取 href，并自动补全为绝对 URL
    description: ".excerpt"
    published: "time@datetime"    # 取 datetime 属性
```

选择器支持 `|` 表示备选（第一个匹配到即用）。未配置的字段可省略。

## 多语言变体（variants）

同一 source 可生成多个输出（如原文 + 中文版），只 fetch 一次。有 variants 时输出到 `rss/{dir}/` 子目录。详见 **[docs/CONFIG.md](docs/CONFIG.md)**。

`to_zh` 只翻译条目；variant 的频道 title/description 需手写中文。

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
    source: { ... }
    variants:
      - output: zh.xml
        feed: { title: "示例（中文）", language: zh-CN }
        transforms:
          use: to_zh
```
