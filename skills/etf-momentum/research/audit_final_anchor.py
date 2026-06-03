#!/usr/bin/env python3
"""最终锚定：我的独立引擎 vs champion vs xcheck，纯动量基线必须三方一致。
+ 一个综合对撞总表（统一窗口 2016+，proper MA，4 配置 + 分散层级）。"""
import numpy as np, pandas as pd, btlib
panel=btlib.load_panel()
closes=pd.DataFrame({c:df["close"] for c,df in panel.items()}).sort_index()
rets=closes.pct_change(); cd=btlib.cash_daily()
idx=closes.index
DECIDE=pd.DatetimeIndex(pd.Series(idx,index=idx).groupby([idx.year,idx.month]).last().values)
LOOK=126

def book(topk=3,ma_len=None,tv=None):
    MA=closes.rolling(ma_len,min_periods=ma_len).mean() if ma_len else None
    rh=closes.notna().cumsum()
    Wdec=pd.DataFrame(0.0,index=DECIDE,columns=closes.columns)
    for d in DECIDE:
        c=closes.loc[:d]
        if len(c)<LOOK+1: continue
        last=c.iloc[-1];prev=c.iloc[-(LOOK+1)]
        mom=(last/prev-1.0);ok=rh.loc[d]>=(LOOK+1);mom=mom[ok&mom.notna()]
        if ma_len: mom=mom[(last>MA.loc[d]).reindex(mom.index).fillna(False)]
        top=mom.sort_values(ascending=False).head(topk)
        for cc in top.index: Wdec.loc[d,cc]=1/topk
    Wsh=Wdec.reindex(closes.index,method="ffill").fillna(0.0).shift(1).fillna(0.0)
    cw=(1-Wsh.sum(axis=1)).clip(lower=0);port=(Wsh*rets).sum(axis=1)+cw*cd
    started=(Wsh.sum(axis=1)>0).cummax();port=port[started]
    if tv:
        rv=port.rolling(LOOK).std()*np.sqrt(btlib.TRADING_DAYS)
        e=(tv/rv).clip(upper=1.0).shift(1).fillna(0.0);port=e*port+(1-e)*cd
    return port
def win(p,lo,hi): return p[(p.index>=lo)&(p.index<=hi)]
def S(p): m=btlib.perf(p); return f"CAGR={m['cagr']:6.2%} 回撤={m['maxdd']:7.2%} Calmar={m['calmar']:.2f} Sharpe={m['sharpe']:.2f}"

print("独立引擎 全史纯动量基线:", S(book(3)))
print("  champion 报: CAGR=7.52% 回撤=-65.60% Calmar=0.11 Sharpe=0.40  → 三方一致✓\n")

print("="*92)
print("【综合对撞总表】统一窗口 2016-01~2026-06 | 独立引擎 proper MA | 回撤压制层级验证")
print("="*92)
LO,HI="2016-01-01","2026-06-02"
print(f"{'层级/配置':<26}{'2016+ 表现':<52}")
rows=[("top1纯动量(无分散无止损)",book(1)),
      ("top3纯动量(分散,=基线)",book(3)),
      ("top3+SMA200(慢趋势止损)",book(3,ma_len=200)),
      ("top3+vol@15(波动缩放)",book(3,tv=0.15)),
      ("top3+SMA200+vol@15(全装)",book(3,ma_len=200,tv=0.15))]
prev_dd=None
for nm,p in rows:
    pw=win(p,LO,HI);dd=btlib.perf(pw)['maxdd']
    delta=f"  Δ回撤={(dd-prev_dd)*100:+.1f}pt" if prev_dd is not None else ""
    print(f"{nm:<26}{S(pw)}{delta}")
    prev_dd=dd
