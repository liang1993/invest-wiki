---
source: value-invest-verify subagent
fetched: 2026-05-11
title: 宁德时代 wiki 独立校验报告（focus list 全量回归）
publisher: Claude Opus 4.7 subagent
type: verify_report
stocks: [宁德时代]
verified: true
---

# 宁德时代 wiki 独立校验报告

## 3 项 Fail（已层次 1 仲裁通过）

### Fail 1（核心元数据级错误）：港股 IPO 日期 + 总股本严重错误

- **wiki**：line 31 "A股创业板 + 港股（**2024 年 9 月**双重上市）"+ line 35 "总股本：**44.08 亿股**"
- **真值**：
  - 港股 3750.HK **2025-05-20** 挂牌（来源：[新浪 2025-05-20](https://finance.sina.com.cn/cj/2025-05-20/doc-inexfrau1102053.shtml)）
  - 2025 年报披露总股本 **45.64 亿股**（catl.com 年报，原文 4,563,868,956 股）
- **影响**：所有 EPS/PE 反推 ~3.4% 系统偏差。EPS = 722/45.64 = **15.82 元**（vs wiki 16.38，偏差 +3.5%）

### Fail 2：市占率叙事强化（月度峰值 vs 累计）

- **wiki**：line 33 "全球市占率：42-45%（2026年1月SNE数据45.2%，1-2月42.2%）"
- **真值**：
  - 1 月单月 45.2%（峰值）[观测：[cnevpost.com](https://cnevpost.com/2026/03/06/global-ev-battery-market-share-jan-2026/)]
  - Q1 累计 **40.7%** [观测：[cnevpost.com 2026-05-06](https://cnevpost.com/2026/05/06/global-ev-battery-market-share-jan-mar-2026/)]
  - 2025 全年 **39.2%**（chinaevhome.com）
- **影响**：把月度峰值当持续状态——line 70 "护城河 +3x：全球市占率 39.2%" 与 line 33 标题 "42-45%" 自相矛盾

### Fail 3：合理价 360 vs 430 双版本并存

- **wiki**：line 18 "综合合理价值 **430元**" / line 93 "综合合理价值 **360元**"（PE 377 + DCF 306 加权）/ line 186 "综合合理价值 **430元**"
- **真值**：line 181-186 加权 (412×0.4 + 417×0.4 + 443×0.2) = **420.2 元**（与 430 偏差 2.3%）
- **影响**：合理价旧（360）/新（430）版本并存，读者无法判断有效锚点

## 4 项 Warning + 6 项 Pass

Warning：PE 中位 [观测] 缺源（baostock 实测 2021-2025 中位 163/69.8/25.0/18.6/23.0）/ 卖方一致 2026E EPS 中位 20.60 vs wiki 22.2 偏乐观 +7.8% / "连续 9 年第一"+"全球大储 +50%" 无源 / TTM EPS 17.91 应为 17.30 (-3.5% 同 Fail 1)

Pass：2025 财务（营收 4237/净利 722/OCF 1332）/ 2026Q1（营收 1291/净利 207）/ 储能 121GWh 624 亿 / 动力 541GWh 3165 亿 等

## 仲裁结论

**3/3 Fail 通过层次 1 独立确认**，未触发 Step 3.6 仲裁。

**关键缺口**：`raw/articles/stocks/宁德时代/` 此前不存在——本归档创建该目录。

## 被引用于

- `wiki/stocks/auto/宁德时代.md` v2（3 项 Fail 已修订）
- `wiki/log.md` 2026-05-11 LINT 条目
