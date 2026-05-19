---
source: claude-subagent-deep-research（多源综合，URL 见正文）
fetched: 2026-05-18
title: 美债 → 全球流动性 → 中国资产传导 deep-research 综合报告
publisher: claude-code-subagent
published: 2026-05-18
topics: [美债, 全球流动性, term-premium, 中美利差, 净流动性, ON-RRP, TGA, 银行准备金, DXY]
verified: partial
note: 该文件为 deep-research 综合产出（非单一原文归档）。所有量化数据已标注 URL 来源，但未逐条 WebFetch 回访核对，故 verified=partial。引用时应回访原 URL 确认最新值。
conflicts:
  - raw/articles/macro/海外国债/2026-05-18_日债carry-trade_research-synthesis.md  # 日债 agent 用了 UST ~4.18% 算 JGB-UST 利差，与本文 UST 4.59% (Advisor Perspectives 5-15) 不符。本文为准。
被引用于:
  - wiki/macro/宏观仪表盘.md#海外国债--carry-trade信号参考
---

# 美债 → 全球流动性 → 中国资产传导研究

## 1. 传导机制（5 条主渠道）

### 1.1 DXY ↔ 美 2Y 利差 → 新兴市场资本流动

美 2Y 反映 12-18 个月联储路径预期。美 2Y 与 G10 短端利差扩大 → DXY 走强 → 美元资产吸引力上升 → EM 资本外流 + 本币贬压。2026 年特殊点：沃什接任后市场定价"higher for longer"，US 2Y 4.11% 显著高于欧央行/日银路径，DXY 反弹至 99.35。对人民币：USD/CNY 6.81，处近三年偏强区间。

### 1.2 美 10Y term premium → 全球风险资产折现率

折现率 = 实际无风险利率 + 通胀预期 + **term premium**。term premium 由负转正（NY Fed ACM 模型 2026-05 升至 +0.70%，2023 来首次持续为正）→ 全球久期资产（科技股、长债、REITs）系统性遭遇估值压制。港股互联网（腾讯/阿里/美团/小米）SOTP DCF 估值远期占比高，对 term premium 敏感度高于成熟价值股。

经验法则 [估计，confidence 中等，基于 DCF 久期 12-15 年]：US 10Y term premium 每升 50bp，恒科 PE 中枢理论压缩 1-1.5x。

### 1.3 ON RRP + TGA + 银行准备金 → 美元基础货币池子

净流动性公式（StreetSmart / Joseph Wang 框架）：
- 净流动性 ≈ Fed 总资产 − TGA − ON RRP

当前快照（2026-05-13）：
- Fed 总资产 6.7 万亿 [观测]
- TGA 8,074 亿 [观测]
- ON RRP < 1,000 亿 [观测]（vs 2022 峰值 2.55 万亿）
- 银行准备金 3.10 万亿 [观测]

判读：ON RRP 蓄水池基本耗尽 → 未来 TGA 上行或 QT 继续将直接抽走银行准备金，进入"准备金稀缺"区间（学界共识阈值约 3 万亿）。2026 下半年最大尾部风险——若准备金跌破 2.8 万亿，回购利率将抽风，类似 2019-09 重演，被迫停止 QT。

### 1.4 中美 10Y 利差 → 北向资金 / 港股汇率β

当前：US 10Y 4.59% − CN 10Y 1.75% = **−284bp**（中国低于美国 284bp，套息资金趋向卖人民币买美元）→ 北向资金净流入承压、人民币贬压、港股汇率β（南向资金）受抑。

用户已设阈值"收敛至 −150bp"验证：
- 要么 US 10Y 跌至 ~3.25%（需联储重启降息 + 财政纪律改善）
- 要么 CN 10Y 升至 ~3.10%（需 PPI 转正持续 + 中国摆脱 BSR）
- 当前距离 134bp，无任何一边在动，**6-12 月内触发概率 < 15% [估计]**
- 建议加一档 "−200bp" 作为预警位（更现实的 12 月窗口）

### 1.5 财政部期限策略 → 短端 vs 长端供需

Bessent 路线（2026-05 TBAC 会议）：
- 维持 "bill-heavy" 发行结构，未来数季度不增加 coupon 拍卖规模
- 启动 buyback 操作——每季度回购长端 10-30Y 非主流券种最多 80 亿美元（"软 yield curve control"）

判读：
- 短端供给压力 → bill 收益率支撑 → MMF 资金仍倾向 bill 而非 ON RRP（ON RRP 持续低位根本原因）
- 长端供给被人为压制 + buyback → 理论上压低 long end term premium
- 但 4 月 PPI 6% 同比创 2022 来新高 → 通胀面证伪了这一压制，30Y 反而冲破 5.12%

## 2. 当前状态快照（2026-05-18）

| 指标 | 当前值 | 来源 |
|------|--------|------|
| US 10Y | 4.59%（5-15） | [Advisor Perspectives](https://www.advisorperspectives.com/dshort/updates/2026/05/15/treasury-yields-snapshot-may-15-2026) |
| US 2Y | 4.11% | [Trading Economics](https://tradingeconomics.com/united-states/2-year-note-yield) |
| US 30Y | 5.12% | [CNBC](https://www.cnbc.com/2026/05/15/treasury-yields-surge-as-inflation-data-points-to-tricky-rates-path.html) |
| US 10Y term premium (ACM) | +0.70%（5-01） | [FRED THREEFYTP10](https://fred.stlouisfed.org/series/THREEFYTP10) |
| ON RRP | < 1,000 亿 | [FRED RRPONTSYD](https://fred.stlouisfed.org/series/RRPONTSYD) |
| TGA | 8,074 亿（5-13） | [FRED WTREGEN](https://fred.stlouisfed.org/series/WTREGEN) |
| 银行准备金 | 3.10 万亿（5-13） | [Fed H.4.1](https://www.federalreserve.gov/releases/h41/current/) |
| DXY | 99.35 | [Trading Economics DXY](https://tradingeconomics.com/united-states/currency) |
| 中美 10Y 利差 | −284bp | [推算] 4.59 − 1.75 |
| 期限利差 10Y-2Y | +48bp | [推算] 已陡峭化 |

## 3. 2026-05 美债主线叙事

1. **沃什接任 + 通胀回潮双击**：5-13 参议院 54-45 确认沃什为联储主席（modern 最窄差，[NPR](https://www.npr.org/2026/05/13/nx-s1-5816235/kevin-warsh-federal-reserve-chair-jerome-powell)）；4 月 CPI 3.8%（22 年来次高）、PPI 6.0% 同比（22-12 以来最高，关税服务业 +2.7%，[CNBC PPI](https://www.cnbc.com/2026/05/13/ppi-inflation-report-april-2026-.html)）。CME FedWatch：2026 内降息预期 < 3%，dot plot 中位数 3.40%。
2. **财政赤字 + term premium 重定价**：30Y 冲破 5.12%，term premium 转正且仍在上行 → 市场定价"美国财政可持续性折扣"。X-date 推至 2027 年中（OBBB 法案上调上限 5 万亿至 41.1 万亿）。
3. **关税通胀贯穿全年**：服装 +0.6%、机票 +20.7% 同比 → 关税成本通过批发端逐步传导到 CPI → Fed 6 月维持中性偏鹰（沃什首次主持 FOMC 6-16/17）。
4. **Treasury buyback + bill-heavy**：Bessent 维持 bill 主导发行（[TBAC 5-05 纪要](https://home.treasury.gov/news/press-releases/sb0491)）；启动季度 buyback 软调长端。

## 4. 对中国资产传导（量级估计）

| US 10Y 情境 | 港股互联网 | A 股券商（中信） | A 股银行（平银） | A 股资源（紫金/海螺） |
|-------------|----|----|----|----|
| 跌破 4.0%（−60bp） | DCF 折现率↓ + DXY↓ → 北向回流，PE 上修 +1-2x [估计] | 利差收敛 → AH 溢价收敛，港股催化 A 股 | NIM 间接受益于人民币稳 | 美元走弱 → 大宗反弹（紫金弹性大） |
| 维持 4.5-4.7% | 高估值天花板，盈利驱动仍能涨 | 流动性受限，需国内增量资金 | 不利但有限 | 平庸 |
| 突破 5.0% | 估值压制，恒科可能补跌 5-10% [估计] | 北向流出 → A 股承压 | NIM 受人民币贬压拖累 | 滞胀逻辑下反而利好（PPI+利率同涨） |

关键判断：当前 4.59%、term premium 正且上行 → **对久期资产中性偏不利**。港股科技敞口（腾讯/阿里/美团/小米）建议**等 US 10Y 跌破 4.3% 再加仓**，或等中美利差实质性收敛（向 −200bp 靠近）。

## 5. 关键发现摘要

1. 当前美 10Y 4.59% + term premium +0.70%：港股科技/中概互联估值面临折现率压制，建议等 10Y 跌破 4.3% 再加仓
2. ON RRP 蓄水池基本耗尽：未来 TGA 上行或 QT 继续将直接抽银行准备金；**准备金跌破 2.8 万亿 = 组合层面降仓信号**
3. 用户原 "−150bp" 阈值方向对但偏激进：6-12 月内触发概率 < 15%，建议加 "−200bp" 预警位
4. 沃什接任 + 通胀回潮 + 30Y 破 5%：2026 全年大概率 higher for longer，A 股高股息相对受益（已与现有 "10Y CN 跌破 1.5%" 信号方向一致）
5. 5 项跟踪指标（US 10Y / 2Y / term premium / ON RRP+TGA+准备金 / DXY / 中美利差）数据均可在 FRED + Trading Economics + Fed H.4.1 免费获取，月度复盘成本低
