#!/usr/bin/env python3
"""申万一级行业轮动快照 — 当日涨跌 + 多窗口涨跌 + 近端波动率。

只观察、不算动量、不给交易信号（industry-rotation skill 描述）。
"""
from __future__ import annotations
import os, sys, time, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "_shared"))
import akshare as ak

OUT_DIR = os.path.join(os.path.dirname(__file__), "research", "data")
os.makedirs(OUT_DIR, exist_ok=True)


def fetch_realtime() -> pd.DataFrame:
    df = ak.index_realtime_sw(symbol="一级行业")
    df = df.rename(columns={"指数代码": "code", "指数名称": "name",
                            "昨收盘": "prev", "今开盘": "open",
                            "最新价": "last", "成交额": "amount_yi"})
    df["d1_pct"] = (df["last"] / df["prev"] - 1.0) * 100.0
    return df[["code", "name", "prev", "open", "last", "amount_yi", "d1_pct"]]


def fetch_hist_metrics(code: str) -> dict:
    """取日 K，返回近 5/20/60 日涨跌幅 + YTD + 60 日年化波动 + 250 日累计。"""
    try:
        df = ak.index_hist_sw(symbol=str(code), period="day")
    except Exception as e:
        return {"err": str(e)[:80]}
    if df is None or len(df) < 5:
        return {"err": "too short"}
    # 列：日期 开盘 收盘 最高 最低 成交量 成交额
    df = df.rename(columns={"日期": "date", "收盘": "close"})
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    c = df["close"].values
    last = c[-1]

    def ret(n):
        if len(c) > n:
            return (last / c[-1 - n] - 1.0) * 100.0
        return np.nan

    yr = df["date"].dt.year
    y = int(yr.iloc[-1])
    prev = df[yr < y]["close"]
    ytd = (last / float(prev.iloc[-1]) - 1.0) * 100.0 if len(prev) else np.nan

    lr = np.log(c[1:] / c[:-1])
    v63 = float(np.std(lr[-63:])) * np.sqrt(252) * 100 if len(lr) >= 63 else np.nan
    v21 = float(np.std(lr[-21:])) * np.sqrt(252) * 100 if len(lr) >= 21 else np.nan

    return {
        "last_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "d5_pct": ret(5),
        "d20_pct": ret(20),
        "d60_pct": ret(60),
        "d250_pct": ret(250),
        "ytd_pct": ytd,
        "vol63_ann_pct": v63,
        "vol21_ann_pct": v21,
    }


def main():
    rt = fetch_realtime()
    print(f"实时行情 {len(rt)} 个行业，拉历史中...")

    rows = []
    for i, r in rt.iterrows():
        m = fetch_hist_metrics(r["code"])
        rec = {**r.to_dict(), **m}
        rows.append(rec)
        time.sleep(0.25)
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{len(rt)}  {r['name']}")
    out = pd.DataFrame(rows)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    out["snapshot_date"] = today
    csv = os.path.join(OUT_DIR, f"sw_l1_{today}.csv")
    out.to_csv(csv, index=False, encoding="utf-8-sig", float_format="%.6f")
    print(f"\n保存：{csv}")
    print(out[["name", "last", "d1_pct", "d5_pct", "d20_pct",
               "ytd_pct", "vol63_ann_pct", "amount_yi"]]
          .sort_values("d1_pct", ascending=False).to_string(index=False))
    return out


if __name__ == "__main__":
    main()
