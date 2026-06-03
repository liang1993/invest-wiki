#!/usr/bin/env python3
"""审计 2+1续: 独立重算 perf 指标 + bt1 状态机/bt2 日内止损防前视。"""
import numpy as np
import pandas as pd
import btlib

# ========== 审计 2: 独立重算 perf ==========
print("="*70)
print("审计 2: 独立手算 perf 指标（不复用 btlib.perf 公式）")
print("="*70)
df = btlib.load_one("sh000935")  # 中证信息技术
bh = df["close"].pct_change()
sig = (df["close"] > btlib.sma(df["close"], 200)).astype(float)
r = btlib.apply_signal(bh, sig)
m = btlib.perf(r)

# 独立重算
rr = r.dropna()
n = len(rr)
eq = (1 + rr).cumprod()
# CAGR: 用 (终值/初值)^(252/n) - 1，初值=1
my_cagr = eq.iloc[-1] ** (252.0/n) - 1
# vol: 日std * sqrt(252)
my_vol = rr.std(ddof=1) * np.sqrt(252)   # pandas .std() 默认 ddof=1
# Sharpe: 年化均值 / 年化vol
my_sharpe = (rr.mean()*252) / my_vol
# MaxDD: 独立用 numpy 滚动峰值
arr = eq.values
peak = np.maximum.accumulate(arr)
dd = arr/peak - 1
my_maxdd = dd.min()
# Calmar
my_calmar = my_cagr/abs(my_maxdd)

print(f"{'指标':<10}{'btlib':>14}{'独立手算':>14}{'差异':>12}")
for nm, a, b in [("CAGR", m['cagr'], my_cagr), ("vol", m['vol'], my_vol),
                 ("Sharpe", m['sharpe'], my_sharpe), ("MaxDD", m['maxdd'], my_maxdd),
                 ("Calmar", m['calmar'], my_calmar)]:
    print(f"{nm:<10}{a:>14.6f}{b:>14.6f}{abs(a-b):>12.2e}")

# 检查 pandas std ddof：btlib 用 ret.std() 默认 ddof=1
print(f"\n[std ddof 检查] btlib 用 ret.std() → ddof={'1 (样本)' }; 年化 vol 差异 ddof0 vs ddof1:")
print(f"  ddof=1 vol={rr.std(ddof=1)*np.sqrt(252):.6f}  ddof=0 vol={rr.std(ddof=0)*np.sqrt(252):.6f}")

# ========== 审计 1续: bt1 状态机防前视 ==========
print("\n" + "="*70)
print("审计 1续: bt1 移动止损状态机 — 信号 t 日产出，apply_signal 再 shift(1)")
print("="*70)
import bt1_single_asset as bt1
# 用一个有明确止损触发的标的
sig_ts = bt1.sig_trailing(df, "pct", 0.20)
# 状态机产出的 sig 是 0/1，apply_signal 内部 shift(1)。
# 验证：sig[t] 只用了 close[<=t]（状态机循环里 close[t]、peak=max(过去..t)）
# 人为篡改 close[t+50] 不应改变 sig[<=t+49]
df2 = df.copy()
ti = 2000
df2.iloc[ti+50, df2.columns.get_loc("close")] *= 1.5
sig_ts2 = bt1.sig_trailing(df2, "pct", 0.20)
# sig 在 [0..ti+49] 应不变（因为篡改的是 ti+50，且 reentry 用 SMA100 当日值）
# 注意 SMA100 是滚动均值，close[ti+50] 改变只影响 sma[ti+50..ti+149]，不影响更早
diff_before = (sig_ts.iloc[:ti+50].values != sig_ts2.iloc[:ti+50].values).sum()
print(f"篡改 close[t={ti+50}] 后，sig 在 [0..t-1] 改变的天数 = {diff_before}  (应=0)")
print(f"  [{'通过：状态机仅用≤t数据' if diff_before==0 else '❌ 前视泄漏'}]")

# 验证 apply_signal 的 pos[t]=sig[t-1]
pos = sig_ts.shift(1).fillna(0)
# 找一个 sig 0→1 的切换点，确认 pos 滞后一天
chg = sig_ts.diff().fillna(0)
first_entry = chg[chg>0].index[0]
loc = df.index.get_loc(first_entry)
print(f"\n首次进场信号日 {first_entry.date()}: sig={sig_ts.iloc[loc]:.0f}, "
      f"pos(已生效)={pos.iloc[loc]:.0f} (应=0,昨天还没信号), pos[t+1]={pos.iloc[loc+1]:.0f} (应=1)")

# ========== 审计 1续: bt2 日内止损防前视 ==========
print("\n" + "="*70)
print("审计 1续: bt2 build_weights 日内止损 — W 未 shift，portfolio_ret 里 W.shift(1)")
print("="*70)
import bt2_rotation as bt2
close, high, low, ret, fv = bt2.build_matrices()
mom, hist, ma, atr = bt2.precompute_indicators(close, high, low)
W = bt2.build_weights(close, ret, mom, hist, ma, atr, topk=3, dd_stop=0.20)
# W[t] 是 t 日「目标权重」，日内止损用 close[<=t]。portfolio_ret 用 W.shift(1)。
# 验证：篡改 close[t+30] 不改变 W[<=t]
close2 = close.copy()
tj = 1500
ccol = close2.columns[0]
close2.iloc[tj+30, close2.columns.get_loc(ccol)] *= 0.5  # 制造一个暴跌触发止损
mom2 = close2 / close2.shift(126) - 1.0
W2 = bt2.build_weights(close2, ret, mom2, hist, ma, atr, topk=3, dd_stop=0.20)
dW_before = (W.iloc[:tj+30] - W2.iloc[:tj+30]).abs().sum().sum()
print(f"篡改 close[t={tj+30}] 后，W 在 [0..t-1] 的总变化 = {dW_before:.2e}  (应=0)")
print(f"  [{'通过：日内止损仅用≤t数据' if dW_before<1e-12 else '❌ 前视泄漏'}]")

# 验证 portfolio_ret 的 pos=W.shift(1)：组合收益 port[t] 用 W[t-1]
pr = bt2.portfolio_ret(W, ret, cost_bps=0)
# 篡改 ret[t]（当日标的收益）只影响 port[t]，不影响 port[<t]
ret3 = ret.copy()
ret3.iloc[tj, ret3.columns.get_loc(ccol)] += 0.5
pr3 = bt2.portfolio_ret(W, ret3, cost_bps=0)
dpr_before = (pr.iloc[:tj] - pr3.iloc[:tj]).abs().max()
print(f"篡改 ret[t={tj}] 后，port 在 [0..t-1] 最大变化 = {dpr_before:.2e}  (应=0)")
print(f"  [{'通过' if dpr_before<1e-15 else '❌'}]")
