#!/usr/bin/env python3
"""bt5_combined —— 选股层(排序指标) × 仓位层(去相关+波动缩放) 叠加测试。

研究问题（BT-4 后续，决策性）：BT-4 证 ER 选股层单用 Calmar 0.19→0.25。但既有研究证
一阶杠杆在仓位层（去相关 top3 + vol@15 → Calmar 0.22）。**ER 的选股层 edge 能否堆在
仓位层之上？** 这是"是否把 momentum.py 排序口径从简单动量切到 ER"的判据——若被仓位层
吃掉（vol-scaling+去相关已捕获大部分收益），则切换冗余；若仍加分，才值得切。

═══ 公平性：复刻 crowding_overlay.py 的去相关+vol 机制（锚定其数字），唯一变量=排序信号 ═══
  - simple : 简单 126d 区间动量 P[t]/P[t-126]-1（现行 momentum.py 口径）
  - er     : 带方向 Kaufman 效率系数（BT-4 赢家）
对每个信号跑 {朴素 top3, 去相关 top3} × {无 vol, vol@15, vol@12}。
去相关 greedy / 波动缩放 / 现金 / 防前视 shift(1) / 原始 close（不 ffill）全部同 crowding_overlay。

锚点：simple 路径必须复现 crowding_overlay —— 朴素 top3 (7.52%/-65.60%)、
       低相关 top3 (7.71%/-50.08%)、低相关+vol@15 (Calmar 0.22 / -31.40% / Sharpe 0.51)。
数据：research/data/idx_*.csv（17 行业指数，sina 价格指数）。
"""
from __future__ import annotations

import sys

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
MAIN_START = "2016-01-01"


# ════════════════════════ 排序信号（截面，仅用 ≤d 数据）════════════════════════
def signal_at(c: pd.DataFrame, kind: str) -> pd.Series:
    """在日期 d（c=closes.loc[:d]）算各指数排序分。越大越强。dropna 即合格集。
    simple 与 er 的合格集恒等（都要求 -(LOOK+1) 处有有效价）。"""
    last, prev = c.iloc[-1], c.iloc[-(LOOK + 1)]
    if kind == "simple":
        return (last / prev - 1).dropna()
    direction = last - prev                                  # 位移（带方向）
    path = c.iloc[-(LOOK + 1):].diff().abs().sum()           # 路程 Σ|Δ|
    er = direction.abs() / path.replace(0.0, np.nan)         # Kaufman 效率系数∈[0,1]
    return (er * np.sign(direction)).dropna()                # 带方向：单边上涨→+1


# ════════════════════════ 去相关 greedy（同 crowding_overlay）════════════════════════
def greedy_lowcorr(ordered, corr):
    picked = [ordered[0]]                                    # 锚定信号最强
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


def book(kind: str, mode: str, topn: int = TOPN):
    """纯多头 top-3 等权 book 日收益（防前视）。kind=排序信号；mode∈{naive,corr}。"""
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    intra = []
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        s = signal_at(c, kind)
        top = s.sort_values(ascending=False)
        if len(top) < TOPK:
            continue
        if mode == "naive":
            pick = list(top.head(TOPK).index)
        else:
            cand = list(top.head(min(topn, len(top))).index)
            corr = rets.loc[:d].iloc[-LOOK:][cand].corr()
            pick = greedy_lowcorr(cand, corr)
        for code in pick:
            Wdec.loc[d, code] = 1.0 / TOPK
        if len(pick) == TOPK:
            cm = rets.loc[:d].iloc[-LOOK:][pick].corr().values
            intra.append((cm.sum() - TOPK) / (TOPK * (TOPK - 1)))
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0).shift(1).fillna(0)
    port = (Wsh * rets).sum(axis=1) + (1 - Wsh.sum(axis=1)) * cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    return port[started], float(np.mean(intra))


def volscale(g: pd.Series, tv: float = 0.15) -> pd.Series:
    rv = g.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    e = (tv / rv).clip(upper=1).shift(1).fillna(0)           # 防前视：截至昨日波动
    return e * g + (1 - e) * cd


def row(label, port, ic=None, start=None):
    p = port.loc[start:] if start else port
    m = btlib.perf(p)
    s = f"{label:<26}{btlib.fmt(m)}"
    if ic is not None:
        s += f" book相关={ic:.2f}"
    return s, m


# ════════════════════════ 主流程 ════════════════════════
def main():
    print("加载 + 跑 book …", file=sys.stderr)
    # 预跑 8 个 book（2 信号 × {朴素, 去相关}，各含 vol 派生）
    G = {}
    for kind in ("simple", "er"):
        for mode in ("naive", "corr"):
            g, ic = book(kind, mode)
            G[(kind, mode)] = (g, ic)

    # ════ 0. 锚点：simple 路径复现 crowding_overlay ════
    print("=" * 100)
    print("锚点校验：simple 路径应复现 crowding_overlay（朴素7.52%/-65.6%，低相关+vol@15 Calmar0.22/-31.4%）")
    print("=" * 100)
    gsn, icsn = G[("simple", "naive")]
    gsc, icsc = G[("simple", "corr")]
    s1, m1 = row("simple 朴素 top3", gsn, icsn)
    print(s1)
    s2, m2 = row("simple 低相关 top3", gsc, icsc)
    print(s2)
    s3, m3 = row("simple 低相关+vol@15", volscale(gsc, 0.15))
    print(s3)
    ok = (abs(m1["cagr"] - 0.0752) < 6e-4 and abs(m1["maxdd"] + 0.6560) < 6e-4
          and abs(m3["calmar"] - 0.22) < 0.01 and abs(m3["maxdd"] + 0.3140) < 6e-3)
    print(f"[{'OK 锚点通过' if ok else '✗ 不一致——停止'}]\n")
    if not ok:
        sys.exit(1)

    # ════ 1. 全史 2009+ 主表：8 配置（无 vol / vol@15 / vol@12）════
    for start, tag in [(None, "全史 2009-07 起（含早期 5-8 指数扩张池）"),
                       (MAIN_START, "主期 2016-01 起（全 17 指数池，去相关真正生效）")]:
        print("=" * 100)
        print(f"{tag}｜top3｜现金1.8%/年｜rf=0")
        print("=" * 100)
        cells = {}
        for kind in ("simple", "er"):
            for mode, mlabel in [("naive", "朴素"), ("corr", "去相关")]:
                g, ic = G[(kind, mode)]
                kn = {"simple": "简单动量", "er": "效率系数ER"}[kind]
                s, m = row(f"{kn} {mlabel} top3", g, ic, start=start)
                print(s)
                cells[(kind, mode, "none")] = m
                for tv in (0.15, 0.12):
                    s, m = row(f"{kn} {mlabel}+vol@{tv:.0%}", volscale(g, tv), start=start)
                    print(s)
                    cells[(kind, mode, f"vol{tv}")] = m
            print("-" * 100)
        # 决策对比：去相关+vol@15 与 +vol@12，ER vs simple
        print("◆ 决策对比（仓位层冠军配置上，ER 相对 简单动量 的增量）:")
        for cfg in ("vol0.15", "vol0.12"):
            b = cells[("simple", "corr", cfg)]
            e = cells[("er", "corr", cfg)]
            dC, dS = e["calmar"] - b["calmar"], e["sharpe"] - b["sharpe"]
            verdict = ("ER 加分" if (dC > 0.01 and dS > 0.02) else
                       "ER 拖累" if (dC < -0.01 or dS < -0.02) else "基本持平/被吃掉")
            tv = cfg.replace("vol", "")
            print(f"  去相关+vol@{float(tv):.0%}: simple Calmar={b['calmar']:.2f}/Sharpe={b['sharpe']:.2f} → "
                  f"ER Calmar={e['calmar']:.2f}/Sharpe={e['sharpe']:.2f}  "
                  f"(ΔCalmar={dC:+.2f} ΔSharpe={dS:+.2f}) → {verdict}")
        print()

    # ════ 2. 分子周期：冠军配置 simple vs ER（去相关+vol@15）════
    print("=" * 100)
    print("分子周期 总收益/最大回撤：去相关+vol@15，simple vs ER（过拟合/regime 检验）")
    print("=" * 100)
    periods = [
        ("2015H2-16熔断", "2015-06-15", "2016-12-31"),
        ("2017-18蓝筹熊", "2017-01-01", "2018-12-31"),
        ("2019-21成长牛", "2019-01-01", "2021-12-31"),
        ("2022-24熊", "2022-01-01", "2024-09-30"),
        ("2024Q4-26反弹", "2024-10-01", "2026-06-02"),
    ]
    champ = {"simple": volscale(G[("simple", "corr")][0], 0.15),
             "er": volscale(G[("er", "corr")][0], 0.15)}
    print(f"{'区间':<16}" + "".join(f"{k+'(总/回撤)':>24}" for k in ("simple", "er")))
    for name, lo, hi in periods:
        line = f"{name:<16}"
        for k in ("simple", "er"):
            seg = champ[k][(champ[k].index >= lo) & (champ[k].index <= hi)]
            tot = (1 + seg).prod() - 1 if len(seg) else float("nan")
            eq = (1 + seg).cumprod()
            dd = float((eq / eq.cummax() - 1).min()) if len(seg) else float("nan")
            line += f"{tot:>11.1%}/{dd:>9.1%}  "
        print(line)

    print("\n[done]", file=sys.stderr)


if __name__ == "__main__":
    main()
