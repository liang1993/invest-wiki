---
name: scheduled-ingest
description: 定时数据采集任务集合。把外部数据（车企销量、宏观指标、资金面、央行会议等）定期塞进 raw/ 并回写 wiki/ 静态数据章节。Use when user wants to ingest periodic data (monthly auto sales, weekly margin balance, CPI release, FOMC decision), run a scheduled-ingest job, set up a data refresh routine, or asks "我每月怎么更新汽车销量". Distinct from periodic-review (which is analysis layer reading these data).
---

# 定时数据采集 Skill

集中管理"按时间或事件触发、把外部数据写进 raw/ 与 wiki/"的任务。区别于：

- **value-invest**：按需触发，单标的，产出估值结论
- **periodic-review**：周期复盘，**读** ingest 写好的数据做分析判断
- **scheduled-ingest（本 skill）**：按时间/事件触发，**写**数据到 raw/ + 回写 wiki/ 静态章节

## When to Use

- 用户说"跑一下 auto-monthly-sales"、"更新本月车企销量"、"刷一下汽车销量榜"
- 用户提及任何 `jobs/` 下登记的 job 名
- 用户问"我每月怎么更新 X 数据"，先看 jobs/ 是否已有，没有再考虑新建
- 月初/季初/会议日前后用户主动要求"把这个月的数据补上"

## 文件结构

```
skills/scheduled-ingest/
├── SKILL.md                          # 本文件
├── jobs/                             # 一个 job 一个 md（自描述 runbook，逻辑 SSOT）
│   └── auto-monthly-sales.md         # 每月车企销量 + 单车型 Top
├── scripts/                          # 实际抓取脚本
│   └── fetch_auto_sales.py
├── references/                       # 数据源 API 规范（扩展前先读）
│   └── dongchedi-api.md              # 懂车帝 API endpoint + 字段 + 参数空间
└── tests/                            # 纯函数单元测试
    └── test_fetch_auto_sales.py
```

## Job 文件规范

每个 `jobs/*.md` 必须包含：

```markdown
# <Job Title>

**Job ID**: <kebab-case-id>（与文件名同名）
**触发**: <cron 表达式 或 事件描述>
**数据源**: <主源 + 备份源 + 各自接口/URL>
**写入目标**: <raw/ 路径 + 是否回写 wiki/ 及具体章节>
**校验级别**: <L1 必跑 / L2 触发条件 / L3 触发条件>
**失败处理**: <数据未发布 / 接口变更 / 字段缺失各自怎么办>

## 步骤

<人类可读的 runbook，让 Claude 跟着走>

## 输出格式范例

<具体表格 / md 片段 demo>
```

## 执行流程（通用）

收到"跑 job X"指令后：

1. **读 job runbook**：`Read skills/scheduled-ingest/jobs/X.md`
2. **跑脚本/查接口**：按 runbook 第 1 步
3. **L1 自检**：数据合理性（量级、口径、极端值）
4. **写入 raw/**：归档原始数据 + 数据源 URL（按 CLAUDE.md `raw/articles/` 规范）
5. **L2 触发判断**：是否涉及估值锚 / 跨市场对照 / 历史首次。触发就走完整 L2（数据声明清单 + WebFetch 校验）
6. **回写 wiki 静态章节**（如果 runbook 要求）：替换月度数字 / 追加新条目
7. **L3 触发判断**：见 CLAUDE.md 豁免梯度。月度销量榜这种"公开榜单 + 多源交叉一致"可豁免 L3（≤ 2 处数字断言且无估值锚变动），但若 runbook 同时改了估值锚（如 wiki/stocks/* 的销量假设），必须 L3
8. **更新 log.md**：一行记录 `INGEST <job-id> <month> 完成`

## 调度方式（不强求自动化）

**第一阶段（推荐起步）**：手动跑——用户在合适时点说 `跑一下 auto-monthly-sales 2026-04`，让 Claude 按 runbook 走。优点：LLM 跑 runbook 比纯脚本健壮（数据格式变化能 adapt）。

**第二阶段（job 稳定 2-3 个月后）**：注册到 Claude Code 的 `mcp__scheduled-tasks__create_scheduled_task`，全自动化。但**只对接口稳定、字段不变、数据源单一**的 job 自动化——别一上来就强自动化，否则接口一变又得改一遍。

## 与现有架构的边界

| 边界场景 | 归属 |
|---|---|
| "把 2026-04 车企销量数据更新到 wiki" | **scheduled-ingest** （auto-monthly-sales）|
| "看下小鹏最新销量趋势，判断买入价" | **value-invest**（按需估值，可调用 ingest 已写好的数据）|
| "本月关注列表整体看下" | **periodic-review**（读 ingest + 自己 fetch 个股行情）|
| 财报 ingest（每季 1 次但触发不规则） | **CLAUDE.md `## 工作流 - Ingest`**（不放 scheduled-ingest，频率太低且涉及深度审查）|
| WebSearch 归档 | **CLAUDE.md `## WebSearch 归档`**（独立纪律，不属于本 skill）|

## 当前 jobs 清单

| Job ID | 触发 | 状态 |
|---|---|---|
| auto-monthly-sales | 每月 10-15 日（懂车帝次月 10 日发布）| ✅ 已上线 + 已注册 cron |

新增 job 时在此表登记 + 创建 `jobs/<id>.md`。

## 已注册的 scheduled tasks

走 Claude Code 内置 `mcp__scheduled-tasks__` 注册的自动定时任务：

| Scheduled Task ID | 对应 Job | Cron | 下次跑 |
|---|---|---|---|
| `auto-monthly-sales-ingest` | auto-monthly-sales | `0 14 10 * *`（每月 10 日 14:00 local）| 6/10 14:00 |

任务文件存放：`~/.claude/scheduled-tasks/<task-id>/SKILL.md`（由 Claude Code 管理）

**注意事项**：
- App 关闭时任务**不会跑**，下次 launch 时补跑
- 首次跑前**建议手动 Run now 一次**（在 sidebar Scheduled 区域）——预授权 Bash / Read / Write / Edit 权限，避免后续跑被卡 permission prompt
- 任务跑完会通知本 session（如还活着）；如已关闭则在 dashboard 看结果
- 修改任务用 `mcp__scheduled-tasks__update_scheduled_task`，list 用 `mcp__scheduled-tasks__list_scheduled_tasks`

## 数据源 references

每个数据源单独一份完整 API 文档（调用规范 + 参数空间 + 字段表 + 陷阱），新增维度前先读对应 reference 避免重复探测：

| Reference | 覆盖 | 状态 |
|---|---|---|
| [`references/dongchedi-api.md`](references/dongchedi-api.md) | 懂车帝车型销量 API（**车型级月度主源**）| ✅ 已写 |

新增数据源时同步创建 `references/<source>-api.md`。
