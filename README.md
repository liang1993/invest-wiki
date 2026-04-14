# invest-wiki

个人投资知识库，基于 [Karpathy LLM Wiki](https://github.com/karpathy/llm-wiki) 模式构建。通过 Claude Code 自动维护结构化的投资研究笔记。

## 结构

```
raw/            # 原始资料（研报、文章、笔记）
wiki/           # 知识页面（个股/基金/行业/宏观/策略/日志）
skills/         # Claude Code skills（估值模型、数据获取等）
CLAUDE.md       # Schema 配置
```

## 工作流

- **Ingest** — 摄入原始资料，自动提取并更新 wiki
- **Query** — 自然语言提问，综合多页面回答
- **Lint** — 检查时效性、链接、索引同步

## 使用

需要 [Claude Code](https://claude.ai/claude-code)，在项目目录下启动即可。
