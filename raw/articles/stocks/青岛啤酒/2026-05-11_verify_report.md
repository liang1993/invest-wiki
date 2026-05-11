---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 青岛啤酒 wiki 独立校验报告（focus list 全量回归）
publisher: Claude Opus 4.7 subagent
type: verify_report
stocks: [青岛啤酒]
verified: true
---

# 青岛啤酒 wiki 独立校验报告

## 3 项 Fail（已层次 1 仲裁通过）

### Fail 1（最严重）：净利率改善幅度被严重低估 5-6 倍

- **wiki**：line 88 "净利率微升见顶迹象：14.0% → 14.1%，同比改善幅度从 2024 年的 +1.2pp 放缓至 +0.1pp"
- **真值**[观测，akshare]：销售净利率 2024=13.98%/2025=14.53%，**实际改善 +0.55pp**；归母净利率 2024=13.52%/2025=14.13%，改善 +0.61pp
- **影响**：wiki 用 "+0.1pp" 作为"净利率见顶"+"模型 23x → 19x 下调"的核心论据，**叙事链断裂**。改善仍在 +0.5pp 级别，行业改善逻辑未到尽头

### Fail 2：近 2 年 PE 中位 20x → 22x

- **wiki**：line 159 "近 2 年 PE 中位数：20x"
- **真值**[观测，baostock peTTM]：2024 中位 22.8x、2025 中位 21.2x、近 2 年均值约 22x；2026 至今中位 18.4x
- **影响**：估值锚定基础失真

### Fail 3："历史低点 PE 18x" 口径不严

- **wiki**：line 207 "锚点B（历史低点PE 18x）"
- **真值**[观测，baostock]：全样本最低 16.4x（2024）；"18x" 仅近 1 年最低
- **影响**：误导"地板价"判定

## 5 项 Warning（详见 git 历史）+ 19 项 Pass

详细数据反推全部 Pass：营收/利润 YoY、OCF +67%、派息率 69.9%、主品牌销量、同业对比等。

## 仲裁结论

**4/4 Fail 通过层次 1 独立确认**，未触发 Step 3.6 仲裁。

## 被引用于

- `wiki/stocks/consumer/青岛啤酒.md` v1.1（3 项 Fail 已修订）
- `wiki/log.md` 2026-05-11 LINT 条目
