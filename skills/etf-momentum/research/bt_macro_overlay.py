#!/usr/bin/env python3
"""宏观大类层 overlay 回测：在"低相关 top3 行业动量"之上叠加 regime 大类配置，
测"宏观状态择时"是否真加分——关键是和 static 大类控制组(无择时,只分散)对比。

资产桶：E=权益(低相关top3行业动量book) / B=债(上证国债指数000012) / G=黄金(518880) / C=现金(1.8%/年)
状态轴(美林时钟本土化, 全部 1 个月数据滞后, 防前视)：
  增长 = 制造业PMI ≥ 50 ; 通胀 = CPI同比 vs 3个月前(上行/下行)
  → 复苏(增↑胀↓)/过热(增↑胀↑)/滞胀(增↓胀↑)/衰退(增↓胀↓)
  M2同比>12月均 → 流动性override(权益±10pt, 替代不可达的社融)
对比组：
  A   纯权益(低相关top3, 100%)                —— 旧基线
  A2  低相关top3 + vol@15                      —— 你当前最优(champion)
  S   static大类(固定均值权重, 无regime择时)   —— 分散-only 控制组(关键对照)
  B   regime大类 overlay(择时)
  B2  regime overlay + vol@15
防前视：行业book内部已shift(1)；大类权重月末定、shift(1)次日生效；宏观数据滞后1个月；
        vol敞口用截至昨日已实现波动。窗口 2013-08~(黄金ETF起点约束)。
"""
import os
import numpy as np
import pandas as pd

import btlib

DM = os.path.join(os.path.dirname(__file__), "data_macro")
LOOK, TOPK, TOPN = 126, 3, 6
START = "2013-08-01"   # 黄金ETF 2013-07-29 起 → 共同窗口
MACRO_LAG = 1          # 宏观数据滞后月数(防前视)

panel = btlib.load_panel()
closes = pd.DataFrame({c: df["close"] for c, df in panel.items()}).sort_index()
rets = closes.pct_change()
cd = btlib.cash_daily()
idx = closes.index
DECIDE = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)


# ---------- 权益桶：低相关 top3 行业动量 book（复用 crowding_overlay 逻辑）----------
def greedy_lowcorr(ordered, corr):
    picked = [ordered[0]]
    cands = list(ordered[1:])
    while len(picked) < TOPK and cands:
        best, bestc = cands[0], 9.0
        for x in cands:
            avg = float(np.mean([abs(corr.loc[x, p]) for p in picked]))
            if avg < bestc:
                best, bestc = x, avg
        picked.append(best)
        cands.remove(best)
    return picked


def equity_book():
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        mom = (c.iloc[-1] / c.iloc[-(LOOK + 1)] - 1).dropna()
        top = mom.sort_values(ascending=False)
        if len(top) < TOPK:
            continue
        cand = list(top.head(min(TOPN, len(top))).index)
        corr = rets.loc[:d].iloc[-LOOK:][cand].corr()
        for code in greedy_lowcorr(cand, corr):
            Wdec.loc[d, code] = 1.0 / TOPK
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0).shift(1).fillna(0)
    port = (Wsh * rets).sum(axis=1) + (1 - Wsh.sum(axis=1)) * cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    return port.where(started, np.nan)


# ---------- 跨资产桶收益（对齐主交易日历）----------
def load_close(fname):
    s = pd.read_csv(os.path.join(DM, fname), parse_dates=["date"]).set_index("date")["close"]
    return s.reindex(closes.index, method="ffill")  # 对齐 SSE 日历


g_equity = equity_book()
rB = load_close("idx_sh000012.csv").pct_change()    # 债券桶
rG = load_close("etf_sh518880.csv").pct_change()     # 黄金桶
rC = pd.Series(cd, index=closes.index)               # 现金桶


# ---------- 宏观 regime ----------
macro = pd.read_csv(os.path.join(DM, "macro_monthly.csv"), parse_dates=["month"]).set_index("month").sort_index()
macro["growth_up"] = macro["pmi"] >= 50
macro["infl_up"] = macro["cpi_yoy"].diff(3) > 0
macro["liq_up"] = macro["m2_yoy"] > macro["m2_yoy"].rolling(12).mean()


def regime_of(row):
    if pd.isna(row["pmi"]) or pd.isna(row["cpi_yoy"]):
        return np.nan
    if row["growth_up"] and not row["infl_up"]:
        return "复苏"
    if row["growth_up"] and row["infl_up"]:
        return "过热"
    if (not row["growth_up"]) and row["infl_up"]:
        return "滞胀"
    return "衰退"


macro["regime"] = macro.apply(regime_of, axis=1)
macro["regime"] = macro["regime"].ffill()

TILT = {  # a priori 投资时钟倾斜，固定、不对数据优化
    "复苏": dict(E=0.70, B=0.15, G=0.10, C=0.05),
    "过热": dict(E=0.45, B=0.05, G=0.35, C=0.15),
    "滞胀": dict(E=0.20, B=0.15, G=0.30, C=0.35),
    "衰退": dict(E=0.25, B=0.55, G=0.10, C=0.10),
}
STATIC = {k: float(np.mean([TILT[r][k] for r in TILT])) for k in "EBGC"}  # 分散-only 控制


def macro_month_for(d, lag=MACRO_LAG):  # DECIDE 在 M 月 → 用 (M-lag) 月数据
    return pd.Timestamp(d.year, d.month, 1) - pd.offsets.MonthBegin(lag)


def build_weights(use_regime: bool, m2_override: bool, lag=MACRO_LAG):
    W = pd.DataFrame(0.0, index=DECIDE, columns=list("EBGC"))
    for d in DECIDE:
        if use_regime:
            mm = macro_month_for(d, lag)
            if mm not in macro.index or pd.isna(macro.loc[mm, "regime"]):
                w = dict(STATIC)
            else:
                w = dict(TILT[macro.loc[mm, "regime"]])
                if m2_override:
                    bump = 0.10 if bool(macro.loc[mm, "liq_up"]) else -0.10
                    w["E"] = min(max(w["E"] + bump, 0.0), 1.0)
                    w["C"] = max(w["C"] - bump, 0.0)
        else:
            w = dict(STATIC)
        for k in "EBGC":
            W.loc[d, k] = w[k]
    s = W.sum(axis=1).replace(0, np.nan)
    W = W.div(s, axis=0)  # 归一化（override 后可能≠1）
    return W.reindex(closes.index, method="ffill").shift(1).fillna(0)


def combine(W):
    return (W["E"] * g_equity.fillna(0) + W["B"] * rB.fillna(0)
            + W["G"] * rG.fillna(0) + W["C"] * rC)


def vol_scale(g, tv=0.15):
    rv = g.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    e = (tv / rv).clip(upper=1.0).shift(1).fillna(0.0)
    return e * g + (1.0 - e) * cd


def clip_win(s):
    return s[(s.index >= START) & s.notna()]


# ---------- 组合 ----------
W_static = build_weights(use_regime=False, m2_override=False)
W_regime = build_weights(use_regime=True, m2_override=False)
W_regime_m2 = build_weights(use_regime=True, m2_override=True)

books = {
    "A  纯权益(低相关top3)": clip_win(g_equity),
    "A2 低相关top3+vol@15": clip_win(vol_scale(g_equity)),
    "S  static大类(无择时)": clip_win(combine(W_static)),
    "B  regime大类(择时)": clip_win(combine(W_regime)),
    "B+ regime+M2 override": clip_win(combine(W_regime_m2)),
    "B2 regime+vol@15": clip_win(vol_scale(combine(W_regime))),
}

print(f"=== 宏观大类层 overlay A/B | 窗口 {START}~{closes.index[-1].date()} | 现金{btlib.CASH_ANNUAL_DEFAULT:.1%}/年 | 宏观滞后{MACRO_LAG}月 ===\n")
print(f"{'组合':<24}{'CAGR':>8}{'波动':>8}{'Sharpe':>8}{'最大回撤':>10}{'Calmar':>8}")
for label, b in books.items():
    m = btlib.perf(b)
    print(f"{label:<24}{m['cagr']:>7.2%}{m['vol']:>8.1%}{m['sharpe']:>8.2f}{m['maxdd']:>10.1%}{m['calmar']:>8.2f}")

print(f"\nstatic 大类权重(分散控制组): " + " ".join(f"{k}={STATIC[k]:.0%}" for k in "EBGC"))

# ---------- regime 频率 + 各 regime 下 overlay 表现 ----------
print("\n=== regime 月度频率(窗口内, 已滞后) + 当期 B 组合月均收益 ===")
reg_dec = pd.Series({d: (macro.loc[macro_month_for(d), "regime"]
                         if macro_month_for(d) in macro.index else np.nan) for d in DECIDE})
reg_daily = reg_dec.reindex(closes.index, method="ffill").shift(1)
B_ret = clip_win(combine(W_regime))
reg_win = reg_daily.reindex(B_ret.index)
for r in ["复苏", "过热", "滞胀", "衰退"]:
    mask = reg_win == r
    days = int(mask.sum())
    if days:
        ann = B_ret[mask].mean() * btlib.TRADING_DAYS
        print(f"  {r}: {days:>4}日({days/len(B_ret):>5.0%})  B年化≈{ann:>7.1%}")

# ---------- 分子周期最大回撤 ----------
print("\n=== 分子周期 总收益/最大回撤 (纯权益 vs 中性P0+vol@12 vs 黄金桶) ===")
def mdd(s):
    eq = (1 + s).cumprod(); return float((eq / eq.cummax() - 1).min())
periods = [
    ("2014-15 杠杆牛灾", "2014-07-01", "2016-01-31"),
    ("2016-18 蓝筹/熊", "2016-02-01", "2018-12-31"),
    ("2019-21 成长牛", "2019-01-01", "2021-12-31"),
    ("2022-24 熊", "2022-01-01", "2024-09-30"),
    ("2024Q4-26 反弹", "2024-10-01", "2026-06-30"),
]
cmp = {"纯权益top3": clip_win(g_equity), "中性P0+vol@12": clip_win(vol_scale(combine(W_static), 0.12)), "黄金桶": clip_win(rG)}
print(f"{'区间':<18}" + "".join(f"{k+'(总/回撤)':>22}" for k in cmp))
for name, lo, hi in periods:
    row = f"{name:<18}"
    for k, b in cmp.items():
        seg = b[(b.index >= lo) & (b.index <= hi)]
        tot = (1 + seg).prod() - 1 if len(seg) else float("nan")
        row += f"{tot:>10.1%}/{mdd(seg):>9.1%}  "
    print(row)

# ---------- 稳健性: 宏观滞后 1 vs 2 月(择时是否经得起更保守的滞后) ----------
print("\n=== 稳健性: 宏观滞后月数 (择时 B 是否仍 ≤ 静态 S) ===")
S_m = btlib.perf(clip_win(combine(W_static)))
print(f"  S 静态(无择时):        Sharpe={S_m['sharpe']:.2f} 回撤={S_m['maxdd']:.1%} Calmar={S_m['calmar']:.2f}")
for lag in (1, 2):
    Bw = build_weights(use_regime=True, m2_override=False, lag=lag)
    bm = btlib.perf(clip_win(combine(Bw)))
    print(f"  B 择时(滞后{lag}月):       Sharpe={bm['sharpe']:.2f} 回撤={bm['maxdd']:.1%} Calmar={bm['calmar']:.2f}")

# ---------- 组合方案候选(静态分散 ± vol-target ± 黄金保守) ----------
def static_w(E, B, G, C):
    tot = E + B + G + C
    W = pd.DataFrame({k: v / tot for k, v in zip("EBGC", [E, B, G, C])}, index=DECIDE)
    return W.reindex(closes.index, method="ffill").shift(1).fillna(0)

print("\n=== 组合方案候选 (窗口同上, 全静态无择时) ===")
print(f"{'方案':<28}{'CAGR':>8}{'波动':>8}{'Sharpe':>8}{'最大回撤':>10}{'Calmar':>8}")
plans = {
    "P0 基准 E40/B22/G21/C16": combine(static_w(40, 22, 21, 16)),
    "P0+vol@12": vol_scale(combine(static_w(40, 22, 21, 16)), 0.12),
    "P0+vol@10": vol_scale(combine(static_w(40, 22, 21, 16)), 0.10),
    "P1 金保守 E40/B27/G12/C21": combine(static_w(40, 27, 12, 21)),
    "P1+vol@10": vol_scale(combine(static_w(40, 27, 12, 21)), 0.10),
    "P2 进取 E50/B20/G18/C12": combine(static_w(50, 20, 18, 12)),
    "P2+vol@12": vol_scale(combine(static_w(50, 20, 18, 12)), 0.12),
}
for label, b in plans.items():
    m = btlib.perf(clip_win(b))
    print(f"{label:<28}{m['cagr']:>7.2%}{m['vol']:>8.1%}{m['sharpe']:>8.2f}{m['maxdd']:>10.1%}{m['calmar']:>8.2f}")

# ---------- 健全性 ----------
print("\n[防前视] 宏观滞后1月 + 权重shift(1) + 行业book内部shift(1) + vol敞口shift(1)")
assert btlib.perf(books["S  static大类(无择时)"])["maxdd"] > btlib.perf(books["A  纯权益(低相关top3)"])["maxdd"], "加债/金分散应降回撤"
print("[OK] static 大类回撤 < 纯权益(分散有效)；下看 B 是否再优于 S(择时是否加分)")
