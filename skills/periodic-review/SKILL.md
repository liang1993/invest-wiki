---
name: periodic-review
description: 定期投资复盘工具。检查关注个股价格与估值区间变化、宏观数据与央行/美联储政策更新、人民币汇率、全球大事件，提示需要更新的 wiki 页面，输出至 wiki/journal/。
---

# 定期投资复盘 Skill

不绑定频率，按需执行。聚焦**会改变投资决策的信号**：个股估值区间变化、重大事件、宏观政策转向、汇率异动。过滤市场噪音（指数涨跌、情绪指标、资金流向）。

## 文件结构

```
skills/periodic-review/
├── SKILL.md                              # 本文件：执行流程与方法论
├── templates/review-report.md            # 复盘报告模板
└── scripts/fetch_data.py                 # 数据获取脚本（个股行情+汇率）
```

### 关注列表

关注个股列表由 `wiki/stocks/focus/` 目录定义（全局约束，见 CLAUDE.md）。脚本自动从该目录读取符号链接，并从文件标题行解析股票代码。双重上市（如 `603259.SH / 2359.HK`）默认取第一个代码（A 股）报价。

### 数据获取脚本

```bash
python3 skills/periodic-review/scripts/fetch_data.py --all        # 全部（默认）
python3 skills/periodic-review/scripts/fetch_data.py --stocks     # 关注个股当前价
python3 skills/periodic-review/scripts/fetch_data.py --forex      # 人民币汇率
```

## When to Use

- 用户请求复盘 / review
- 用户问"最近有什么变化"
- 用户要求检查持仓状态

## 执行流程

**步骤 1 的各子任务之间无依赖，应分别用独立的工具调用并行执行。**

---

### Step 1: 并行数据采集

同时启动以下 4 组采集：

#### 1A. 关注个股行情 + 估值锚点（脚本 + wiki）

**两件事并行：**

1. **运行脚本获取行情**：`python3 skills/periodic-review/scripts/fetch_data.py --stocks`
2. **读取 wiki/stocks/focus/*.md**（即关注列表中的个股），提取每只股票的：
   - 估值锚点（价格区间表格中的买入价、合理价值、减仓价、清仓价）
   - 个股"下一步关注"章节中的近期催化剂/风险事件
   - 若页面无价格区间表（未做过 value-invest 分析），锚点记为 "—"

**估值区间判定规则**：

| 当前价位置 | 区间 | 含义 |
|-----------|------|------|
| < 买入价 | 买入区间 | 低于安全边际，积极买入 |
| 买入价 ~ 合理价值 | 关注区间 | 低估但未到安全边际 |
| 合理价值 ~ 减仓价 | 持有区间 | 合理估值，持有 |
| 减仓价 ~ 清仓价 | 减仓区间 | 高估，分批减仓 |
| > 清仓价 | 清仓区间 | 显著高估，清仓 |

**重点关注**：相比上次复盘，是否有个股跨越了区间边界。

#### 1B. 人民币汇率

运行脚本：`python3 skills/periodic-review/scripts/fetch_data.py --forex`

输出：USD/CNY 最新汇率。

若脚本获取失败，改用 WebSearch 搜索"人民币汇率 USD CNY"。

#### 1C. 宏观数据与政策（WebSearch + akshare）

**1C-1. 检查近期是否有宏观数据发布**

参照中国宏观数据发布节奏表，判断自上次复盘以来是否有新数据：

| 数据 | 通常发布时间 | akshare 接口 |
|------|-------------|-------------|
| PMI | 每月最后一天 | `macro_china_pmi()` |
| CPI/PPI | 每月 9-12 日 | `macro_china_cpi()` / `macro_china_ppi()` |
| M2/信贷 | 每月 10-15 日 | `macro_china_money_supply()` / `macro_china_new_financial_credit()` |
| GDP | 季后 15-17 日（1/4/7/10月） | `macro_china_gdp()` |
| 进出口 | 每月 7-10 日 | `macro_china_hgjck()` |
| 社零 | 每月 15-16 日 | `macro_china_consumer_goods_retail()` |
| 工业增加值 | 每月 15-16 日 | `macro_china_gyzjz()` |
| LPR | 每月 20 日 | `macro_china_lpr()` |

若有新数据发布，用 akshare 拉取最新值，与上期对比。

**1C-2. 央行重大操作**

WebSearch 搜索：`央行 降息 降准 MLF LPR`（限最近一周或自上次复盘以来）

关注：降准/降息、LPR 调整、MLF/PSL 等非常规操作。常规逆回购不需要关注。

**1C-3. 国内重大政策**

WebSearch 搜索：`国务院 证监会 财政部 重大政策`（限最近一周）

关注：产业政策、资本市场改革、财政刺激、房地产政策等可能影响持仓的政策。

#### 1D. 美联储与全球大事件（WebSearch）

**1D-1. 美联储动态**

WebSearch 搜索：`Federal Reserve FOMC interest rate decision`（限最近一周）

关注：
- FOMC 利率决议结果
- 关键官员讲话的鹰/鸽信号转变
- 美国重要数据（CPI、非农、PCE）对降息预期的影响

**1D-2. 全球大事件**

WebSearch 搜索：`重大国际新闻 市场影响`（限最近一周）

关注：
- 地缘冲突（中东、俄乌、台海、中美关系）
- 贸易政策（关税、制裁、供应链）
- 大宗商品剧烈波动（原油、铜、黄金）
- 重大科技/AI 事件（影响持仓科技股）

---

### Step 2: 读取 wiki 基准

从 `wiki/macro/宏观仪表盘.md` 提取上次更新的核心指标值，用于对比是否有变化。

若该文件不存在，跳过此步，Wiki 变更检测中的宏观对比标注"无基准数据"。

> 个股估值锚点已在 Step 1A 中一并读取，不再重复。

---

### Step 3: Wiki 变更检测

扫描采集到的信息，与 wiki 现有页面交叉比对，检测以下变更：

1. **个股估值区间跨越**
   - 股价从一个区间跳到另一个区间（如从"持有"进入"买入"）
   - → 提示：`stocks/xxx.md` 的"当前股价"行和区间判定需要更新

2. **个股重大事件**
   - 发布了新季报/年报
   - 重大公告（并购、分红、回购、管理层变动等）
   - → 提示：`stocks/xxx.md` 需要 ingest 新数据，估值模型可能需要修订

3. **宏观数据更新**
   - 有新的 PMI/CPI/PPI/M2/GDP 等数据发布
   - → 提示：`macro/宏观仪表盘.md` 对应指标需要更新
   - 若新数据改变了经济周期判断 → 提示需修订

4. **政策变化**
   - 央行降准/降息、LPR 调整 → 提示：`macro/资本市场政策.md` 需追加
   - 行业政策变化 → 提示：相关 `sectors/xxx.md` 需更新

5. **汇率重大变动**
   - 突破关键整数关口（如 7.0、7.1、7.2、6.8）
   - → 提示：`macro/宏观仪表盘.md` 汇率部分需要更新

6. **美联储政策转向**
   - 利率决议结果、点阵图变化、鹰鸽转向
   - → 提示：`macro/宏观仪表盘.md` 美国部分需要更新

7. **行业格局变化**
   - 关注个股所在行业出现重大新闻（竞争对手财报、行业事件）
   - → 提示：相关 `sectors/xxx.md` 需要更新

**重要**：本模块只做提示，不自动修改任何 wiki 页面。所有更新由用户确认后再执行。

---

### Step 4: 合成报告

按 `templates/review-report.md` 模板合成复盘报告，写入 `wiki/journal/YYYY-MM-DD.md`。

---

### Step 5: 更新索引与日志

1. 检查 `wiki/index.md` 的"投资日志"章节，若无本次复盘条目则添加
2. 在 `wiki/log.md` 头部追加操作记录

---

## 输出要求

- **简洁**：每个模块用数据+一句话判断，不写废话
- **对比**：个股价格必须对照估值区间，给出明确的区间判定
- **信号优先**：只输出会影响投资决策的信息，过滤噪音
- **变化优先**：重点标出与上次复盘相比发生变化的部分

## 与其他 Skill 的关系

| Skill | 关系 |
|-------|------|
| yahoo-finance | 个股行情和汇率数据源 |
| macro-analysis | 宏观指标数据源（有新数据发布时调用） |
| value-invest | 估值模型的生产者，本 skill 消费其输出的价格区间 |

## Error Handling

- yfinance 或 akshare 接口报错：标注"数据获取失败"，跳过该模块继续
- WebSearch 无结果：去掉日期限定，用更宽泛的关键词重试一次
- wiki 中个股缺少估值区间：价格区间列显示"—"
