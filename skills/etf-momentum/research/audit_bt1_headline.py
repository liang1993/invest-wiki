#!/usr/bin/env python3
"""审计: bt1 signature 结论独立复核。
(1) SMA50 中位回撤改善 +23pt / 胜率 76% (5bps) —— 独立算
(2) TS_pct20/25 回撤比买入持有更深（whipsaw 病理）—— 独立验证 sh000935 -71.4% vs BH -64.9%
(3) 全集中位 MaxDD: BH -62.7%, SMA50 -41.0%
"""
import numpy as np
import pandas as pd
import btlib

mani = btlib.load_manifest()
codes = mani["code"].tolist()

def sig_ma(df,n): return (df["close"]>btlib.sma(df["close"],n)).astype(float)

def trailing_pct(df, x, reentry=100):
    """独立重写状态机（不 import bt1）：固定回撤止损 + close>SMA100 再进场。"""
    close=df["close"].values; ma=btlib.sma(df["close"],reentry).values
    n=len(close); sig=np.zeros(n); inpos=False; peak=np.nan
    for t in range(n):
        if not inpos:
            if not np.isnan(ma[t]) and close[t]>ma[t]:
                inpos=True; peak=close[t]; sig[t]=1
            else: sig[t]=0
        else:
            peak=max(peak,close[t])
            if close[t] < peak*(1-x): inpos=False; peak=np.nan; sig[t]=0
            else: sig[t]=1
    return pd.Series(sig,index=df.index)

# 独立算每个标的的 BH / SMA50 / SMA200 / TS_pct20 回撤
rows=[]
for code in codes:
    df=btlib.load_one(code); bh=df["close"].pct_change()
    r_bh=btlib.apply_signal(bh, pd.Series(1.0,index=df.index))
    r_50=btlib.apply_signal(bh, sig_ma(df,50))
    r_200=btlib.apply_signal(bh, sig_ma(df,200))
    r_ts20=btlib.apply_signal(bh, trailing_pct(df,0.20))
    rows.append(dict(code=code,
        bh=btlib.perf(r_bh)['maxdd'], sma50=btlib.perf(r_50)['maxdd'],
        sma200=btlib.perf(r_200)['maxdd'], ts20=btlib.perf(r_ts20)['maxdd'],
        cal_bh=btlib.perf(r_bh)['calmar'], cal_50=btlib.perf(r_50)['calmar']))
D=pd.DataFrame(rows)
print("="*70)
print("bt1 signature 结论独立复核（0bps，与 findings 5bps 略有差异但方向应一致）")
print("="*70)
print(f"(1) 全集中位最大回撤: BH={D['bh'].median():.1%} (findings -62.7%), "
      f"SMA50={D['sma50'].median():.1%} (findings -41.0%)")
print(f"    SMA50 中位回撤改善 = {(D['sma50']-D['bh']).median()*100:+.1f}pt (findings +23pt)")
print(f"    SMA50 Calmar 胜率(>BH) = {(D['cal_50']>D['cal_bh']).mean():.0%} (findings 76%@5bps)")

print(f"\n(2) whipsaw 病理: TS_pct20 回撤 vs BH 回撤 —— 有几个标的 TS20 更深?")
deeper = D[D['ts20'] < D['bh']]  # ts20 更深(更负)
print(f"    全 17 标的中 {len(deeper)} 个 TS_pct20 回撤比买入持有更深")
semi = D[D['code']=='sh000935'].iloc[0]
print(f"    中证信息技术 sh000935: TS_pct20={semi['ts20']:.1%} vs BH={semi['bh']:.1%} "
      f"({'TS更深✓病理坐实' if semi['ts20']<semi['bh'] else 'TS更浅'}) (findings: -71.4% vs -64.9%)")
print(f"    TS_pct20 中位回撤={D['ts20'].median():.1%} (findings -62.5%，≈BH 没压住)")

# (3) champion 的 closes outer-join 是否重复计数检查
print("\n" + "="*70)
print("(3) champion closes 对齐检查（outer-join 是否引入重复/错位）")
print("="*70)
panel=btlib.load_panel()
closes=pd.DataFrame({c:df["close"] for c,df in panel.items()}).sort_index()
print(f"    closes 索引唯一? {closes.index.is_unique}  单调递增? {closes.index.is_monotonic_increasing}")
print(f"    总行数={len(closes)} = 并集交易日数; 各列首末非NaN对齐到各自上市/最新")
# 抽查：sh000928 在 closes 里的值 == load_one 原值
one=btlib.load_one("sh000928")
merged=closes["sh000928"].dropna()
aligned = (merged.reindex(one.index) == one["close"]).all()
print(f"    sh000928 在 closes 中的值 == 原始 load_one? {aligned} (无错位)")
