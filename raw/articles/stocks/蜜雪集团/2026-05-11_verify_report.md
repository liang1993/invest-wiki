---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 蜜雪集团 wiki 独立校验报告（focus list 全量回归）
publisher: Claude Opus 4.7 subagent
type: verify_report
stocks: [蜜雪集团]
verified: true
---

# 蜜雪集团 wiki 独立校验报告

## 3 项 Fail（已层次 1 仲裁通过）

### Fail 1：霸王茶姬归母净利润口径错误（同行对比关键）

- **wiki**：line 327 "霸王茶姬 归母净利 **19.1 亿** / 净利率 14.8%"
- **真值**：
  - 归母净利润 **11.35 亿（同比 -52.4%）** [观测：[网易财经](https://m.163.com/dy/article/KPF9QT400511U82T.html)、[36氪](https://36kr.com/p/3747862964663040)]
  - 19.1 亿是**经调整后净利润**（non-GAAP）
- **影响**：
  - 同行对比口径混用（蜜雪用 GAAP 58.8 亿 vs 霸王茶姬用 non-GAAP 19.1 亿）
  - 实际护城河差距：58.8/11.35 = **5.2 倍**（不是 wiki 推算的 3.08 倍）
  - "霸王茶姬崛起" 叙事失真——GAAP 利润 -52.4% + 营收增速 +4% 是**显著放缓**

### Fail 2：经营现金流 vs 第三方研报数据冲突

- **wiki**：line 92-95 OCF 67.94 亿 RMB / Capex 15.50 亿 RMB / FCF 52.44 亿 RMB
- **东吴研报**[观测，[东吴 2026-08-27](https://pdf.dfcfw.com/pdf/H3_AP202508271735579525_1.pdf)]：OCF 60.09 / Capex 14.50
- **差额**：OCF +7.85 亿（+13%）/ Capex +1 亿
- **影响**：FCF 基线 52.44 vs 真实可能 ~45.6 亿，DCF 敏感性表所有数字（326/340/...）需重算

### Fail 3：DCF FCF 币种口径混乱

- **wiki**：line 95 FCF = 52.44 亿 RMB；line 179 "FCF 基准 53.6 亿 HKD / 3.796 亿股 = 14.12 HKD/股"
- **真值**：52.44 × 1.095 ≈ 57.4 亿 HKD（不是 53.6）；53.6 亿 HKD ÷ 1.095 = 49 亿 RMB（与 52.44 不符）
- **影响**：DCF 模型 326 HKD 基础不清

## 4 项 Warning + Pass 项

Warning：股息率反推 1% 实际 1.68% / BPS 73.2 HKD 无源 / 海外 14 国 vs 13 国（含 2026Q1 巴西/墨西哥筹备 vs 2025 末口径）/ 研发投入 26 亿 +23% 缺出处（占营收 7.75% 偏高，可能含 Capex 资本化）

Pass：市值反推总股本 3.798 ≈ 3.796 ✓ / EPS RMB 15.49 ✓ / 海外净关店 -428 ✓ / 全球门店 59,823 净增 13,344 ✓

## 仲裁结论

**3/3 Fail 通过层次 1 独立确认**，未触发 Step 3.6 仲裁。

## 被引用于

- `wiki/stocks/consumer/蜜雪集团.md` v3（3 项 Fail 已修订）
- `wiki/log.md` 2026-05-11 LINT 条目
