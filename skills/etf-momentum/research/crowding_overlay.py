#!/usr/bin/env python3
"""拥挤度/低相关叠加层（主 agent 独立，测文献 H5 + 回应"top3 全在一个主题"原始顾虑）。

机制：在 top-N(=6) 动量合格里，贪心挑 TOPK(=3) 个"互相关最低"的（滚动 126 日收益相关阵），
对冲"3 个全挤同一主题"。对比 朴素 top3，并各叠 vol@15。自含，仅 btlib 只读。
防前视：月末(含)数据定权重，shift(1) 次日生效；相关阵只用 ≤d 数据。
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
LOOK, TOPK, TOPN = 126, 3, 6


def greedy_lowcorr(ordered, corr):
    """ordered=按动量降序的候选；从动量第1个起，依次加"对已选平均|相关|最低"的。"""
    picked = [ordered[0]]
    cands = [x for x in ordered[1:]]
    while len(picked) < TOPK and cands:
        best, bestc = cands[0], 9.0
        for x in cands:
            avg = float(np.mean([abs(corr.loc[x, p]) for p in picked]))
            if avg < bestc:
                best, bestc = x, avg
        picked.append(best)
        cands.remove(best)
    return picked


def book(mode, topn=TOPN):
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    intra = []  # 记录每月所选 book 的平均两两相关（验机制）
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        mom = (c.iloc[-1] / c.iloc[-(LOOK + 1)] - 1).dropna()
        top = mom.sort_values(ascending=False)
        if len(top) < TOPK:
            continue
        if mode == "naive":
            pick = list(top.head(TOPK).index)
        else:
            cand = list(top.head(min(topn, len(top))).index)
            win = rets.loc[:d].iloc[-LOOK:][cand]
            corr = win.corr()
            pick = greedy_lowcorr(cand, corr)
        for code in pick:
            Wdec.loc[d, code] = 1.0 / TOPK
        if len(pick) == TOPK:
            win = rets.loc[:d].iloc[-LOOK:][pick].corr().values
            intra.append((win.sum() - TOPK) / (TOPK * (TOPK - 1)))  # 平均非对角相关
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0).shift(1).fillna(0)
    port = (Wsh * rets).sum(axis=1) + (1 - Wsh.sum(axis=1)) * cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    return port[started], float(np.mean(intra))


def volscale(g, tv=0.15):
    rv = g.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    e = (tv / rv).clip(upper=1).shift(1).fillna(0)
    return e * g + (1 - e) * cd


print(f"=== 拥挤度/低相关叠加 | {closes.index[0].date()}~{closes.index[-1].date()} ===\n")
for label, mode in [("朴素 top3", "naive"), ("低相关 top3", "corr")]:
    g, ic = book(mode)
    print(f"{label:<13}{btlib.fmt(btlib.perf(g))}  book内平均相关={ic:.2f}")
    pv = volscale(g)
    print(f"{label}+vol@15 {btlib.fmt(btlib.perf(pv))}")
    print()

print("=== 稳健性: TOPN 候选池敏感性(低相关 top3,验非刀尖参数) ===")
for tn in (5, 6, 8):
    g, ic = book("corr", topn=tn)
    m = btlib.perf(g)
    print(f"TOPN={tn}: CAGR={m['cagr']:.2%} 回撤={m['maxdd']:.1%} Calmar={m['calmar']:.2f} 相关={ic:.2f}")
