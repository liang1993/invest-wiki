---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 阿里巴巴 wiki 独立校验报告（focus 回归 Phase 2）
type: verify_report
stocks: [阿里巴巴]
verified: true
---

# 阿里巴巴 wiki 校验报告

## 3 Fail（层次 1 通过）

### F1：FY+2 含息年化算错
- wiki "(133.9/125.5)^(1/2) - 1 + 1.6% ≈ 4.1%"
- 真值：用 125.5 基价正确算 **4.89%**；用当前价 136.40 算 0.68%
- wiki 数字与口径分别错（4.1% 既不是 125.5 也不是 136.40 基价的正确算式）

### F2：悲观情景 PE 算式断裂
- wiki "合理PE 15x × 正常化EPS 6.24 HKD = 106.0"
- 真值：15 × 6.24 = 93.6，不是 106；反推 106/6.24 = 17.0x 而非 15x

### F3：投资结论与当前价 PE 口径错位
- wiki "当前 136.40 → 静态 PE 16.9x"
- 真值：136.40/7.44 = **18.33x**；16.9x 是基于 125.5 价格
- 价格已更新但派生指标未同步

## 7 Warning + Pass

Warning：总股本/市值未随价格更新 / raw/articles 完全空（违反 WebSearch 归档强约束）/ FY+2 增速系数推导无公式 / TTM EPS 时效 / FY26 季报数据缺 PDF 回读 / 同行对比缺源

Pass：FY25 营收/经营利润比例 / 分业务占比 / SOTP PE 贡献合计 16.6 / 综合合理价值 107 加权数学 / 正常化 EPS 5.15 等。

## 仲裁结论：3/3 Fail 层次 1 通过。
