# 多 Harness 兼容方案 — 路线 B（脱离 Claude Code 专属）+ 双 Agent 混用协议

> 状态：**方案 v2.1（门 1 已过；2026-06-10 用户裁定：第二 harness 首选 Hermes Agent）** | 创建：2026-06-10 | 关联：[`skill-refactor-plan.md`](skill-refactor-plan.md)（五原语蓝图）/ [`data-discipline.md`](data-discipline.md)（L1/L2/L3 细则）
>
> **背景**：仓库执行层（指令入口 / skill 触发 / hooks 接线 / L3 subagent / WebFetch·WebSearch 纪律）深绑 Claude Code。目标：① 让 Hermes Agent、OpenCode+DeepSeek 等任意 harness 能跑完整工作流；② 多个 agent 在同一仓库分时/分角色混用时互不破坏、纪律等价、产出可溯源。
>
> **核心判断**：混用场景下，**所有 agent 共享的只有 git 和文件系统**。因此：强制纪律下沉 git 层（pre-commit 是唯一全 agent 必经的强制点——前提是堵住 `--no-verify` 旁路，见协议 7）；共享状态全部进 repo 文件（AGENTS.md / docs / log.md），不依赖任何 harness 私有记忆；harness 差异收敛到"薄适配层 + 工具映射表"。这是 [`skill-refactor-plan.md`](skill-refactor-plan.md)「Hook 守确定性地板」原则在多 harness 下的自然延伸。
>
> **v2 修订（review 后）**：堵住两个地板旁路（机械任务写 wiki 豁免 B1、`--no-verify` 旁路 B2）；verify-cli 补章节定位 / WebFetch 预算 / 完整工具映射（S3）；改写点扩到 value-invest-verify SKILL.md（S4）；worktree 隐私盲区（S5）；存量 memory 迁移审计（S6）；权限接线落 Phase 6（S7）；砍掉 OpenCode 原生 verifier 双路径与 search 多后端抽象（Simplicity）。详见附录 A。
>
> **v2 后增补（2026-06-10，门 1 review 之后）**：校验员选型由单值 `default_verifier` 升级为「异构 × 档位」两轴，新增**按 spawn 点定校验档位**（L3 → 便宜快档 / value-invest · arbiter → 强推理档）——见 Phase 3「校验员选型两轴」。属对既有「异构校验红利」的直接延伸，**未单独过 review 门**，如需可补一轮门 1。

---

## 0. 目标与非目标

**目标**
1. 任一支持 Agent Skills 开放标准 + bash 的 harness，照接线文档配置后能跑：query / ingest（含 L1→L2→L3）/ verify / commit（pre-commit 生效）
2. 双 agent 混用（如 Claude Code 主力 + DeepSeek 副手；或 Hermes Agent 跑机械任务）有明确协作协议：开工自检、产出归属、并发边界、纪律等价
3. L3 / value-invest-verify 的"零上下文校验"获得 harness 无关的脚本实现，**且支持异构模型校验**（校验员 ≠ 主笔模型，误差不相关）

**非目标**
- 不做 CI / 云端自动化（本地工作流为界）
- 不重构 skills 职责划分（那是 skill-refactor-plan 的范围，本方案不与其冲突）
- 不追求"任意弱模型都能跑好判断型流程"——未通过冒烟验收的模型限定跑**只读 + 不写 wiki/ 的机械任务**，见 §Phase 5 协议 5 与 §Phase 7 通过标准
- 不动 `.trae/`（2026-04 旧产物，已 gitignore，不在范围内）

## 1. 现状耦合审计

| # | 耦合点 | 位置 | 性质 |
|---|---|---|---|
| 1 | 指令入口 CLAUDE.md / CLAUDE.local.md | 仓库根 | 仅 Claude Code（及 OpenCode fallback）自动加载 |
| 2 | skill 入口 `.claude/skills/` 符号链接 | 本地手建（`.claude/` 整目录 gitignore） | Claude Code + OpenCode 认；换机/换 harness 需重建 |
| 3 | 工具名硬编码 WebFetch / WebSearch / Agent / `Read pages=` | 约 130 行、散布 19 个文件（2026-06-10 review 实测，命令见注¹；大头：value-invest-verify 三 md 26 / data-discipline 26 / CLAUDE.md 22 / stock-deep-dive 含 references 24 / periodic-review 17）。另有字面变体 `Read PDF pages=X`（`templates/财报摘要模板.md:164`）与伪代码 `Agent({...})`（verify 三个 md） | 指令语义绑 Claude Code 工具集 |
| 4 | PostToolUse 两个 lint | `skills/_shared/hooks/lint-*.py`，靠 stdin JSON 取 `tool_input.file_path`（lint-interval-terms.py:28-32） | 逻辑已版控且自包含，仅入参协议绑 Claude Code |
| 5 | L3 校验 + value-invest-verify + arbiter | CLAUDE.md §L3、`value-invest-verify/SKILL.md`（Agent 工具 spawn，三级仲裁） | 流程绑 Claude Code Agent 工具 |
| 6 | 财报 PDF 逐页回读（`Read pages=X`） | CLAUDE.md Ingest §3、`templates/财报摘要模板.md:164` | 绑 harness 的 PDF 渲染 + 模型多模态能力 |
| 7 | Claude auto-memory 中的偏好/教训 | `~/.claude/projects/.../memory/` | 仓库外，换 harness 即失效（存量迁移见 Phase 5） |
| 8 | 权限 allowlist | `.claude/settings.local.json` | 各 harness 各有体系，不可移植（基线接线见 Phase 6） |

> ¹ 统计命令：`grep -rE 'WebFetch|WebSearch|Agent 工具|Read pages=' CLAUDE.md docs/ skills/ templates/`（行计，排除本方案文件）。Phase 1 验证以重跑此命令为基线。

**无需调整**（已是 harness 中立）：`raw/` `wiki/` `templates/`（纯 markdown+git）；`skills/_shared/marketdata` + 各 skill `scripts/*.py`（纯 Python）；git pre-commit 隐私闸门（`core.hooksPath`，对所有 commit 路径生效）；SKILL.md frontmatter（15 个 skill 全部仅 `name`+`description`，已是 agentskills.io 开放标准最小格式）。

## 2. 目标 harness 事实基线（2026-06 核查）

| 能力 | Claude Code | OpenCode | Hermes Agent | 脚本 fallback |
|---|---|---|---|---|
| 指令文件 | CLAUDE.md | AGENTS.md，**fallback 读 CLAUDE.md** | AGENTS.md（OpenClaw 系约定） | — |
| Skills | `.claude/skills/` | **原生读 `.claude/skills/` 及 `.agents/skills/`** | agentskills.io 标准 | AGENTS.md 内 skill 索引表 |
| 模型 | Anthropic | 任意 OpenAI 兼容（`@ai-sdk/openai-compatible`；DeepSeek 有官方接入文档） | Nous Portal / OpenRouter / 自定义端点 | — |
| Subagent | Agent 工具 | `.opencode/agent/*.md`（mode: subagent）+ task 工具 | 支持 spawn 隔离 subagent | **verify-cli（Phase 3）** |
| 写后 hook | PostToolUse | 无原生兼容；JS 插件可挂 | 无同类机制 | **pre-commit 双栈（Phase 4）** |
| Web 搜索/抓取 | WebSearch / WebFetch（Anthropic 侧） | 无内置，走 MCP | 内置工具集 + MCP | **webtools（Phase 2）** |
| PDF 逐页读 | Read pages= | 无保证 | 无保证 | **pdf_text.py（Phase 2）** |

来源：[OpenCode skills](https://opencode.ai/docs/skills/) / [rules](https://opencode.ai/docs/rules/) / [agents](https://opencode.ai/docs/agents/) / [providers](https://opencode.ai/docs/providers/)、[DeepSeek×OpenCode 官方集成](https://api-docs.deepseek.com/guides/agent_integrations/opencode)、[hermes-agent README](https://github.com/NousResearch/hermes-agent)。
**纪律注**：第三方文档时效衰减快，上表仅作设计输入；每项能力以 Phase 7 冒烟实测为准，不以文档为准。

## 3. 分阶段执行

每 Phase = 一次独立 commit，在 feature 分支 `feat/multi-harness` 上推进。**合入时点（防半成品指令外泄）**：P0–P6 全部完成且冒烟 #1–#3 通过后整体合入 main——避免出现"AGENTS.md 已引用 verify-cli 但脚本尚不存在"的窗口期。方案与实施 diff 各过一道独立 review（双门）。

### Phase 0 — 指令入口统一（AGENTS.md 为 SSOT）

- 动作：
  1. `git mv CLAUDE.md AGENTS.md`（保 history）；`ln -s AGENTS.md CLAUDE.md`（Claude Code 沿 symlink 读，不感知变化）
  2. AGENTS.md 开头加一行：「若存在 `CLAUDE.local.md`，开工前必须完整读取并遵守（Claude Code 已自动加载，无需重复读）」——给不自动加载 local 指令的 harness 一个指令式 include。**CLAUDE.local.md 文件名与 gitignore 均不动**（review 裁定：改名+symlink 是多余环节）
- 本 Phase 仅动入口文件与这一行 include，不触其余正文（正文工具中立化在 Phase 1，分开 commit 便于回滚）
- 验证：`cat CLAUDE.md` 内容正确；Claude Code 新会话能复述 CLAUDE.md 中某条规则；`git log --follow AGENTS.md` history 连续
- 风险：低。某 harness 不解析 symlink → 回滚 = 互换真身与链接方向

### Phase 1 — 工具中立化：抽象动作 + 映射表（最小 diff 策略）

- 动作 A：AGENTS.md 新增「运行环境与工具映射」章节（置于文档前部）：

  | 抽象动作 | Claude Code | OpenCode | Hermes Agent | 脚本 fallback（全员可用） |
  |---|---|---|---|---|
  | 网页搜索 | WebSearch | search MCP | 内置 search | `python3 skills/_shared/webtools/search.py "<query>"` |
  | 原文抓取 | WebFetch | fetch MCP | 内置 fetch | `python3 skills/_shared/webtools/fetch.py <url>` |
  | PDF 逐页读 | Read pages=X | —（用 fallback） | —（用 fallback） | `python3 skills/_shared/webtools/pdf_text.py <pdf> --pages X` |
  | 零上下文校验（L3 / verify） | Agent 工具 spawn | task 工具或 fallback | subagent 或 fallback | `python3 skills/_shared/verify/run_verify.py …` |
  | 行情/宏观取数 | Bash + `_shared/marketdata` | 同左 | 同左 | 同左（已中立） |

  解析规则两条：
  1. 「本仓库所有文档（CLAUDE.md/AGENTS.md、docs/、skills/、templates/）中出现的 `WebFetch` / `WebSearch` / `Agent 工具` / `Agent({...})` / `subagent_type=general-purpose` / `Read pages=` / `Read PDF pages=` 均指上表抽象动作；非 Claude Code 环境按本表解析，**纪律语义不变**（如"[观测] 必须 WebFetch 原 URL"= 必须用本环境的"原文抓取"动作取回原文核对，禁止用搜索摘要替代）。」
  2. 「**原生优先**：本环境有原生实现时用原生（Claude Code 不要用 fetch.py 替代 WebFetch）；fallback 仅在原生不存在或失败时使用。」
- 动作 B：**5 处语义关键句改写**（不逐处改写约 130 行——避免大面积 diff 引入回归）：
  1. CLAUDE.md §L3「spawn general-purpose Agent」补"或运行 verify-cli（见映射表）"，并补档位标注 **L3 spawn 传 `model=sonnet`**（高频检索型，见 Phase 3「校验员选型两轴」；value-invest / arbiter 的原生 spawn 维持继承 Opus，不降档、本清单不改）
  2. CLAUDE.md Ingest §6 同上
  3. CLAUDE.md Ingest §3 `Read pages=X` 补 fallback 引用
  4. `value-invest-verify/SKILL.md` Step 2 补"非 Claude Code 环境：`run_verify.py --template value-invest`"
  5. `value-invest-verify/SKILL.md` Step 3.6 补"非 Claude Code 环境：`run_verify.py --template arbiter`"
- 验证：重跑 §1 注¹ 统计命令对照基线（仅 5 处新增行）；映射表 fallback 命令在 Phase 2/3 落地后逐一可执行
- 风险：中——弱模型可能不做"工具名翻译"。缓解：映射表置于 AGENTS.md 前部；Phase 7 冒烟里专测"模型是否按映射表选对工具"

### Phase 2 — webtools：搜索/抓取/PDF 的脚本地板

- 动作：新增 `skills/_shared/webtools/`（CLI 形态，任何能跑 bash 的 harness/模型可用；同时供 verify-cli import）：
  - `fetch.py <url> [--raw]` — requests + trafilatura（或 readability-lxml）→ markdown 到 stdout，头部带 URL/抓取时间戳/HTTP 状态；超时与重试上限硬编码
  - `search.py "<query>" [-n 5]` — **仅 Tavily 单后端**（key 走 `TAVILY_API_KEY` 环境变量），输出 title/url/snippet 列表。多后端抽象推迟到出现第二个真实需求（review 裁定：投机性灵活度）
  - `pdf_text.py <pdf> [--pages 3-5]` — pypdf/pdfplumber 按页抽取文本，页码对齐 PDF 物理页（供财报摘要「逐项回读校对」引用页码）；扫描版 PDF 报错提示走 OCR（不内置 OCR，超出范围）
- **对纪律的意义**：财报 PDF 摄入在纯文本模型下不再断链——`templates/财报摘要模板.md` 的"逐项 `Read PDF pages=X` 回读校对"在 fallback 下等价为"逐项 `pdf_text.py --pages X` 回读比对"。文本型 A 股财报 PDF 适用；扫描版降级人工
- 验证：`skills/_shared/eval/` 增 `smoke_webtools.py`——fetch 一个稳定 URL、search 一个 query（无 key 时 skip 并提示）、抽取 `raw/reports/` 任一既有 PDF 第 1 页非空。**本机代理环境实测可达性**（参照教训：东财全系 ProxyError，A 股数据走腾讯/新浪）
- 风险：中。Tavily 可达性/配额需实测（不可达 → 备选 Serper / 自托管 SearXNG，到时再实现）；trafilatura 对部分财经站抽取质量待验。fetch.py 同时也是 Claude Code 下 WebFetch 403 时的备选，对现有流程是纯增益

### Phase 3 — verify-cli：L3/verify 的 harness 无关实现（本方案核心交付）

- 动作：新增 `skills/_shared/verify/run_verify.py`：
  - **模板三模式**（prompt 单一事实源，运行时读取，不复制粘贴成第二份）：
    - `--template l3 --files <wiki…> --sections "<本次新增/修改的章节定位>" [--raw <原始材料路径或URL…>]` → 渲染 [`data-discipline.md` §数据校验 Agent prompt 模板](data-discipline.md#数据校验-agent-prompt-模板)。**`--sections` 必填**——L3 模板要求"文件路径 + 关键章节定位"（data-discipline.md:106），缺定位会让校验员全页扫描、10 次 search 预算失焦（个股页常上千行）
    - `--template value-invest --file <个股wiki>` → 渲染 `skills/value-invest-verify/prompt-template.md`（七项框架，全页校验本就是其语义）
    - `--template arbiter --diff <分歧描述文件>` → 渲染 `skills/value-invest-verify/arbiter-prompt.md`（Step 3.6 层次 2 仲裁）。**arbiter 模式下 `read_file` 机械排除 `wiki/**`**——把 arbiter-prompt.md:48"严禁读 wiki"的盲化从指令级升为代码级
  - **后端**：OpenAI 兼容 chat-completions + function calling。配置 `~/.config/invest-wiki/llm.json`（仓库外，天然不入库）：`{"backends": {"deepseek-lite": {…便宜快档…}, "deepseek": {…强推理档…}, "hermes-or": {…OpenRouter…}, …}, "verifier": {"l3": "deepseek-lite", "value-invest": "deepseek", "arbiter": "deepseek", "default": "deepseek"}}`——**`verifier` 按 `--template` 选 backend，实现"按 spawn 点定档"（见下「校验员选型两轴」）；原单值 `default_verifier` 升级为分模板 map**
  - **内置 tool-loop**（4 个 function）+ **完整工具名映射前言**（注入渲染后 prompt 头部，不改模板原文）：`Read → read_file`（限仓库内路径）/ `WebFetch → run_fetch`（webtools fetch.py）/ `WebSearch → run_search`（webtools search.py）/ `Bash 取数脚本 → run_script`（白名单：`skills/_shared/marketdata`、各 skill `scripts/` 只读取数脚本）/ `Grep → 无对应 function，读全文后自行扫描`。映射必须穷举模板中出现的全部工具名，弱模型在"模板指令与可用工具不一致"处最易卡死
  - **预算完整继承现纪律**：L3 模板 search ≤ 10 次（data-discipline.md:124）；value-invest 模板校验 6+7 共享 search 8 次（SKILL.md:233）**且 WebFetch ≤ 3 次（prompt-template.md:228）**；另加 max-steps 总闸防失控
  - **输出契约**：报告 markdown 到 stdout（格式 = 模板既有要求：全 ✓ 只回一行「通过 (扫描 N 项)」；否则列 ✗/⚠️ 项 + 必附 search URL）；退出码 `0`=全✓、`1`=有 ✗/⚠️、`2`=执行失败——主 agent / 脚本可机械判断；`--out <path>` 可选落盘（默认不入库，估值页归档沿用现有 `raw/articles/stocks/<name>/<date>_verify_report.md` 流程，由主 agent 决定）
- **AGENTS.md L3 规则改写**（Phase 1 动作 B 预留）：「L3 = 零上下文校验。Claude Code 用 Agent 工具；其它 harness 运行 verify-cli。完成标准与失败处理一致（0✗0⚠️ → log 记录后方可 commit），**不得以"本环境没有 subagent 工具"为由跳过 L3**」
- **校验员选型两轴（异构 × 档位，可叠加）**：
  - **异构轴（误差去相关）**：校验员家族 ≠ 主笔家族（主笔 Claude → 校验 DeepSeek；主笔 DeepSeek → 校验 Claude API/Hermes）。误差不相关，强于同模型自校；也让 Hermes/DeepSeek 在"判断力要求低、独立性要求高"的校验位先上岗。**仅 verify-cli 路径可得**——Claude Code 原生 Agent 工具只能起 Claude 家族，无此红利
  - **档位轴（按 spawn 点匹配推理需求，定档原则 = 频率 × 单次 stakes × 检索/推理比例）**：
    - **L3**：高频（每次写入）、检索/比对为主、第三道兜底 → **便宜快档**（Claude 侧 Sonnet——不建议 Haiku，L3 模板含 10 次 search 预算管理 / 三档来源判定 / 反推链，过弱模型跟随复杂指令易掉链；verify-cli 侧 deepseek-lite 等）
    - **value-invest 校验 + arbiter 仲裁**：低频（建档 / 锚点改 >10% / 分歧仲裁）、推理与召回为主（校验 6/7 漏标会静默溜过、仲裁是最后一道判断）、单次 stakes 高 → **强推理档**（Opus / 强模型），**不降档**
  - **两路径落地**：
    - **Claude Code 原生**：`Agent` 工具 `model=` 参数——L3 spawn 传 `model: sonnet`，value-invest / arbiter 不传（继承主力 Opus）。此路径**只有档位轴、无异构轴**（同 Claude 家族）；其"误差去相关"靠模板强制 WebSearch 锚定外部真值，不靠模型差异
    - **verify-cli**：`llm.json` 的 `verifier` map 按 `--template`（l3 / value-invest / arbiter / default）取 backend，可同时叠加异构（选非 Claude 家族）+ 档位（便宜 / 强档分配）
- 主 agent 侧仲裁流程（verify SKILL.md Step 3.5 层次 1 回访）不变——那是主 agent 的职责，与校验员实现无关
- 验证：`--dry-run`（渲染 prompt 不调 API）对三模板各跑一次，人工核对渲染结果与工具映射前言；对一个已通过 Claude L3 的近期页面（如 `wiki/macro/黄金趋势跟踪.md`）用 DeepSeek 后端实跑，对照两份报告的扫描项数与结论方向
- 风险：中高（本方案最大工作量，约 300 行 + 配置）。模型函数调用质量参差 → budget/max-steps 双闸 + 「无 URL 的判断不可信」规则继承自模板原文；报告质量低于 Claude subagent 时，纪律仍成立（报告必须附可点 URL，主 agent Step 3.5 回访把关）

### Phase 4 — lint 双栈：写后 hook 降级 commit 时地板

- 动作：
  1. `lint-interval-terms.py` / `lint-frontmatter.py` 加 argv 模式：`python3 lint-x.py <file>…`（有 argv 用 argv，无则按现状读 stdin JSON——一份逻辑两个入口，约 10 行改动）
  2. `skills/_shared/hooks/pre-commit` 末尾追加：对 staged 的 `wiki/**/*.md`（`git diff --cached --name-only --diff-filter=ACM`）逐个跑两个 lint argv 模式；**warn-only 与现状对齐**（打 stderr、`|| true` 保证不改 exit 码）；将来升 block 与 PostToolUse 同步改。实现注：argv 模式扫的是工作区文件而非 staged 内容，warn-only 下可接受（严格 staged 版 `git show :path` 留待升 block 时实现）
  3. **拦截提示语修订（B2 配套）**：`pre-commit:80` 与 `hooks/README.md:56` 现有"误报可 `git commit --no-verify` 跳过"改为「**误报请停下来，把拦截输出原样转给用户，由用户人工决定是否 `--no-verify`；agent 一律禁止自行使用**（见 AGENTS.md 混用协议 7）」——现 stderr 会回喂模型，等于把逃生门的钥匙递给被拦的 agent，真阳性（隐私泄漏）场景下不可接受
- 效果：Claude Code 双保险（写时 PostToolUse + commit 时）；其它 harness 至少 commit 时有地板——**pre-commit 成为混用下唯一对所有 agent 生效的机械纪律点**
- OpenCode 写时 hook（JS 插件挂 `tool.execute.after` 调同两脚本）列为可选项，放 Phase 6 之后按需做，不阻塞主线
- 验证：手工 staged 一个含 `加仓区间` 的测试页 → commit 时 stderr 出现警告且提交放行（warn-only）；缺 frontmatter 同理；正常页零输出；拦截提示语不再含"可 --no-verify 跳过"的直接教学
- 风险：低。脚本逻辑零改动，仅加入参分支 + 提示语

### Phase 5 — 多 Agent 混用协议（写入 AGENTS.md 新章节）+ 存量 memory 迁移

> 协议七条 + 两个配套动作。协议引用 verify-cli / webtools，故本 Phase 在 Phase 3 之后执行。

1. **开工自检**：会话开始若 `git status` 不干净，先向用户确认残留归属（可能是另一 agent 的未竟工作），不得擅自 commit / revert / 续写他人未提交内容
2. **产出归属**：每条 `wiki/log.md` 条目末尾加 `- **执行**：<harness>/<model>`（如 `claude-code/fable-5`、`opencode/deepseek-v4`、`hermes-agent/hermes-4-405b`）。价值：数字错误可溯源到产出模型，跨模型质量对比有数据基础。约定起步；后续可升级为 pre-commit 对新增 log 条目做"含执行行"的 warn 检查（列入 hook 候选，与 skill-refactor-plan 附录 B 的 lint-narrative 同队列）
3. **并发边界**：默认**分时**——同一时刻只有一个 agent 写仓库（`wiki/log.md` 与 `index.md` 是追加热点，同工作区并发必冲突）。确需并行：各开 `git worktree` + 独立分支，由用户合并；禁止两个 agent 共享同一工作区。**worktree 隐私盲区**：gitignore 的 `CLAUDE.local.md` 不会出现在新 worktree——worktree 内 agent 视为**未读隐私指令**，禁止撰写任何涉持仓/金额/个人财务的内容，相关任务回主工作区分时执行
4. **纪律等价**：L1/L2/L3 的触发范围、豁免梯度、完成标准 harness 无关。L2 阶段 A 清单必须在该 agent 的对话/输出中可见；L3 用 Agent 工具或 verify-cli 二选一，标准同一。**模型弱不构成豁免理由**——恰恰相反，弱模型环境更依赖 pre-commit 地板 + verify-cli 必跑
5. **能力分级分工**（建议默认，非强制）：判断型流程（value-invest 估值、ingest 财报解读、macro-ellie 解读）→ 强模型。**机械型 = 不写 `wiki/` 的任务**（行情/宏观取数计算、etf-momentum 快照、verify-cli 驱动、`raw/` 采集落盘）→ 任意通过冒烟 #1/#3 的模型。**注意：scheduled-ingest 的"回写 wiki 静态章节"段与 wiki-review 改写 wiki 正文，均属写入类**——必须通过冒烟 #2 才可跑（B1 修订：堵住"机械任务"名义下的未校验写入旁路）
6. **状态共享走 repo**：教训、偏好、约定一律落 AGENTS.md / docs/ / log.md，不留在 harness 私有记忆（Claude auto-memory、Hermes 的 MEMORY.md/SOUL.md 体系）。Hermes Agent 的项目级记忆文件若生成在仓库内，加入 `.gitignore`，防止单 harness 私有状态混入共享事实源
7. **破坏性操作基线**：`git push` / 改写历史 / 批量删除，任何 harness 默认须用户确认；**任何 agent 禁止 `git commit --no-verify`（pre-commit 旁路），仅限用户人工执行**——没有这条，"pre-commit 是唯一强制点"对弱遵循模型不成立（B2）。各 harness 权限机制的对应配置见 Phase 6 接线清单
- 配套动作 A：AGENTS.md「Skills」章节扩为 skill 索引表（skill 名 + 一句话触发场景），给不支持 skill 自动触发的 harness 当路由表。**由 bootstrap.sh 从各 SKILL.md frontmatter 生成**到 `<!-- skill-index:begin/end -->` 标记块（避免 skills/ 目录、.claude 符号链接之外出现第三个手工登记点漂移）
- 配套动作 B（S6）：**存量 auto-memory 迁移审计**——把 `~/.claude/.../memory/` 现有条目逐条打标四类：①已编码进 repo → 不动；②通用工作纪律 → 迁 AGENTS.md 或对应 SKILL.md；③个人化 → 迁私有层（**不得入公开层**，遵守隐私边界）；④过时 → 弃置。
  **裁定已完成（2026-06-10，19 条全按建议，Phase 5 照此执行、无需再询问）**：
  - ①已编码 5 条不动：远期前瞻（value-invest SKILL.md:563）/ 一阶原因归因（:901）/ 弱周期成长 P/S（:87）/ 数据校验纪律（CLAUDE.md L1-L3）/ 宏观量化月度工作流（macro-quant-rebalance SKILL.md）
  - ②通用纪律 6 条迁仓库：财报分析一次到位 → value-invest SKILL.md；单位量级改基数后 grep 重算派生值 → data-discipline「反推校验」；大改动双门 review 工作流 → AGENTS.md「工程改动工作流」小节；时间序列红线看日序+akshare 陈旧接口兜底 → data-discipline / `_shared/eval` known-fail 注释；取数源可达性全局约束 → marketdata README（etf_hist.py:7 已有局部）；博主蒸馏 pipeline 踩坑 → skills/macro-ellie/references/
  - ③个人化 8 条迁私有层：指令型 4 条（展示格式 / 分层框架 / wiki 个人财务禁令 / 个股分析范围）→ `CLAUDE.local.md`；**数字型 4 条落本仓外私有层**——`CLAUDE.local.md` 仅留一行"涉个人财务分析时再读"指针（第三方模型 API 默认接触不到数字）
  - ④弃置 0 条。迁移完成后对应 memory 文件按 CLAUDE.md memory 规则瘦身/删除，防双源漂移
- 验证：协议落 AGENTS.md；索引表生成可重入（重跑 bootstrap.sh 无 diff）；memory 打标清单输出

### Phase 6 — 薄适配层 + 一键接线

- 动作：
  1. `scripts/bootstrap.sh`（幂等）：`git config core.hooksPath skills/_shared/hooks`；重建 `.claude/skills/` 符号链接（遍历 `skills/` 排除 `_shared`）；生成/刷新 AGENTS.md skill 索引块；检查 python 依赖（akshare/pandas/pypdf/trafilatura）并提示缺失项——把 README/hooks README 里的"本地接线"从文字变成一条命令
  2. **Hermes Agent 接线（首选 harness，2026-06-10 用户裁定）**：无仓库内目录需求（home 级配置 + 读 AGENTS.md），接线步骤进文档——provider 指 Nous Portal / OpenRouter / 自定义端点；**harness 与模型解耦：写入类任务建议配 DeepSeek 等中文强模型，Hermes 4 跑校验/机械位**；权限/审批按协议 7 基线（含 `--no-verify` 禁令）；其私有记忆文件（MEMORY.md/SOUL.md 系）若落仓库内则加 `.gitignore`（协议 6）；skill 发现的具体目录约定以冒烟实测为准（agentskills.io 标准）
  3. （可选，接入 OpenCode 时再做）`.opencode/opencode.json` 入库（key 用环境变量引用，不含明文）：DeepSeek provider（`@ai-sdk/openai-compatible`，参照官方集成文档）+ permission 基线：`git push` / 破坏性 bash / `--no-verify` 设 ask（S7：协议 7 的接线落地）；`.gitignore` 不加 `.opencode/`（与 `.claude/` 不同：无机器本地 settings，皆可共享）。OpenCode 原生 verifier subagent（`.opencode/agent/verifier.md`）推迟——verify-cli 是唯一校验路径，实测不够用再加（review 裁定：双路径属过度设计）
  4. `docs/harness-setup.md`：每 harness 克隆后清单（bootstrap.sh → 各家鉴权/模型配置 → `llm.json` → **权限基线核对（协议 7）** → smoke 命令），沿用 hooks README「本地接线」文体
- 验证：删除 `.claude/skills/` 后跑 bootstrap.sh 完整重建且索引块无 diff；Hermes Agent 会话能发现并调用 repo skills、能复述 AGENTS.md 任一规则；（接入 OpenCode 时）OpenCode 启动列出 15 个 skill、`git push` 触发 ask
- 风险：低

### Phase 7 — 跨 harness 冒烟验收（人工 checklist + 半自动）

- `docs/harness-setup.md` 附验收四项，每接入一个新 harness 跑一遍：
  1. **只读 query**：问一个 wiki 内可答的问题 → 正确引用页面、零写入
  2. **微型 ingest**：给一段含 2-3 个数字的样例材料走 L1→L2（清单可见 + fetch 核对）→ 写测试页 → L3（verify-cli）→ 清理。检查点：阶段 A 清单是否可见输出、是否按映射表选对工具
  3. **pre-commit 地板**：staged 敏感行 + 非白名单区间术语 → 前者被拦、后者出警告；**确认 agent 面对拦截的反应是"转给用户"而非尝试 `--no-verify`**
  4. **verify 对照**：对最近一个 Claude L3 已通过的页面跑 verify-cli（异构后端）→ 报告结论方向与 Claude 版一致（允许覆盖面差异，不允许方向冲突无解释）
- **通过标准（B1 修订）**：四项全过 → 才可跑**任何写 `wiki/` 的任务**（含 ingest / query 回写 / scheduled-ingest 的 wiki 回写段 / wiki-review）；只过 1/3/4 → 限只读 + 不写 wiki 的机械任务（协议 5 定义）。**不存在"机械任务"名义的写入豁免**
- 工作量预期：每 harness 1-2h 起，弱模型大概率需多轮调试（冒烟 #2 全链最长）

## 4. 依赖与执行序

```
Phase 0 (入口) ──→ Phase 1 (映射表) ──┐
Phase 2 (webtools) ──→ Phase 3 (verify-cli) ──→ Phase 5 (混用协议+memory 迁移)
Phase 4 (lint 双栈) ──┘（0/2/4 相互独立，可穿插）
Phase 6 (适配层+bootstrap) ── 依赖 0–4
Phase 7 (冒烟验收) ── 最后，逐 harness；#1–#3 通过 = feature 分支合入 main 的前置条件
```

执行序：**0 → 1 → 2 → 3 → 4 → 5 → 6 → 7**（1 的动作 B 第 4/5 条与 3 同窗口落地，合入前整体生效）。粗工作量：P0/P4/P6 各 ≤1h；P1 约 1h；P5 约 1.5h（含 memory 打标）；P2 约 2-3h；P3 约 3-4h（主体）；P7 每 harness 1-2h 起。

## 5. 风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| symlink 入口某 harness 不认 | Phase 0 单独 commit；回滚 = 互换真身与链接 |
| 弱模型不守 L2（清单跳过、摘要替代 fetch） | 地板三件套：pre-commit lint + verify-cli 必跑 + Phase 7 冒烟未过不放权写入（含 B1 堵漏：无机械任务写入豁免）；映射表前置降低翻译失败率 |
| agent 自行 `--no-verify` 解除闸门 | 协议 7 红线 + Phase 4 提示语去教学化 + Phase 6 权限 ask + 冒烟 #3 实测反应（B2） |
| worktree 并行丢失隐私指令 | 协议 3：worktree 内禁写持仓/金额类内容（S5） |
| 搜索 API 不可达 / 配额（本机代理环境特殊） | Phase 2 smoke 实测；不可达 → 换 Serper/SearXNG（到时实现）；全不可用时该 harness 降级只读+机械任务 |
| verify-cli 报告质量低于 Claude subagent | `--sections` 定位防预算失焦（S3）+ 报告必须附 URL + 主 agent Step 3.5 回访仲裁不变 + Phase 7 第 4 项对照把关 |
| prompt 模板被两处消费产生漂移 | verify-cli 运行时读模板原文渲染，仓库内始终单份；工具名差异用注入前言解决（穷举映射，S3），不改模板 |
| 双 agent 写作风格/口径漂移 | verify 标准同一 + log.md 执行归属可溯源 + index.md 区间术语契约已有 hook 看护 |
| Hermes 4 中文写作质量（Llama 3.1 基座）或弱于 DeepSeek，而 wiki 为中文 | harness 与模型解耦：Hermes Agent 内写入类任务配 DeepSeek 等中文强模型；Hermes 4 先上校验/机械位；冒烟 #2 实测把关 |
| 第二 harness 复跳 Claude 已踩过的坑 | Phase 5 配套动作 B：存量 memory 打标迁移（S6） |
| 一次动太多 | 严格分 Phase commit，feature 分支整体合入，双门 review，可逐 Phase 回滚 |

## 6. 开放决策（实施前与用户确认）

| 决策 | 默认建议 | 备选 |
|---|---|---|
| 第二 harness 首选 | **已裁定（2026-06-10）：Hermes Agent**——harness 与模型解耦，其内写入类配 DeepSeek 模型、Hermes 4 跑校验/机械 | OpenCode + DeepSeek 降为备选（原生兼容面最大，后续可加） |
| search 后端 | Tavily 单后端起步 | 不可达再换 Serper / 自托管 SearXNG |
| verify 报告落盘 | 默认 stdout 不入库；估值页沿用既有 `raw/articles/.../verify_report.md` 归档 | 全部落 `/tmp` |
| log.md 执行归属是否回填存量 | 不回填，新条目起 | — |
| memory 迁移打标结果 | **已裁定（2026-06-10）**：19 条全按建议执行；数字型 4 条走本仓外私有层。明细见 Phase 5 配套动作 B，实施时照单执行 | — |

---

## 附录 A：v2 修订记录（独立 subagent review，门 1）

| # | Review finding | v2 处置 |
|---|---|---|
| B1 | "机械任务"豁免可让未过冒烟的模型经 scheduled-ingest/wiki-review 写 wiki | 协议 5 收紧机械型定义为"不写 wiki/"；Phase 7 通过标准明确无写入豁免 |
| B2 | `--no-verify` 旁路被 pre-commit stderr 主动教学，"唯一强制点"对弱模型不成立 | 协议 7 红线（agent 禁用，仅限用户）；Phase 4 提示语去教学化；Phase 6 权限 ask；冒烟 #3 实测 |
| S1 | 耦合审计数字不可复现（138/8 实测应为 ~130/19）、漏 `Read PDF pages=X` 变体 | §1 改用 review 实测数字 + 注明统计命令；变体列入映射解析规则 |
| S2 | Phase 1 引用 verify-cli 早于其存在，合入时点未定义 | §3 头部明确"P0–P6 完成 + 冒烟 #1–#3 通过后整体合入 main" |
| S3 | verify-cli 三缺口：无章节定位 / 漏 WebFetch≤3 预算 / 工具映射不穷举（Grep 等） | `--sections` 必填；预算补全；映射前言穷举 + Grep 声明读全文扫描 |
| S4 | 改写处遗漏 value-invest-verify SKILL.md（弱模型主入口）；缺原生优先声明 | 改写扩为 5 处（含 Step 2 / 3.6）；解析规则加"原生优先" |
| S5 | worktree 不含 gitignored 的 local 指令，隐私纪律在并行模式下残缺 | 协议 3 补 worktree 隐私盲区条款 |
| S6 | 耦合点 #7（存量 auto-memory）无 Phase 解决，与核心判断自相矛盾 | Phase 5 配套动作 B：四类打标迁移，用户裁定 |
| S7 | 协议 7"各 harness 权限各配"无人落实 | Phase 6 接线清单含权限基线 + 验证步骤 |
| Nit | AGENTS.local.md 改名多余 / OpenCode verifier 双路径过度设计 / search 多后端投机 / 依赖图与文本张力 / lint argv 实现注 / arbiter read_file 代码级盲化 / 协议 2 理由混淆 / 索引表第三登记点 / P7 工时乐观 / 行号偏差 | 全部采纳：Phase 0 简化保留 CLAUDE.local.md 原名；verifier.md 推迟；Tavily 单后端；依赖图改 Phase 5 依赖 3；`|| true` 与 staged 备注；arbiter 排除 `wiki/**`；协议 2 改"约定起步+hook 候选"；索引表 bootstrap 生成；P7 改 1-2h 起；行号修正 |
