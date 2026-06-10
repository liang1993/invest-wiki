# 投资知识 Wiki — Schema 配置

你是个人投资知识库的维护者。三层架构：
- **raw/** — 不可变的原始资料
- **wiki/** — 你生成和维护的知识页面
- **CLAUDE.md** — 本文件，定义结构和工作流

数据纪律细则（自检详解 / 校验 Agent prompt / WebSearch 归档详解）见 [`docs/data-discipline.md`](docs/data-discipline.md)。

> **指令入口（多 harness）**：本文件 `AGENTS.md` 为本仓库指令 SSOT，`CLAUDE.md` 是指向它的兼容符号链接（Claude Code 沿链接读取本文件）。若存在 `CLAUDE.local.md`，开工前必须完整读取并遵守（Claude Code 已自动加载，无需重复读；**非 Claude Code harness 必须主动读取**）。

## Skills

skill 位于 `skills/`，通过 `.claude/skills/` 符号链接引用，适时自动调用。新建 skill 默认创建在 `skills/` 并补充符号链接。

> `skills/_shared/` 是跨 skill 共享层（`marketdata` 取数库含 A 股路由唯一来源 `codes.py` / `hooks` git+PostToolUse 钩子 / `eval` smoke 与单测），**非 skill 本身，不建符号链接**；取数与确定性校验逻辑统一放此，由各 skill 脚本 import。详见 [`docs/skill-refactor-plan.md`](docs/skill-refactor-plan.md)。

## 数据时效性（强约束）

分析任何标的时**必须用最新可获取数据**：

1. 先 WebSearch 该公司最近一次财报（季报/年报），确认最新报告期。**不得仅依赖 yfinance** 的 `income_stmt` / `balance_sheet`——经常滞后一个或多个季度
2. yfinance `info` 的 TTM 指标（`totalRevenue` / `netIncomeToCommon` / `trailingEps`）可能与年报口径不一致，必须 WebSearch 交叉验证
3. 所有财务数据**标注报告期**（如 "2025 年报" / "2026Q1"），不得模糊表述
4. 发现 API 数据明显滞后时主动 WebSearch 获取最新

## 数据写入纪律（强制）

> 2026-05-20 升级为三层防线。同型错误连续 3 次（长鑫横向对标 / 消费趋势金价 / 4 月信贷历史对照 + 房贷 GDP），原"事前自检 + 事后 subagent"两层在叙事流中被跳过。**强制原则**：数据正确性优先于 token 节省和对话节奏。

### 三层防线总览

| 层 | 时点 | 范围 | 强度 |
|---|---|---|---|
| **L1 轻量自检** | 写入前 | 口径 / 反推 / 叙事 / 极端值（表达层） | 轻（4 项 checklist） |
| **L2 两阶段分离工作流** | 写入前 | 所有数字（清单 + 强制 WebFetch） | 重（A 声明 → B 校验 → C 写入） |
| **L3 数据校验 Agent** | 事后 | 所有数字（subagent 独立 search） | 中（subagent 兜底，不可省） |

L2（事前）+ L3（事后）是两道独立防线，不可互替——主 agent 写入纪律完整 ≠ subagent 可省。完整细则见 [`docs/data-discipline.md`](docs/data-discipline.md)。

> **Hook 地板（2026-05-29）**：可机械判定的纪律已下沉为 hook 强制——隐私边界走 git pre-commit、个股区间术语 + frontmatter 走 PostToolUse（warn-only）。**Hook 守确定性地板，L1/L2/L3 + verify 守判断天花板**（[观测] WebFetch 核对、计算链反推这类判断型不进 hook）。接线与清单见 [`skills/_shared/hooks/README.md`](skills/_shared/hooks/README.md)，全局蓝图见 [`docs/skill-refactor-plan.md`](docs/skill-refactor-plan.md)。

### 触发范围（适用 L1 / L2 / L3）

所有 INGEST / QUERY 回写 / PERIODIC-REVIEW / VALUE-INVEST / LINT 中写入 wiki 的具体数字（市值/营收/PE/份额/利率/汇率/同业对标/历史对照等）。模糊场景默认触发。

### 豁免梯度

**L1 / L2 / L3 三层独立触发，独立判断豁免；任意一层未豁免就必须执行该层。**

| 层 | 豁免门槛（满足任一即豁免） |
|---|---|
| **L1 + L2**（写入前最严） | 纯文字修订（typo / 排版 / 链接） / 撤销操作 / **0 新增数字断言且 0 改动已有数字** |
| **L3**（事后兜底，比写入前宽） | **新增/修改数字 ≤ 2 处且无估值锚点变动** / 纯排版 / 撤销操作 |

> 源头便宜，事后贵；源头错了 subagent 也未必 catch。**执行顺序固定：L1 → L2（A→B→C）→ L3，不可跳步、不可并行、不可累积多次写入再批量 spawn L3。**

**豁免红线**：以上豁免**不适用于**[高时效衰减领域](docs/data-discipline.md#c-高时效衰减领域每季度复审下次2026-08-20)的数字（HBM/AI 算力、美联储利率/美债/汇率、中国房地产、中美关税、国家队 ETF、金价/油价）——这类数字哪怕只改 1 处也强制 L1 / L2 / L3 全跑。

历史教训案例见 `wiki/log.md` 含 `LINT` 关键字的条目，根因汇总见 [`docs/data-discipline.md` §历史教训索引](docs/data-discipline.md#历史教训索引)。

---

### L1：轻量自检 checklist（写入前快速过）

L2 触发词表没覆盖的"表达层"问题：

| 自检 | 一句话 |
|---|---|
| 1. 口径双列 | 份额/持仓/市值表格必须分列两个口径 |
| 2. 反推校验 | 派生数字用分子/分母反推一次 |
| 3. 叙事去强化 | "精准/腰斩/80%" 等强叙事词默认标"待核实" |
| 4. 极端数字溯源 | ≥ 50% 变动或破极值必须贴原始数据源链接 |

> 估值三档溯源（[观测]/[推算]/[估计] 标注）+ 横向对标必查由 L2 强制 enforce，不在 L1 重复。详见 [`docs/data-discipline.md`](docs/data-discipline.md#数字-sanity-check-详解)。

---

### L2：两阶段分离工作流（写入前强制）

#### 阶段 A：数据声明清单（写入前强制输出）

**前置条件**：先过 L1 4 项轻量自检。任一项未过 → 修正叙事/口径后才能进入阶段 A。

主 agent 在 `Edit`/`Write` wiki 文件**之前**，必须在对话里**以可见的表格或列表形式**输出"数据声明清单"，列出所有具体数字 + 来源 + 配套信息：

| 来源类型 | 配套信息 |
|---|---|
| **[观测]** | 可访问 URL |
| **[推算]** | 公式（如 `BPS 内生增速 = ROE × (1-分红率)`） |
| **[估计]** | confidence 区间 + 外推方法 |

**硬规则**：
- 清单未在对话里可见输出 → 不能进入阶段 B/C
- **不允许**"心中默念清单后直接 Edit/Write"——外部读者必须能看到清单
- 清单与最终写入的数字必须一一对应，写入时新增的数字必须回头补登清单

#### 阶段 B：校验执行（每项强制）

- **[观测]**：必须 `WebFetch` 原 URL 核对——**不接受 WebSearch 摘要**（AI 总结可能错配，案例见 [`docs/data-discipline.md` §历史教训索引](docs/data-discipline.md#历史教训索引)）。验证：(i) URL 可访问；(ii) 数字在原文完整句子中。**同一来源 URL 的多个数字只需 WebFetch 一次**，清单里按来源分组
- **[推算]**：列出公式 + 反推验算一次
- **[估计]**：标 confidence 区间 + 外推方法

**触发词硬规则**（机械触发，不依赖判断）。关联历史教训案例见 [`docs/data-discipline.md`](docs/data-discipline.md#阶段-b校验执行)：

| 触发模式 | 必触发动作 |
|---|---|
| 写"X 国 Y 指标 N%"（跨国/跨市场对照） | WebSearch + WebFetch |
| 写其他公司市值 / PE / 份额（同业对标） | WebSearch + WebFetch |
| 写"YYYY-MM 单月数据 N 亿" | WebFetch 该月权威发布稿 |
| 写"同比/环比 ±N%"等变化率 | WebFetch 分子分母原始数据反推 |
| 写"近 X 年中位 / 平均 / 历史 PE N"（行业均值） | WebFetch 数据源直查（禁止分位反推中位） |
| 写"历史首次 / 创口径新高 / N 年以来" | WebSearch 历史对照 |
| 引用任何 URL 作为 [观测] 来源 | WebFetch 验证 URL 可访问 + 数字在原文中 |
| 复用 WebSearch 摘要里的具体数字 | WebFetch 原 URL 核对 |

#### 阶段 C：写入 wiki

基于阶段 B **已校验数字**撰写。校验失败的数字降档为 [估计] 或删除，不允许"凭印象保留"。

**完成阶段 C 后必须立即进入 L3**——不可累积多次 wiki 写入再批量 spawn 一次 L3（subagent 是 zero-context 设计，多文件混跑会失焦）。每次完整的 L2 流程对应一次独立 L3 spawn。

#### L2 失败处理

- 阶段 B 发现偏差（WebFetch 与清单不一致） → 修正清单 → 重跑阶段 B（修正项 + 周边相关项） → 阶段 C 写入
- 阶段 B URL 不可访问 / 数字不在原文 → 该数字降档 [估计] 或删除断言

成本权衡（+15-20% token / 多 5-7 次 WebFetch）已接受。详见 [`docs/data-discipline.md` §成本与权衡](docs/data-discipline.md#成本与权衡)。

---

### L3：数据校验 Agent（事后审计，强制）

主 agent 完成 wiki 写入（阶段 C）后**必须立即** spawn `general-purpose` Agent 做事后校验。Prompt 模板见 [`docs/data-discipline.md`](docs/data-discipline.md#数据校验-agent-prompt-模板)。

**commit 前必跑**：任何 commit 操作前必须确认 L3 已跑且通过。用户主动要求 commit 但 L3 未跑 → 主 agent 先 spawn L3，校验通过后再 commit；不可"先 commit 等会儿补校验"。

#### L3 失败处理

| 校验结果 | 主 agent 动作 |
|---|---|
| 0 ✗ + 0 ⚠️ | `log.md` 末尾追加 `校验通过 (扫描 N 项)`，继续 commit |
| ≥ 1 偏差 > 10% / ✗ / ⚠️ | **修正后才能 commit**；只需重跑"修正项 + 首轮报告的所有 ✗/⚠️ 项" |
| 校验员预算耗尽（10 次 WebSearch 后还有可疑项） | 主 agent 接手剩余项 WebSearch 自查，不再 spawn 第二次 subagent |

**禁止**：跳过校验直接 commit；用主 agent 回忆代替 subagent search（仅预算耗尽 fallback 启用）。

## WebSearch 归档（raw/articles/）

WebSearch 结果被写进 wiki 正文时，同步归档到 `raw/articles/`。文件格式、数据准确性硬要求、frontmatter 字段详见 [`docs/data-discipline.md`](docs/data-discipline.md#websearch-归档-rawarticles)。

### 归档触发

| 场景 | 归档 |
|---|---|
| ingest 财报/政策 PDF | ✅（走 `raw/reports/` 流程） |
| periodic-review 引用新财报/政策 | ✅ |
| value-invest 写进 wiki 的数据 | ✅ |
| 日常 query / 股价查询 / 八卦问答 | ❌ |

### 反向引用

wiki "信息来源"章节同时写 `raw/articles/` 路径：
```
- [原文标题](URL) — 已归档 `raw/articles/stocks/中信证券/2026-04-09_Q1业绩快报_证券时报.md`
```

### 不归档清单

一次性股价波动 / 纯观点营销文 / 仅搜索入口页 / >3 年老数据 / 同一事实多篇重复报道（留 1-2 篇）。

## 语言

wiki 页面以**中文**撰写。原始资料英文时翻译为中文。股票代码、专有名词可保留英文。

## 目录结构

```
raw/
  reports/    # 研报、财报 PDF + .md 摘要
  articles/   # WebSearch 归档（stocks/macro/sectors 子目录）
wiki/
  index.md
  log.md
  stocks/                # 个股研究页（按行业分子目录）
    consumer/            # 食品饮料/家电
    internet/            # 互联网平台/科技消费
    financial/           # 银行/券商
    telecom/             # 电信运营商
    auto/                # 汽车/动力电池
    tech-hardware/       # 半导体/电子制造/工控
    industrial/          # 工程机械/电力设备/建筑
    healthcare/          # 医药
    resources/           # 资源/周期
    focus/               # 重点关注（符号链接 → 对应行业目录）
  funds/      # 基金/ETF
  macro/      # 宏观主题
  sectors/    # 行业/板块
  strategies/ # 投资策略框架
  journal/    # 投资日志与复盘
```

## 重点关注列表（全局约束）

`wiki/stocks/focus/` 存放重点关注个股的**符号链接**。

- 所有消费关注列表的 skill（`periodic-review` / `value-invest` 等）统一从此目录获取，不得各自维护独立列表
- 添加：`ln -sf ../<sector>/xxx.md wiki/stocks/focus/`（sector ∈ consumer / internet / financial / telecom / auto / tech-hardware / industrial / healthcare / resources）
- 移除：删除 `focus/` 下符号链接
- `stocks/` 中未链入 focus 的页面仍保留，仅不在定期复盘流程自动追踪

## 命名规范

- 个股：A 股中文名 `贵州茅台.md`，美股代码 `NVDA.md`
- 基金：`{基金简称}.md`，如 `沪深300ETF.md`
- 宏观：主题命名 `美联储利率周期.md`
- 行业：`{行业名}.md`
- 策略：`{策略名}.md`
- 日志：`{YYYY-MM-DD}.md`

## 页面模板

创建新页面时读 `templates/页面模板.md`。Frontmatter 必填 `tags: [...]` 与 `updated: YYYY-MM-DD`。

## 工作流

### Ingest（摄入）

1. 读 `raw/` 中文件或抓取 URL
2. 提取关键信息（公司 / 行业 / 宏观 / 数据点）
3. **【财报 PDF 专属】结构化摘要 + 审查** — 按 `templates/财报摘要模板.md` 抽取到 `raw/reports/<公司>_<报告期>.md`（每数据点标 PDF 页码 + 末尾生成核对清单），逐项 `Read pages=X` 回读校对，偏差必须修正摘要 md，审查通过后 frontmatter 设 `reviewed: true`。**禁止跳审直接回填 wiki**
4. **走数据写入纪律 L1 → L2（强制，顺序执行）** — L1 轻量自检 → L2 阶段 A 数据声明清单 → 阶段 B 校验执行 → 阶段 C 写入 wiki。**L2 未完成不可进入 §5**。详见上文「[数据写入纪律](#数据写入纪律强制)」章节
5. 维护辅助文件 — 交叉引用 / 更新 `index.md` / 更新 `log.md`
6. **L3：立即 spawn 数据校验 Agent（强制）** — 阶段 C 完成后立即触发，commit 前必跑。见上文「[数据写入纪律 §L3](#l3数据校验-agent事后审计强制)」

注意：
- 不删除已有信息，追加或修正
- 标注来源和日期
- 新旧信息矛盾时两者都保留并标注
- 二次消费财报优先读 `.md` 摘要而非重解析 PDF

### Query（查询）

1. 搜索相关 wiki 页面
2. 综合回答
3. 引用来源
4. 有价值的洞察回写到相关页面 — **若涉及新数字，必须先走数据写入纪律 L1 → L2**（轻量自检 → 数据清单 → 校验 → 写入）。**L2 未完成不可进入 §5**
5. 更新 `log.md`
6. 若 §4 回写涉及新数字 → 立即触发 L3 数据校验 Agent（commit 前必跑）

### Lint（维护）

调用 `wiki-review` skill。
