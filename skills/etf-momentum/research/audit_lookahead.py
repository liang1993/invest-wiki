#!/usr/bin/env python3
"""审计 1: 防前视泄漏的逐点核查。
重点检查 champion.vol_scale 的 rv 是否真干净：
rv = gross.rolling(126).std() —— rolling 窗口截至当日 t（含 t）。
expo = (target/rv).clip().shift(1) —— shift 后 expo[t] 用的是 rv[t-1]，
而 rv[t-1] = std(gross[t-126 .. t-1])，全部是 t 日之前的收益。
今日组合 = expo[t]*gross[t]，expo[t] 只含 ≤t-1 信息 → 干净。
但要确认：gross 本身是否已防前视（gross_book 里 Wsh 已 shift(1)）。
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

# 复制 champion.gross_book 的逻辑，但显式检查 shift
Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
for d in DECIDE:
    c = closes.loc[:d]
    if len(c) < LOOK + 1:
        continue
    last, prev = c.iloc[-1], c.iloc[-(LOOK + 1)]
    mom = (last / prev - 1).dropna()
    top = mom.sort_values(ascending=False).head(TOPK)
    for code in top.index:
        Wdec.loc[d, code] = 1.0 / TOPK
Wsh = Wdec.reindex(closes.index, method="ffill").fillna(0.0).shift(1).fillna(0.0)
cash_w = 1.0 - Wsh.sum(axis=1)
gross = (Wsh * rets).sum(axis=1) + cash_w * cd
started = (Wsh.sum(axis=1) > 0).cummax()
gross = gross[started]

# 关键测试：vol_scale 的 expo 是否只依赖过去
rv = gross.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
expo = (0.15 / rv).clip(upper=1.0).shift(1).fillna(0.0)

# 测试 A: expo[t] 与 gross[t] 是否独立？人为把 gross 的某一天放大 100 倍，
# 看 expo 在「同一天及之前」是否变化（若变，说明 expo[t] 偷看了 gross[t]）
test_date_i = 3000
gross2 = gross.copy()
gross2.iloc[test_date_i] *= 100  # 篡改第 3000 天的收益
rv2 = gross2.rolling(LOOK).std() * np.sqrt(btlib.TRADING_DAYS)
expo2 = (0.15 / rv2).clip(upper=1.0).shift(1).fillna(0.0)
# expo 在 [0, test_date_i] 应完全不变（含 test_date_i 本身）
diff_upto_t = (expo.iloc[:test_date_i+1] - expo2.iloc[:test_date_i+1]).abs().max()
diff_after_t = (expo.iloc[test_date_i+1:] - expo2.iloc[test_date_i+1:]).abs().max()
print(f"[vol_scale 前视测试] 篡改 gross[t={test_date_i}] 后:")
print(f"  expo 在 [0..t] 的最大变化 = {diff_upto_t:.2e}  (应=0，expo[t] 不得偷看 gross[t])")
print(f"  expo 在 (t..end] 的最大变化 = {diff_after_t:.2e}  (应>0，未来 expo 才受影响)")
assert diff_upto_t < 1e-15, "❌ 泄漏！expo[t] 偷看了 gross[t]"
print("  [通过] expo[t] 只依赖 gross[<=t-1]，vol_scale 无前视")

# 测试 B: 组合收益 port[t] = expo[t]*gross[t]，验证 port 篡改传播
port = expo * gross + (1.0 - expo) * cd
port2 = expo2 * gross2 + (1.0 - expo2) * cd
# port[t] 会变（因 gross2[t] 变），但 port[<t] 不应变
dport_before = (port.iloc[:test_date_i] - port2.iloc[:test_date_i]).abs().max()
print(f"\n[组合收益传播] port 在 [0..t-1] 的最大变化 = {dport_before:.2e}  (应=0)")
assert dport_before < 1e-15
print("  [通过] 历史组合收益不受未来篡改影响")

# 测试 C: gross_book 的 Wsh.shift(1) —— 月末决策日 d 的权重在 d 日是否生效？
# Wdec 在 DECIDE 日有值，ffill 后 shift(1)：d 日的目标权重在 d+1 日才进 Wsh
# 验证：找一个 DECIDE 日 d，Wsh 在该 d 日的值应等于「上一个交易日的目标」而非 d 日新目标
sample_d = DECIDE[100]
loc_d = closes.index.get_loc(sample_d)
target_at_d = Wdec.loc[sample_d]  # d 日新决策
applied_at_d = Wsh.iloc[loc_d]     # d 日实际生效
applied_next = Wsh.iloc[loc_d + 1] # d+1 日实际生效
print(f"\n[gross_book shift 验证] 决策日 {sample_d.date()}:")
print(f"  d 日新目标 nonzero codes: {list(target_at_d[target_at_d>0].index)}")
print(f"  d 日实际生效 nonzero:     {list(applied_at_d[applied_at_d>0].index)}  (应=上月旧仓)")
print(f"  d+1 日实际生效 nonzero:   {list(applied_next[applied_next>0].index)}  (应=d 日新目标)")
match = set(applied_next[applied_next>0].index) == set(target_at_d[target_at_d>0].index)
print(f"  d 日新目标 == d+1 实际生效? {match}  [{'通过' if match else '❌ 失败'}]")
