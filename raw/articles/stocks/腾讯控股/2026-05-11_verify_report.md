---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 腾讯控股 wiki 独立校验报告（focus list 全量回归）
publisher: Claude Opus 4.7 subagent
type: verify_report
stocks: [腾讯控股]
verified: true
---

# 腾讯控股 wiki 独立校验报告

## 5 项 Fail（已层次 1 仲裁通过）

### Fail 1：分业务表 vs 整体表 FY+1 营收双轨

- 分业务表：3,080 + 1,416 + 2,576 + 1,279 = **8,351 亿**（+11.08%）
- 整体法表：**8,420 亿**（+12.0%）
- 差 69 亿 RMB，FY+1 OP 差 22 亿、EPS HKD 差 ~0.26，FY+1 目标价差 5 HKD

### Fail 2：FY+2 EPS 推导逻辑不一致

- wiki：FY+1 EPS 28.61 / FY+2 32.79
- 反推：FY+1 +7.0%（与高盛口径一致）/ FY+2 +14.6%（与营收 +10% / OPM 33% 不匹配）
- 用整体 OPM 法直推：FY+1 = 29.09 / FY+2 = **33.00**（差 0.21）

### Fail 3：FY+2 含息年化回报率算错

- wiki：14.8%
- 真值：(665.6/478.6)^(1/2) - 1 = **17.9%** + 股息 1% ≈ **18.9%**
- 14.8% 反推 n ≈ 2.55 年（把 2 年算成 2.5 年）

### Fail 4：SOTP 增速调整系数公式与表数值不符

- 公式：`coef = 0.8 + (g-0.03)/0.22 × 0.7`
- 公式代入 g=9%/16.5%/12% → 0.99/1.23/1.09
- 表实际：1.15/1.30/1.15（全部偏高 0.06-0.16，是手工估计而非公式产出）

### Fail 5："基本面支撑 25x" v1 残留语

- v1：合理 PE 25x
- v2：已下修至 23x
- 但 line 210 仍写"基本面支撑 25x 估值"——内部叙事矛盾

## 1 项 Warning + 10 项 Pass

核心财务全 verified：营收/经营利润/净利/毛利率/OPM/OCF/FCF/SBC/回购/AI Capex/DCF 472 HKD 等。

## 仲裁结论

**5/5 Fail 通过层次 1 独立确认**，未触发 Step 3.6 仲裁。

## 被引用于

- `wiki/stocks/internet/腾讯控股.md` v3（5 项 Fail 已修订）
- `wiki/log.md` 2026-05-11 LINT 条目
