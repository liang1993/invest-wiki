"""ETF 日线历史取数（sina 源，国内直连稳定）。

供 etf-momentum 等 skill import，算动量/均线/流动性。
sina 返回全历史 DataFrame[date, open, high, low, close, volume, amount]，升序。
amount 单位 = 元。

注：eastmoney(fund_etf_hist_em) 在部分代理环境会被 TLS 重置，sina 源更稳；
若被代理干扰，unset HTTP(S)_PROXY 后运行。
"""
from __future__ import annotations

import os
import sys

import akshare as ak
import pandas as pd

# 作为 marketdata.etf_hist 被 import 时 marketdata 已在路径上；直接 `python3 etf_hist.py`
# 跑 __main__ 时父目录不在路径，补一下，保证两种入口都能 `from marketdata import codes`。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marketdata import codes  # noqa: E402

_NUM = ("open", "high", "low", "close", "volume", "amount")
# 单日 |涨跌| 超过此阈值 = 份额折算/拆分等公司行为，需前复权。现金分红幅度小，不调，
# 对 6 月动量影响可忽略。
# 阈值 0.35 依据：实测全 universe 最大真实单日波动仅 10.0%（软件 159852），而份额折算
# 幅度 ≥49.8%（稀土 516780 -49.8%、通信 515880 -65.7%）；0.35 落在二者干净间隙。
# 已知局限：<35% 的小幅折算仍会漏（罕见），改 universe 后须抽查新代码。
_CORP_ACTION = 0.35


def _qfq(df: pd.DataFrame) -> pd.DataFrame:
    """前复权：sina 返回不复权价，份额折算/拆分会制造虚假跳空（如 515880 折算单日 -66%）。
    检测单日 |return|>35% 的公司行为日，回溯把历史价缩放到当前口径，使序列连续。
    成交额(amount,真实成交金额)不调整，可继续做流动性度量。
    """
    c = df["close"].to_numpy(dtype=float)
    n = len(c)
    if n < 2:
        return df
    cum = 1.0
    factor = [1.0] * n  # 每日的前复权乘数
    for i in range(n - 1, 0, -1):
        r = c[i] / c[i - 1] if c[i - 1] else 1.0
        if r < (1 - _CORP_ACTION) or r > (1 + _CORP_ACTION):
            cum *= r  # 该公司行为前的价需乘此比例对齐到行为后口径
        factor[i - 1] = cum
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        if col in out.columns:
            out[col] = out[col].to_numpy(dtype=float) * factor
    return out


def get_etf_hist(code: str, qfq: bool = True) -> pd.DataFrame | None:
    """取单只 ETF 全历史日线，按日期升序，默认前复权。失败返回 None。"""
    try:
        df = ak.fund_etf_hist_sina(symbol=codes.to_sina_symbol(code))
        if df is None or len(df) == 0:
            return None
        for col in _NUM:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        return _qfq(df) if qfq else df
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "159995"
    d = get_etf_hist(code)
    if d is None:
        print("FAIL", code)
    else:
        print(code, "rows:", len(d), "| last:", d["date"].iloc[-1], round(float(d["close"].iloc[-1]), 3))
