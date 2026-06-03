#!/usr/bin/env python3
"""冠军候选对决（主 agent 自建，补 BT-2 网格未覆盖的 文献头号种子）：
在 6 月动量 top-3 月度轮动上，对比不同 出场/仓位 模块：
  - none      : 纯动量(基线)
  - ma200     : 现价>200SMA 才合格(当前默认)
  - tsmom     : 只持有 6 月动量>0 的(符号出场, Moskowitz-Ooi-Pedersen)
  - volscale  : 在纯动量 book 上做波动率缩放(目标年化波动, Barroso/银河 低波)
  - ma200+vol : 趋势过滤 + 波动缩放

防前视: 月末定权重→shift(1)次日生效; 波动缩放用截至昨日的已实现波动。
锚定: none / ma200 必须复现 _xcheck_rotation.py 的数字(7.52%/-65.6%, 5.96%/-63.9%)。
"""
import numpy as np
import pandas as pd

import btlib

panel = btlib.load_panel()
closes = pd.DataFrame({c: df["close"] for c, df in panel.items()}).sort_index()
rets = closes.pct_change()
cd = btlib.cash_daily()
idx = closes.index
DECIDE = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)

LOOK, TOPK, MA = 126, 3, 200


def gross_book(eligibility: str, ma_len: int = 200) -> pd.Series:
    """纯多头 top-3 等权 book 的日收益(防前视)。eligibility 决定哪些可入选。"""
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        last, prev = c.iloc[-1], c.iloc[-(LOOK + 1)]
        mom = (last / prev - 1).dropna()
        if eligibility.startswith("ma"):
            window = c.iloc[-ma_len:]
            ma = window.mean().where(window.notna().sum() >= ma_len)  # 真 min_periods,不 skipna
            mom = mom[(last > ma).reindex(mom.index).fillna(False)]
        elif eligibility == "tsmom":
            mom = mom[mom > 0]              # 6 月动量符号>0 才持有
        top = mom.sort_values(ascending=False).head(TOPK)
        for code in top.index:
            Wdec.loc[d, code] = 1.0 / TOPK  # 不足 TOPK→余额留现金
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0.0).shift(1).fillna(0.0)
    cash_w = 1.0 - Wsh.sum(axis=1)
    port = (Wsh * rets).sum(axis=1) + cash_w * cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    return port[started], Wsh[started]


def vol_scale(gross: pd.Series, target_vol: float = 0.15, cash_rate: float = cd) -> pd.Series:
    """波动率缩放(long-only, 杠杆上限 1.0): 用过去 126 日已实现波动(截至昨日)定今日敞口。"""
    rv = gross.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    expo = (target_vol / rv).clip(upper=1.0).shift(1)   # 防前视
    expo = expo.fillna(0.0)
    return expo * gross + (1.0 - expo) * cash_rate, expo


def vol_scale_monthly(gross: pd.Series, target_vol: float = 0.15) -> pd.Series:
    """波动缩放的月频版(敞口每月末才调,降日频换手)。"""
    rv = gross.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    expo_d = (target_vol / rv).clip(upper=1.0)
    expo_m = expo_d.reindex(DECIDE, method="ffill")          # 月末取值
    expo = expo_m.reindex(gross.index, method="ffill").shift(1).fillna(0.0)
    return expo * gross + (1.0 - expo) * cd, expo


def maxdd(port):
    eq = (1 + port).cumprod()
    return float((eq / eq.cummax() - 1).min())


def line(label, port, expo=None):
    m = btlib.perf(port)
    extra = f" 平均敞口={expo.mean():.0%}" if expo is not None else ""
    print(f"{label:<22}{btlib.fmt(m)}{extra}")


print(f"=== 冠军候选对决 | {closes.index[0].date()}~{closes.index[-1].date()} | 现金{btlib.CASH_ANNUAL_DEFAULT:.1%}/年 ===\n")

g_none, _ = gross_book("none")
g_ma, _ = gross_book("ma200")
g_ts, _ = gross_book("tsmom")

line("纯动量(基线)", g_none)
line("+200SMA 过滤", g_ma)
line("+TSMOM 符号出场", g_ts)
print()
for tv in (0.12, 0.15, 0.20):
    p, e = vol_scale(g_none, tv)
    line(f"纯动量+波动缩放@{tv:.0%}", p, e)
print()
p, e = vol_scale(g_ma, 0.15)
line("200SMA+波动缩放@15%", p, e)
p, e = vol_scale(g_ts, 0.15)
line("TSMOM+波动缩放@15%", p, e)

print("\n[锚定校验] 纯动量应≈CAGR7.52%/回撤-65.6%; +200SMA应≈5.96%/-63.9%(对齐 _xcheck)")

# ---- 稳健性 1: 现金收益假设敏感性(现金@0 看 vol-scaling 是否靠现金收益取胜) ----
print("\n=== 稳健性①: 现金收益@0 vs @1.8% (检验 vol-scaling 是否靠现金息) ===")
for tv in (0.12, 0.15):
    p18, _ = vol_scale(g_none, tv, cash_rate=cd)
    p00, _ = vol_scale(g_none, tv, cash_rate=0.0)
    print(f"波动缩放@{tv:.0%}: 现金1.8% CAGR={btlib.perf(p18)['cagr']:.2%}/回撤{maxdd(p18):.1%}  |  "
          f"现金0% CAGR={btlib.perf(p00)['cagr']:.2%}/回撤{maxdd(p00):.1%}")

# ---- 稳健性 2: 月频敞口(降换手)是否仍有效 ----
print("\n=== 稳健性②: 波动缩放 日频 vs 月频敞口(换手现实性) ===")
pd_, _ = vol_scale(g_none, 0.15)
pm_, em = vol_scale_monthly(g_none, 0.15)
print(f"日频敞口: {btlib.fmt(btlib.perf(pd_))}")
print(f"月频敞口: {btlib.fmt(btlib.perf(pm_))} 平均敞口={em.mean():.0%}")

# ---- 稳健性 3: 分子周期(每个 regime 都成立吗?过拟合检验) ----
print("\n=== 稳健性③: 分子周期最大回撤(基线 vs vol@15 vs 200SMA+vol@15) ===")
periods = [
    ("2015H2-16熔断", "2015-06-15", "2016-12-31"),
    ("2017-18蓝筹熊", "2017-01-01", "2018-12-31"),
    ("2019-21成长牛", "2019-01-01", "2021-12-31"),
    ("2022-24熊", "2022-01-01", "2024-09-30"),
    ("2024Q4-26反弹", "2024-10-01", "2026-06-02"),
]
pv, _ = vol_scale(g_none, 0.15)
pmv, _ = vol_scale(g_ma, 0.15)
books = {"基线": g_none, "vol@15": pv, "200SMA+vol@15": pmv}
print(f"{'区间':<16}" + "".join(f"{k+'(总/回撤)':>22}" for k in books))
for name, lo, hi in periods:
    row = f"{name:<16}"
    for k, b in books.items():
        seg = b[(b.index >= lo) & (b.index <= hi)]
        tot = (1 + seg).prod() - 1 if len(seg) else float("nan")
        row += f"{tot:>10.1%}/{maxdd(seg):>9.1%}  "
    print(row)

# ---- 稳健性 4: 轮动里 MA 长度扫描 (单用 vs +vol@15) —— 回应"止损点设多长" ----
print("\n=== 稳健性④: 轮动 MA 长度扫描 (BT-1 说单标的 SMA50 最优,轮动里呢?) ===")
print(f"{'MA长度':<9}{'单用 CAGR/回撤/Calmar':>26}{'+vol@15 CAGR/回撤/Calmar':>30}")
for n in (50, 100, 150, 200, 250):
    g, _ = gross_book("ma", n)
    pv, _ = vol_scale(g, 0.15)
    a, v = btlib.perf(g), btlib.perf(pv)
    print(f"SMA{n:<6}{a['cagr']:>8.2%}/{a['maxdd']:>7.1%}/{a['calmar']:>5.2f}"
          f"{v['cagr']:>13.2%}/{v['maxdd']:>7.1%}/{v['calmar']:>5.2f}")

# ---- 稳健性 5: 交易成本净后(换手现实性, c=单边 bps) —— vol-scaling 赢家扛得住成本吗 ----
print("\n=== 稳健性⑤: 净成本后 Calmar (含轮动+敞口调整全部换手) ===")
gn, Wn = gross_book("none")
gm, Wm = gross_book("ma", 200)
ones = pd.Series(1.0, index=gn.index)
en = vol_scale(gn, 0.15)[1]
em = vol_scale(gm, 0.15)[1]


def net_ret(Wsh, expo, c):
    pos = Wsh.mul(expo, axis=0)                       # 有效持仓(已防前视)
    cash_w = 1.0 - pos.sum(axis=1)
    gross = (pos * rets).sum(axis=1) + cash_w * cd
    cost = c * pos.diff().abs().sum(axis=1)           # 单边换手×成本
    return gross - cost, pos.diff().abs().sum(axis=1).sum() / (len(pos) / btlib.TRADING_DAYS)


configs = {"基线(纯动量)": (Wn, ones), "vol@15": (Wn, en), "200SMA+vol@15": (Wm, em)}
print(f"{'配置':<16}{'年换手':>8}{'Calmar@0bps':>13}{'@5bps':>9}{'@10bps':>9}")
for name, (W, e) in configs.items():
    _, tpa = net_ret(W, e, 0)
    cal = []
    for c in (0.0, 0.0005, 0.0010):
        p, _ = net_ret(W, e, c)
        cal.append(btlib.perf(p)["calmar"])
    print(f"{name:<16}{tpa:>7.1f}x{cal[0]:>12.2f}{cal[1]:>9.2f}{cal[2]:>9.2f}")
