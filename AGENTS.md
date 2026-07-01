# AI 协作指南

本仓库：从网页/API 抓取列表数据，经可选转换管道，生成 RSS 并由 GitHub Pages 发布。

## 主流程

```
config.yaml → fetch（一次/source）→ transforms（可选）→ build_feed → rss/*.xml
```

## 关键目录

| 路径 | 职责 |
|------|------|
| `scripts/generate_rss.py` | CLI 入口 |
| `scripts/config.yaml` | 本地 feed 配置（gitignore，勿提交密钥） |
| `scripts/rss/config.py` | 解析 feeds / pipelines / variants / 输出路径 |
| `scripts/rss/fetchers/` | `html`、`next_json` 数据源 |
| `scripts/rss/transforms/` | 转换管道（Registry + translate 等） |
| `scripts/rss/dates.py` | 日期解析 |
| `scripts/rss/feed.py` | feedgen 组装 RSS |
| `rss/` | 生成的 XML（Actions 提交） |
| `.agent/skills/rss-from-url/` | 从 URL 推断 config 的技能 |

详细架构见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 常见任务 → 改哪里

| 任务 | 位置 |
|------|------|
| 新增 RSS 源 | `scripts/config.yaml`；可用 skill `rss-from-url` |
| 新增 fetch 类型 | `scripts/rss/fetchers/` + `fetchers/__init__.py` |
| 新增 transform（如 summarize） | `scripts/rss/transforms/<name>.py` + `@register` + 在 `__init__.py` import |
| 新增日期格式 | `scripts/rss/dates.py` → `parse_date` |
| 多语言 / 变体输出 | `config.yaml` → `variants` + `pipelines` |
| CI 定时与提交 | `.github/workflows/generate-rss.yml` |

## 运行与验证

```bash
pip install -r requirements.txt
python scripts/generate_rss.py
```

- 成功：stderr 打印 `已生成: rss/... (N 条)`，N ≥ 1
- 抓取或转换失败：若目标 XML 已存在则**保留旧文件**，不中断其他 feed

## 约定

- **无 variants** 的 feed：输出到 `rss/<output>`
- **有 variants** 的 feed：同组输出到 `rss/<dir>/`（`dir` 可显式指定，否则取主 output 文件名 stem）
- variant 的 `output` 只写文件名（如 `zh.xml`）
- 转换结果缓存：`.cache/transforms/`（gitignore）
- `pipelines.to_zh` 只译条目；variant 的频道 title/description 手写目标语言

## 文档索引

- 用户部署：`README.md`
- 架构与 config schema：`docs/ARCHITECTURE.md`
- 从 URL 加源：`.agent/skills/rss-from-url/SKILL.md`
