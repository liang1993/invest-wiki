#!/usr/bin/env python3
"""审计 3: 截面处理 — 扩张型 universe 的对齐/幸存者偏差/NaN skipna。
重点：
(a) champion.gross_book 用 closes（每个指数各自 index，未对齐到公共网格！）
    pd.DataFrame({c: df['close']}) 会自动外连接对齐，缺失处为 NaN。
(b) mom = (last/prev-1).dropna() —— 半导体 2019-08 才有数据，之前 last 或 prev 是 NaN→dropna 剔除，OK
(c) MA 过滤 ma = c.iloc[-ma_len:].mean() —— 对含 NaN 的列，.mean() skipna 默认 True，
    所以一个只有 50 天历史的指数，iloc[-200:].mean() 会用「能取到的非 NaN」算均值 → 可能假合格！
(d) (Wsh*rets).sum(axis=1) 的 0*NaN 问题
"""
import numpy as np
import pandas as pd
import btlib

panel = btlib.load_panel()
closes = pd.DataFrame({c: df["close"] for c, df in panel.items()}).sort_index()
print(f"公共网格行数={len(closes)}, 列={closes.shape[1]}")
print(f"各列首个非NaN日期:")
for c in closes.columns:
    print(f"  {c}: {closes[c].first_valid_index().date()}  非NaN数={closes[c].notna().sum()}")

# 关键问题 (c): champion 的 MA 用 c.iloc[-ma_len:].mean()，对刚上市指数会 skipna 假合格吗？
print("\n[问题c] champion gross_book MA 计算 skipna 风险:")
idx = closes.index
DECIDE = pd.DatetimeIndex(pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last().values)
rets = closes.pct_change()
# 模拟半导体 sz980017 (2019-08 上市) 在 2019-09 月末的 MA200 计算
semi = "sz980017"
first = closes[semi].first_valid_index()
print(f"  半导体 {semi} 上市日 {first.date()}")
# 找上市后第一个月末
dec_after = [d for d in DECIDE if d >= first][1]  # 第二个月末
c_slice = closes.loc[:dec_after]
ma200 = c_slice[semi].iloc[-200:].mean()  # champion 写法
real_hist = c_slice[semi].iloc[-200:].notna().sum()
last_px = c_slice[semi].iloc[-1]
print(f"  在 {dec_after.date()} 月末: iloc[-200:] 含真实历史 {real_hist} 天 (不足200)")
print(f"  MA200(skipna)={ma200:.1f}, 现价={last_px:.1f}, 现价>MA? {last_px>ma200}")
print(f"  → 仅 {real_hist} 天就被当 MA200 用（skipna），可能让新上市指数过早合格")

# 但关键：mom 是否也要求 LOOK+1 历史？gross_book 用 prev=c.iloc[-(LOOK+1)]
prev = c_slice[semi].iloc[-(126+1)]
print(f"  动量 prev=iloc[-127] = {prev} (NaN则该指数动量=NaN被dropna剔除)")
print(f"  → 动量门槛 LOOK+1=127 天才有非NaN prev，比 MA 的 skipna 更严，部分对冲了 (c)")

# 对比 bt2：bt2 用 hist_count>=126 显式门槛 + MA.at[d,c] 用真正的 rolling(min_periods=n)
print("\n[对比] bt2 用 btlib.sma(min_periods=n) → 不足 n 天为 NaN，且 hist_count>=126 显式过滤")
print("  → bt2 截面处理更严谨；champion 的 MA skipna 是潜在小瑕疵（下面量化影响）")

# 量化 (c) 的影响：champion 里有多少 (决策日,指数) 是「历史<ma_len 但被 skipna 判合格」
def gross_book_orig(ma_len=200):
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    flagged = 0
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < 126 + 1:
            continue
        last, prev = c.iloc[-1], c.iloc[-(126 + 1)]
        mom = (last / prev - 1).dropna()
        ma = c.iloc[-ma_len:].mean()
        elig = mom[(last > ma).reindex(mom.index).fillna(False)]
        # 检查 elig 里有没有真实历史<ma_len 的
        for code in elig.index:
            realh = c[code].iloc[-ma_len:].notna().sum()
            if realh < ma_len:
                flagged += 1
        top = elig.sort_values(ascending=False).head(3)
        for code in top.index:
            Wdec.loc[d, code] = 1/3
    return Wdec, flagged

Wd, flg = gross_book_orig(200)
print(f"\n  champion MA200: 共 {flg} 个(决策日×指数)出现「真实历史<200 但 skipna 判合格」")
print(f"  其中真正进入 top3 的影响需看 (d). 下面对比修正版")

# (d) 0*NaN 检查
print("\n[问题d] (Wsh*rets).sum(axis=1) 的 0*NaN:")
Wsh = Wd.reindex(closes.index, method="ffill").fillna(0.0).shift(1).fillna(0.0)
# 某指数上市前 rets=NaN，但 Wsh=0。0*NaN=NaN！sum 默认 skipna 会忽略 NaN
test = (Wsh * rets)
nan_cnt = test.isna().sum().sum()
print(f"  Wsh*rets 中 NaN 单元格数 = {nan_cnt}（0*NaN=NaN）")
print(f"  .sum(axis=1) 默认 skipna=True → 这些 NaN 被忽略，不污染组合收益")
# 验证：手动核对某天
port = (Wsh*rets).sum(axis=1)
print(f"  组合收益 NaN 天数 = {port.isna().sum()} (应仅极早期或无)")
print(f"  → 0*NaN=NaN 但 sum skipna 救了它；若哪天持仓指数 ret 真 NaN 会少算，但持仓必有≥126历史故 ret 非NaN")
