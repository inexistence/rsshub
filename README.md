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
- **自带 rss-from-url 技能**：在 Cursor 等支持 Agent Skills 的环境下，本项目包含 **rss-from-url** 技能。直接对 Agent 说「把某链接配成 RSS」「从链接生成配置」并给出列表页 URL，会按「抓取页面 → 推断选择器 → 写出 config」的流程自动生成对应 `config.yaml` 片段并处理日期格式。技能定义见 `.agent/skills/rss-from-url/SKILL.md`。

## 快速开始

### 1. 推送到 GitHub

```bash
git init
git add .
git commit -m "feat: add RSS generator workflow"
git remote add origin https://github.com/<你的用户名>/rsshub.git
git push -u origin main
```

### 2. 配置多数据源

```bash
cp scripts/config.example.yaml scripts/config.yaml
```

编辑 `scripts/config.yaml`：

- **defaults.feed**：所有 feed 共用的默认值（如 link、language）。每个 feed 里只写要覆盖或各自不同的字段（如 title、description）。
- **feeds**：列表，每项包含 **output**（生成文件名）、**feed**（该订阅的 title/link/description）、**source**（type: html，以及 url、item_selector、selectors）。见 `config.example.yaml`。

注意：`config.yaml` 已被 `.gitignore`。若要在 Actions 里用，可在 workflow 里用 Secrets 生成该文件，或提交不含敏感信息的 config。

### 3. 开启 GitHub Pages

- 仓库 **Settings** → **Pages**
- **Source** 选 **Deploy from a branch**
- **Branch** 选 `main`，目录选 **/ (root)**，Save

订阅地址示例（多份 RSS）：

```
https://<你的用户名>.github.io/rsshub/blog.xml
https://<你的用户名>.github.io/rsshub/news.xml
```

### 4. 可选：Repo 变量

在 **Settings** → **Secrets and variables** → **Actions** → **Variables** 中可添加 `RSS_TITLE`、`RSS_LINK`、`RSS_DESCRIPTION`，作为未在 config 里写死的 feed 默认值。

## 定时与触发

- **定时**：默认每天 UTC 0:00、8:00、16:00 各跑一次，可在 `.github/workflows/generate-rss.yml` 里改 `schedule`。
- **手动**：Actions 页选择 **Generate RSS** → **Run workflow**。
- **推送**：修改 `scripts/` 或该 workflow 并推送到 `main` 时也会跑一次。

## 项目结构

```
rsshub/
├── .agent/skills/rss-from-url/          # 自带技能：从链接生成 config
│   └── SKILL.md
├── .github/workflows/generate-rss.yml   # 定时 + 生成 + 提交所有 *.xml
├── scripts/
│   ├── config.example.yaml              # 多源示例（仅网页解析）
│   ├── config.yaml                      # 本地配置（不提交）
│   └── generate_rss.py                  # 多源生成脚本
├── *.xml                                # 生成的 RSS（由 Actions 提交）
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
