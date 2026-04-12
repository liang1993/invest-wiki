# invest-wiki

个人投资知识库，基于 [Karpathy LLM Wiki](https://github.com/karpathy/llm-wiki) 模式构建。通过 Claude Code 自动维护结构化的投资研究笔记。

## 目录结构

```
raw/            # 不可变的原始资料（研报PDF、文章、笔记）
wiki/           # LLM 生成和维护的知识页面
  stocks/       # 个股研究（贵州茅台、青岛啤酒、中信证券…）
  sectors/      # 行业分析（白酒…）
  macro/        # 宏观经济（仪表盘、消费趋势…）
  funds/        # 基金/ETF 研究
  strategies/   # 投资策略与框架
  journal/      # 投资日志与复盘
  index.md      # 内容索引
CLAUDE.md       # Schema 配置，定义页面模板和工作流
```

## 工作流

- **Ingest** — 将研报、文章等原始资料摄入 `raw/`，LLM 自动提取关键信息并更新 wiki 页面
- **Query** — 提出投资问题，LLM 综合多个页面回答并引用来源
- **Lint** — 检查 wiki 健康度：时效性、链接、索引同步、矛盾检测

## 当前内容

| 分类 | 页面 |
|------|------|
| 个股 | 贵州茅台、青岛啤酒、中信证券、腾讯控股、阿里巴巴 |
| 基金/ETF | 中证红利ETF招商(515080)、中证红利ETF易方达(515180)、红利低波ETF华泰柏瑞(512890)、红利低波100ETF景顺(515100) |
| 行业 | 白酒、啤酒、证券、储能 |
| 宏观 | 宏观仪表盘、消费趋势、资本市场政策 |
| 日志 | 2026-04-12 宏观全景分析 |

## 使用方式

需要 [Claude Code](https://claude.ai/claude-code) CLI。在项目目录下启动 Claude Code，它会自动读取 `CLAUDE.md` 中的 schema 配置。

```bash
# 摄入一份研报
# 把 PDF 放入 raw/reports/，然后告诉 Claude 处理它

# 查询
# 直接用自然语言提问，如"茅台当前估值是否合理？"

# 维护
# 要求 Claude 执行 lint 检查
```
