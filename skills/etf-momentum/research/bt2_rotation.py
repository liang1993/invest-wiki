#!/usr/bin/env python3
"""bt2_rotation —— 6 月动量行业轮动 + 趋势止损网格回测。

研究问题：在「6M 动量 top-K 行业轮动」里，哪种趋势止损最能压制组合回撤、缓解动量崩溃，
而不过度牺牲收益？

地基（btlib.py）：load_panel / sma / ema / atr / perf / cash_daily。
数据：research/data/idx_*.csv（17 个行业指数，sina 价格指数，无需复权，列 date/o/h/l/c/v）。

═══ 防前视铁律 ═══
- 月度再平衡：用月末收盘算动量排名 + MA 过滤，**次交易日起**持有。
- 每日权重矩阵 W（行=日，列=指数，行和≤1，缺额为现金）。组合收益用 W.shift(1) 与当日
  各指数收益相乘。绝不同日 look-ahead。
- 移动止损（回撤/ATR）按**日**检查：用 t 日(含)及之前的最高价/ATR 判定，t+1 日生效（同样 shift）。

═══ 扩张型截面 ═══
- 17 指数起点交错（5 个 2009、2 个 2011、399 系 2014-2015、半导体 2019-08）。
- 每个再平衡日只对「已有 ≥126 日真实历史」的指数排名 → 池子随时间扩张。
- 主分析期 2016 起（16/17 截面），2009-2015 作长史稳健性参考。完整 17 截面 2019-08 才齐。

═══ 假设 ═══
- 现金 1.8%/年（btlib.CASH_ANNUAL_DEFAULT），空仓/缺额拿现金。
- rf=0（A 股惯例，Sharpe 不减无风险）。
- 交易成本档 c∈{0,5,10}bps，按当日权重变动的 L1 范数（双边换手）的一半 × c 扣减。
- 动量=过去 126 交易日收益（close[t]/close[t-126]-1）。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import btlib

LOOKBACK = 126          # 6M 动量
MIN_HIST = 126          # 合格最小历史
ATR_N = 14
MAIN_START = "2016-01-01"
LONG_START = "2009-07-03"


# ════════════════════════ 数据准备 ════════════════════════
def build_matrices():
    """返回对齐到公共交易日网格的 close/high/low/ret 矩阵 + 各指数首个有效日。

    公共网格 = 所有指数交易日并集。每个指数 reindex 后，仅在其首个真实观测**之后**
    ffill（桥接小网格错位，最多桥几天）；首个观测之前留 NaN（不伪造 IPO 前数据）。
    """
    panel = btlib.load_panel()
    union = sorted(set().union(*[df.index for df in panel.values()]))
    union = pd.DatetimeIndex(union)

    close = pd.DataFrame(index=union)
    high = pd.DataFrame(index=union)
    low = pd.DataFrame(index=union)
    first_valid = {}
    for code, df in panel.items():
        first_valid[code] = df.index.min()
        c = df["close"].reindex(union)
        h = df["high"].reindex(union)
        lo = df["low"].reindex(union)
        # 仅在首个真实观测之后 ffill（桥接网格错位）；之前保持 NaN
        mask_after = union >= df.index.min()
        c = c.where(~mask_after, c.ffill())
        h = h.where(~mask_after, h.ffill())
        lo = lo.where(~mask_after, lo.ffill())
        close[code] = c
        high[code] = h
        low[code] = lo
    ret = close.pct_change()
    return close, high, low, ret, pd.Series(first_valid)


def month_end_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """每个自然月的最后一个交易日。"""
    s = pd.Series(idx, index=idx)
    last = s.groupby([idx.year, idx.month]).last()
    return pd.DatetimeIndex(last.values)


def precompute_indicators(close, high, low):
    """预算每个指数的 6M 动量、各档 MA、ATR(14)。返回 dict 便于网格复用。"""
    codes = list(close.columns)
    mom = close / close.shift(LOOKBACK) - 1.0
    hist_count = close.notna().cumsum()  # 已有真实历史天数（含当日）

    ma = {}
    for n in (100, 120, 150, 200, 250):
        ma[("sma", n)] = close.apply(lambda s: btlib.sma(s, n))
        ma[("ema", n)] = close.apply(lambda s: btlib.ema(s, n))

    # ATR 需逐指数（high/low/close 同列对齐）
    atr = pd.DataFrame(index=close.index, columns=codes, dtype=float)
    for c in codes:
        sub = pd.DataFrame({"high": high[c], "low": low[c], "close": close[c]})
        atr[c] = btlib.atr(sub, ATR_N)
    return mom, hist_count, ma, atr


# ════════════════════════ 权重生成 ════════════════════════
def build_weights(close, ret, mom, hist_count, ma, atr,
                  topk=3, ma_key=None, dd_stop=None, atr_k=None,
                  buffer=False, drop_rank=5):
    """生成每日目标权重矩阵 W（未 shift；行=日，列=指数，行和≤1）。

    参数：
      topk        : 持仓数（top-K 等权）
      ma_key      : ('sma'|'ema', N) 或 None。月末 close>MA(N) 才合格。
      dd_stop     : 移动回撤止损阈值（如 0.20），持仓自进场峰值回撤> 即剔出。None 关闭。
      atr_k       : ATR 移动止损倍数（如 3.0），持仓 < 进场后峰值 - k×ATR 即剔出。None 关闭。
      buffer      : 缓冲带（滞后）。True=进 top-K 才买、跌出 top-{drop_rank} 或失格才卖。
      drop_rank   : 缓冲带卖出阈值（默认跌出 top-5）。

    月末定动量排名 + MA 合格；移动止损按日检查（日内峰值/ATR）。
    """
    dates = close.index
    codes = list(close.columns)
    me = set(month_end_dates(dates))

    MA = ma[ma_key] if ma_key else None
    W = pd.DataFrame(0.0, index=dates, columns=codes)

    held = {}            # code -> entry peak close（用于移动止损追踪）
    cur = []             # 当前持仓 code 列表

    # 预转 numpy 视图加速逐日循环
    close_v = close
    mom_v = mom
    hist_v = hist_count
    atr_v = atr

    for i, d in enumerate(dates):
        # ---- 1. 日内移动止损检查（对已持仓，用 t 日及之前数据）----
        if cur and (dd_stop is not None or atr_k is not None):
            survivors = []
            for c in cur:
                px = close_v.at[d, c]
                if pd.isna(px):
                    continue
                peak = held.get(c, px)
                if px > peak:
                    peak = px
                    held[c] = peak
                stopped = False
                if dd_stop is not None and peak > 0 and (px / peak - 1.0) <= -dd_stop:
                    stopped = True
                if atr_k is not None:
                    a = atr_v.at[d, c]
                    if pd.notna(a) and px <= peak - atr_k * a:
                        stopped = True
                if not stopped:
                    survivors.append(c)
                else:
                    held.pop(c, None)
            cur = survivors

        # ---- 2. 月末再平衡：定动量排名 + MA 合格 ----
        if d in me:
            # 合格池：有≥MIN_HIST 真实历史
            elig = [c for c in codes if hist_v.at[d, c] >= MIN_HIST and pd.notna(mom_v.at[d, c])]
            # MA 过滤
            if MA is not None:
                elig = [c for c in elig
                        if pd.notna(MA.at[d, c]) and close_v.at[d, c] > MA.at[d, c]]
            # 移动止损也作为「合格」条件：当前被止损出场的，本月末若仍满足排名也允许重进
            # （移动止损只在持仓期生效，月末重排时给重新进场机会——标准做法）
            ranked = sorted(elig, key=lambda c: mom_v.at[d, c], reverse=True)
            top_set = ranked[:topk]
            keep_set = set(ranked[:drop_rank])  # 缓冲带卖出阈值

            if not buffer:
                new_cur = top_set
            else:
                # 缓冲带：保留仍在 top-{drop_rank} 且合格的旧仓，空位用 top-K 新标的补
                new_cur = [c for c in cur if c in keep_set]
                for c in top_set:
                    if len(new_cur) >= topk:
                        break
                    if c not in new_cur:
                        new_cur.append(c)
                new_cur = new_cur[:topk]

            # 更新持仓追踪：新进场的设 entry peak=当日 close
            for c in new_cur:
                if c not in held:
                    px = close_v.at[d, c]
                    held[c] = px if pd.notna(px) else 0.0
            for c in list(held.keys()):
                if c not in new_cur:
                    held.pop(c, None)
            cur = new_cur

        # ---- 3. 写入当日目标权重（等权，缺额=现金）----
        if cur:
            w = 1.0 / topk  # 固定 1/topk，不足 topk → 行和<1，差额拿现金
            for c in cur:
                W.at[d, c] = w
    return W


# ════════════════════════ 组合收益 ════════════════════════
def portfolio_ret(W, ret, cost_bps=0.0, cash_annual=btlib.CASH_ANNUAL_DEFAULT):
    """W=每日目标权重（未 shift）。防前视：用 W.shift(1) 作当日实际持仓。

    组合日收益 = Σ pos_i × ret_i + (1-Σpos) × cash - 换手成本。
    换手成本 = 0.5 × Σ|W_t - W_{t-1}| × cost_bps（双边换手的一半）。
    成本在调仓发生日（W 变动日）扣，归到该日收益。
    """
    pos = W.shift(1).fillna(0.0)
    cash_d = btlib.cash_daily(cash_annual)
    asset_r = (pos * ret).sum(axis=1)
    cash_w = (1.0 - pos.sum(axis=1)).clip(lower=0.0)
    gross = asset_r + cash_w * cash_d

    # 换手成本：W 在 t 日变动 → 仓位在 t+1 生效，成本计在 t+1（与收益同日）
    turnover = W.diff().abs().sum(axis=1)  # Σ|ΔW|，行=信号日
    cost = (0.5 * turnover * cost_bps / 1e4).shift(1).fillna(0.0)
    return gross - cost


def annual_turnover(W) -> float:
    """年化单边换手率 = 平均每年 Σ 0.5|ΔW|。"""
    turnover = 0.5 * W.diff().abs().sum(axis=1)
    years = len(W) / btlib.TRADING_DAYS
    return float(turnover.sum() / years) if years > 0 else np.nan


def avg_cash(W) -> float:
    """平均空仓/现金占比（按已生效仓位 shift(1)）。"""
    pos = W.shift(1).fillna(0.0)
    return float((1.0 - pos.sum(axis=1)).clip(lower=0.0).mean())


# ════════════════════════ 报告辅助 ════════════════════════
SUBPERIODS = [
    ("2015H2-2016 股灾熔断", "2015-07-01", "2016-12-31"),
    ("2017-2018 蓝筹+贸易战", "2017-01-01", "2018-12-31"),
    ("2019-2021 成长牛", "2019-01-01", "2021-12-31"),
    ("2022-2024 熊", "2022-01-01", "2024-12-31"),
    ("2024Q4-2026 反弹", "2024-10-01", "2026-12-31"),
]


def sub_perf(ret, start, end):
    sub = ret.loc[start:end].dropna()
    if len(sub) < 5:
        return None
    return btlib.perf(sub)


def worst_12m(ret):
    """最差的滚动 12 个月（252 日）累计收益。返回 (end_date, ret)。"""
    eq = (1.0 + ret.fillna(0)).cumprod()
    roll = eq / eq.shift(252) - 1.0
    roll = roll.dropna()
    if roll.empty:
        return None
    end = roll.idxmin()
    return end, roll.min()


# ════════════════════════ 主流程 ════════════════════════
def fmt_row(name, m, cash=None, turn=None, extra=""):
    s = (f"{name:<26} CAGR={m['cagr']:6.2%} 波动={m['vol']:6.2%} "
         f"Sharpe={m['sharpe']:5.2f} MaxDD={m['maxdd']:7.2%} Calmar={m['calmar']:5.2f}")
    if cash is not None:
        s += f" 现金={cash:4.0%}"
    if turn is not None:
        s += f" 换手={turn:4.1f}x"
    if extra:
        s += f" {extra}"
    return s


def main():
    print("加载数据 + 预计算指标 …", file=sys.stderr)
    close, high, low, ret, first_valid = build_matrices()
    mom, hist_count, ma, atr = precompute_indicators(close, high, low)

    print(f"公共网格 {close.index.min().date()}..{close.index.max().date()}  "
          f"{len(close)} 日  {close.shape[1]} 指数", file=sys.stderr)

    # ─── 定义策略网格 ───
    # 每个条目：(label, build_weights kwargs)
    strategies = []
    # (a) 基线：纯动量 top-3 / top-2，无趋势过滤，无缓冲
    strategies.append(("纯动量 top3 (基线)", dict(topk=3)))
    strategies.append(("纯动量 top2", dict(topk=2)))
    # (b) MA 过滤 top-3，SMA + EMA，N 网格
    for n in (100, 120, 150, 200, 250):
        strategies.append((f"top3 SMA{n}", dict(topk=3, ma_key=("sma", n))))
    for n in (100, 120, 150, 200, 250):
        strategies.append((f"top3 EMA{n}", dict(topk=3, ma_key=("ema", n))))
    # (c) 移动止损 top-3：回撤 x∈{15,20,25}%
    for x in (15, 20, 25):
        strategies.append((f"top3 回撤止损{x}%", dict(topk=3, dd_stop=x / 100)))
    # (c) ATR 移动止损 top-3：k∈{2.5,3}
    for k in (2.5, 3.0):
        strategies.append((f"top3 ATR止损{k}x", dict(topk=3, atr_k=k)))
    # 缓冲带 on：纯动量 + 最优 MA（先占位，下面统一跑 on/off 对照）
    strategies.append(("top3 SMA200 +缓冲带", dict(topk=3, ma_key=("sma", 200), buffer=True)))
    strategies.append(("纯动量 top3 +缓冲带", dict(topk=3, buffer=True)))
    # MA + 移动止损叠加（看能否进一步压回撤）
    strategies.append(("top3 SMA200+回撤20%", dict(topk=3, ma_key=("sma", 200), dd_stop=0.20)))
    # top2 + SMA200 对照
    strategies.append(("top2 SMA200", dict(topk=2, ma_key=("sma", 200))))

    # ─── 运行每个策略：先建 W（耗时），缓存供多用途 ───
    results = {}  # label -> dict(W=, ret0=, perf_main=, perf_long=)
    for label, kw in strategies:
        W = build_weights(close, ret, mom, hist_count, ma, atr, **kw)
        r0 = portfolio_ret(W, ret, cost_bps=0.0)
        r5 = portfolio_ret(W, ret, cost_bps=5.0)
        r10 = portfolio_ret(W, ret, cost_bps=10.0)
        results[label] = dict(W=W, r0=r0, r5=r5, r10=r10)
        print(f"  built {label}", file=sys.stderr)

    # ════ 主表（2016 起，0bps）════
    print("\n" + "=" * 110)
    print(f"主分析期 {MAIN_START} 起（成本=0bps，现金 1.8%/年，rf=0）")
    print("=" * 110)
    rows_main = []
    for label, kw in strategies:
        r = results[label]["r0"].loc[MAIN_START:]
        W = results[label]["W"].loc[MAIN_START:]
        m = btlib.perf(r)
        rows_main.append((label, m, avg_cash(W), annual_turnover(W)))
        print(fmt_row(label, m, cash=avg_cash(W), turn=annual_turnover(W)))

    # 也给一个「全市场买入持有等权 16/17 指数」与「中证全指消费 BH」作锚
    print("-" * 110)
    bh_eq = ret.loc[MAIN_START:].mean(axis=1)  # 等权全行业（仅含已上市的，NaN 跳过）
    print(fmt_row("等权全行业 BH (锚)", btlib.perf(bh_eq)))

    # ════ 交易成本敏感性（主期，看排名是否变）════
    print("\n" + "=" * 110)
    print("交易成本敏感性（2016 起；CAGR @ 0/5/10 bps；按 0bps CAGR 排序看 top）")
    print("=" * 110)
    cost_rows = []
    for label, kw in strategies:
        c0 = btlib.perf(results[label]["r0"].loc[MAIN_START:])["cagr"]
        c5 = btlib.perf(results[label]["r5"].loc[MAIN_START:])["cagr"]
        c10 = btlib.perf(results[label]["r10"].loc[MAIN_START:])["cagr"]
        turn = annual_turnover(results[label]["W"].loc[MAIN_START:])
        cost_rows.append((label, c0, c5, c10, turn))
    for label, c0, c5, c10, turn in sorted(cost_rows, key=lambda x: -x[1]):
        print(f"{label:<26} 0bps={c0:6.2%}  5bps={c5:6.2%}  10bps={c10:6.2%}  "
              f"Δ(0→10)={c0-c10:+.2%}  换手={turn:4.1f}x")

    # ════ 分子周期表（选代表性策略）════
    rep = ["纯动量 top3 (基线)", "top3 SMA200", "top3 SMA250", "top3 回撤止损20%",
           "top3 ATR止损3.0x", "top3 SMA200 +缓冲带", "top3 SMA200+回撤20%", "top2 SMA200"]
    print("\n" + "=" * 110)
    print("分子周期：各段 CAGR / MaxDD（成本=0bps）")
    print("=" * 110)
    header = "策略".ljust(24)
    for pname, _, _ in SUBPERIODS:
        header += f"│ {pname[:14]:<14}"
    print(header)
    for label in rep:
        r0 = results[label]["r0"]
        line = label[:24].ljust(24)
        for _, s, e in SUBPERIODS:
            m = sub_perf(r0, s, e)
            if m is None:
                line += "│ " + "n/a".ljust(14)
            else:
                line += f"│ {m['cagr']:+5.1%}/{m['maxdd']:+5.1%} "
        print(line)

    # ════ 动量崩溃分析：最差 12 个月 ════
    print("\n" + "=" * 110)
    print("动量崩溃：最差滚动 12 个月累计收益（2016 起对齐）")
    print("=" * 110)
    for label in rep:
        r0 = results[label]["r0"].loc[MAIN_START:]
        w12 = worst_12m(r0)
        if w12:
            print(f"{label:<26} 最差12M={w12[1]:7.2%}  (截至 {w12[0].date()})")

    # ════ 长史稳健性（2009 起，仅早期 5-7 指数池）════
    print("\n" + "=" * 110)
    print(f"长史稳健性参考 {LONG_START} 起（早期池仅 5-8 指数，扩张型截面）")
    print("=" * 110)
    for label in ["纯动量 top3 (基线)", "top3 SMA200", "top3 回撤止损20%", "top3 ATR止损3.0x"]:
        r0 = results[label]["r0"]
        m = btlib.perf(r0.dropna())
        W = results[label]["W"]
        print(fmt_row(label, m, cash=avg_cash(W), turn=annual_turnover(W)))

    print("\n[done]", file=sys.stderr)
    return results


if __name__ == "__main__":
    main()
