#!/usr/bin/env python3
"""审计 4+5: 统一窗口对撞 + 独立复核两条 headline。
完全独立实现（不 import champion/bt2 的函数，只用 btlib 取数 + 自写引擎），
对撞 champion(全史) 与 bt2(2016+) 口径差。
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
LOOK, TOPK_DEFAULT = 126, 3

# ============ 独立引擎（从零写，proper min_periods MA，显式 ≥127 历史门槛）============
def run_engine(topk=3, ma_len=None, target_vol=None, dd_stop=None):
    """6M动量 top-k 月度轮动。ma_len: 现价>SMA(ma_len)才合格(proper min_periods).
    target_vol: 组合层波动缩放. dd_stop: 日内回撤止损(自进场峰值)."""
    # proper SMA
    MA = closes.rolling(ma_len, min_periods=ma_len).mean() if ma_len else None
    real_hist = closes.notna().cumsum()
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        last = c.iloc[-1]; prev = c.iloc[-(LOOK+1)]
        mom = (last/prev - 1.0)
        # 显式门槛：真实历史 >= LOOK+1
        ok = real_hist.loc[d] >= (LOOK+1)
        mom = mom[ok & mom.notna()]
        if ma_len:
            mav = MA.loc[d]
            mom = mom[(last > mav).reindex(mom.index).fillna(False)]
        top = mom.sort_values(ascending=False).head(topk)
        for code in top.index:
            Wdec.loc[d, code] = 1.0/topk
    Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0.0).shift(1).fillna(0.0)

    # 日内回撤止损（可选）：对已生效持仓按日跟踪峰值
    if dd_stop is not None:
        Wsh = apply_dd_stop(Wsh, dd_stop)

    cash_w = (1.0 - Wsh.sum(axis=1)).clip(lower=0)
    port = (Wsh*rets).sum(axis=1) + cash_w*cd
    started = (Wsh.sum(axis=1) > 0).cummax()
    port = port[started]; Wsh = Wsh[started]
    if target_vol is not None:
        rv = port.rolling(LOOK).std()*np.sqrt(btlib.TRADING_DAYS)
        expo = (target_vol/rv).clip(upper=1.0).shift(1).fillna(0.0)
        port = expo*port + (1.0-expo)*cd
    return port

def apply_dd_stop(Wsh, dd):
    """对已生效权重矩阵做日内回撤止损：持仓自进场峰值回撤≥dd则当日剔出(置0)。"""
    W = Wsh.copy().values
    cols = list(Wsh.columns); pxs = closes.reindex(Wsh.index).values
    peak = {}
    for i in range(len(W)):
        for j in range(len(cols)):
            if W[i,j] > 0:
                p = pxs[i,j]
                if np.isnan(p): continue
                pk = peak.get(j, p)
                if p > pk: pk = p; peak[j]=pk
                if pk>0 and (p/pk-1.0) <= -dd:
                    W[i,j] = 0.0; peak.pop(j,None)
            else:
                peak.pop(j,None)
    return pd.DataFrame(W, index=Wsh.index, columns=cols)

def maxdd(p):
    eq=(1+p).cumprod(); return float((eq/eq.cummax()-1).min())
def stats(p):
    m=btlib.perf(p); return m['cagr'], m['maxdd'], m['calmar'], m['sharpe']

def win(p, lo, hi):
    return p[(p.index>=lo)&(p.index<=hi)]

# ============ 审计 4: 统一窗口对撞（都取 2016-01~2026-06）============
print("="*86)
print("审计4: 统一窗口对撞 2016-01-01 ~ 2026-06-02（独立引擎，proper MA）")
print("  对比 基线 / 200SMA / vol@15 / 200SMA+vol@15 —— 确认结论方向一致")
print("="*86)
LO, HI = "2016-01-01", "2026-06-02"
configs = {
    "基线(top3纯动量)": run_engine(3),
    "200SMA": run_engine(3, ma_len=200),
    "vol@15": run_engine(3, target_vol=0.15),
    "200SMA+vol@15": run_engine(3, ma_len=200, target_vol=0.15),
}
print(f"{'配置':<22}{'CAGR':>9}{'最大回撤':>11}{'Calmar':>9}{'Sharpe':>9}")
for k,p in configs.items():
    pw = win(p, LO, HI)
    cg,dd,cal,sh = stats(pw)
    print(f"{k:<22}{cg:>9.2%}{dd:>11.2%}{cal:>9.2f}{sh:>9.2f}")

# 同一引擎全史口径（对比 champion 的全史数字）
print(f"\n  [同引擎全史 2010+ 口径，对比 champion 全史]")
print(f"{'配置':<22}{'CAGR':>9}{'最大回撤':>11}{'Calmar':>9}")
for k,p in configs.items():
    cg,dd,cal,sh = stats(p)
    print(f"{k:<22}{cg:>9.2%}{dd:>11.2%}{cal:>9.2f}")

# ============ 审计 5a: vol-scaling 把全史回撤 -65%→-38% ============
print("\n" + "="*86)
print("审计5a: 独立复核「vol-scaling 把全史最大回撤 ~-65% 砍到 ~-38%」")
print("="*86)
base = run_engine(3)  # 纯动量全史
volp = run_engine(3, target_vol=0.15)
_,dd_base,_,_ = stats(base)
_,dd_vol,_,_ = stats(volp)
print(f"  全史纯动量基线 最大回撤 = {dd_base:.2%}   (champion 报 -65.6%)")
print(f"  全史 vol@15      最大回撤 = {dd_vol:.2%}   (champion 报 -38.5%)")
print(f"  → 回撤压制 = {dd_base-dd_vol:+.1%}  [{'复现' if abs(dd_base-(-0.656))<0.03 and abs(dd_vol-(-0.385))<0.03 else '⚠️偏差'}]")

# ============ 审计 5b: top1→top3 分散贡献 -15.5pts（2016 起）============
print("\n" + "="*86)
print("审计5b: 独立复核「bt2 的 top1→top3 分散贡献 -15.5pts 回撤」(2016起)")
print("  注意：top1 数字(-56.65%)在任何脚本里都查不到，仅 findings.md 出现 → 必须独立算")
print("="*86)
top1 = win(run_engine(topk=1), "2016-01-01", "2026-12-31")
top3 = win(run_engine(topk=3), "2016-01-01", "2026-12-31")
_,dd1,_,_ = stats(top1); cg1=btlib.perf(top1)['cagr']
_,dd3,_,_ = stats(top3); cg3=btlib.perf(top3)['cagr']
print(f"  top1 纯动量(2016+): CAGR={cg1:.2%} 最大回撤={dd1:.2%}   (findings 报 8.23%/-56.65%)")
print(f"  top3 纯动量(2016+): CAGR={cg3:.2%} 最大回撤={dd3:.2%}   (findings 报 7.87%/-41.13%)")
print(f"  → 分散贡献 = {dd1-dd3:+.1f}pts  (findings 报 -15.5pts)  "
      f"[{'复现' if abs((dd1-dd3)-(-0.155))<0.03 else '⚠️偏差'}]")
