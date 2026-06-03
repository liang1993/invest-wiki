#!/usr/bin/env python3
"""拥挤度/低相关叠加层 —— 真实 38 行业/主题 ETF 细粒度稳健性检验。

照搬 crowding_overlay.py(17 宽基指数)逻辑,数据换成 data_etf/ 的 38 个前复权 ETF。
机制:在 top-N(=6) 动量合格里,贪心挑 TOPK(=3) 个"互相关最低"的(滚动 126 日收益相关阵),
对冲"3 个全挤同一主题"。对比 朴素 top3,并各叠 vol@15。

ETF 历史交错(最老 2015、多数 2020-2024、最新 2025-03 仅 287 天)——必须**扩张型截面**:
每决策日只对 ≥126 日历史的 ETF 排名(mom.dropna() 自动剔除未上市/历史不足者)。

防前视铁律:月末(含)数据定权重,shift(1) 次日生效;相关阵只用 ≤d 数据。
可选流动性闸:amount 近 20 日均值 ≥ 1 亿才入候选池。

自含,仅 btlib 只读。数据已缓存,plain python3 即可(无需联网)。
"""
import glob
import os

import numpy as np
import pandas as pd

import btlib

DATA_ETF = os.path.join(os.path.dirname(__file__), "data_etf")
LOOK, TOPK, TOPN = 126, 3, 6
LIQ_WIN, LIQ_MIN = 20, 1e8  # 流动性闸:amount 近 20 日均值 ≥ 1 亿


# ---------- 自写 loader：读 data_etf/etf_*.csv（btlib.load_panel 读的是 data/ 指数）----------
def load_etf_panel() -> dict[str, pd.DataFrame]:
    """{code: DataFrame[index=date, open/high/low/close/volume/amount]}。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(DATA_ETF, "etf_*.csv"))):
        code = os.path.basename(f)[4:-4]  # etf_<code>.csv
        df = pd.read_csv(f, parse_dates=["date"]).sort_values("date").set_index("date")
        out[code] = df
    return out


panel = load_etf_panel()
manifest = pd.read_csv(os.path.join(DATA_ETF, "manifest_etf.csv"), dtype={"code": str})
NAME = dict(zip(manifest["code"], manifest["name"]))

closes = pd.DataFrame({c: df["close"] for c, df in panel.items()}).sort_index()
amounts = pd.DataFrame({c: df["amount"] for c, df in panel.items()}).sort_index()
rets = closes.pct_change()
cd = btlib.cash_daily()
idx = closes.index
DECIDE = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)

# 流动性掩码:amount 20 日均值 ≥ LIQ_MIN（在决策日按 ≤d 数据算，防前视）
amt_ma = amounts.rolling(LIQ_WIN, min_periods=LIQ_WIN).mean()


def greedy_lowcorr(ordered, corr):
    """ordered=按动量降序的候选;从动量第1个起,依次加"对已选平均|相关|最低"的。"""
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


def book(mode, topn=TOPN, liq_gate=False):
    """mode∈{naive,corr}。返回(组合日收益(从首次有仓位起), book内平均两两相关均值)。"""
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    intra = []  # 每月所选 book 的平均两两相关（验机制）
    nsel = []   # 每月入选候选池规模（验扩张型截面：池子随历史变厚）
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        mom = (c.iloc[-1] / c.iloc[-(LOOK + 1)] - 1).dropna()  # 扩张截面：历史不足者自动 NaN→剔除
        if liq_gate:
            ok = amt_ma.loc[d].reindex(mom.index)
            mom = mom[ok >= LIQ_MIN]
        nsel.append(len(mom))
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
    return port[started], float(np.mean(intra)), (min(nsel) if nsel else 0, max(nsel) if nsel else 0)


def volscale(g, tv=0.15):
    rv = g.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    e = (tv / rv).clip(upper=1).shift(1).fillna(0)
    return e * g + (1 - e) * cd


def last_book(mode, topn=TOPN, liq_gate=False):
    """最近一个决策日的实际选券（直观展示 book，验"是否全挤同一主题"）。"""
    d = DECIDE[-1]
    c = closes.loc[:d]
    mom = (c.iloc[-1] / c.iloc[-(LOOK + 1)] - 1).dropna()
    if liq_gate:
        ok = amt_ma.loc[d].reindex(mom.index)
        mom = mom[ok >= LIQ_MIN]
    top = mom.sort_values(ascending=False)
    if mode == "naive":
        pick = list(top.head(TOPK).index)
    else:
        cand = list(top.head(min(topn, len(top))).index)
        corr = rets.loc[:d].iloc[-LOOK:][cand].corr()
        pick = greedy_lowcorr(cand, corr)
    return d, [(p, NAME.get(p, p), top[p]) for p in pick]


if __name__ == "__main__":
    print(f"=== 38 ETF 拥挤度/低相关叠加 | {closes.index[0].date()}~{closes.index[-1].date()} "
          f"| {len(closes.columns)} 个标的 ===\n")

    print("--- A. 无流动性闸 ---")
    for label, mode in [("朴素 top3", "naive"), ("低相关 top3", "corr")]:
        g, ic, (nmin, nmax) = book(mode)
        print(f"{label:<13}{btlib.fmt(btlib.perf(g))}  book内平均相关={ic:.2f}  截面池={nmin}~{nmax}")
        pv = volscale(g)
        print(f"{label}+vol@15 {btlib.fmt(btlib.perf(pv))}")
        print()

    print("--- B. 叠流动性闸(amount 近 20 日均值 ≥ 1 亿) ---")
    for label, mode in [("朴素 top3", "naive"), ("低相关 top3", "corr")]:
        g, ic, (nmin, nmax) = book(mode, liq_gate=True)
        print(f"{label:<13}{btlib.fmt(btlib.perf(g))}  book内平均相关={ic:.2f}  截面池={nmin}~{nmax}")
        pv = volscale(g)
        print(f"{label}+vol@15 {btlib.fmt(btlib.perf(pv))}")
        print()

    print("=== 稳健性: TOPN 候选池敏感性(低相关 top3,无闸,验非刀尖参数) ===")
    for tn in (5, 6, 8):
        g, ic, _ = book("corr", topn=tn)
        m = btlib.perf(g)
        print(f"TOPN={tn}: CAGR={m['cagr']:.2%} 回撤={m['maxdd']:.1%} Calmar={m['calmar']:.2f} 相关={ic:.2f}")

    print("\n=== 最近决策日实际选券(验'是否全挤同一主题') ===")
    for label, mode in [("朴素 top3", "naive"), ("低相关 top3", "corr")]:
        d, picks = last_book(mode)
        s = "  ".join(f"{nm}({code},动量{mv:+.1%})" for code, nm, mv in picks)
        print(f"{label} @ {d.date()}: {s}")
