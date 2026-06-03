#!/usr/bin/env python3
"""btlib —— ETF 趋势止损回测共享库（数据加载 + 指标 + 防前视信号约定）。

只放**可信地基**：指标数学 + 防前视约定。具体策略(MA过滤/移动止损/动量轮动)由
各回测脚本实现，import 本库的 primitives。

⚠️ 防前视铁律：信号用 t 日**收盘**算，仓位 t+1 日才生效。本库 apply_signal() 内部
对 signal 做 .shift(1)，所有策略必须经它转成收益，禁止自行 pos*ret（易漏 shift）。

数据：research/data/idx_*.csv（sina 价格指数，无份额折算，不需复权）。
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "data")
TRADING_DAYS = 252
CASH_ANNUAL_DEFAULT = 0.018  # 货币基金 ~1.8%/年，给空仓期合理收益（对趋势止损公平）


# ---------- 数据 ----------
def load_manifest() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA, "manifest.csv"))


def load_one(code: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA, f"idx_{code}.csv"), parse_dates=["date"])
    return df.sort_values("date").set_index("date")


def load_panel(codes: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """{code: DataFrame[index=date, open/high/low/close/volume]}。codes=None 加载全部。"""
    files = sorted(glob.glob(os.path.join(DATA, "idx_*.csv")))
    out = {}
    for f in files:
        code = os.path.basename(f)[4:-4]  # idx_<code>.csv
        if codes and code not in codes:
            continue
        out[code] = load_one(code)
    return out


def cash_daily(cash_annual: float = CASH_ANNUAL_DEFAULT) -> float:
    return (1.0 + cash_annual) ** (1.0 / TRADING_DAYS) - 1.0


# ---------- 指标 (技术) ----------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def rolling_high(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).max()


# ---------- 防前视信号 → 收益 ----------
def apply_signal(asset_ret: pd.Series, signal: pd.Series, cash_annual: float = CASH_ANNUAL_DEFAULT) -> pd.Series:
    """signal∈[0,1]（1=满仓该标的,0=空仓拿现金）。内部 shift(1) 防前视：
    今日收益 = 昨日信号×今日标的收益 + (1-昨日信号)×现金日收益。"""
    pos = signal.shift(1).fillna(0.0).clip(0, 1)
    return pos * asset_ret + (1.0 - pos) * cash_daily(cash_annual)


def buy_hold_ret(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change()


# ---------- 绩效指标 ----------
def perf(ret: pd.Series, rf_annual: float = 0.0) -> dict:
    """传入策略日收益序列，返回绩效字典。rf 默认 0（A 股惯例，Sharpe 不减无风险）。"""
    ret = ret.dropna()
    n = len(ret)
    if n < 2:
        return dict(n=n, years=0, total=np.nan, cagr=np.nan, vol=np.nan,
                    sharpe=np.nan, maxdd=np.nan, calmar=np.nan)
    eq = (1.0 + ret).cumprod()
    years = n / TRADING_DAYS
    cagr = eq.iloc[-1] ** (1.0 / years) - 1.0
    vol = ret.std() * np.sqrt(TRADING_DAYS)
    sharpe = (ret.mean() * TRADING_DAYS - rf_annual) / vol if vol > 0 else np.nan
    dd = eq / eq.cummax() - 1.0
    maxdd = dd.min()
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan
    return dict(n=n, years=round(years, 2), total=eq.iloc[-1] - 1.0, cagr=cagr,
                vol=vol, sharpe=sharpe, maxdd=maxdd, calmar=calmar)


def exposure(signal: pd.Series) -> float:
    """在场时间占比（按已生效仓位 shift(1)）。"""
    pos = signal.shift(1).fillna(0.0).clip(0, 1)
    return float(pos.mean())


def n_switches(signal: pd.Series) -> int:
    """信号 0↔1 切换次数（近似换手/交易频次）。"""
    pos = (signal.shift(1).fillna(0.0) > 0.5).astype(int)
    return int((pos.diff().abs() > 0).sum())


def fmt(m: dict) -> str:
    return (f"年={m['years']} CAGR={m['cagr']:.2%} 波动={m['vol']:.2%} "
            f"Sharpe={m['sharpe']:.2f} 最大回撤={m['maxdd']:.2%} Calmar={m['calmar']:.2f}")


# ---------- 自测 ----------
if __name__ == "__main__":
    print("== btlib 自测：中证信息技术 sh000935 ==")
    df = load_one("sh000935")
    print(f"行数 {len(df)}  {df.index[0].date()}..{df.index[-1].date()}")

    bh = buy_hold_ret(df)
    print("买入持有       ", fmt(perf(bh)))

    # 200 日 SMA 过滤（防前视）
    sig200 = (df["close"] > sma(df["close"], 200)).astype(float)
    r200 = apply_signal(bh, sig200)
    print("200SMA 过滤    ", fmt(perf(r200)), f"在场={exposure(sig200):.0%} 切换={n_switches(sig200)}")

    # 120 日 SMA 过滤
    sig120 = (df["close"] > sma(df["close"], 120)).astype(float)
    r120 = apply_signal(bh, sig120)
    print("120SMA 过滤    ", fmt(perf(r120)), f"在场={exposure(sig120):.0%} 切换={n_switches(sig120)}")

    # 健全性断言
    assert perf(r200)["maxdd"] > perf(bh)["maxdd"], "趋势过滤应降低最大回撤(maxdd 更接近0)"
    print("\n[OK] 自测通过：趋势过滤的最大回撤显著小于买入持有")
