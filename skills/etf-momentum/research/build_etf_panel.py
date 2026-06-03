#!/usr/bin/env python3
"""取 38 ETF 前复权日线缓存到 data_etf/，供细粒度 crowding 复测（聚集更重的真 universe）。

用 _shared/marketdata/etf_hist(sina + 前复权,已修 通信/稀土 折算)。需联网:
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
      python3 skills/etf-momentum/research/build_etf_panel.py
"""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "_shared"))  # marketdata
sys.path.insert(0, os.path.join(HERE, ".."))                    # universe

from marketdata.etf_hist import get_etf_hist  # noqa: E402
from universe import UNIVERSE  # noqa: E402

OUT = os.path.join(HERE, "data_etf")
os.makedirs(OUT, exist_ok=True)

man = []
print(f"{'代码':<8}{'名称':<14}{'行数':>6} {'起':<11}{'止':<11}{'最大单日':>9}  flag")
print("-" * 70)
for code, name, group, index, theme in UNIVERSE:
    try:
        df = get_etf_hist(code)  # 前复权
        time.sleep(0.2)
        if df is None or len(df) == 0:
            print(f"{code:<8}{name:<14}  取数失败")
            continue
        df = df[["date", "open", "high", "low", "close", "volume", "amount"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df.to_csv(os.path.join(OUT, f"etf_{code}.csv"), index=False)
        ret = df["close"].pct_change()
        mx = float(ret.abs().max())
        d0, d1 = df["date"].iloc[0].date(), df["date"].iloc[-1].date()
        flag = "ok" if mx < 0.20 else f"跳{mx:.0%}查折算"  # 前复权后应无折算大跳
        man.append(dict(code=code, name=name, group=group, theme=theme,
                        rows=len(df), start=str(d0), end=str(d1), max_move=round(mx, 4)))
        print(f"{code:<8}{name:<14}{len(df):>6} {str(d0):<11}{str(d1):<11}{mx:>8.1%}  {flag}")
    except Exception as e:
        print(f"{code:<8}{name:<14}  FAIL {type(e).__name__}: {str(e)[:40]}")

pd.DataFrame(man).to_csv(os.path.join(OUT, "manifest_etf.csv"), index=False)
print(f"\n缓存 {len(man)} 个 ETF 到 {OUT}")
