---
name: value-invest-verify
description: 价值投资 wiki 独立校验工具。对已有的个股估值 wiki 做"零上下文"反推核对——通过全新 subagent 不带主对话历史，检查每个数字的 [观测]/[推算]/[估计] 来源、计算链一致性、口径混用、叙事与数据匹配。Use when user says "verify 某 wiki"、"校验某个股估值"、"核实 wiki 数据"，或刚做完估值修订想要独立核对。也由 value-invest 主流程 Step 9 自动触发。
---

# Value-Invest Verify Skill

## 定位

价值投资 wiki 的**独立校验员**。本 skill 的核心价值是**通过全新 subagent 提供"另一双不带上下文的眼睛"**——解决主 LLM 对自己产出的数字存在确认偏差的结构性盲点。

## 为什么需要独立校验

主 LLM 是"数据采集 + 建模 + 写作"的执行者，对自己产出的数字看不到盲点。过去案例：

| 案例 | 主作者盲点 | 后果 |
|---|---|---|
| 中国建筑 v1 | "PE 中位 8x 反推" 错（实际 5.07x） | 合理价高估 16% |
| 平安银行 5/9 | PB 中位漏扫（口径错位） | 用户 push 才补 |
| 招商银行 v1.0 | "-3bp" 接受用户数字、"0.85 PB" 心算 | 用户两次 push |
| 焦点科技 v1 | Q1 -12% 没追一阶原因（SBC 摊销） | 差点错下调估值 |

CLAUDE.md 五项 sanity check 是纪律存在但**执行靠自觉**。独立 subagent 强制核对每个数字。

## 何时触发

### 用户主动调用
- "verify 招行 wiki"、"校验 X 估值"、"核实 X 的数据"
- 估值修订后想独立核对
- 对老 wiki（v1.0 之前建档）做一次性反向核对

### 主流程自动触发（value-invest Step 9）
- 首次建档（new wiki page）
- 估值锚点修订幅度 > 10%（如合理价 46 → 55）
- 多模型差距 > 30% 触发交叉验证后

## 核心实现：通过 Agent 工具调起全新 subagent

**关键设计**：subagent 必须"零上下文"——不能带主对话的分析过程，只能：
- 读最终 wiki 文件
- 读已归档的 raw/articles
- 独立跑脚本拉数据
- WebSearch 交叉验证

**禁止**：在 prompt 里塞主分析的结论、估值锚点、判断方向——会让 subagent "被叙事拖走"，失去独立性。

## 执行流程

### Step 1: 准备工作

读取目标 wiki 文件路径（用户指定，或 value-invest 主流程传入）：
- A 股：`wiki/stocks/<sector>/<name>.md`
- 已 focus 标的：`wiki/stocks/focus/<name>.md`（symlink，自动 follow）
- 如对应 `raw/articles/stocks/<name>/` 存在，列出归档文件路径

### Step 2: 调起 general-purpose subagent

使用 `Agent` 工具，`subagent_type=general-purpose`，prompt 严格按照 `prompt-template.md` 的模板（见 [`prompt-template.md`](prompt-template.md)）填充：

```
Agent({
  description: "招行 wiki 独立校验",
  subagent_type: "general-purpose",
  prompt: <prompt-template.md 内容 + wiki 路径>
})
```

**prompt 必须包含**：
- 任务定义（独立校验，不做估值修订）
- wiki 文件路径
- 七项校验框架（含覆盖完整性 + 质化深度）
- 输出格式（三档清单）

**prompt 禁止包含**：
- 主对话讨论的具体数字（如"NIM -5bp"、"合理价 46 元"）
- 当前的判断方向（如"市场过度悲观"）
- 已知的 BPS / 锚点价格

### Step 3: 接收校验报告

subagent 返回一份**三档分级清单**：

| 档位 | 含义 | 主 agent 行动 |
|---|---|---|
| ✅ Pass | 数据与计算自洽 | 跳过 |
| ⚠️ Warning | 不严谨但不影响结论 | 走 Step 3.5 |
| ❌ Fail | 数字错误或推导错误 | **必须走 Step 3.5** |

### Step 3.5: 原始数据源回访（强制纪律，不开新 agent）

**为什么这个 Step 是强制的**：subagent 也可能错。"主 agent 写 X / subagent 说 Y / 谁对谁错？"——若主 agent 直接信 subagent，就是用一个偏差替换另一个偏差。**层次 1 仲裁**——主 agent 必须独立 fetch 原始数据源核对一次，才能决定修订或保留。

历史教训：招行 v1.2 校验首测中，subagent 报告说"原文同时给净利差 1.77% 和净息差 1.83%"——主 agent 独立 WebFetch 原文后发现**真实情况是原文直接给 NIM 1.83%，净利差 1.77% 是从原文给的"生息资产收益率 2.84% - 计息负债成本率 1.07%"反推出来的**。subagent 结论正确但表述不严谨——若主 agent 不做层次 1 仲裁就直接信，会把 [推算] 当 [观测] 写进 wiki。

**强制动作**（对每项 Fail 和影响结论的 Warning）：

| subagent 标注 | 主 agent 必做核对 |
|---|---|
| **[观测]** + URL + 原文摘录 | 必须 `WebFetch` 该 URL，独立确认原文与 subagent 摘录一字一致 |
| **[推算]** + 公式 + 底层数据 URL | 必须 `WebFetch` 底层 URL **+** 独立代入公式核对结果 |
| **[估计]** + 置信度区间 | 评估置信度区间是否合理。**[估计] 项不走 Step 3.6 仲裁**（仲裁员靠原始数据也无法判断"主观猜测是否合理"）——若主 agent 认为置信度区间不合理，应直接**修订置信度标注**或**保留 [估计] 但拓宽区间**；只有当 [估计] 涉及估值核心假设且主 agent 怀疑能找到原始数据（subagent 漏查）时，才走 Step 3.6 |
| 脚本输出（AKShare / baostock）| 必须重跑脚本独立核对 |

**Step 3.5 输出**：对每项 Fail/Warning 给一个仲裁结论：

| 仲裁结论 | 行动 |
|---|---|
| ✅ subagent 正确 | 进 Step 4 修订 wiki |
| ⚠️ subagent 部分正确（如结论对但置信度档位标错）| 进 Step 4 修订 wiki，但**修正置信度标注** |
| ❌ subagent 错误 | 不修订 wiki，记录 subagent 误判到归档报告 |
| 🤔 主-sub 仍分歧无法独立确认 | **触发 Step 3.6（层次 2 仲裁）** |

### Step 3.6: 层次 2 仲裁（按需触发，开第三个 subagent）

**触发条件**（任一）：
- Step 3.5 仍无法确认（原始 URL 失效 / 数据源本身冲突 / 反推公式有争议）
- 分歧涉及估值核心假设（合理 PB、长期 ROE、NIM 中枢、安全边际比例）
- subagent 引用的数据源被主 agent 怀疑不可信

**实现**：用 Agent 工具调起**第三个 general-purpose subagent**（仲裁员 / arbiter），prompt 用 [`arbiter-prompt.md`](arbiter-prompt.md) 模板。

**关键设计**：仲裁员 prompt **不透露**哪个是主 agent 版本、哪个是 subagent 版本，只给两个版本的差异描述 + 独立去查原始数据。

**何时跳过 Step 3.6**：层次 1 已经能独立确认结论（如刚才招行案例中 5 项 Fail 全部通过层次 1 WebFetch + 重跑脚本独立确认，未触发层次 2）。

**Step 3.5 与 Step 3.6 仲裁结论维度不同**（避免误读）：
- **Step 3.5（层次 1）输出维度**：按"subagent 是否正确"分类（subagent 正确 / 部分正确 / 错误 / 仍分歧）
- **Step 3.6（层次 2）输出维度**：按"真值是什么"分类（A 正确 / B 正确 / 都对但口径不同 / 都不对 / 数据冲突 / 无法核对），见 [`arbiter-prompt.md`](arbiter-prompt.md) 第 Step 2 仲裁结论表

两者不矛盾：层次 1 是"主 agent 视角对 subagent 的评价"，层次 2 是"独立仲裁员对真值的认定"——前者关心"该不该信 sub"，后者关心"事实是什么"。

### Step 4: 呈现给用户 + 后续修订（用户决策后）

把 Step 3.5/3.6 仲裁后的**最终结论**呈现给用户（不要塞回 subagent 原始报告——经过仲裁的更可信）。

#### 4.1 校验报告归档（无论修订与否都做）

- 归档到 `raw/articles/stocks/<name>/<YYYY-MM-DD>_verify_report.md`
- Frontmatter 包含 `type: verify_report` + `verified: true`，作为时间戳证据

#### 4.2 用户决定修订时——**强制走 4 步完整落地**（不只是改 frontmatter）

**为什么强调"完整落地"**：2026-05-11 招行 v1.2 + 茅台 v1.1 + focus list 全量回归（Phase 1+2+3）实测发现——**Phase 1+2 只改 frontmatter 标注的做法是不完整的**，wiki 正文还有大量旧数据、过期叙事、未同步区间判定。下游 skill（periodic-review / portfolio-review）grep wiki 时会读到错误数据。**Phase 3 落地工作量是 Phase 1+2 的 2-3 倍**，但是必须的。下次跑 verify 强制走完整闭环。

##### Step 4.2.1：Frontmatter 加 v1.x 校验修订说明（最轻量但易导致下游误用）

```yaml
> **2026-MM-DD v1.x 独立校验修订**（value-invest-verify focus 回归）：
> - **Fail N [严重度]** 摘要
> - 校验报告：[路径]
> - 估值锚点变化 OR 保持
```

⚠️ **仅 frontmatter 标注不构成完整修订**——必须继续走 4.2.2。

##### Step 4.2.2：wiki 正文贯穿（最容易遗漏的步骤）

**对每项 Fail / 影响结论的 Warning，必须 grep 该数字 / 叙事在 wiki 内出现的所有位置**，不能只改一处。

实测教训：
- 海螺水泥净现金 **394 亿出现 5 处**（核心判断 / 一句话 / PE 推导 / 净资产分拆 / 看多论点），只改 frontmatter 会让下游读到 5 处旧数据
- 紫金矿业合理价 **31 元出现 3 处**（结论速览表 / 综合估值表 / 锚点 A 公式）
- 汇川技术"**67-71 元处乐观区间下沿**" 出现 2 处（价格区间表 / 操作建议段一句话总结）
- 蜜雪集团"**霸王茶姬崛起**" 叙事出现 3 处（一句话 / 同行对比段 / 风险点段）

**强制流程**：
1. 对每项 Fail/影响结论的 Warning，先 `grep -n "<key term>" wiki/stocks/.../X.md` 看出现位置
2. 逐处修订，加 `（v1.x verify 修订）` 标注
3. 修订后再 `grep -n` 一次确认无遗漏

##### Step 4.2.3：跨文件一致性同步

修订完 wiki 主页面后，必须同步：

| 同步对象 | 内容 |
|---|---|
| `wiki/index.md` | 该标的的个股摘要行（含估值锚点 / 区间判定 / 关键叙事）|
| `wiki/stocks/价格区间总览.md`（如存在该标的）| 四档锚点价格 |
| 相关 sectors/行业 wiki（如该标的被引用作为同业对比）| 同业数据更新 |
| `wiki/journal/<最近一次复盘>.md` | 如已写入复盘的区间判定与本次修订冲突，加 caveat |

##### Step 4.2.4：log.md 加 LINT 条目

记录本次修订的：触发原因 / 修订项数 / 关键 Fail / 影响估值 / surprising 发现 / 最大不确定性。

#### 4.3 区间判定术语契约（CLAUDE.md 6 档白名单）

修订区间判定时必须从白名单取（不允许自创术语）：
- **个股 6 档**：`买入区间` / `关注区间` / `持有区间` / `谨慎区间` / `减仓区间` / `清仓区间`
- 位置修饰：`XX 区间下沿/上沿/中段/中位`

wiki 正文与 index.md **同一标的的区间判定必须一致**（下游 skill 依赖此契约）。

#### 4.4 完整闭环 checklist（修订前自检）

| 步骤 | 完成 |
|---|---|
| □ 校验报告已归档到 `raw/articles/stocks/<name>/<YYYY-MM-DD>_verify_report.md` |
| □ Frontmatter 加 v1.x 修订说明 |
| □ 对每项 Fail grep 该数字 / 叙事出现的所有位置，逐处修订 |
| □ index.md 个股摘要行同步 |
| □ 如修订了区间判定：从 6 档白名单取，wiki 正文与 index.md 一致 |
| □ 如影响价格区间总览 / sectors 引用：同步 |
| □ log.md 加 LINT 条目 |

**所有 □ 全部 ✓ 才算完整修订**。仅做前 2 项是"半完成"状态，下游会读错数据。

## 七项校验框架

详细见 [`prompt-template.md`](prompt-template.md)，简述如下：

| 项 | 校验内容 | 失败示例 |
|---|---|---|
| 1. 数据来源三档 | 每个核心数字标 [观测]/[推算]/[估计] 是否到位？数据源 URL 是否可验证？ | "PB 中位 1.29" 未标 [观测：baostock] |
| 2. 计算链一致性 | 戈登 PB、DDM、含息回报、合理价加权等数学正确性 | (ROE-g)/(r-g) 算错 / 加权和 ≠ 综合价 |
| 3. 口径混用 | EPS / BPS / 股本 / NIM / ROE 的时点与口径是否前后一致？ | EPS 表用 5.70 但 PE 反推 5.97 |
| 4. 反推校验 | 派生数字与基数的反推关系（占比、同比、环比）| 机构持仓 735 亿 / 总份额 735 亿 = 100% 报警 |
| 5. 叙事 vs 数据 | "护城河 / 第一 / 显著低估 / 过度悲观" 等强叙事词是否有数据支撑？ | "市场过度悲观" 无量化反推 |
| **6. 覆盖完整性** ★ | 业务结构 / 竞争对手 / 风险点 / 关键事件是否完整覆盖？强制 WebSearch 验证 | 漏报 ≥ 1 个直接竞争对手 / 漏报 ≥ 1 个独立融资的子公司 / 行业格局只列硬件出货层未列方案+服务层对手 |
| **7. 质化深度** ★ | 创始团队 / 人才密度 / 接班准备 / 央企政策定位 / 合规文化等"不易量化但影响长期估值"的维度，**按企业类型差异化** | AI 创业型缺创始人 IDL/学术背景 / 民营成长股缺接班准备 / 央企被错误地按"创始人"框架写（结构性错位）/ 金融股缺合规文化与风控对比 |

**校验 1-7 的关系**：
- **校验 1-5**：检查"已写下的内容是否正确"（防"数据假"和"算错"）—— 主要"读 + 反推"
- **校验 6**：检查"应该写但没写的内容是否完整"（防"漏对手"和"漏分部"）—— 2026-05 新增，主动 WebSearch 验证
- **校验 7**：检查"质化深度是否到位"（创始团队 / 人才密度 / 接班 / 央企政策等）—— 2026-05 新增，**按企业类型差异化**——AI 创业型查创始团队 / 央企查政策定位 / 金融股查合规风控 / 真周期查管理层周期反应。**绝对禁止"创始团队"框架硬套央国企**（结构性错位）

## 不做什么（边界）

- ❌ 不重做估值（不重算合理 PB、不调整锚点）
- ❌ 不更新当前价（只校验 wiki 已写数字之间的自洽性）
- ❌ 不做投资建议
- ❌ 不写 wiki 修订 patch（仅输出问题清单）
- ❌ **校验 6 + 校验 7 不是"补充研究"**——WebSearch 仅用于验证覆盖完整性（校验 6）和质化深度（校验 7），两者**共享 8 次配额**，不深入分析对手详细信息或创始人详细背景，只指出"漏了什么"

校验员的职责是**指出问题**（包括"漏了什么"），不是**解决问题**——保持独立性。

## 输出格式（呈现给用户）

```
## 校验报告：<wiki 路径>

### ✅ Pass（N 项）
- 项目 1：数据 + 反推链
- 项目 2：数据 + 反推链
...

### ⚠️ Warning（N 项）
- 项目：问题描述 + 不影响结论的原因 + 建议修订（可选）

### ❌ Fail（N 项）
- 项目：错误数字 + 正确数字 + 数据源 URL + 必须修订的原因

### 元数据
- 校验日期：YYYY-MM-DD
- subagent 类型：general-purpose
- 使用工具：Read / Bash(脚本) / WebFetch / WebSearch
- 校验耗时：约 N 分钟
```

## 与 value-invest 主 skill 的关系

| 角色 | value-invest | value-invest-verify |
|---|---|---|
| 任务 | 建档 + 估值 + 写 wiki | 校验已写 wiki 的数据与结论 |
| 上下文 | 全部主对话历史 | 零上下文（subagent） |
| 输出 | wiki 修改 + 估值结论 | 问题清单（不改 wiki） |
| 触发 | 用户问"分析 X" | 用户问 "verify X" 或主流程自动触发 |

value-invest Step 9 通过**调用** value-invest-verify 间接使用 [`prompt-template.md`](prompt-template.md)（prompt-template.md 的唯一直接消费者是 value-invest-verify）——避免在 value-invest 和 value-invest-verify 两边维护两份校验逻辑。

## 与 wiki-review 的区别

| skill | 解决问题 |
|---|---|
| wiki-review | 格式对齐 + 过期内容归档（文本布局） |
| value-invest-verify | 数据与结论的反推校验（数字正确性） |

两者互补：先校验数字正确性，再做格式整理。
