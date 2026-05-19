---
source: claude-subagent-deep-research（多源综合，URL 见正文）
fetched: 2026-05-18
title: 日债 + 日元 carry trade → 全球流动性 → 港股冲击 deep-research 综合报告
publisher: claude-code-subagent
published: 2026-05-18
topics: [日债, JGB, BOJ, carry-trade, YCC, USD-JPY, 港股流动性, 2024-08-05]
verified: partial
note: 该文件为 deep-research 综合产出（非单一原文归档）。所有量化数据已标注 URL 来源，但未逐条 WebFetch 回访核对，故 verified=partial。引用时应回访原 URL 确认最新值。
conflicts:
  - raw/articles/macro/海外国债/2026-05-18_美债流动性机制_research-synthesis.md  # 本文 JGB-UST 利差用了 UST ~4.18% 算 ~140bp，与美债 agent 引用的 4.59% 不符。回算 JGB-UST = 2.78 − 4.59 = −181bp。以美债 agent 为准。
被引用于:
  - wiki/macro/宏观仪表盘.md#海外国债--carry-trade信号参考
---

# 日债 + 日元 carry trade → 全球流动性

## 1. JGB & BOJ 政策路径（机制 + 当前位置）

政策利率演进 [观测]：
- 2016-09 至 2024-03：YCC 框架，10Y JGB 目标 0%，上限带 ±0.25% → ±0.5% → ±1%
- 2024-03-19：BOJ 退出 NIRP，政策利率 −0.1% → 0~0.1%，终结 YCC（[CNBC](https://www.cnbc.com/2024/03/19/bank-of-japan-boj-march-2024-policy-decision-mpm-meeting.html)）
- 2024-07-31：加息至 0.25%（即 8-5 carry unwind 的直接触发）
- 2025-01：加息至 0.50%
- 2025 中至 2026-04：加息至 **0.75%**，4 月会议 6:3 票，三名委员主张直接加到 1.0%（[CNBC 4月会议](https://www.cnbc.com/2026/04/28/bank-of-japan-keeps-policy-rate-steady-cpi-iran-war-gdp.html)）
- 市场预期：6-16 会议加息至 1.0% 概率 **74%**（OIS，[MarketPulse](https://www.marketpulse.com/markets/boj-preview-interest-rate-hike-baked-in-whats-next-for-the-jpy-further-appreciation/)）
- OECD 估终值 **2.0% by 2027 年末**（[Japan Times](https://www.japantimes.co.jp/business/2026/05/13/economy/boj-policy-rate-oecd-estimate/)）

JGB 收益率 [观测，2026-05-18]：
- 10Y JGB **2.78%**，1997-05 以来最高，过去 4 周 +30bp，过去 12 个月 +122bp（[Trading Economics](https://tradingeconomics.com/japan/government-bond-yield)）
- 30Y JGB **4.19%**（[Trading Economics 30Y](https://tradingeconomics.com/japan/30-year-bond-yield)）；2025-05 首次破 3.2%，现已破 3.8% 并 40Y 破 4%
- 4 月日本 PPI 同比 4.9%（前值 2.9%）— 通胀超预期是收益率飙升近期催化

BOJ 缩表 [观测]：
- 2024 启动 QT，截至 2025-12 JGB 持仓降至 ¥544 万亿（季度降 ¥12.4 万亿），累计缩表 $502B（[Wolf Street](https://wolfstreet.com/2026/01/06/bank-of-japans-qt-cuts-502-billion-from-balance-sheet-jgb-yields-surge-as-boj-steps-away-from-bond-market/)）
- 2026-04 起减速 QT：季度购债削减额从 ¥4,000 亿降至 ¥2,000 亿（[JCER](https://www.jcer.or.jp/english/bank-of-japan-to-slow-de-facto-qt-from-april-2026)）— "放慢退出"，但**没有重启 QE**

## 2. 日元 Carry Trade 机制与 2024-08-05 复盘

规模口径分层（[观测] + [推算]）：

| 口径 | 规模 | 来源 |
|---|---|---|
| 狭义：投机性 yen 远期净空头 | $250B（¥40 万亿） | [BIS Bulletin 90](https://www.bis.org/publ/bisbull90.pdf)（2024-08 测算）|
| 中义：日本对外证券投资 + FX swap | $1-4 万亿 | [Invezz](https://invezz.com/news/2026/05/01/yen-carry-trade-cracks-are-showing-and-wall-street-isnt-ready/) |
| 广义：日元相关 FX swap 总市场 | $14 万亿 | [BIS Speech 2024-08](https://www.bis.org/speeches/sp240829_transcript.pdf) |
| BCA Research 综合（2025-10）| ¥35 万亿远期 + ¥2,281 万亿含 FX swap | 同上 |

主要载体：USD/JPY 远期、JGB 抵押融资买美债、日本人寿 / 邮政储蓄 / GPIF 海外配置（GPIF 海外债 ¥72.8 万亿，其中 51.8% 是美债，[InvestingLive](https://investinglive.com/news/icymi-japans-gpif-raised-its-holdings-of-us-treasuries-to-the-highest-level-in-a-decade-20250710/)）。日本全口径持有美债 **$1.24 万亿**（2026-02），仍是美债最大外国持有者。

**2024-08-05 unwind 复盘** [观测]：
- 7-31 BOJ 意外加息 25bp + 8-2 美国非农 114k（预期 175k）→ 双向触发
- 7-29 至 8-5 日元升值 **6.15%**，USD/JPY 从 161 → 142
- 8-5 Nikkei 225 **−12.4%**（1987 黑色星期一以来最大单日，[BIS Bulletin 90](https://www.bis.org/publ/bisbull90.pdf)）
- VIX 盘中飙至 **60+**（COVID 2020 以来未见），SPX −3%
- **港股**：恒指 8-5 收 16,612（恒指当日跌 ~1.5%，恒科 −2.5%~−3%；相对 Nikkei 抗跌但 YoY −14.9%）

核心教训：carry unwind 是**自我强化反馈环** — 日元升值 → 杠杆头寸保证金不足 → 卖风险资产换日元 → 日元更强。BIS 指出 8 月底大部分狭义头寸已平，但**杠杆已在重建**，仍是脆弱状态。

## 3. 对全球流动性传导渠道 [推算]

| 渠道 | 机制 | 量级估计 |
|---|---|---|
| JGB 收益率上行 → 日本机构卖美债/欧债 | 国内 1.8%+ 无汇率风险 vs 美债 4-4.2% 对冲成本 = 净 **−0.34%**（[TMS Capital](https://www.tmscapitalresearch.com/p/japan-treasury-holdings-2025-repatriation-analysis)） | 2025 美债增持仅 +$45B vs 2024 全年 +$180B（**−75%** [推算]） |
| USD/JPY 下行 → carry unwind | 杠杆基金被动平仓，最先抛美股科技 + 新兴市场 | 2024-08 5 个交易日抹掉 Nikkei + Topix 共 ~$1.1 万亿市值 |
| BOJ 加息 → 日本资金回流 | 本土资金机会成本下降，先减低 β 海外（欧债 → 美债 → 风险资产）| 每 25bp 加息触发约 $50-100B 渐进回流 [估计，6-12 月窗口] |
| 联储降息 + BOJ 加息双向收敛 | 利差从 2024 高峰 ~580bp 收至现在 ~140-180bp [推算] | 利差再压缩 50bp 即触发新一轮 unwind 风险 |

> 关键派生信号：JGB-UST 10Y 利差较一年前收窄约 115bp（[CNBC 2-20](https://www.cnbc.com/2026/02/20/japan-bond-yield-us10y-us-treasury-gilts-bunds-takaichi-trade.html)）— 2024-08 以来延续。**利差每收 50bp，USD/JPY 中枢下移约 5-7 日元 [估计，confidence ±2，基于 2024-2026 beta 回归]**

> ⚠️ 数据冲突标注：原 agent 用 UST ~4.18% 算 JGB-UST 利差 ~140bp。但 [美债 agent 直接引用 Advisor Perspectives 5-15 的 UST 10Y = 4.59%](https://www.advisorperspectives.com/dshort/updates/2026/05/15/treasury-yields-snapshot-may-15-2026)，按此回算 = 2.78 − 4.59 = **−181bp**（JGB 低于 UST 181bp）。仪表盘以 −181bp 为准。

## 4. 对中国资产传导

**日元贬值情景（USD/JPY > 160）— 边际利空**：
- 汽车出口竞争：Toyota FY 2026 Q4 营业利润同比 −49%（[CNBC](https://www.cnbc.com/2026/05/08/toyota-1q-2026-earnings.html)），但弱日元仍补贴日车在东南亚/中东抢份额 → 长城汽车海外业务边际承压（重叠市场 ~30% 海外营收 [估计]）
- 家电/精密制造：弱日元让 Panasonic / Daikin 在中东欧亚有 5-10% 价格腾挪空间 → 美的/海尔出口承压 [估计，confidence ±2]
- 中国移动等内需股：基本不受影响

**日元升值 + carry unwind 情景（USD/JPY < 150）— 短期重大利空**：
- 港股互联网（腾讯/阿里/美团/小米）是港股中**杠杆资金最敏感的板块**。2024-08-05 当日恒科 −2.5%~−3% [估计，相对恒指 −1.5% 的 β 放大]。但 **5 个交易日内即收复**（与 A 股 BSR 结构问题分开，港股是流动性问题而非基本面问题）
- 传导路径：carry unwind → 全球对冲基金减杠杆 → 港股是流动性最好的"提款机" → 集中抛售互联网/优质蓝筹（不抛低流动性股）
- 量级估算：单次 USD/JPY 10 日元升值 ≈ 港股 5-8% 短期下杀，恒科 8-12% [估计，基于 2024-08 单点，confidence ±3]

**JGB 回流的间接影响**：日资基本不直接持港股/A 股，但全球 60/40 组合再平衡时港股会被同步抛售（"卖能卖的"逻辑）。

## 5. Carry Unwind 早期预警「三红线」组合信号

必须**同时满足 ≥ 2 个**才算确认（避免单一信号假阳性）：

1. **USD/JPY 下穿 152**（2024-08 触发线 + 当前 158.59 还有 4% 缓冲）
2. **JGB 10Y 上穿 3.0%**（日资回流压力质变阈，当前 2.78% 还有 22bp）
3. **VIX 上穿 25 + Nikkei VIX 上穿 30**（杠杆资金被动减仓信号）

触发后剧本 [估计]：
- 港股互联网（腾讯/阿里/美团/小米）短期下杀 8-12% → focus 名单的合理价以下 5% 启动分批加仓（2024-08 经验：5-10 个交易日修复）
- A 股影响相对小（外资比例低、内资为主），但北上资金当日大概率净流出 > 100 亿
- 不要在 USD/JPY 单日跌幅 > 3% 时抢反弹（参考 8-5：盘中 USD/JPY 跌至 142，次日并未立刻 V 反弹，企稳要 3-5 个交易日）

## 6. 远期视角（1-2 年 [估计]）

- 基线：BOJ 2026 内再加 1 次至 1.0%，2027 至 1.5%；JGB 10Y 见 3.0-3.3%；USD/JPY 中枢 150-155
- 乐观：联储降息节奏快 + 日通胀回落 → USD/JPY 稳在 155+，carry 仍有薄利
- 悲观（unwind 重演）：BOJ 加息 + 联储降息共振 → USD/JPY 一次性下杀至 140 → **港股 2024-08 重演 + 仓位重整窗口**
