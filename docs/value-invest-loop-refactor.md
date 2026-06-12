# value-invest 借 Loop Engineering 重构 — 算术固化 + 研究步 worker 双门

> 状态：**方案 v1（待门 1 review）** | 创建：2026-06-10 | 关联：[`skill-refactor-plan.md`](skill-refactor-plan.md)（五原语蓝图）/ [`data-discipline.md`](data-discipline.md)（L1/L2/L3）/ [`multi-harness-plan.md`](multi-harness-plan.md)（能力分级 / verify-cli）
>
> **背景**：读《Loop Engineering—从 ReAct 到 Orchestration》后审视 value-invest。该 skill 已是一条 Step 0→9 的判断流水线（清晰阶段 + 可验收中间产物 + step 间硬契约），结构上最接近文章里的「深度研究」Dynamic Workflow——但它的**确定性（算术 + 阈值）几乎全在散文里，模型每次心算**，而 `scripts/fetch_data.py` 只做取数 + PE/PB 区间统计，估值算术一行都不在脚本里。
>
> **核心判断**：把文章的「确定性交给代码、判断交给模型」落到 value-invest = 两条正交改造：① **算术固化**（散文算术 → 纯函数 `compute_valuation.py` + 外部化 state），消灭 Step 9 事故清单里的心算错误类；② **研究步 worker 化**（2B/2C → spawn 工作 agent + verificationPrompt 完整性门），对「遗漏型」事故（地平线漏子公司/对手）做结构性补丁。**两者都不改变判断归属——加分/减分因子值、质化、方法选择仍是模型的活**。

---

## 0. 目标与非目标

**目标**
1. 把 value-invest 的**确定性算术**（合理 PE / 四档锚点 / 综合加权 / 6 档区间分类 / 阈值校验）从散文抽进 `scripts/compute_valuation.py` 纯函数，模型只供判断型输入，脚本做乘法与 min/max/clamp
2. 中间产物外部化为 `valuation_state.json`，获得 Stop/Resume + Repeatability（治"宁德 Q1 花 4 轮对话、40% 浪费在 context 重传"）
3. 研究/mapping 重步（2B.1 / 2B.2 / 2C）可**条件触发 spawn 工作 agent**，每个自带 verificationPrompt（现有 Fail 条件 / 反向 sanity check 提炼）做完整性门，通过后由主 agent 汇总

**非目标**
- **不做完整 workflow 引擎**（phase/log/drainInbox/orchestrator）——value-invest 是交互式分析、非 headless 批任务，那套机械是过度设计
- **不 spawn 算术步**——Step 3/4/6/7/8 走代码，不用 LLM 做乘法
- **不替代、不降档 Step 9**——独立零上下文校验仍是 correctness 门，按 AGENTS.md「value-invest 校验继承 Opus、不降档」保持
- 不动判断归属——因子值 / 确定性档 / 预期差状态 / 质化结论仍由模型决定（脚本只接收已决定的数值）
- 不重写 Step 0→9 的阶段划分（只换"算术由谁执行""研究步由谁执行"）

## 1. 现状诊断

### 1.1 流水线与「确定性在哪」

| Step | 做什么 | 性质 | 现在在哪 |
|---|---|---|---|
| 0 | 选估值方法 + 反向健康检查 | 规划 + 校验(阈值) | 散文（判断+**阈值可抽**） |
| 1 | 取数 | 机械 | ✅ 脚本 `fetch_data.py` |
| 1B | 利润表分解 → EPS 基线 | 判断 | 散文（留模型） |
| 2 / 2B / 2C / 2D | 财务评分 / 业务+对手 mapping / 质化 / 现金流 | 判断为主 | 散文（**2B/2C 可 worker 化**） |
| 3 | 合理 PE = 基础 + 加分 + 减分（8/50 截断） | 判断定输入 + **机械算** | 散文 |
| 4 / 4B | 多模型加权交叉验证 / 远期 | 判断 + **机械算（加权）** | 散文 |
| 5 | 预期差 → 调安全边际 | 判断 | 散文（留模型） |
| 6 | 三锚定价 → 买入价 | **机械算** | 散文 |
| 7 | 卖出双锚 → 减仓/清仓 | **机械算** | 散文 |
| 8 | 6 档区间分类 → 白名单术语 | **机械算** | 散文 |
| 9 | 独立零上下文校验 | assert(correctness) | ✅ subagent / verify-cli |

### 1.2 8 部件映射（已具雏形、缺三样）

Planner（Step 0）✅ / Workers（取数=脚本、研究=模型）⚠️ / Evaluator（Step 0 反向检查 + Step 4 交叉 + Step 9）✅ / Loop-Branch（偏离>±40% 重走、分歧>30% 复查、按需跳过）✅ / **State ❌（活在上下文）** / **Stop-Resume ❌** / **Repeatability ❌（每次重新心算）**。

### 1.3 失败类分析（Step 9 事故清单的根因）

| 事故 | 根因类 | 本方案哪条治 |
|---|---|---|
| 中国建筑 v1 PE 反推错 16% / 招行 0.85 PB 心算 / 单位量级错 | **心算错（算术在散文）** | 线 A：算术固化 |
| 地平线 v1 漏地瓜机器人（子公司）/ 漏 Momenta（对手） | **遗漏（完整性无门）** | 线 B：worker + 完整性门 |
| 焦点科技 Q1 -12% 没追一阶原因 | 判断（归因） | 仍靠模型 + Step 9，不在本方案范围 |

> **门 1 校正（别夸大线 A）**：核对后，部分估值算术**已是代码/伪代码形态**——`calc_pe_band` 已消除"分位反推中位"陷阱（招行类心算部分已被 baostock 治）、DCF 与 4B 增速系数已是 references 里的 Python 伪代码。线 A 的真增量 = 把这些**散落伪代码 + 散文算术固化成被调用的单一纯函数 + 补上 B1/B3 两条最高频出错的接缝（`+2x` 后处理 / `PE×EPS`）**，而非"消灭整类心算"。

## 2. 设计

### 2.1 线 A：算术固化 → `scripts/compute_valuation.py`（纯函数 + 单测）

无状态纯函数，输入=模型已决定的数值，输出=锚点/分类/flag。建议函数面：

| 函数 | 输入（模型供：判断型数值） | 输出（代码算：纯算术） |
|---|---|---|
| `fair_pe(base, plus, minus, trend_bonus=0)` | 行业基础 PE、加分 dict、减分 dict、**盈利趋势 +2x 布尔（Step 6.4，门 1·B1 补）** | 合理 PE，clamp[8,50] |
| `value_from_pe(fair_pe, eps)` | 合理 PE、**1B.6 选定 EPS** | 合理价值_PE = fair_pe × eps（**门 1·B3 补：中国建筑 16% 事故的接缝，必须入码**） |
| `fwd_pe_growth_adj(base_pe, growth)` | 基础 PE、远期增速 | 增速调整 PE（4B 线性插值 `0.8+(g-.03)/.22×.7`，门 1·N2：本就是干净算术、原漏点名） |
| `blended_value(static, fy1, fy2, w=(.4,.4,.2))` | 三档**价值**（非 PE） | 综合合理价值 |
| `margin_pct(certainty, gap_adj, redflag_adj)` | 确定性档 / 预期差调整 / red flag 调整 | 安全边际比例，clamp[5,40]，多 red flag = max 单项 + 累加上限 10 |
| `buy_anchors(value, margin, min_disc, hist_low_pe, ttm_eps)` | 综合价值、安全边际、最低折扣、历史低点 PE 中位、TTM EPS | 锚点 A、有效 B = min(原始, 上限)、**买入价 = max(A, 有效 B)**；**锚点 C = value×0.7 仅 display-only，不参与定价（门 1·S1）** |
| `sell_anchors(value, cut_mult, exit_mult, hist_high_pe, ttm_eps)` | 倍数、历史高点 PE | 减仓锚 = min(D减, E)、清仓 = D清（**展示锚，主 agent 可附近取整微调，门 1·S5**） |
| `annualize_eps(partial_eps, ratio)` | 季度 EPS、**占比（含季节性判断，模型供）** | 年化 EPS |
| `classify_band(price, buy, value, cut, exit)` | 当前价 + 四锚 | **前 6 档白名单术语** + `needs_revaluation` flag（价<买入×0.85 只返 flag，**重做估值是主 agent 判断、不在函数内，门 1·S3**）|
| `sanity_flags(value, price, hist_1y, models)` | 综合价值、市价、历史 1 年区间、三模型 | 触发的 flag 列表（偏离>±40% / 区间外 / 分歧>30%·弱周期>50% / 快速通道>50%） |

**契约不变**：净现金只做下行托底（不进任何锚点）—— `compute_valuation` 不接收净现金参数，从结构上堵住"反向上调锚点"。

**附带红利**：
- `classify_band` 只吐白名单词 → 区间术语**源头正确**，现有「区间术语自检」+ `lint-interval-terms.py` + pre-commit warn **降为兜底**（地板/天花板原则的延伸）。
- 单测用 2-3 个已建档标的（青啤示例、茅台、地平线）反算锚点，对齐 wiki 现值，保证迁移无回归。

### 2.2 线 A：state 外部化 → `valuation_state.json`

每次分析的中间产物落文件（企业类型 / EPS 基线 / 合理 PE / 综合价值 / 四档锚点 / 各 step 是否执行）。**首要论证（门 1·S2）= Step 5.4 修正联动**：合理 PE 一改，合理价值 / 买入价（锚点 A、B 上限）/ 减仓 / 清仓**全部派生重算**（`SKILL.md:721-727`；教训 [[feedback_unit_scale_rederive]]——改基数后派生值必须逐项重算，长鑫发行价踩过）。state + compute_valuation 一次调用全派生，替掉"散文里逐项心算重算"。其次：① Step 间契约从散文约定升为读写同一对象（Step 4 SOTP 必须从 state 里 2B.1 写的分部取）；② Stop/Resume；③ Repeatability。**只落 `/tmp` 或单独 gitignore 目录，不落 `raw/articles/`**（门 1·N4：那目录是 [观测] 来源归档语义，分析中间态混入会污染）。

### 2.3 线 B：研究步 worker 化（2B.1 / 2B.2 / 2C）

**结构**：主 agent（Opus）规划 → spawn 工作 agent 并行执行 2B.1 / 2B.2 / 2C，每个 agent 带 `verificationPrompt`（现有 rubric 提炼）自验完整性 → 通过后返回结构化产物 → **主 agent 汇总**（喂 Step 4 SOTP/可比表、Step 6 安全边际 red flag、写 wiki）。

> **门 1 裁定（worker 模型档，B2）**：原方案默认 sonnet worker 与 AGENTS.md:307「判断型 value-invest 估值 → 强模型」**直接冲突**，且本方案 §1.1 自标 2B/2C 为"判断为主"——AGENTS.md 的"不降档"只护 Step 9/arbiter 校验，**不护 2B/2C 正向判断步**，不能借前者合规去做后者降档。**默认改 Opus worker**（只取"完整性门"红利、不取省钱红利）；sonnet 降档列为冒烟达标后的单独优化项 + 须用户就 AGENTS.md:307 例外明确裁定（见 §5）。另：若启用 sonnet，worker 档须与 Step 9 校验员**异构**——同源（都 sonnet）会让漏报相关、打折异构红利。

| worker | taskPrompt 摘要 | verificationPrompt（完整性门，提炼自现有 rubric） |
|---|---|---|
| 2B.1 业务结构 | 查子公司/战略持股≥20%/期权资产/分部≥5%，输出业务结构树 | 4 维度全查、每项有数据源、≥5% 营收分部单列（2B.1 Fail 条件 + 2B.3） |
| 2B.2 对手 mapping | 产品层 + 方案层 + 触发的扩展/行业维度，每对手附 URL | 基础 2 维每维≥1 对手 + URL、扩展 2 维触发条件已检查（2B.2 Fail + 2B.3） |
| 2C 质化 | 按企业类型选对清单查（不硬套创始团队到央国企） | 类型匹配、该类型必查项全覆盖、red flag 已识别（2C.1 分级 + 2C.2 清单） |

**条件触发**（避免每次分析都 fan-out 拖慢交互）：
- **spawn 模式**：首次建档 / 估值章节大改（2B/2C 本就强制、遗漏风险最高）
- **inline 模式**：季报微更新 / 锚点修订 <10%（2B/2C 本就跳过或按需）

**完整性门 ≠ correctness 门，worker loop 不替代 Step 9（门 1·命题 3 + 用户追问）**：

| | worker 自验门（线 B）| Step 9 / L3（事后）|
|---|---|---|
| 时点 | 生成中 | 全部写完后 |
| 验对象 | 单个 worker 自己的产出（2B/2C）| 整篇 wiki 终态，**含主 agent 汇总（SOTP 拼装 / 安全边际联动 / 四档锚点 / 叙事）**|
| 验者 | worker 自己（self）| 独立 zero-context **异构** subagent，独立重 fetch |
| 抓的错 | 遗漏 / 格式（completeness）| 算术错 / 口径混 / 叙事-数据不符 / **自信的错值**（correctness）|

**致命点**：worker 只验自己产出的那块；**主 agent 的汇总（把 2B 拼成 SOTP、把 2C red flag 联动进安全边际、写四档锚点与叙事）是 stakes 最高的产物，却没有任何 worker 看过它**——而汇总正是 confirmation bias 最咬人处（主 agent 给自己终答打分）。撤掉 Step 9 = 汇总层裸奔。

两条独立依据：① **文章自己保留两层**——深度研究 loop 里每个 `agent()` 有 verificationPrompt（per-worker 门）+ 结尾独立 `assert()` 终验，是 Evaluator 两层、非冗余；② **本仓库 L2/L3 铁律**——「L2（事前）+ L3（事后）不可互替；主 agent 写入纪律完整 ≠ subagent 可省」（AGENTS.md）。worker loop = 加强版事前（L2），Step 9 = value-invest 的 L3 事后，按仓库法不可互替。

**真正的效率红利**：worker 完整性门把"遗漏类"（地平线漏对手）挡在上游、生成时 → Step 9 的 omission 负载下降，**聚焦 correctness / 汇总层**，变轻、不消失。既有豁免（轻量更新 / <30 天已校验 / 锚点改 <10%）不变——季报微更本就不 spawn 也不跑 Step 9，首次建档/大改才两者都上。

### 2.4 边界清单（哪些动、哪些不动）

| 处理 | Step |
|---|---|
| → 抽进 `compute_valuation.py`（代码） | 3 算术 / 4 加权 / 6 / 7 / 8 / 0 与 4 的阈值校验 |
| → 外部化 `valuation_state.json` | 全流程中间产物 |
| → spawn 工作 agent + 完整性门（条件触发） | 2B.1 / 2B.2 / 2C |
| **留主 agent（判断，不动）** | Step 0 选方法、1B EPS 基线、2 评分、2D 现金流深挖、加减分因子值、Step 5 预期差、汇总 |
| **不动（已是独立 assert）** | Step 9（Opus 不降档） |

## 2.5 目标执行模型（TO-BE 四相）

把线 A + 线 B 收口成一条执行流。判据：**并发** = 互不消费对方产出（只依赖 Step 1）；**可验证** = 有 pass/fail 门。两者交集 = `Promise.all([agent(task, verify)…])` 候选。

| 相 | 步骤 | 形态 | 门 |
|---|---|---|---|
| **0–1 顺序前缀** | Step 0 选型 → Step 1 取数 | 串行（写 `valuation_state.json`）| — |
| **2 尽调并发扇出** | `Promise.all([1B, 2, 2B★, 2C★, 2D])` | 并发；★=spawn worker（Web 重+易漏），余 inline 并发 | **① 完整性门**（per-worker：1B 归母≈扣非<1% / 2D 勾稽反推 / 2B 2B.3 rubric / 2C 类型清单 / 2 比率反推）|
| **3 汇总脊** | Step 3→4→4B→5→6→7→8 | 串行（`compute_valuation` 算术；Step 5 判断输入）| **② 交叉验证 assert**（Step 4：差距>30%/偏离±20% → 反向健康检查回 Step 0）|
| **4 终验** | 汇总写 wiki → Step 9 → 提交 | 串行 | **③ 独立终验 assert**（Step 9：异构零上下文，验汇总层 correctness）|

**三门层层不同面**：① 完整性（漏没漏，生成时）→ ② 交叉验证（方法/参数自洽，汇总时）→ ③ correctness（数字对不对，事后独立）。worker 的 ① 不替代 Step 9 的 ③（见 §2.3）。

**并发边界**：相 2 的并发 = 主 agent 一次 `Promise.all` fan-out（Agent 工具同工作区 spawn），**非常驻 loop、非 workflow 引擎**——主 agent 仍是交互式 orchestrator（文章对非 headless 任务的告诫）。

**横切 State**：`valuation_state.json` 贯穿四相 → 断点续跑 + Step 5.4 修正联动 = 对 compute_valuation 一次重算。

**相对 AS-IS 的三处变化**：尽调 5 步 顺序叙事 → 一次扇出；算术 6 步 心算 → compute_valuation；校验 全压事后 Step 9 → 门分三层（Step 9 负载变轻、不撤）。

## 3. 分阶段执行（feature 分支，逐 phase 独立 commit）

| Phase | 动作 | 验证 |
|---|---|---|
| **A1** | `compute_valuation.py` 纯函数 + `test_compute_valuation.py` 单测 | **oracle = 手工独立复算的标准答案**（测试写死预期输入→输出、人核对一次）；**不拿 wiki 现值当 assert 基准**（门 1·S4：wiki 现值可能是 verify 抓出前的旧错值——中国建筑 v1 高估 16%、地平线锚点 v1.1→v1.5 多次改，会把错误焊进回归网）；wiki 现值仅作"是否偏离"弱提示 |
| **A2** | SKILL.md Step 3/4/6/7/8 改为"调 compute_valuation"；区间术语 section 标注"由 classify_band 保证、自检降兜底"；`valuation_state.json` schema | SKILL.md diff 仅换执行主体不改方法学；跑一个标的端到端锚点与手算一致 |
| **B1** | 把 2B.1/2B.2/2C 的 Fail 条件/sanity check 提炼成 `references/worker-rubrics.md`（verificationPrompt 模板） | rubric 与现有 SKILL.md 表逐项对齐、无新增/丢失检查项 |
| **B2** | SKILL.md Step 2B/2C 加"spawn 模式（条件触发）"小节 + 汇总契约；Claude Code 用 Agent 工具（`model=sonnet`），非 CC harness 用 task/fallback（按 multi-harness 映射表） | 干跑：首次建档触发 spawn、季报微更走 inline |
| **C** | 冒烟：用地平线（2B/2C omission 反例）重跑 spawn 模式 | 对比是否捕捉 v1 漏的地瓜机器人/Momenta；锚点经 compute_valuation 与 v1.x 一致 |

**门 2**：合并前 spawn 独立 subagent review 整个 `main..HEAD` diff。仅用户明确说"合"才 merge。

## 4. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 算术抽码后边缘 case 失去灵活度 | 脚本只接收"已决定数值"做乘法/clamp，判断仍在模型；边缘 case 体现在模型给的输入里，非脚本逻辑 |
| worker self-verify 被误当 Step 9 替代 | 方案 §2.3 明确两门叠加；SKILL.md Step 9「禁止行为」补一条"worker 完整性门不豁免 Step 9" |
| spawn fan-out 拖慢交互 / 成本 | 条件触发（仅首次建档/大改）；并行 Promise.all 而非串行 |
| sonnet 做对手 mapping 质量不足 | Phase C 冒烟实测；不达标则该 worker 回退 inline 或升 Opus（开放决策）|
| 真并行（worktree）丢隐私指令 | 本方案 worker 走 Agent 工具 spawn（同工作区、非 worktree），不触发 worktree 隐私盲区；产出均为公开 wiki 业务内容、无持仓 |
| state 文件入库污染 | 默认 `/tmp` 或 raw（gitignore 中间态）；只有最终 wiki + verify_report 入库 |
| 一次动太多 | 严格分 phase commit、feature 分支、双门、可逐 phase 回滚 |

## 5. 开放决策（门 1 / 用户裁定）

| 决策 | 默认建议 | 备选 |
|---|---|---|
| **worker 模型档（门 1 重点，待裁定）** | **Opus（门 1 默认：合 AGENTS.md 判断型→强模型，只取完整性门红利）** | sonnet 降档（省/快，须裁定 AGENTS.md:307 例外 + 冒烟达标后才上）；或 hybrid（2B.1 检索型 sonnet / 2C 错位风险 Opus）|
| spawn 模式触发面 | 仅首次建档 + 估值大改 | 也覆盖 >6 个月刷新 |
| 2B/2C 是否真并行 | Agent 工具同工作区并行（Promise.all） | 串行（更省、更慢）|
| state 落盘位置 | `/tmp`（纯中间态）| `raw/articles/stocks/<name>/`（留痕可复盘）|
| 是否先做线 A 再评估线 B | 线 A 先行（收益确定、风险低）；线 B 等 A 落地 + 冒烟再决定 | 两线并行推进 |

---

## 附录 A：门 1 review 记录（独立 subagent，2026-06-10）

独立 subagent 逐条核对方案断言 vs 源文件（非采信自我描述）。裁决与处置：

| 命题 | 裁决 | 处置 |
|---|---|---|
| 算术能安全抽码 | 部分成立（漏 3 处算术接缝） | B1/B3/N2：补 `fair_pe(trend_bonus)` / `value_from_pe` / `fwd_pe_growth_adj` |
| classify_band 消灭区间术语 | 部分成立 | S3：B×0.85 改返 `needs_revaluation` flag，重做判断不在函数内 |
| worker 自验不削弱 Step 9 独立性 | 基本成立 | Step 9 读终态 wiki 零上下文，结构性独立保住；补"worker 档须与校验员异构" |
| 2B/2C 降 sonnet 不违反能力分级 | **不成立** | **B2：默认改 Opus worker；sonnet 须用户裁定 AGENTS.md:307 例外** |
| 契约一致性（净现金/SOTP/DCF） | 成立 | `compute_valuation` 不收净现金参数确堵反向上调，不改 |
| 过度/不足工程 | 混合 | S2：state 以 5.4 重算链为首要论证；N4：state 不落 raw |
| 单测 oracle = wiki 现值 | 部分成立（锁死旧错值风险） | S4：oracle 改手工独立复算，wiki 现值仅作弱提示 |

**主 agent 自核（不盲信 subagent）**：B1（`SKILL.md:832` Step 6.4 +2x）、B3（`PE×EPS` 接缝、中国建筑事故）、B2（AGENTS.md:307 + 本方案 §1.1 自标"判断为主"双向印证）均回源核对**属实**。

**未决（待用户裁定）**：B2 worker 模型档 → 见 §5。
