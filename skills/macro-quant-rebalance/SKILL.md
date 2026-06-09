---
name: macro-quant-rebalance
description: 专用于个人 A 股「宏观量化中性组合」的再平衡计算器——**不是通用再平衡器**，只服务这一套策略：静态大类 E40/B22/G21/C17 + 整组合波动率目标 12% + 权益用 etf-momentum 去相关 top3。给定当前持仓或资金量，输出手数级买卖调整清单。Use when 用户要这套中性组合的月度再平衡/调仓方案、从零建仓配置、发来券商持仓截图要调整方案、或问"50万怎么配 / 现在该买卖什么 / 按持仓出再平衡"。不做个股估值（那是 value-invest）、不做任意组合或其它策略的通用资产配置、不做宏观 regime 择时（回测证明不加分）。策略与回测见 wiki/strategies/宏观量化策略框架.md 与 skills/etf-momentum/research/findings_macro_overlay.md。
---

# 宏观量化中性组合 · 再平衡计算器（macro-quant-rebalance）

把"中性宏观量化组合"的目标配置算出来，并（给定当前持仓时）出**买卖调整清单**。是 [宏观量化策略框架](../../wiki/strategies/宏观量化策略框架.md) + [行业ETF动量轮动](../../wiki/strategies/行业ETF动量轮动.md) 的"执行器"——上层用 [etf-momentum](../etf-momentum/SKILL.md) 选权益、本 skill 叠大类配置 + 波动率目标 + 持仓对照。

## 策略（中性方案，回测背书）

静态大类 **E40 / B22 / G21 / C17 + 整组合波动率目标 12%**；权益桶 = etf-momentum **去相关 top3** 行业动量。
回测（2013-08~2026-06，防前视，独立审计，见 `../etf-momentum/research/findings_macro_overlay.md`）：
- **宏观 regime 择时不加分、反而 ≤ 静态分散**（择时 Sharpe 0.68 < 静态 0.83）→ 本 skill **不做 regime 择时**，只做静态分散 + 波动率目标两层风控。
- 推荐档 P0+vol@12 ≈ Sharpe 0.90 / Calmar 0.49 / 回撤 -18% / CAGR 8.9%（gross 口径，实盘打折）。
- caveat：静态组高 Sharpe 约半数来自黄金 2013-26 牛市。

## 隐私边界（为什么能进 skills/）

本 skill 是**抽象工作流执行器，自身不含任何持仓数据**——持仓在运行时由 `--holdings <path>` 传入。
持仓数据文件属个人隐私，应放在**本仓库之外的私有位置**（勿提交）；本 skill 通过参数读取，**无隐私耦合**，故可公开。
**不要**在本 skill 里硬编码任何私有路径或金额。

## When to Use

- "按我持仓出再平衡方案 / 月度调仓清单 / 50 万怎么配 / 中性组合现在该买卖什么"
- 月度工作流：用户发券商持仓截图 → 录入持仓文件 → 跑本 skill 出调整清单。

## Prerequisites

```bash
pip install akshare pandas numpy
```
数据源 = sina 日线（前复权，算波动）+ 腾讯实时（现价）。代理干扰时 unset：
`env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY ... python3 rebalance.py ...`

## 用法

```bash
# 从零建仓：给资金量，出目标配置 + 下单手数清单
python3 skills/macro-quant-rebalance/rebalance.py --capital 500000

# 月度再平衡：给当前持仓，出买卖调整（含缓冲带）
python3 skills/macro-quant-rebalance/rebalance.py --holdings <你的持仓文件路径>

# 改档（进取/保守）：调权重 + 波动率目标
python3 skills/macro-quant-rebalance/rebalance.py --holdings <path> --weights 50,20,18,12 --vol-target 0.10
```

**持仓文件格式**（每行 `代码 市值元`；现金写 `CASH 金额`；`#` 注释；只填市值不需股数）：
```
515880 51500    # 通信
511260 81000    # 10年国债ETF
518880 81000    # 黄金ETF
CASH   180000
```

## 月度协作工作流（与用户）

1. 用户发券商持仓截图。
2. 把每只「市值」+「可用现金」录入持仓文件（存私有位置，勿提交本仓库）。
3. 跑 `rebalance.py --holdings <该文件>`。
4. 把输出的「买卖调整清单」relay 给用户。
5. （可选）把这次调整记一笔到用户的私有投资日志。

## 计算逻辑

- **权益 top3**：调 etf-momentum 的 `_decorrelate`（动量前 6 挑互相关最低 3）。
- **vol 敞口**：整组合近 126 日已实现波动（含今日腾讯价）→ `敞口 = min(1, vol_target / 波动)`，上限 100% 不加杠杆。
- **目标金额** = 总资产 × 大类权重 × 敞口；省下的并入现金。
- **调整**：建仓/清仓必动；已有仓微调 < 总资产 1.5%（`BAND`）则不动（省零碎换手）；权益每月直接换到去相关 top3（默认不挂缓冲带，回测证明缓冲带降收益）。

## 参数（`rebalance.py` 顶部 / CLI）

`--weights`（默认 `40,22,21,17`）· `--vol-target`（默认 `0.12`）· `--bond`（默认 `511260`）· `--gold`（默认 `518880`）· `BAND=0.015`（不动带）。

## 边界

- 只算**通用再平衡**（holdings-agnostic）；持仓数据、个人金额映射、买入成本/盈亏由调用方私有保管，不进本 skill。
- 不做 regime 择时（回测证明不加分）；不做固定 %/ATR 止损（A 股有害）；不加杠杆。
- 债桶默认 `511260`（10 年国债 ETF）；回测用上证国债指数代理，实盘口径略差异。
- 现价为腾讯实时快照，**真实下单以成交价为准**，手数会微调。
