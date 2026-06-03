#!/usr/bin/env python3
"""bt1_single_asset —— 单 A 股行业指数多头持仓的趋势止损横评。

研究问题：对单个行业指数的多头持仓，哪种趋势止损最能压制回撤而不过度牺牲收益？

策略族：
  1. 买入持有（基线）
  2. MA 过滤：close>MA(N) 持有否则空仓，N∈{50,100,120,150,200,250}，SMA/EMA 各一套
  3. 移动止损（状态机）：持有中若 close < 进场以来最高×(1-x) 出场；空仓后 close>MA(100) 重进场
       固定回撤 x∈{10,15,20,25}%；ATR 版出场线=进场以来最高 - k×ATR(14)，k∈{2,2.5,3}
  4. 时序动量 TSMOM：过去 126/252 日收益>0 持有否则空仓

交易成本：每次 0/1 切换扣 c，c∈{0,5bps,10bps}，对每策略重算。

防前视：所有信号经 btlib.apply_signal（内部 shift(1)）。状态机也先产出 0/1 信号再交付。
成本：在 apply_signal 之后、按已生效仓位 pos=signal.shift(1) 的变化日扣减。

假设：现金 1.8%/年、rf=0。样本期见各指数 manifest。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import btlib as bt

# ------------------------------------------------------------------ 成本模型
def apply_cost(ret: pd.Series, signal: pd.Series, c_bps: float) -> pd.Series:
    """在 apply_signal 产出的策略收益上，按已生效仓位的切换日扣成本。
    pos=signal.shift(1)（与 apply_signal 内部一致）；pos 变化日（进或出）各扣 c。
    c 以单边计：一次完整进+出 = 2 次切换 = 2c。与 n_switches 口径一致。"""
    if c_bps <= 0:
        return ret
    c = c_bps / 1e4
    pos = (signal.shift(1).fillna(0.0) > 0.5).astype(int)
    switch = pos.diff().abs().fillna(0.0)  # 1 在切换日
    return ret - switch * c


# ------------------------------------------------------------------ 信号构造
def sig_buyhold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=df.index)


def sig_ma(df: pd.DataFrame, n: int, kind: str) -> pd.Series:
    c = df["close"]
    ma = bt.sma(c, n) if kind == "SMA" else bt.ema(c, n)
    return (c > ma).astype(float)


def sig_tsmom(df: pd.DataFrame, lookback: int) -> pd.Series:
    c = df["close"]
    past = c.pct_change(lookback)  # 过去 lookback 日收益
    return (past > 0).astype(float)


def sig_trailing(df: pd.DataFrame, mode: str, param: float,
                 reentry_n: int = 100) -> pd.Series:
    """移动止损状态机 → 0/1 信号。

    mode='pct'：出场线 = 进场以来最高 close × (1-param)
    mode='atr'：出场线 = 进场以来最高 close - param × ATR(14)（用进场以来 ATR 的当日值）

    规则（全部仅用 ≤t 日数据，apply_signal 再 shift 防前视）：
      - 空仓 → 持有：close[t] > MA(reentry_n)[t]（MA 未成形则不进场）
      - 持有 → 空仓：close[t] < 出场线[t]
      - 进场以来最高 = 自最近一次进场日起 close 的累计最高（含进场日与当日）
      - ATR 用 btlib.atr(df,14)，当日值；ATR 未成形（NaN）时该日不触发 ATR 止损
    """
    close = df["close"].values
    ma = (bt.sma(df["close"], reentry_n)).values
    atr14 = bt.atr(df, 14).values if mode == "atr" else None

    n = len(close)
    sig = np.zeros(n)
    in_pos = False
    peak = np.nan
    for t in range(n):
        if not in_pos:
            # 尝试进场
            if not np.isnan(ma[t]) and close[t] > ma[t]:
                in_pos = True
                peak = close[t]
                sig[t] = 1.0
            else:
                sig[t] = 0.0
        else:
            # 更新进场以来最高
            peak = max(peak, close[t])
            if mode == "pct":
                stop = peak * (1.0 - param)
                exit_now = close[t] < stop
            else:  # atr
                a = atr14[t]
                if np.isnan(a):
                    exit_now = False  # ATR 未成形不触发（保守）
                else:
                    stop = peak - param * a
                    exit_now = close[t] < stop
            if exit_now:
                in_pos = False
                peak = np.nan
                sig[t] = 0.0
            else:
                sig[t] = 1.0
    return pd.Series(sig, index=df.index)


# ------------------------------------------------------------------ 策略目录
def build_strategies() -> dict:
    """返回 {strat_name: builder(df)->signal}。基线单列处理。"""
    strats: dict[str, callable] = {}
    # MA 过滤
    for kind in ("SMA", "EMA"):
        for n in (50, 100, 120, 150, 200, 250):
            strats[f"MA_{kind}{n}"] = (lambda d, k=kind, nn=n: sig_ma(d, nn, k))
    # 移动止损 固定回撤
    for x in (10, 15, 20, 25):
        strats[f"TS_pct{x}"] = (lambda d, xx=x: sig_trailing(d, "pct", xx / 100.0))
    # 移动止损 ATR
    for k in (2.0, 2.5, 3.0):
        kk_label = str(k).replace(".0", "")
        strats[f"TS_atr{kk_label}"] = (lambda d, kv=k: sig_trailing(d, "atr", kv))
    # TSMOM
    strats["TSMOM_126"] = (lambda d: sig_tsmom(d, 126))
    strats["TSMOM_252"] = (lambda d: sig_tsmom(d, 252))
    return strats


COSTS = (0.0, 5.0, 10.0)  # bps per switch


# ------------------------------------------------------------------ 单指数评估
def eval_index(code: str, df: pd.DataFrame, strats: dict) -> pd.DataFrame:
    """对一个指数跑全部策略×成本，返回长表 DataFrame。"""
    asset_ret = bt.buy_hold_ret(df)
    rows = []

    # 基线（买入持有）：永远满仓，0 切换，成本无关
    bh_sig = sig_buyhold(df)
    bh_ret = bt.apply_signal(asset_ret, bh_sig)
    bh_m = bt.perf(bh_ret)
    for c in COSTS:
        rows.append(dict(code=code, strat="BuyHold", cost_bps=c,
                         **{k: bh_m[k] for k in ("cagr", "vol", "sharpe", "maxdd", "calmar", "years")},
                         exposure=1.0, switches=0))

    for name, builder in strats.items():
        sig = builder(df)
        base_ret = bt.apply_signal(asset_ret, sig)
        expo = bt.exposure(sig)
        sw = bt.n_switches(sig)
        for c in COSTS:
            ret = apply_cost(base_ret, sig, c)
            m = bt.perf(ret)
            rows.append(dict(code=code, strat=name, cost_bps=c,
                             **{k: m[k] for k in ("cagr", "vol", "sharpe", "maxdd", "calmar", "years")},
                             exposure=expo, switches=sw))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 聚合
def aggregate(long: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """跨指数聚合：给定成本档，每策略的中位 Calmar/Sharpe/MaxDD + Calmar 胜率（vs BuyHold）。"""
    sub = long[long["cost_bps"] == cost_bps].copy()
    # BuyHold 的 calmar 按指数取（成本无关，取 cost_bps==该档即可）
    bh = sub[sub["strat"] == "BuyHold"].set_index("code")["calmar"]
    agg_rows = []
    for strat, g in sub.groupby("strat"):
        g = g.set_index("code")
        # 胜率：该策略 calmar > 对应指数 BuyHold calmar 的占比
        common = g.index.intersection(bh.index)
        wins = (g.loc[common, "calmar"] > bh.loc[common]).sum()
        n_idx = len(common)
        agg_rows.append(dict(
            strat=strat,
            cost_bps=cost_bps,
            med_calmar=g["calmar"].median(),
            med_sharpe=g["sharpe"].median(),
            med_maxdd=g["maxdd"].median(),
            med_cagr=g["cagr"].median(),
            med_expo=g["exposure"].median(),
            med_switches=g["switches"].median(),
            calmar_winrate=wins / n_idx if n_idx else np.nan,
            n_idx=n_idx,
        ))
    out = pd.DataFrame(agg_rows).sort_values("med_calmar", ascending=False)
    return out


def median_excess_dd(long: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """每策略相对 BuyHold 的中位 MaxDD 改善与中位 CAGR 让渡（同指数配对差）。"""
    sub = long[long["cost_bps"] == cost_bps].copy()
    bh = sub[sub["strat"] == "BuyHold"].set_index("code")[["maxdd", "cagr"]]
    rows = []
    for strat, g in sub.groupby("strat"):
        if strat == "BuyHold":
            continue
        g = g.set_index("code")
        common = g.index.intersection(bh.index)
        # maxdd 是负数，改善 = 策略maxdd - bh.maxdd > 0 表示更浅（更接近0）
        dd_improve = (g.loc[common, "maxdd"] - bh.loc[common, "maxdd"])
        cagr_give = (g.loc[common, "cagr"] - bh.loc[common, "cagr"])
        rows.append(dict(strat=strat,
                         med_dd_improve=dd_improve.median(),
                         med_cagr_delta=cagr_give.median()))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def run(codes: list[str] | None = None) -> pd.DataFrame:
    panel = bt.load_panel(codes)
    strats = build_strategies()
    parts = [eval_index(code, df, strats) for code, df in panel.items()]
    return pd.concat(parts, ignore_index=True)


def fmt_pct(x):
    return "—" if pd.isna(x) else f"{x:.2%}"


def fmt_num(x, d=2):
    return "—" if pd.isna(x) else f"{x:.{d}f}"


def print_agg_table(agg: pd.DataFrame, title: str):
    print(f"\n### {title}")
    print(f"{'策略':<12}{'中位Calmar':>11}{'中位Sharpe':>11}{'中位MaxDD':>11}"
          f"{'中位CAGR':>10}{'在场':>7}{'切换':>6}{'Calmar胜率':>11}")
    for _, r in agg.iterrows():
        print(f"{r['strat']:<12}{fmt_num(r['med_calmar']):>11}{fmt_num(r['med_sharpe']):>11}"
              f"{fmt_pct(r['med_maxdd']):>11}{fmt_pct(r['med_cagr']):>10}"
              f"{fmt_pct(r['med_expo']):>7}{fmt_num(r['med_switches'],0):>6}"
              f"{fmt_pct(r['calmar_winrate']):>11}")


if __name__ == "__main__":
    import sys
    mani = bt.load_manifest()
    name_map = dict(zip(mani["code"], mani["name"]))
    group_map = dict(zip(mani["code"], mani["group"]))

    # 全集
    print("=" * 88)
    print("全集（17 个行业指数，各自样本期；现金 1.8%/年，rf=0）")
    print("=" * 88)
    long = run()
    long.to_csv("bt1_results_long.csv", index=False)

    for c in COSTS:
        agg = aggregate(long, c)
        print_agg_table(agg, f"跨 17 指数聚合 — 成本 {c:.0f}bps/切换")

    # 成本 5bps 下的回撤压制 vs 收益让渡
    print("\n### 回撤压制 vs 收益让渡（成本 5bps，相对买入持有的同指数中位配对差）")
    print("（dd_improve>0 = 回撤更浅; cagr_delta<0 = 收益让渡）")
    exc = median_excess_dd(long, 5.0).sort_values("med_dd_improve", ascending=False)
    print(f"{'策略':<12}{'中位回撤改善':>14}{'中位CAGR增减':>14}")
    for _, r in exc.iterrows():
        print(f"{r['strat']:<12}{fmt_pct(r['med_dd_improve']):>14}{fmt_pct(r['med_cagr_delta']):>14}")

    # ----- 稳定性：长史子集（2009 起一级 5 个）vs 全集
    print("\n" + "=" * 88)
    print("稳定性：长史子集 — 中证一级 5 个（2009-07 起）")
    print("=" * 88)
    primary5 = mani[mani["note"] == "一级"]["code"].tolist()
    print("长史子集：", [f"{name_map[c]}({c})" for c in primary5])
    long_p = run(primary5)
    long_p.to_csv("bt1_results_long_primary5.csv", index=False)
    for c in (5.0,):
        agg_p = aggregate(long_p, c)
        print_agg_table(agg_p, f"长史子集聚合 — 成本 {c:.0f}bps/切换")

    # 全集里仅 2015+ 起的（行业级）单独看一眼，判断子样本漂移
    print("\n" + "=" * 88)
    print("稳定性：短史子集 — 2015 年及以后起始的指数")
    print("=" * 88)
    short_codes = mani[mani["start"] >= "2015-01-01"]["code"].tolist()
    print("短史子集：", [f"{name_map[c]}({c})" for c in short_codes])
    long_s = run(short_codes)
    for c in (5.0,):
        agg_s = aggregate(long_s, c)
        print_agg_table(agg_s, f"短史子集聚合 — 成本 {c:.0f}bps/切换")

    print("\n[完成] 长表已存 bt1_results_long.csv / bt1_results_long_primary5.csv")
