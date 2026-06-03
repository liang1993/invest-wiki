#!/usr/bin/env python3
"""审计 3续: 量化 champion MA skipna 瑕疵对 headline 的影响。
对比：原版 gross_book(skipna MA) vs 修正版(min_periods=ma_len 的真 SMA)。
若 200SMA / 200SMA+vol@15 的 headline 数字变化 <0.5pt → 瑕疵无害。
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
LOOK, TOPK = 126, 3

# 预算真·SMA（min_periods=n，不足n天为NaN）
def proper_ma(n):
    return closes.apply(lambda s: s.rolling(n, min_periods=n).mean())

def gross_book(eligibility, ma_len=200, fix_ma=False):
    if eligibility.startswith("ma") and fix_ma:
        MA_df = proper_ma(ma_len)
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        last, prev = c.iloc[-1], c.iloc[-(LOOK + 1)]
        mom = (last / prev - 1).dropna()
        if eligibility.startswith("ma"):
            if fix_ma:
                ma = MA_df.loc[d]
            else:
                ma = c.iloc[-ma_len:].mean()   # 原版 skipna
            mom = mom[(last > ma).reindex(mom.index).fillna(False)]
        elif eligibility == "tsmom":
            mom = mom[mom > 0]
        top = mom.sort_values(ascending=False).head(TOPK)
        for code in top.index:
            Wdec.loc[d, code] = 1.0 / TOPK
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0.0).shift(1).fillna(0.0)
    cash_w = 1.0 - Wsh.sum(axis=1)
    port = (Wsh * rets).sum(axis=1) + cash_w * cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    return port[started]

def vol_scale(gross, tv=0.15):
    rv = gross.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
    expo = (tv / rv).clip(upper=1.0).shift(1).fillna(0.0)
    return expo * gross + (1.0 - expo) * cd

def show(label, port):
    m = btlib.perf(port)
    print(f"{label:<28} CAGR={m['cagr']:.2%} 回撤={m['maxdd']:.2%} Calmar={m['calmar']:.2f} Sharpe={m['sharpe']:.2f}")

print("="*78)
print("champion MA skipna 瑕疵 影响量化（原版 vs 修正版 min_periods MA）")
print("="*78)
print("--- 纯动量基线（不含MA，应完全一致）---")
show("基线 (无MA)", gross_book("none"))

print("\n--- 200SMA 单用 ---")
g_ma_orig = gross_book("ma200", 200, fix_ma=False)
g_ma_fix  = gross_book("ma200", 200, fix_ma=True)
show("200SMA 原版(skipna)", g_ma_orig)
show("200SMA 修正(min_periods)", g_ma_fix)

print("\n--- 200SMA + vol@15 (headline 冠军) ---")
show("200SMA+vol@15 原版", vol_scale(g_ma_orig))
show("200SMA+vol@15 修正", vol_scale(g_ma_fix))

print("\n--- MA长度扫描 原版 vs 修正 (看结论方向是否变) ---")
print(f"{'MA':<8}{'原版 CAGR/回撤/Calmar':>30}{'修正 CAGR/回撤/Calmar':>30}")
for n in (50,100,150,200,250):
    go = gross_book("ma", n, fix_ma=False)
    gf = gross_book("ma", n, fix_ma=True)
    mo, mf = btlib.perf(go), btlib.perf(gf)
    print(f"SMA{n:<5}{mo['cagr']:>10.2%}/{mo['maxdd']:>7.1%}/{mo['calmar']:>5.2f}"
          f"{mf['cagr']:>13.2%}/{mf['maxdd']:>7.1%}/{mf['calmar']:>5.2f}")
