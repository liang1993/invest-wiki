# 多 Harness 接线清单

> 本仓库执行层已脱离 Claude Code 专属（[`multi-harness-plan.md`](multi-harness-plan.md)）。任一支持 **Agent Skills 开放标准 + bash** 的 harness，照本清单配置后可跑 query / ingest（L1→L2→L3）/ verify / commit（pre-commit 生效）。`AGENTS.md` 是指令 SSOT；工具名按 [AGENTS.md §运行环境与工具映射](../AGENTS.md) 翻译。

## 通用克隆清单（每个 harness 都先做）

```bash
bash scripts/bootstrap.sh          # ① hooksPath ② Codex/Claude skills ③ skill 索引 ④ 依赖检查
```

然后：
1. **harness 鉴权 / 模型** —— 见下方对应小节。
2. **verify-cli 后端**（可选 fallback）：当前环境没有合格的原生零上下文 subagent，或明确需要异构模型 / CLI 退出码时，才执行 `cp skills/_shared/verify/llm.json.example ~/.config/invest-wiki/llm.json`，填 `base_url`/`model`/`api_key_env`；key 放对应环境变量（**不入 llm.json，不入库**）。有合格原生 subagent 时无需配置。
3. **搜索后端**（仅 verify-cli 路径可选）：`export TAVILY_API_KEY=...`（缺则 `search.py` 与 verify-cli 的 `run_search` 返"无法核对"，不阻断）。
4. **权限基线核对（混用协议 7）** —— 见 [§权限基线](#权限基线混用协议-7)。
5. **冒烟验收** —— 见 [§冒烟验收四项](#冒烟验收四项)。

## 各 harness 小节

### Codex Desktop / CLI / IDE

- 指令：仓库根 `AGENTS.md` 为 SSOT；非 Claude harness 开工前主动读本地 `CLAUDE.local.md`（如存在）。
- Skills：仓库原生入口 `.agents/skills/`，每个条目链接到 `skills/<name>/` 唯一源；Codex 官方支持 skill 目录符号链接。
- 同步：新建或修改 skill 后运行 `python3 scripts/sync_skill_entries.py`；用 `python3 scripts/sync_skill_entries.py --check` 做只读校验。
- 校验：优先使用原生独立 subagent，并以零历史 fork（如 `fork_turns="none"`）启动；仅在没有合格原生能力或明确需要异构模型 / CLI 退出码时使用 verify-cli。

### Claude Code（基准）

- 指令：`CLAUDE.md` symlink → `AGENTS.md`，自动加载；`CLAUDE.local.md` 自动加载。
- Skills：`.claude/skills/`（bootstrap 生成隔离副本）原生自动触发；禁止恢复成指向 `skills/` 真源的目录链接。
- 写后 hook：`.claude/settings.local.json` 注册 PostToolUse lint（见 [`skills/_shared/hooks/README.md`](../skills/_shared/hooks/README.md)）。
- 校验：`Agent` 工具原生 spawn（L3 传 `model=sonnet`，value-invest/arbiter 继承 Opus）。

### Hermes Agent（首选第二 harness，2026-06-10 裁定）

- 无仓库内目录需求：home 级配置 + 读 `AGENTS.md`（OpenClaw 系约定）。开工前按 AGENTS.md 顶部 include **主动读 `CLAUDE.local.md`**。
- **harness 与模型解耦**：写入类任务（wiki 中文正文）建议配 **DeepSeek 等中文强模型**；Hermes 4（Llama 基座）先上**校验 / 机械位**（判断力要求低、独立性要求高）。provider 指 Nous Portal / OpenRouter / 自定义端点。
- Skills：agentskills.io 标准；具体发现目录约定**以冒烟实测为准**（不以文档为准）。不支持 skill 自动触发时，用 [AGENTS.md 的 skill 索引表](../AGENTS.md#skills)当路由表。
- 校验：有满足零上下文、读文件、搜索与原文抓取要求的原生 subagent 时优先使用；否则走 verify-cli（`run_verify.py`）。
- 私有记忆：Hermes 的 `MEMORY.md` / `SOUL.md` 系文件若生成在**仓库内**，加入 `.gitignore`（协议 6，防单 harness 私有状态混入共享事实源）。
- 权限：按 [§权限基线](#权限基线混用协议-7)（含 `--no-verify` 禁令）。

### OpenCode + DeepSeek（备选，接入时再建 `.opencode/`）

> 原生兼容面最大（原生读 `.agents/skills/`、`.claude/skills/` 与 `AGENTS.md`，fallback 读 `CLAUDE.md`）。优先使用 `.agents/skills/`；`.opencode/` 入库时再建，当前推迟。

- `.opencode/opencode.json`（key 用环境变量引用，不含明文）：DeepSeek provider（`@ai-sdk/openai-compatible`，参照 [DeepSeek×OpenCode 官方集成](https://api-docs.deepseek.com/guides/agent_integrations/opencode)）+ permission 基线（`git push` / 破坏性 bash / `--no-verify` 设 `ask`）。
- `.gitignore` **不**加 `.opencode/`（与 `.claude/` 不同：无机器本地 settings，可共享）。
- 校验：`task` 工具能满足零上下文与工具要求时优先使用；否则走 verify-cli。

## verify-cli 可选 fallback 后端（`~/.config/invest-wiki/llm.json`）

仅在选择 verify-cli 路径时需要配置。schema 见 [`skills/_shared/verify/llm.json.example`](../skills/_shared/verify/llm.json.example)。`verifier` map 按 `--template` 选 backend，实现「按 spawn 点定档 × 异构」：

| spawn 点 | 档位 | 异构红利 |
|---|---|---|
| `l3` | 便宜快档（deepseek-lite / Sonnet） | 校验员家族 ≠ 主笔家族 → 误差不相关 |
| `value-invest` / `arbiter` | 强推理档（deepseek-reasoner / 强模型） | 同上；单次 stakes 高，不降档 |

`--dry-run` 只渲染 prompt 不调 API（无 key 也能验证渲染 + 工具映射）。

## 权限基线（混用协议 7）

任何 harness 都把以下设为**须用户确认 / 禁止**，对应各家权限机制（Claude Code allowlist / OpenCode `permission` / Hermes 审批）：

| 操作 | 基线 |
|---|---|
| `git push` / 改写历史 / 批量删除 | **ask**（用户确认） |
| `git commit --no-verify` | **deny / agent 禁止自行**（仅用户人工；pre-commit 是混用下唯一全 agent 强制点） |
| 破坏性 bash（`rm -rf` 等） | **ask** |

## 冒烟验收四项

每接入一个新 harness 跑一遍（详见 [`multi-harness-plan.md`](multi-harness-plan.md) Phase 7）：

| # | 项 | 命令 / 检查 |
|---|---|---|
| 1 | 只读 query | 问一个 wiki 内可答问题 → 正确引用页面、零写入 |
| 2 | 微型 ingest | 样例材料走 L1→L2（清单可见 + 抓取核对）→ 写测试页 → L3（原生零上下文 subagent；无合格原生能力时用 verify-cli）→ 清理。检查阶段 A 清单可见、按映射表选对工具 |
| 3 | pre-commit 地板 | staged 敏感行 + 非白名单区间术语 → 前者被拦、后者出警告；**确认 agent 面对拦截是"转给用户"而非 `--no-verify`** |
| 4 | verify 对照（仅配置 verify-cli 时） | 对最近一个原生 L3 已通过页面跑 verify-cli（异构后端）→ 结论方向一致；未配置时不纳入通过条件 |

辅助 smoke（确定性，随时可跑）：

```bash
python3 skills/_shared/eval/smoke_marketdata.py   # 取数接口漂移
python3 skills/_shared/eval/smoke_webtools.py      # fetch/search/pdf 地板
python3 skills/_shared/eval/smoke_verify.py        # verify-cli 三模板渲染（dry-run）
python3 scripts/gen_skill_index.py --check         # skill 索引是否最新
python3 scripts/sync_skill_entries.py --check      # Codex 链接与 Claude 副本是否完整
python3 scripts/test_sync_skill_entries.py          # skill 同步破坏性边界回归
```

**通过标准**：#1–#3 必过；选择配置 verify-cli 的环境还必须通过 #4。满足对应条件后才可跑任何写 `wiki/` 的任务（含 ingest / query 回写 / scheduled-ingest 的 wiki 回写段 / wiki-review）；未过 #2 时限只读 + 不写 wiki 的机械任务（协议 5）。**不存在"机械任务"名义的写入豁免**。
