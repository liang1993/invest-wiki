---
name: etf-momentum
description: 行业 ETF 动量轮动计算器。按"6 月动量 + 200 日趋势过滤"算 A 股行业/主题 ETF 当前动量状态，并出**去相关 top-K 选择 + 波动率目标敞口建议**(回测验证的风控层)，生成快照。Use when 用户问"现在行业动量怎么样 / 哪些板块强 / 跑一下 ETF 动量 / 刷新动量状态 / 行业轮动信号"。策略框架见 wiki/strategies/行业ETF动量轮动.md。
---

# ETF Momentum Skill

计算 A 股行业/主题 ETF 的**当前动量状态 + 轮动信号**。是 [行业ETF动量轮动](../../wiki/strategies/行业ETF动量轮动.md) 策略的"计算器"——wiki 存规则+universe（静态），本 skill 跑实时数据出状态（瞬时）。

## When to Use
- "现在行业动量状态 / 哪些板块强 / 跑一下 ETF 动量 / 刷新动量快照 / 行业轮动信号"

## Prerequisites
```bash
pip install akshare pandas
```
数据源 = sina 日线（国内直连）。若被代理干扰：`env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY python3 momentum.py`

## 用法
```bash
python3 skills/etf-momentum/momentum.py        # 打印状态表 + 当前信号
python3 skills/etf-momentum/momentum.py --md   # 输出 wiki 快照 markdown
```
刷新 wiki 快照 `wiki/strategies/行业ETF动量状态.md`：重跑 `--md`，**替换其数据表区，保留 frontmatter + 解读 + 方法学**（解读是人工判断，skill 不生成）。

## 组成
- `universe.py` —— ETF 代码**唯一来源**（single source of truth；wiki 清单以此为准）
- `momentum.py` —— 算 6 月动量 / 200 日均线 / AUM / 流动性 / 排名 / **去相关选择 + 波动率目标敞口** / 信号
- 取数 `_shared/marketdata/etf_hist.py` —— sina 日线 + **前复权**（符号路由用 `marketdata.codes.to_sina_symbol`）
- AUM 快照 `_shared/marketdata/quote_tencent.py` —— 腾讯 `total_mcap_y`（批量 ≤50/批）

## 参数（`momentum.py` 顶部，与 wiki 默认一致）
`LOOKBACK=126`(6月) · `MA=200` · `TOPK=3` · `LIQ_MIN_YI=1.0` · `AUM_MIN_YI=20`
**风控升级层**（回测验证，见 wiki §六 / `research/`）：`TOPN=6`(去相关候选池) · `VOL_TARGET=0.15`(波动率目标) · `VOL_LB=126`(波动/相关回看)
- **去相关选择**：从动量前 `TOPN` 合格里挑 `TOPK` 个互相关最低的(抗主题聚集)，替代机械 top-K——推荐持仓表按去相关 pick 顺序(非纯动量降序)。
- **波动率目标**：建议敞口 = `min(1, VOL_TARGET / 组合已实现波动)`，危机自动减仓(上限 100%，不加杠杆)。
- **MA 用真 min_periods**：未满 200 日历史的票不算"在均线上"(防 skipna 假合格)。

流动性闸 = **规模 ≥ 20 亿 且 日均成交 ≥ 1 亿**（对齐策略页）。AUM 取腾讯「总市值」(`total_mcap_y`)近似，**非 f10 基金净资产口径**；作 ≥20 亿 粗闸够用（量级实测吻合，如 510300≈1391.92 亿）。取不到 AUM 的视为不合格（宁缺毋滥）。

## ⚠️ 关键数据质量点
sina 返回**不复权价**，份额折算/拆分会制造虚假暴跌（如通信 515880 单日 -66% 折算 → 6 月动量被误算成 -37%，实为 +83%）。`etf_hist.py` 已做**前复权**（检测单日 \|涨跌\|>35% 的公司行为日回溯复权）。阈值 0.35 依据：实测全 universe 最大真实单日波动仅 10.0%（软件 159852），份额折算 ≥49.8%（稀土 516780 -49.8%、通信 515880 -65.7%），0.35 落在干净间隙；已知局限：<35% 的小幅折算仍会漏（罕见）。**改 universe 后务必抽查**新代码（拿基金页"近6月"对一下，方向应一致）。

## 边界
只算**通用**动量状态(holdings-agnostic)。个人持仓的"去重叠 / 5-4-1 / 仓位映射"是 `private/因子配置框架.md` 的事；**buffer 出场状态机**(对照持仓标出触发出场门的票)是 `private/etf_holdings_check.py`——都碰持仓，不进本 skill、不进 wiki。
