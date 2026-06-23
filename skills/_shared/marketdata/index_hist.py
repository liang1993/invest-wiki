#!/usr/bin/env python3
"""index_hist —— 大盘指数日线 + 年化波动取数（跨市场路由）。

按指数路由到本机可达源（东财全系列不可达，见 README）：
  - A 股 / 中证系 → 新浪 `stock_zh_index_daily`（绕开东财 `_em`）
  - 港股        → 新浪 `stock_hk_index_daily_sina`
  - 美股        → yfinance 优先（含重试），限流/失败回退 akshare `index_us_stock_sina`

供 periodic-review 等 skill import，算逐年波动率 / YTD / 近端已实现波动 / 波动档。

口径：
  - 年化波动率 = 日对数收益率 std × √252（已实现波动）。指数无份额折算/拆分，
    不需 etf_hist 那套前复权剔跳空。
  - 涨跌幅 = 上年末收盘 → 当年末收盘（无上年数据时以区间首日为基；2026 即 YTD）。
  - 波动档 = 近 3 月已实现波动落在该指数「自身」5 年波动区间 [min,max] 的相对位置
    —— 跨指数不可比（恒生科技的 35% 对它自己只是常态，对标普却是极端）。
"""
from __future__ import annotations

import os
import sys
import time
import unicodedata

import numpy as np
import pandas as pd

# 作为 marketdata.index_hist 被 import 时 marketdata 已在路径上；直接 `python3
# index_hist.py` 跑 __main__ 时父目录不在路径，补一下。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TRADING_DAYS = 252

# 跟踪指数注册表：name -> (market, symbol[, us_fallback_symbol])
#   market: cn = 中证/上证系（新浪）, hk = 港股（新浪）, us = 美股（yfinance/akshare）
INDICES: dict[str, tuple] = {
    "标普500":  ("us", "^GSPC", ".INX"),
    "纳斯达克100": ("us", "^NDX", ".NDX"),
    "沪深300":  ("cn", "sh000300"),
    "上证50":   ("cn", "sh000016"),
    "中证500":  ("cn", "sh000905"),
    "中证1000": ("cn", "sh000852"),
    "恒生科技":  ("hk", "HSTECH"),
}


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    """统一成 [date(datetime), close(float)] 升序、去 NaN。"""
    out = df[["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    return out.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def _load_us(yf_sym: str, ak_sym: str) -> pd.DataFrame | None:
    """美股指数：yfinance 优先（重试 3 次抗限流），失败回退 akshare 新浪。"""
    try:
        import yfinance as yf
        for _ in range(3):
            s = yf.Ticker(yf_sym).history(period="6y", auto_adjust=False)["Close"].dropna()
            if len(s) > 100:
                return pd.DataFrame({"date": pd.to_datetime(s.index).tz_localize(None),
                                     "close": s.values})
            time.sleep(1.5)
    except Exception:
        pass
    try:
        import akshare as ak
        return ak.index_us_stock_sina(symbol=ak_sym)
    except Exception:
        return None


def get_index_hist(name: str) -> pd.DataFrame | None:
    """取单个注册指数全历史日线 [date, close] 升序。未知名/失败返回 None。"""
    spec = INDICES.get(name)
    if spec is None:
        return None
    market, symbol = spec[0], spec[1]
    try:
        if market == "cn":
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol=symbol)
        elif market == "hk":
            import akshare as ak
            df = ak.stock_hk_index_daily_sina(symbol=symbol)
        elif market == "us":
            df = _load_us(symbol, spec[2])
        else:
            return None
        if df is None or len(df) == 0:
            return None
        return _norm(df)
    except Exception:
        return None


def annualized_vol(close: pd.Series) -> float | None:
    """日对数收益率 std × √252。样本 < 5 返回 None。"""
    c = close.astype(float)
    lr = np.log(c / c.shift(1)).dropna()
    if len(lr) < 5:
        return None
    return float(lr.std()) * np.sqrt(TRADING_DAYS)


def trailing_vol(df: pd.DataFrame, window: int = 63) -> float | None:
    """近 window 个交易日的年化已实现波动率（默认 63 ≈ 3 月）。"""
    if df is None or len(df) <= window:
        return None
    return annualized_vol(df["close"].iloc[-(window + 1):])


def ytd_return(df: pd.DataFrame) -> float | None:
    """今年至今涨跌幅 %（以上年末收盘为基）。"""
    if df is None or len(df) == 0:
        return None
    yr = df["date"].dt.year
    y = int(yr.iloc[-1])
    prev, cur = df[yr < y], df[yr == y]
    if len(cur) == 0 or len(prev) == 0:
        return None
    return (float(cur["close"].iloc[-1]) / float(prev["close"].iloc[-1]) - 1.0) * 100.0


def per_year_stats(df: pd.DataFrame, years) -> dict:
    """{year: {"vol": 年化波动率%, "ret": 涨跌幅%}}；涨跌幅以上年末收盘为基。"""
    out: dict = {}
    if df is None or len(df) == 0:
        return {y: {"vol": None, "ret": None} for y in years}
    yr = df["date"].dt.year
    for y in years:
        g = df[yr == y]
        if len(g) < 5:
            out[y] = {"vol": None, "ret": None}
            continue
        v = annualized_vol(g["close"])
        prev = df[yr < y]
        base = float(prev["close"].iloc[-1]) if len(prev) else float(g["close"].iloc[0])
        out[y] = {"vol": v * 100.0 if v is not None else None,
                  "ret": (float(g["close"].iloc[-1]) / base - 1.0) * 100.0}
    return out


def regime_tag(cur_vol_pct, year_vols_pct) -> str:
    """近端波动落在该指数自身 5 年 [min,max] 区间的档位（相对自身，不跨指数比）。"""
    vs = [v for v in year_vols_pct if v is not None]
    if cur_vol_pct is None or not vs:
        return "—"
    lo, hi = min(vs), max(vs)
    if hi <= lo:
        return "正常"
    p = (cur_vol_pct - lo) / (hi - lo)
    if p > 1.0:
        return "极端↑"
    if p < 0.0:
        return "极静↓"
    if p >= 0.67:
        return "偏高"
    if p <= 0.33:
        return "平静"
    return "正常"


# ── 控制台展示（供 periodic-review fetch_data.py 复用） ──────────────────────

def _dw(s) -> int:
    """显示宽度：CJK 全角字符记 2。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s, width: int, right: bool = False) -> str:
    s = str(s)
    gap = max(0, width - _dw(s))
    return (" " * gap + s) if right else (s + " " * gap)


def print_monitor(years=(2021, 2022, 2023, 2024, 2025)) -> None:
    """打印「大盘指数波动监测」：当前读数 + 波动档 + 逐年波动率基准表。"""
    years = list(years)
    print("=" * 64)
    print("大盘指数波动监测（{} 指数 · 跨市场 regime 信号）".format(len(INDICES)))
    print("=" * 64)
    print(_pad("指数", 13) + _pad("最近收盘", 11, True) + _pad("YTD", 9, True)
          + _pad("近1月", 8, True) + _pad("近3月", 8, True) + "  波动档")

    py_cache: dict = {}
    for name in INDICES:
        df = get_index_hist(name)
        if df is None:
            print(_pad(name, 13) + _pad("取数失败", 36))
            py_cache[name] = {}
            continue
        py = per_year_stats(df, years)
        py_cache[name] = py
        latest = float(df["close"].iloc[-1])
        ytd = ytd_return(df)
        v1 = trailing_vol(df, 21)
        v3 = trailing_vol(df, 63)
        tag = regime_tag(v3 * 100.0 if v3 else None, [py[y]["vol"] for y in years])
        print(_pad(name, 13)
              + _pad(f"{latest:,.1f}", 11, True)
              + _pad(f"{ytd:+.1f}%" if ytd is not None else "—", 9, True)
              + _pad(f"{v1*100:.1f}%" if v1 else "—", 8, True)
              + _pad(f"{v3*100:.1f}%" if v3 else "—", 8, True)
              + "  " + tag)

    print("-" * 64)
    print(_pad("逐年年化波动率(%)", 18) + "".join(_pad(str(y), 7, True) for y in years)
          + _pad("| 5年均值", 10, True))
    for name in INDICES:
        py = py_cache.get(name, {})
        cells = ""
        vs = []
        for y in years:
            v = py.get(y, {}).get("vol")
            vs.append(v)
            cells += _pad(f"{v:.1f}" if v is not None else "—", 7, True)
        mean = np.mean([v for v in vs if v is not None]) if any(v is not None for v in vs) else None
        cells += _pad(f"| {mean:.1f}" if mean is not None else "| —", 10, True)
        print(_pad(name, 18) + cells)

    print("-" * 64)
    print("波动档 = 近3月已实现波动落在该指数自身5年[最低,最高]的位置"
          "（平静<33% / 正常 / 偏高>67% / 极端↑破5年高）。")
    print("源：A股/恒科=新浪, 美股=yfinance(限流回退akshare新浪)；最近收盘可能滞后实时约1日。")


if __name__ == "__main__":
    print_monitor()
