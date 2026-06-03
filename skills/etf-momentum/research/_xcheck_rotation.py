#!/usr/bin/env python3
"""独立交叉校验（主 agent 自核，非 BT-2 产出）：最小版 6 月动量 top-3 月度轮动，
对比 纯动量 vs +200SMA趋势过滤 的 headline 指标。用来对撞 BT-2 的结果，catch 前视/逻辑 bug。

防前视：月末收盘定权重，shift(1) 次日生效。现金 1.8%/年。
"""
import numpy as np
import pandas as pd

import btlib

panel = btlib.load_panel()
closes = pd.DataFrame({c: df["close"] for c, df in panel.items()}).sort_index()
rets = closes.pct_change()
cd = btlib.cash_daily()

# 月末决策日 = 每月最后一个交易日
idx = closes.index
month_end = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
DECIDE = pd.DatetimeIndex(month_end.values)

LOOK, TOPK = 126, 3


def run(use_ma200: bool):
    Wdec = pd.DataFrame(0.0, index=DECIDE, columns=closes.columns)
    for d in DECIDE:
        c = closes.loc[:d]
        if len(c) < LOOK + 1:
            continue
        last, prev = c.iloc[-1], c.iloc[-(LOOK + 1)]
        mom = (last / prev - 1).dropna()
        if use_ma200:
            window = c.iloc[-200:]
            ma = window.mean().where(window.notna().sum() >= 200)  # 真 min_periods,不 skipna
            above = last > ma
            mom = mom[above.reindex(mom.index).fillna(False)]
        top = mom.sort_values(ascending=False).head(TOPK)
        for code in top.index:
            Wdec.loc[d, code] = 1.0 / TOPK  # 等权；不足 TOPK 余额自动留现金
    Wdaily = Wdec.reindex(closes.index, method="ffill").fillna(0.0)
    Wsh = Wdaily.shift(1).fillna(0.0)             # 防前视：次日生效
    cash_w = 1.0 - Wsh.sum(axis=1)
    port = (Wsh * rets).sum(axis=1) + cash_w * cd
    invested = Wsh.sum(axis=1) > 0
    port = port[invested.cummax()]                # 从首次建仓起算
    avg_cash = float(cash_w[invested.cummax()].mean())
    return port, avg_cash


for label, ma in [("纯动量 top3", False), ("动量 top3 +200SMA", True)]:
    port, avg_cash = run(ma)
    m = btlib.perf(port)
    print(f"{label:<20} {btlib.fmt(m)} 平均现金={avg_cash:.0%}  "
          f"({port.index[0].date()}~{port.index[-1].date()})")
