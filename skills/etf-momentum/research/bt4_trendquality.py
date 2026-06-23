#!/usr/bin/env python3
"""bt4_trendquality —— 排序指标对照：趋势"质量"指标 vs 简单区间动量。

研究问题（外部输入：抖音"小木之之"复现公众号"量化均野"全天候 ETF 轮动）：
把 top-K 轮动的**排序指标**从「简单区间动量」换成「趋势质量指标」——
  - 效率系数 ER（Kaufman，位移/路程，区分单边趋势 vs 来回震荡）
  - 斜率 × R²（对数价 25/126 日线性回归，斜率=涨得猛、R²=涨得稳）
  - 动量 × ER（"又猛又稳"，ER∈[0,1] 当作干净度乘子）
  - V4 完整版（对数 + OHLC 均价"价格中枢" 上的 ER）
——在**同一 A 股行业指数池子**、同一月度再平衡/top-3/成本引擎下，到底加不加分？

═══ 公平性设计（只换排序指标，其它全部冻结）═══
- 复用 bt2_rotation 的 build_matrices / build_weights / portfolio_ret：池子、合格规则
  （hist≥126）、月末再平衡、防前视 shift(1)、成本模型完全一致。
- build_weights 的 `mom` 形参本质是"排序打分矩阵"；本脚本只把它替换成各趋势质量矩阵。
- 合格门槛仍 MIN_HIST=126：无论指标自身窗口多短，可排序集合对所有指标恒等 → 唯一变量=指标。
- **锚点**：简单动量 126d 路径必须复现 bt2 基线（CAGR 7.87% / MaxDD -41.13%）。

防前视：不自己算收益，一律走 bt2.portfolio_ret（内部 W.shift(1)）。
数据：research/data/idx_*.csv（17 行业指数，sina 价格指数，无需复权）。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

import btlib
import bt2_rotation as bt2

N_BASE = bt2.LOOKBACK  # 126 = 6M，与用户现行 etf-momentum 同口径


# ════════════════════════ 排序指标构造 ════════════════════════
# 约定：矩阵与 close 同形（index=日, columns=指数），越大=越强的"干净上涨"，
# 窗口不足或首个有效观测前为 NaN（与简单动量一致，保证合格集恒等）。

def simple_mom(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """简单区间动量 = P[t]/P[t-n] - 1。n=126 时 == bt2 基线 mom。"""
    return close / close.shift(n) - 1.0


def _er_signed(level: pd.DataFrame, n: int, use_log: bool) -> pd.DataFrame:
    """带方向的 Kaufman 效率系数：ER × sign(净变动)。
    ER = |位移| / 路程 = |P[t]-P[t-n]| / Σ|ΔP|。单边趋势→±1，来回震荡→0。"""
    p = np.log(level) if use_log else level
    direction = p - p.shift(n)
    path = p.diff().abs().rolling(n, min_periods=n).sum()
    er = direction.abs() / path.replace(0.0, np.nan)
    return er * np.sign(direction)


def _er_unsigned(level: pd.DataFrame, n: int, use_log: bool) -> pd.DataFrame:
    """无方向 ER∈[0,1]，作干净度乘子。"""
    p = np.log(level) if use_log else level
    net = (p - p.shift(n)).abs()
    path = p.diff().abs().rolling(n, min_periods=n).sum()
    return net / path.replace(0.0, np.nan)


def mom_x_er(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """动量 × ER：保留动量方向，用干净度[0,1]缩放（"又猛又稳"）。"""
    return simple_mom(close, n) * _er_unsigned(close, n, use_log=False)


def slope_r2(level: pd.DataFrame, n: int) -> pd.DataFrame:
    """对数价过去 n 日线性回归的 斜率 × R²（V3 指标）。
    闭式：x=0..n-1 固定 → slope=Sxy/Sxx, R²=Sxy²/(Sxx·Syy), 乘积=Sxy³/(Sxx²·Syy)。
    符号随 slope（下跌→负），R²∈[0,1]。逐列 sliding_window_view 向量化。"""
    logp = np.log(level)
    x = np.arange(n, dtype=float)
    dx = x - x.mean()
    Sxx = float((dx ** 2).sum())
    out = pd.DataFrame(np.nan, index=level.index, columns=level.columns)
    for c in level.columns:
        arr = logp[c].to_numpy()
        if len(arr) < n:
            continue
        W = sliding_window_view(arr, n)              # (len-n+1, n)，行对齐到窗口末日
        valid = ~np.isnan(W).any(axis=1)
        ybar = W.mean(axis=1, keepdims=True)
        Sxy = (W * dx).sum(axis=1)                   # Σdx·y（dx 均值0 → 自动去 ybar）
        Syy = ((W - ybar) ** 2).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            slope = Sxy / Sxx
            r2 = np.where(Syy > 0, Sxy ** 2 / (Sxx * Syy), 0.0)
        sig = np.where(valid, slope * r2, np.nan)
        full = np.full(len(arr), np.nan)
        full[n - 1:] = sig
        out[c] = full
    return out


def build_ohlc_mean() -> pd.DataFrame:
    """价格中枢 = (O+H+L+C)/4，按 bt2 同款"首个有效观测后才 ffill"规则对齐公共网格。"""
    panel = btlib.load_panel()
    union = pd.DatetimeIndex(sorted(set().union(*[df.index for df in panel.values()])))
    pc = pd.DataFrame(index=union)
    for code, df in panel.items():
        m = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
        m = m.reindex(union)
        mask_after = union >= df.index.min()
        pc[code] = m.where(~mask_after, m.ffill())
    return pc


# ════════════════════════ 跑一个策略 → 绩效 ════════════════════════
def run(close, ret, sig, hist_count, ma, atr, *, topk=3, ma_key=None,
        start, cost_bps=0.0):
    W = bt2.build_weights(close, ret, sig, hist_count, ma, atr, topk=topk, ma_key=ma_key)
    r = bt2.portfolio_ret(W, ret, cost_bps=cost_bps).loc[start:]
    Wm = W.loc[start:]
    m = btlib.perf(r)
    m["cash"] = bt2.avg_cash(Wm)
    m["turn"] = bt2.annual_turnover(Wm)
    m["_W"] = W
    m["_r"] = bt2.portfolio_ret(W, ret, cost_bps=cost_bps)  # 全期，供分周期/长史
    return m


# ════════════════════════ 主流程 ════════════════════════
def main():
    print("加载数据 + 预计算 …", file=sys.stderr)
    close, high, low, ret, _ = bt2.build_matrices()
    mom, hist_count, ma, atr = bt2.precompute_indicators(close, high, low)
    pc = build_ohlc_mean().reindex(index=close.index, columns=close.columns)

    print(f"公共网格 {close.index.min().date()}..{close.index.max().date()}  "
          f"{len(close)} 日  {close.shape[1]} 指数\n", file=sys.stderr)

    # ── 排序指标（126d 主口径）──
    SIG = {
        "简单动量126 (基线)": mom,                       # == bt2 基线（复用同一矩阵）
        "效率系数ER126": _er_signed(close, N_BASE, use_log=False),
        "动量×ER126": mom_x_er(close, N_BASE),
        "斜率×R²126(对数)": slope_r2(close, N_BASE),
        "V4 对数中枢ER126": _er_signed(pc, N_BASE, use_log=True),
    }
    NAMES = list(SIG)

    # ════ 0. 锚点：简单动量路径复现 bt2 基线 ════
    base = run(close, ret, SIG["简单动量126 (基线)"], hist_count, ma, atr,
               start=bt2.MAIN_START)
    print("=" * 104)
    print("锚点校验：简单动量126 top3 应复现 bt2 基线 CAGR≈7.87% / MaxDD≈-41.13%")
    print("=" * 104)
    print(bt2.fmt_row("简单动量126 top3", base, cash=base["cash"], turn=base["turn"]))
    ok = abs(base["cagr"] - 0.0787) < 5e-4 and abs(base["maxdd"] - (-0.4113)) < 5e-4
    print(f"[{'OK' if ok else '✗ 不一致——引擎接线有误，停止'}] 锚点{'通过' if ok else '失败'}\n")
    if not ok:
        sys.exit(1)

    # ════ 1. 主对照表（2016 起，0bps）：无过滤 + SMA200 过滤 ════
    for ma_key, tag in [(None, "无趋势过滤"), (("sma", 200), "+SMA200 过滤")]:
        print("=" * 104)
        print(f"主期 {bt2.MAIN_START} 起｜top3｜{tag}｜成本0bps｜现金1.8%/年｜rf=0")
        print("=" * 104)
        cells = {}
        for name in NAMES:
            m = run(close, ret, SIG[name], hist_count, ma, atr,
                    ma_key=ma_key, start=bt2.MAIN_START)
            cells[name] = m
            print(bt2.fmt_row(name, m, cash=m["cash"], turn=m["turn"]))
        # 加分判定：相对简单动量，Calmar 与 Sharpe 是否同时改善
        b = cells["简单动量126 (基线)"]
        print("-" * 104)
        for name in NAMES[1:]:
            m = cells[name]
            dC, dS = m["calmar"] - b["calmar"], m["sharpe"] - b["sharpe"]
            dCAGR, dDD = m["cagr"] - b["cagr"], m["maxdd"] - b["maxdd"]
            verdict = ("加分" if (dC > 0.01 and dS > 0.02) else
                       "不加分" if (dC < -0.01 or dS < -0.02) else "持平")
            print(f"  {name:<18} ΔCAGR={dCAGR:+6.2%} ΔMaxDD={dDD:+6.2%} "
                  f"ΔSharpe={dS:+5.2f} ΔCalmar={dC:+5.2f} → {verdict}")
        print()

    # ════ 2. 成本敏感性（2016 起，0/5/10bps，无过滤）════
    print("=" * 104)
    print(f"成本敏感性（{bt2.MAIN_START} 起，无过滤，CAGR @ 0/5/10bps）")
    print("=" * 104)
    for name in NAMES:
        c = [run(close, ret, SIG[name], hist_count, ma, atr,
                 start=bt2.MAIN_START, cost_bps=b)["cagr"] for b in (0, 5, 10)]
        turn = run(close, ret, SIG[name], hist_count, ma, atr,
                   start=bt2.MAIN_START)["turn"]
        print(f"{name:<18} 0bps={c[0]:6.2%}  5bps={c[1]:6.2%}  10bps={c[2]:6.2%}  "
              f"Δ(0→10)={c[0]-c[2]:+.2%}  换手={turn:4.1f}x")
    print()

    # ════ 3. 窗口扫描（无过滤，2016 起）：横轴=回看天数 ════
    print("=" * 104)
    print(f"窗口扫描（{bt2.MAIN_START} 起，无过滤，top3）｜视频用 25d，用户现行 126d")
    print("=" * 104)
    windows = [25, 63, 126, 252]
    builders = {
        "简单动量": lambda n: simple_mom(close, n),
        "效率系数ER": lambda n: _er_signed(close, n, use_log=False),
        "斜率×R²(对数)": lambda n: slope_r2(close, n),
    }
    print(f"{'指标\\窗口':<16}" + "".join(f"│ {w}d (CAGR/MaxDD/Calmar)".ljust(26) for w in windows))
    for bname, fn in builders.items():
        line = bname.ljust(16)
        for w in windows:
            m = run(close, ret, fn(w), hist_count, ma, atr, start=bt2.MAIN_START)
            line += f"│ {m['cagr']:+5.1%}/{m['maxdd']:+5.1%}/{m['calmar']:.2f}".ljust(26)
        print(line)
    print()

    # ════ 4. 分子周期（126d，无过滤）════
    print("=" * 104)
    print("分子周期 CAGR/MaxDD（126d，无过滤，0bps）")
    print("=" * 104)
    cache = {name: run(close, ret, SIG[name], hist_count, ma, atr, start=bt2.MAIN_START)
             for name in NAMES}
    header = "策略".ljust(20)
    for pname, _, _ in bt2.SUBPERIODS:
        header += f"│ {pname[:13]:<13}"
    print(header)
    for name in NAMES:
        r0 = cache[name]["_r"]
        line = name[:20].ljust(20)
        for _, s, e in bt2.SUBPERIODS:
            mm = bt2.sub_perf(r0, s, e)
            line += "│ " + ("n/a".ljust(13) if mm is None
                            else f"{mm['cagr']:+5.1%}/{mm['maxdd']:+5.1%}")
        print(line)
    print()

    # ════ 5. 长史稳健性（2009 起，扩张型早期池）════
    print("=" * 104)
    print(f"长史稳健性参考 {bt2.LONG_START} 起（早期池 5-8 指数，扩张型截面，无过滤）")
    print("=" * 104)
    for name in NAMES:
        r0 = cache[name]["_r"].dropna()
        m = btlib.perf(r0)
        print(bt2.fmt_row(name, m))

    print("\n[done]", file=sys.stderr)


if __name__ == "__main__":
    main()
