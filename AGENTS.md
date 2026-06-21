# 投资知识 Wiki — Schema 配置

你是个人投资知识库的维护者。三层架构：
- **raw/** — 不可变的原始资料
- **wiki/** — 你生成和维护的知识页面
- **CLAUDE.md** — 本文件，定义结构和工作流

数据纪律细则（自检详解 / 校验 Agent prompt / WebSearch 归档详解）见 [`docs/data-discipline.md`](docs/data-discipline.md)。

> **指令入口（多 harness）**：本文件 `AGENTS.md` 为本仓库指令 SSOT，`CLAUDE.md` 是指向它的兼容符号链接（Claude Code 沿链接读取本文件）。若存在 `CLAUDE.local.md`，开工前必须完整读取并遵守（Claude Code 已自动加载，无需重复读；**非 Claude Code harness 必须主动读取**）。

## Skills

skill 位于 `skills/`，通过 `.claude/skills/` 符号链接引用，适时自动调用。新建 skill 默认创建在 `skills/` 并补充符号链接。

**skill 索引**（给不支持 skill 自动触发的 harness 当路由表；由 [`scripts/gen_skill_index.py`](scripts/gen_skill_index.py) 从各 `SKILL.md` frontmatter 生成，`bootstrap.sh` 刷新，**勿手改标记块内**）：

<!-- skill-index:begin -->

| skill | 触发场景（节选，完整见各 SKILL.md） |
|---|---|
| `a-share-market` | A股市场数据获取工具 |
| `asr` | 本地中文 ASR 工具 |
| `douyin-distill` | 把一个抖音博主蒸馏成可复用的"人设 skill"——给定博主主页 URL，自动跑通【扫码登录→旁路枚举全部作品→识别会员/付费视频→选样下载→批量转写→读稿蒸馏成 skill→独立校验】整条流水线，产… |
| `etf-momentum` | 行业 ETF 动量轮动计算器 |
| `find-skills` | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a… |
| `invest-tusi` | 用抖音"土斯土耶夫斯基"（老司机日记 / 中国好公司）的视角做价值投资解读——把一家公司或一段宏观周期，用他那套"学院派、长线、看资产、定周期"的框架讲成散户能用的判断 |
| `macro-analysis` | 宏观经济数据获取与分析工具 |
| `macro-ellie` | 用"艾丽的无废话财经"的视角解读宏观经济数据与财经事件——把官方数据/政策/地缘博弈翻译成"这说明什么 + 对普通投资者意味着什么" |
| `macro-quant-rebalance` | 专用于个人 A 股「宏观量化中性组合」的再平衡计算器——**不是通用再平衡器**，只服务这一套策略：静态大类 E40/B22/G21/C17 + 整组合波动率目标 12% + 权益用 etf-mome… |
| `media-fetch` | 本地媒体下载工具，按 URL 自动分流 |
| `periodic-review` | 定期投资复盘工具 |
| `scheduled-ingest` | 定时数据采集任务集合 |
| `stock-deep-dive` | 个股产品/经营深度分析工具 |
| `stock-kuaidao` | 用抖音"快刀斩股"的视角做个股财报体检与估值——把一家 A 股公司用招牌"斩股十刀"从营收砍到估值，大白话拆术语、现场手算、武侠刀法叙事，给散户一个"这公司牛不牛、贵不贵"的痛快判断 |
| `value-invest-verify` | 价值投资 wiki 独立校验工具 |
| `value-invest` | 个人价值投资分析工具 |
| `wiki-review` | 单个 wiki 页面"格式对齐 + 过期归档"工具 |
| `yahoo-finance` | Get stock prices, quotes, fundamentals, earnings, options, dividends, and analyst ratings using Yaho… |

<!-- skill-index:end -->

> `skills/_shared/` 是跨 skill 共享层（`marketdata` 取数库含 A 股路由唯一来源 `codes.py` / `hooks` git+PostToolUse 钩子 / `eval` smoke 与单测），**非 skill 本身，不建符号链接**；取数与确定性校验逻辑统一放此，由各 skill 脚本 import。详见 [`docs/skill-refactor-plan.md`](docs/skill-refactor-plan.md)。

## 运行环境与工具映射

本仓库工作流原文多以 Claude Code 工具名书写。**非 Claude Code harness 按下表把"抽象动作"映射到本环境实现**；最右「脚本 fallback」列对任何能跑 bash 的 harness/模型都可用，且也是 Claude Code 下原生工具失败（如 WebFetch 403）时的备选。

| 抽象动作 | Claude Code | OpenCode | Hermes Agent | 脚本 fallback（全员可用） |
|---|---|---|---|---|
| 网页搜索 | WebSearch | search MCP | 内置 search | `python3 skills/_shared/webtools/search.py "<query>"` |
| 原文抓取 | WebFetch | fetch MCP | 内置 fetch | `python3 skills/_shared/webtools/fetch.py <url>` |
| PDF 逐页读 | Read pages=X | —（用 fallback） | —（用 fallback） | `python3 skills/_shared/webtools/pdf_text.py <pdf> --pages X` |
| 零上下文校验（L3 / verify） | Agent 工具 spawn | task 工具或 fallback | subagent 或 fallback | `python3 skills/_shared/verify/run_verify.py …` |
| 行情/宏观取数 | Bash + `_shared/marketdata` | 同左 | 同左 | 同左（已中立） |

**解析规则**：
1. 本仓库所有文档（AGENTS.md/CLAUDE.md、`docs/`、`skills/`、`templates/`）中出现的 `WebFetch` / `WebSearch` / `Agent 工具` / `Agent({...})` / `subagent_type=general-purpose` / `Read pages=` / `Read PDF pages=` 均指上表抽象动作；非 Claude Code 环境按本表解析，**纪律语义不变**（如"[观测] 必须 WebFetch 原 URL"= 必须用本环境的"原文抓取"动作取回原文核对，**禁止用搜索摘要替代**）。
2. **原生优先**：本环境有原生实现时用原生（Claude Code 不要用 `fetch.py` 替代 WebFetch）；fallback 仅在原生不存在或失败时使用。

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

主 agent 完成 wiki 写入（阶段 C）后**必须立即**做零上下文事后校验。两条等价路径任选其一，**完成标准与失败处理一致（0✗0⚠️ → log 记录后方可 commit），不得以"本环境没有 subagent 工具"为由跳过 L3**：
- **Claude Code**：spawn `general-purpose` Agent，**传 `model=sonnet`**（L3 为高频检索/比对型，用便宜快档即可；value-invest 校验 / arbiter 仲裁维持继承主力 Opus，**不降档**）
- **非 Claude Code harness**：运行 verify-cli —— `python3 skills/_shared/verify/run_verify.py --template l3 --files <wiki…> --sections "<本次新增/修改章节>"`（见[运行环境与工具映射](#运行环境与工具映射)）

Prompt 模板见 [`docs/data-discipline.md`](docs/data-discipline.md#数据校验-agent-prompt-模板)。

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
3. **【财报 PDF 专属】结构化摘要 + 审查** — 按 `templates/财报摘要模板.md` 抽取到 `raw/reports/<公司>_<报告期>.md`（每数据点标 PDF 页码 + 末尾生成核对清单），逐项 `Read pages=X`（非 Claude Code harness 用 `pdf_text.py --pages X`，见[运行环境与工具映射](#运行环境与工具映射)）回读校对，偏差必须修正摘要 md，审查通过后 frontmatter 设 `reviewed: true`。**禁止跳审直接回填 wiki**
4. **走数据写入纪律 L1 → L2（强制，顺序执行）** — L1 轻量自检 → L2 阶段 A 数据声明清单 → 阶段 B 校验执行 → 阶段 C 写入 wiki。**L2 未完成不可进入 §5**。详见上文「[数据写入纪律](#数据写入纪律强制)」章节
5. 维护辅助文件 — 交叉引用 / 更新 `index.md` / 更新 `log.md`
6. **L3：立即触发零上下文数据校验（强制）** — 阶段 C 完成后立即触发，commit 前必跑。Claude Code spawn `general-purpose` Agent（传 `model=sonnet`）；非 Claude Code harness 运行 verify-cli（`run_verify.py --template l3`）。见上文「[数据写入纪律 §L3](#l3数据校验-agent事后审计强制)」

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

## 多 Agent 混用协议（多 harness 共享同一仓库时）

> 适用：多个 agent（不同 harness / 模型）分时或分角色操作同一仓库。所有 agent 共享的只有 git 与文件系统——故约定全部落 repo，纪律等价、产出可溯源。蓝图见 [`docs/multi-harness-plan.md`](docs/multi-harness-plan.md)。

1. **开工自检**：会话开始若 `git status` 不干净，先向用户确认残留归属（可能是另一 agent 的未竟工作），**不得擅自 commit / revert / 续写他人未提交内容**。
2. **产出归属**：每条 `wiki/log.md` 条目末尾加 `- **执行**：<harness>/<model>`（如 `claude-code/opus-4.8`、`opencode/deepseek-v4`、`hermes-agent/hermes-4-405b`）——数字错误可溯源到产出模型，跨模型质量对比有据。
3. **并发边界**：默认**分时**（`wiki/log.md` 与 `index.md` 是追加热点，同工作区并发必冲突）。确需并行：各开 `git worktree` + 独立分支，由用户合并；禁止两 agent 共享同一工作区。**worktree 隐私盲区**：gitignore 的 `CLAUDE.local.md` 与 `private/` 不出现在新 worktree——worktree 内 agent 视为**未读隐私指令**，禁止撰写任何涉持仓 / 金额 / 个人财务内容，相关任务回主工作区分时执行。
4. **纪律等价**：L1/L2/L3 的触发范围、豁免梯度、完成标准 harness 无关。L2 阶段 A 清单必须在该 agent 输出中可见；L3 用 Agent 工具或 verify-cli 二选一，标准同一。**模型弱不构成豁免理由**——弱模型环境更依赖 pre-commit 地板 + verify-cli 必跑。
5. **能力分级分工**（建议默认）：判断型流程（value-invest 估值、ingest 财报解读、macro-ellie 解读）→ 强模型。**机械型 = 不写 `wiki/` 的任务**（行情 / 宏观取数、etf-momentum 快照、verify-cli 驱动、`raw/` 采集落盘）→ 任意通过冒烟的模型。**注意 scheduled-ingest 回写 wiki 静态章节段、wiki-review 改 wiki 正文均属写入类**，必须过冒烟 #2 才可跑（无"机械任务"名义的未校验写入旁路）。
6. **状态共享走 repo**：教训、偏好、约定一律落 AGENTS.md / `docs/` / `log.md`，不留 harness 私有记忆（Claude auto-memory、Hermes 的 MEMORY.md / SOUL.md 体系）。任一 harness 的项目级记忆文件若生成在仓库内，加入 `.gitignore`，防单 harness 私有状态混入共享事实源。
7. **破坏性操作基线**：`git push` / 改写历史 / 批量删除，任何 harness 默认须用户确认；**任何 agent 禁止 `git commit --no-verify`（pre-commit 旁路），仅限用户人工执行**——pre-commit 是混用下唯一对所有 agent 生效的强制点，堵不住 `--no-verify` 这条对弱遵循模型就不成立。

## 工程改动工作流（代码 / 架构 / skill 重构，非 wiki 内容）

> 与上文「[工作流](#工作流)」（wiki ingest / query / lint）区分：本节针对仓库**工程改动**（脚本、hook、skill 结构、兼容方案这类）。

重大重构 / 多步改动走**双门 review**：
1. 出方案落 `docs/` → **门 1**：spawn 独立 subagent 对抗式 review **方案** → 按 review 修订；
2. 逐 **phase 独立 commit**（每步带验证检查），在 **feature 分支**推进；
3. **门 2**：合并前 spawn 独立 subagent review 整个 **diff（`main..HEAD`）** → 修；
4. 仅在用户明确说"合"时 `merge` + `push`。

**不盲信 subagent**：review report 要自己 `fetch` / `grep` / 跑测试核对（subagent 会误判，如把某 skill 专属纪律误读成重复拷贝）。指令托底的自检会在叙事流里被跳过，独立 zero-context subagent 是结构性补丁。
