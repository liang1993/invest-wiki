---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 美团 wiki 独立校验报告（focus list 全量回归）
publisher: Claude Opus 4.7 subagent
type: verify_report
stocks: [美团]
verified: true
---

# 美团 wiki 独立校验报告

## 3 项 Fail（已层次 1 仲裁通过）

### Fail 1（最严重）：股本口径错误

- **wiki**：line 142、220 "基准正常化EPS：5.0元（280亿÷55.95亿股）"
- **真值**：yfinance marketCap 5,211 亿 HKD / 84.35 = **61.78 亿股**
- **影响**：
  - 正常化 EPS：280/61.78 = **4.53 元**（不是 5.0 元）
  - 静态合理价：18 × 4.53 = 81.5 RMB ≈ **88.6 HKD**（不是 97.8）
  - 综合合理价：104 → **≈ 94 HKD**（-10%）
  - 安全边际买入 72 → **≈ 65 HKD**

### Fail 2：Forward PE 货币单位混算

- **wiki**：line 23/290/299/309/372 "Forward PE 15.5x"
- **真值**：yfinance forwardPE 15.78 是 **84.35 HKD ÷ 5.348 RMB 混算**
- **正确 RMB 口径**：84.35/0.92/5.35 = **17.1x**
- **影响**：市场隐含 2026 净利 311 亿（wiki）→ **280 亿 RMB**；模型 18-19x vs 实际 17.1x **分歧仅 5-10%**（不是 25%）

### Fail 3：市值标注口径与 EPS 章节不一致

- 市值：5,338 亿 HKD / 86.45 = 61.75 亿股
- EPS 计算：用 55.95 亿股
- wiki 内部不自洽——市值章用真实股本，EPS 章用旧/流通股

## 3 项 Warning + Pass 项

Warning：销售费用 +389 亿口径不明 / 外卖份额 67% vs 摩根大通 50% 未双列 / FY+2 销售费用 780 亿假设无源标 [估计]

Pass：综合合理价加权数学自洽、毛利率/销售费用率反推一致、外卖大战亏损 -234-358=-592 ≈ 600 亿一致

## 仲裁结论

**3/3 Fail 通过层次 1 独立确认**，未触发 Step 3.6 仲裁。

## 被引用于

- `wiki/stocks/internet/美团.md` v2（3 项 Fail 已修订，估值锚点下修）
- `wiki/log.md` 2026-05-11 LINT 条目
