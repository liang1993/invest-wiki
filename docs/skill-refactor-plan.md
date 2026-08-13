# 工程结构重构方案 — 对齐 Skill / Rule / Hook / Memory / Eval

> 状态：**Phase 0–4 已执行**（4.2 拆 a-share/macro 为可选项，主动跳过）| 创建：2026-05-29 | 经独立 subagent review 修订（v2）| 关联：[`data-discipline.md`](data-discipline.md)
>
> 本方案收敛三轮分析：① value-invest 是否上 workflow（→ Skill 形态问题）② 按角色拆 skill（→ 抽共享数据层 + 缺回归 Eval）③ 五原语体检（→ 真正欠的是 Hook + Eval）。
>
> **核心判断**：项目过去用 **Skill / Rule / Memory** 去填 **Hook / Eval** 的洞——`log.md` 36 条 LINT 教训是"指令托底反复漏网"的实证。本方案把**可机械判定**的纪律从 Rule 降到 Hook，把**接口/重构正确性**交给 Eval，让 Memory 回归"判断型决策记忆"的本分。
>
> **v2 修订（review 后）**：隐私闸门改走 git pre-commit（非 PreToolUse JSON）；hook 脚本入受版控目录；数据层合并先写代码转换单测；golden 闸门改比结构非数值；scheduled-ingest 移出数据迁移范围。

---

## 1. 五原语 × 现状 × 终态

| 原语 | 现状评级 | 关键问题 | 终态 |
|---|---|---|---|
| **Skill** | ★★★★★ 过重 | 取数/持久化职责外溢到 6/4 个 skill | 按 L0–L4 五层分工，每 skill 单一职责 |
| **Rule** | ★★★★☆ | 数据纪律有重复拷贝；机械规则混在判断规则里 | CLAUDE.md 唯一 SSOT，每条标注「Hook / Eval / 指令」执行方式 |
| **Hook** | ★☆☆☆☆ | 项目级 0 功能 hook；隐私闸门 `check-sensitive.sh` 是孤儿且输出契约不合规 | 确定性纪律 hook 化（隐私走 git pre-commit；区间术语/frontmatter 走 PostToolUse） |
| **Memory** | ★★★★☆ 超载 | 在替 Hook/Eval 干活 | 仅留判断型决策；机械教训迁出为 Hook/Eval |
| **Eval** | ★★☆☆☆ | 仅 1 个单测；接口漂移靠手工记；重构无回归网 | 数据层 smoke + 代码转换单测 + 结构回归 + 沿用 verify 报告作证据 |

---

## 2. Skill 终态职责卡

五层：**L0 取数 → L1 验证 → L2 计算/分析 → L3 编排 → L4 持久化**。

| Skill | 层 | 唯一职责 | 不做（交给谁） | 依赖 |
|---|---|---|---|---|
| `yahoo-finance` | L0 知识 | 美股/港股/外汇 yfinance 接口 | A 股取数 → marketdata | — |
| `a-share-market` | L0 知识 | A 股**市场层** akshare 接口速查 | 个股估值 → value-invest | — |
| `macro-analysis` | L0 知识 | 宏观 akshare 接口速查 | 市场情绪 → a-share-market | — |
| **`_shared/marketdata`** 🆕 | L0 库 | 个股财报/行情/PE 时序/同业取数；**唯一**代码转换 + 腾讯封装 | 任何判断/分析 | akshare/腾讯/baostock/yfinance |
| `value-invest-verify` | L1 验证 | 零上下文反推校验（判断型 eval） | 取数 / 写 wiki | marketdata |
| `value-invest` | L2 估值 | 估值方法论 Step 0→8（**保持整链**） | 取数(库)/校验(verify)/格式(wiki-review) | marketdata, verify |
| `stock-deep-dive` | L2 业务 | 产品/经营/竞争分析 | 财务估值 → value-invest | — |
| `periodic-review` | L3 编排 | focus 复盘，消费估值锚点 | **自带取数**（改用库） | marketdata, value-invest 输出 |
| `scheduled-ingest` | L3 编排 | 定时写 raw/ + wiki 静态章节 | 估值/分析 | （懂车帝 API，**不依赖 marketdata**）|
| `wiki-review` | L4 维护 | 格式对齐 + 过期归档 | 产生新内容 | value-invest 模板 |

> **不拆的红线**：`value-invest` 的 Step 0→8 是带反向健康检查回环的单一判断链，**不再下切**为子 skill。层间拆（降耦合）对，链内拆（降内聚）错。
>
> **`_shared/` 不会被误挂成 skill**：Codex 的 `.agents/skills/` 只为含 `SKILL.md` 的目录建链接；Claude 隔离层虽复制 `_shared/` 供脚本 import，但 `_shared/` 没有 `SKILL.md`，不会被当 skill 加载。
>
> 非投资 skill（`asr` / `media-fetch` / `find-skills`）不在本次范围。

---

## 3. 目录结构 before → after

```
# BEFORE
skills/value-invest/scripts/{fetch_data.py, quote_tencent.py}
skills/periodic-review/scripts/fetch_data.py   # sys.path hack 伸进 value-invest/scripts import quote_tencent
skills/stock-deep-dive/references/data-discipline.md   # 唯一真·纪律全文拷贝
.claude/scripts/check-sensitive.sh             # 孤儿：自述是 hook 但未注册，且 .claude/ 被 gitignore（不入版控）

# AFTER
skills/_shared/                       # 受版控（skills/ 不在 .gitignore）
  ├── marketdata/
  │   ├── codes.py        # 唯一代码转换（先有单测再实现，见 Phase 2.2）
  │   ├── quote.py        # 腾讯 + yfinance 行情
  │   ├── financials.py   # akshare 财报 + baostock PE/PB 时序 + 一致预期 + 同业
  │   └── README.md       # 接口契约 + 消费者如何 import（centralized 路径注入）
  ├── eval/
  │   ├── smoke_marketdata.py    # 接口漂移 smoke（含 known-fail 用例）
  │   ├── test_codes.py          # 代码转换金标准单测（先写）
  │   └── regression/structure/  # 结构不变量快照（列名/类型/分类，非数值）
  └── hooks/                     # 受版控的 hook 逻辑
      ├── pre-commit             # git pre-commit（隐私闸门，core.hooksPath 指向此目录）
      ├── lint-interval-terms.sh # 区间术语（PostToolUse，上下文感知）
      └── lint-frontmatter.sh    # frontmatter 必填（PostToolUse）

# 本地接线（不入版控，提供一行 setup 复现）
.claude/settings.local.json   # 注册 PostToolUse hook（指向 skills/_shared/hooks/*）
git config core.hooksPath skills/_shared/hooks   # 一次性，让 git pre-commit 生效
```

> **关键修正**：`.claude/` 整目录被 gitignore（`.gitignore:3,5`），故 hook **逻辑**放受版控的 `skills/_shared/hooks/`，**接线**（settings.local.json / `git config`）才放本地。逻辑跟随 repo，换机只需重跑一行 `git config`。

---

## 4. 分阶段迁移

每阶段 = 一次独立 commit，含 **动作 / 触碰文件 / 验证标准 / 风险**。

### Phase 0 — 止血 + 安全网

**0.1 隐私闸门 → git pre-commit（受版控）** 🔴
- 动作：把敏感信息检测逻辑落到 `skills/_shared/hooks/pre-commit`，**按 git hook 语义重写**——发现敏感内容时 `echo` 人类可读理由到 **stderr** 并 `exit 1`（git 只看退出码，不需要 PreToolUse 的 JSON schema）；本地一次性 `git config core.hooksPath skills/_shared/hooks`
- 为什么不沿用原 PreToolUse 设计：原 `.claude/scripts/check-sensitive.sh` 发 `{"decision":"block"}`（非 PreToolUse 合规 schema，理由写错流），且 `.claude/` 不入版控、PreToolUse matcher 只匹配工具名拦不住 `git commit -am`/`&&`/别名。**git pre-commit 才是能拦住所有 commit 路径的确定性层**
- 触碰：`skills/_shared/hooks/pre-commit`（新，受版控）；本地 `git config`
- 验证：staged 一行测试敏感信息（密钥/卡号等） → commit 被 exit 1 拦 + stderr 显示理由；正常内容 → 放行；空 staged → 放行
- 风险：低；旧 `.claude/scripts/check-sensitive.sh` 标记 superseded

**0.2 数据层 smoke Eval（Phase 2 基线）**
- 动作：`smoke_marketdata.py` 分两部分——(a) 对 value-invest 取数函数（`fetch_market_data`/`fetch_financial_summary`/`fetch_history_with_pe`/`fetch_research_consensus`/`fetch_peers`）断言「可调 + 返回非空 + 关键列存在」；(b) 对 macro-analysis / a-share-market SKILL.md 里记的**裸 akshare 调用**直接 `import akshare` 调（这两个 skill 无 .py 模块），把手工记的坏接口（`macro_china_shrzgm` SSL、`macro_china_rmb` TypeError）写成 **known-fail** 用例不阻断
- 触碰：新增 `skills/_shared/eval/smoke_marketdata.py`
- 验证：跑一次输出 ✅/❌/⚠️known-fail 清单
- 风险：低（只读接口）

### Phase 1 — Hook 层补齐

**1.1 区间术语 → PostToolUse hook（上下文感知，非平铺 grep）**
- 动作：对 `wiki/stocks/**/*.md` 写入后扫描，但必须**按上下文判定**：
  - 个股 wiki 禁 `加仓区间`/`高估区间`/`低估区间`
  - **白名单豁免** `深度买入区间`：这是 value-invest SKILL.md:905,922-924 认可的特例（跌破买入价×0.85 机械警告），泡泡玛特.md 现有 4 处合法使用——**不可误杀**
  - `持有/减仓/清仓区间` 在个股与 ETF 表均合法，按文件类型区分
- 先 **warn-only 跑一周**（只报不拦），确认零误报再升 block
- 触碰：`skills/_shared/hooks/lint-interval-terms.sh`、`settings.local.json`
- 验证：写含 `加仓区间` 的个股测试页→报警；写 `深度买入区间`→不报；存量泡泡玛特.md→零误报
- 风险：中（上下文逻辑比平铺 grep 工作量大，故 warn-only 起步）

**1.2 frontmatter 必填 → PostToolUse hook**
- 动作：对 `wiki/**/*.md` 写入后校验 `tags:` + `updated:` 存在
- 触碰：`skills/_shared/hooks/lint-frontmatter.sh`、`settings.local.json`
- 验证：写缺字段测试页→报警
- 风险：低
- 注：全局 `~/.claude/settings.json` 已有 PostToolUse `Write|Edit|MultiEdit` 遥测 hook，项目级同 matcher hook **叠加执行**（不冲突）

**1.3 标注规则执行方式**
- 动作：CLAUDE.md 数据纪律表加列「执行方式：Hook / Eval / 指令」
- 边界：判断型纪律（L2「[观测] 必 WebFetch」、L3 计算链反推）**不能** hook 化，仍由 Rule + verify Eval 守。**Hook 守确定性地板，Eval 守判断天花板**

### Phase 2 — 数据获取层收口（由 0.2 + 2.2 兜底）

**2.1 建 `skills/_shared/marketdata/`**
- 动作：合并取数逻辑；腾讯封装迁入 `quote.py`
- **路径方案（诚实版）**：`__init__.py` **不能**消除跨目录 import——三个 skill 的 `scripts/` 不同包树。改为：marketdata 放唯一规范位置 `skills/_shared/`，消费者用**一处** `sys.path.insert(repo/skills/_shared)` + `import marketdata`（或 `pip install -e`）。改进点是**集中到一个规范位置**、消灭"伸进兄弟 skill 取数"的 hack，而非号称"消除路径注入"
- 触碰：新增 `skills/_shared/marketdata/*`

**2.2 代码转换金标准单测（先写，再实现 codes.py）** 🔴
- 动作：BLOCKER 4——两份转换实测分歧 4 处：`.SH`→`.SS`（value-invest 不转）、港股前导零（`02097.HK` value-invest 留 / periodic-review `int().zfill(4)` 砍成 `2097.HK`）、B 股 `900xxx`（.SS vs .SZ）、纯数字判定入口。focus 列表里 `02097.HK`(蜜雪)/`03968.HK`(招行H)/`00700.HK` 正中此例。**先写 `test_codes.py` 钉死期望 ticker**（蜜雪/招行H/紫金H/B股/上交所），HK 砍零 + `.SH→.SS` 取 periodic-review 版（与 yfinance 兼容），再实现 `codes.py` 通过
- 触碰：`skills/_shared/eval/test_codes.py`、`skills/_shared/marketdata/codes.py`
- 验证：`test_codes.py` 全绿

**2.3 消费者改用库（仅 value-invest + periodic-review）**
- 动作：两者脚本改 import `marketdata`；删本地重复 + 删 periodic-review 的 sys.path hack；改各自 SKILL.md 数据源章节
- **修正**：scheduled-ingest 的 `fetch_auto_sales.py` 只用 urllib（懂车帝 API），**不碰** akshare/quote_tencent → **移出本阶段**；其 `tests/test_fetch_auto_sales.py` 独立加载自身脚本，Phase 2 后**不会 break**
- 触碰：value-invest + periodic-review 的 `scripts/` + SKILL.md

**2.4 结构回归验证（比结构不比数值）** ✅ 闸门
- **修正**：数据源全是 live（腾讯实时价/akshare 季更/baostock 日增/研报累积），存 golden 再 `diff 数值` 必然天天红、闸门失效。改为只比**结构不变量**：列名/字段集、返回类型、代码转换映射（纯函数可精确 diff）、`is_a_share` 分类、单位口径（亿/%）、关键字段非空计数
- 数值正确性由 2.2 纯函数单测 + 0.2 smoke 守
- 触碰：`skills/_shared/eval/regression/structure/`
- 验证：新库结构快照 vs 基线快照 diff 为空；不一致先解释再放行；不通过不删旧脚本
- 风险：中（故有 2.2/2.4 + 不删旧兜底）

### Phase 3 — Rule / Memory 去重归位

**3.1 数据纪律 SSOT 化**
- **修正**：实测仅 `stock-deep-dive/references/data-discipline.md` 是真·全文拷贝；`scheduled-ingest/SKILL.md:65-69` 已是"见 CLAUDE.md"引用，无需动。本阶段范围缩小到 stock-deep-dive 那一份 → 改为引用
- 触碰：`stock-deep-dive/references/data-discipline.md` + SKILL.md
- 验证：grep 确认无重复全文

**3.2 LINT 教训重分类**
- 动作：审计 `log.md` 36 条 LINT，每条打标 `→Hook` / `→Eval` / `判断型留Memory`；机械项（区间术语、单位量级反推）已落 Hook/Eval 的，从 Memory 降级
- 验证：产出分类清单

### Phase 4 — Skill 收尾（可选 / 低优先）

- **4.1** value-invest SKILL.md 数据源章节改为「调用 marketdata 库」，删内嵌取数细节
- **4.2**（可选）a-share-market / macro-analysis 拆「接口速查（L0）vs 分析判断（L2）」
- **4.3** CLAUDE.md「目录结构」段补 `skills/_shared/`；增「Skill 职责卡」表（§2）作为新增 skill 归属裁判

---

## 5. 依赖顺序

```
Phase 0.1 (git pre-commit) ─── 独立，立即可做
Phase 0.2 (smoke) ──────┐
Phase 1   (Hook 层) ───── 独立（1.1 工作量偏大，warn-only 起步）
                        ├─→ Phase 2 (数据层，需 0.2 基线 + 2.2 单测先行)
                        │      └─→ 2.4 结构回归闸门
Phase 3   (去重)  ─────── 独立，可并行
Phase 4   (收尾)  ─────── 依赖 Phase 2
```

执行序：**0.1 → 0.2 → 2 →（1 / 3 穿插）→ 4**。

---

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 代码转换合并有损（4 处分歧） | Phase 2.2 先写单测钉死期望，再实现 |
| golden 比数值天天红 | Phase 2.4 改比结构不变量 |
| Hook 误杀（区间术语特例） | 1.1 warn-only 起步 + 白名单豁免 `深度买入区间` |
| hook 不入版控丢失 | 逻辑放受版控 `skills/_shared/hooks/`，接线一行 `git config` 复现 |
| 数据层合并改了口径 | 不通过结构回归不删旧脚本 |
| 一次动太多 | 严格按 Phase 串行；每 Phase 独立 commit 可单独回滚 |

> 每 Phase 结束 = 一次独立 commit + `log.md` 记一行。全部完成后 §1 终态评级应全部 ≥ ★★★★。

---

## 附录 A：Phase 3.1 修正（review 过校）

`stock-deep-dive/references/data-discipline.md` 经实读**不是** CLAUDE.md 的全文拷贝（review 误判），而是 deep-dive **业务侧专属**内容（数字标签 / SKU 降级 / 小米年份错配教训），仅引用 CLAUDE.md 不复述。故 Phase 3.1 不删，只加交叉引用头澄清其专属定位。`scheduled-ingest` 亦早已是引用而非拷贝。**真·重复拷贝不存在**，3.1 范围归零。

## 附录 B：Phase 3.2 — 36 条 LINT 教训 → 原语归类

主题 tally（一条 LINT 可命中多类）：

| 主题（命中数） | 归类 | 现状 |
|---|---|---|
| 区间术语 / 档位 (20) | **→ Hook** | Phase 1.1 已机械强制（warn-only），20 条从"靠记忆"转确定性 |
| frontmatter 缺失 | **→ Hook** | Phase 1.2 |
| 隐私 / 个人数据泄漏 | **→ Hook** | Phase 0.1 pre-commit |
| 接口漂移 / 坏接口 | **→ Eval** | Phase 0.2 smoke + known-fail |
| 代码转换 (15 部分) | **→ Eval** | Phase 2.2 test_codes；单位 10× 残留仍需 L1 反推 |
| 口径混用 (22) | **判断·留 Memory** | L2/L3 + verify，不可 hook |
| 横向对标 (11) | **判断·留 Memory** | L2 WebFetch + verify |
| 年份错配 (8) | **判断·留 Memory** | L2 报告期核对 |
| 强叙事词 (14) | **→ Hook 候选（未做）** | 可加 lint-narrative：grep 腰斩/精准/暴跌 → 提示标"待核实"。下一个 hook 候选 |

**结论**：~20 条区间术语类教训已转确定性 hook，Memory 这部分可瘦身；口径/对标/年份/叙事（判断型）仍是 Memory + verify 的天花板职责，不下沉。**强叙事词是下一个 hook 候选**。
