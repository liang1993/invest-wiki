#!/usr/bin/env python3
"""审计 6: 过拟合诚实度 + bt2 长史 ATR 主张 + 成本shift细节。
(a) 确认 5b 的 pts 计算（修我自己的打印 bug）
(b) bt2 长史 ATR -50% vs others -65% 主张是否成立（独立引擎复核）
(c) bt2 portfolio_ret 成本 shift(1) 是否双重 shift（W已shift，cost又shift）
(d) 区分族级结论 vs 样本依赖参数：跨子样本一致性矩阵
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
LOOK = 126

# ---- (a) 修正 5b 打印 ----
def run_topk(topk, lo=None, hi=None):
    real_hist = closes.notna().cumsum()
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK+1: continue
        last=c.iloc[-1]; prev=c.iloc[-(LOOK+1)]
        mom=(last/prev-1.0); ok=real_hist.loc[d]>=(LOOK+1)
        mom=mom[ok & mom.notna()]
        top=mom.sort_values(ascending=False).head(topk)
        for code in top.index: Wdec.loc[d,code]=1.0/topk
    Wsh=Wdec.reindex(closes.index,method="ffill").fillna(0.0).shift(1).fillna(0.0)
    cw=(1-Wsh.sum(axis=1)).clip(lower=0)
    port=(Wsh*rets).sum(axis=1)+cw*cd
    started=(Wsh.sum(axis=1)>0).cummax(); port=port[started]
    if lo: port=port[(port.index>=lo)&(port.index<=hi)]
    return port
def mdd(p): eq=(1+p).cumprod(); return float((eq/eq.cummax()-1).min())

t1=run_topk(1,"2016-01-01","2026-12-31"); t3=run_topk(3,"2016-01-01","2026-12-31")
print(f"(a) 5b pts 修正: top1 回撤={mdd(t1):.2%}, top3 回撤={mdd(t3):.2%}, "
      f"分散贡献={(mdd(t1)-mdd(t3))*100:+.1f}pts (findings 报 -15.5pts)")

# ---- (b) bt2 长史 ATR 主张：全史 ATR3.0 -50.19% vs SMA200 -60.62% / 基线 -65.60% ----
print("\n(b) bt2 长史 ATR 主张复核（用 bt2 自己的引擎，全史）:")
import bt2_rotation as bt2
close, high, low, ret2, fv = bt2.build_matrices()
mom, hist, ma, atr = bt2.precompute_indicators(close, high, low)
for label, kw in [("基线top3", dict(topk=3)), ("SMA200", dict(topk=3,ma_key=("sma",200))),
                  ("ATR3.0x", dict(topk=3,atr_k=3.0))]:
    W = bt2.build_weights(close, ret2, mom, hist, ma, atr, **kw)
    p = bt2.portfolio_ret(W, ret2, cost_bps=0).dropna()
    m = btlib.perf(p)
    print(f"  {label:<10} 全史 CAGR={m['cagr']:.2%} 回撤={m['maxdd']:.2%} Calmar={m['calmar']:.2f}  (findings: ATR -50.19%)")

# ---- (c) bt2 成本 shift 细节 ----
print("\n(c) bt2 portfolio_ret 成本 shift 检查:")
print("    代码: turnover=W.diff()(信号日); cost=(0.5*turnover*c).shift(1)")
print("    收益: gross 用 pos=W.shift(1)。成本 shift(1) 把'信号日换手'对齐到'生效日'。")
print("    → W.diff() 在信号日 t，cost.shift 后落在 t+1，与 pos=W.shift(1) 的生效日一致。逻辑自洽，无双重penalty。")
# 数值验证：一次完整换仓的成本是否=0.5*Σ|ΔW|*c 一次
W = bt2.build_weights(close, ret2, mom, hist, ma, atr, topk=3)
r0 = bt2.portfolio_ret(W, ret2, cost_bps=0)
r10 = bt2.portfolio_ret(W, ret2, cost_bps=10)
tot_cost = (r0 - r10).sum()  # 全期成本累加(近似)
turn_sum = (0.5*W.diff().abs().sum(axis=1)).sum()
expected = turn_sum * 10/1e4
print(f"    全期 (r0-r10) 累加={tot_cost:.4f}; 预期 0.5Σ|ΔW|×10bps={expected:.4f}; "
      f"比值={tot_cost/expected:.3f} (应≈1)")

# ---- (d) 族级 vs 参数级：跨样本一致性 ----
print("\n(d) 族级结论 vs 样本依赖参数 — 跨窗口一致性:")
windows = [("全史2010+", "2010-01-01","2026-12-31"),
           ("2016+","2016-01-01","2026-12-31"),
           ("2019+(全17截面)","2019-08-16","2026-12-31")]
def run_ma(ma_len, lo, hi):
    MA = closes.rolling(ma_len, min_periods=ma_len).mean()
    real_hist = closes.notna().cumsum()
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c=closes.loc[:d]
        if len(c)<LOOK+1: continue
        last=c.iloc[-1];prev=c.iloc[-(LOOK+1)]
        mom=(last/prev-1.0);ok=real_hist.loc[d]>=(LOOK+1);mom=mom[ok&mom.notna()]
        mav=MA.loc[d];mom=mom[(last>mav).reindex(mom.index).fillna(False)]
        top=mom.sort_values(ascending=False).head(3)
        for code in top.index: Wdec.loc[d,code]=1/3
    Wsh=Wdec.reindex(closes.index,method="ffill").fillna(0.0).shift(1).fillna(0.0)
    cw=(1-Wsh.sum(axis=1)).clip(lower=0);port=(Wsh*rets).sum(axis=1)+cw*cd
    started=(Wsh.sum(axis=1)>0).cummax();port=port[started]
    port=port[(port.index>=lo)&(port.index<=hi)]
    return btlib.perf(port)
print(f"{'窗口':<18}{'SMA50回撤':>11}{'SMA200回撤':>12}{'SMA250回撤':>12}  哪个MA压回撤更优")
for wn,lo,hi in windows:
    m50=run_ma(50,lo,hi);m200=run_ma(200,lo,hi);m250=run_ma(250,lo,hi)
    best=min([('SMA50',m50['maxdd']),('SMA200',m200['maxdd']),('SMA250',m250['maxdd'])],key=lambda x:-x[1])
    print(f"{wn:<18}{m50['maxdd']:>11.1%}{m200['maxdd']:>12.1%}{m250['maxdd']:>12.1%}   {best[0]}")
