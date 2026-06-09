#!/usr/bin/env python3
"""构建"宏观大类层 overlay 回测"所需数据缓存（cross-asset + macro），存 data_macro/。

跨资产（sina 可达）：
  - 上证国债指数 sh000012（2003+，财富口径，作债券桶；比国债ETF长且无分红跳空）
  - 黄金ETF sh518880（2013-07+，黄金桶）
宏观（akshare，注意原始倒序，解析后升序）：
  - PMI 制造业  macro_china_pmi          → pmi
  - CPI 全国同比 macro_china_cpi          → cpi_yoy
  - PPI 当月同比 macro_china_ppi          → ppi_yoy
  - M2 同比     macro_china_money_supply → m2_yoy（替代不可达的社融做流动性轴）

跑法（unset 代理 + 关沙箱）：
  env -u HTTP_PROXY ... python3 skills/etf-momentum/research/build_macro_panel.py
输出 data_macro/{idx_sh000012.csv, etf_sh518880.csv, macro_monthly.csv}
"""
import os
import re
import akshare as ak
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "data_macro")
os.makedirs(OUT, exist_ok=True)


def parse_month(s: str) -> pd.Timestamp:
    m = re.match(r"(\d{4})年(\d{1,2})月", str(s))
    return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)


def save_price_index(symbol, fname):
    df = ak.stock_zh_index_daily(symbol=symbol)
    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df.to_csv(os.path.join(OUT, fname), index=False)
    print(f"  {symbol}: {len(df)} 行 {df['date'].iloc[0].date()}..{df['date'].iloc[-1].date()} → {fname}")


def save_etf(symbol, fname):
    df = ak.fund_etf_hist_sina(symbol=symbol)
    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df.to_csv(os.path.join(OUT, fname), index=False)
    print(f"  {symbol}: {len(df)} 行 {df['date'].iloc[0].date()}..{df['date'].iloc[-1].date()} → {fname}")


print("== ① 跨资产 ==")
save_price_index("sh000012", "idx_sh000012.csv")  # 上证国债指数（债券桶）
save_etf("sh518880", "etf_sh518880.csv")          # 黄金ETF（黄金桶）

print("== ② 宏观（解析倒序→升序，统一 month 索引）==")
pmi = ak.macro_china_pmi()[["月份", "制造业-指数"]].rename(columns={"制造业-指数": "pmi"})
cpi = ak.macro_china_cpi()[["月份", "全国-同比增长"]].rename(columns={"全国-同比增长": "cpi_yoy"})
ppi = ak.macro_china_ppi()[["月份", "当月同比增长"]].rename(columns={"当月同比增长": "ppi_yoy"})
m2 = ak.macro_china_money_supply()[["月份", "货币和准货币(M2)-同比增长"]].rename(
    columns={"货币和准货币(M2)-同比增长": "m2_yoy"})

frames = []
for df, col in [(pmi, "pmi"), (cpi, "cpi_yoy"), (ppi, "ppi_yoy"), (m2, "m2_yoy")]:
    df = df.copy()
    df["month"] = df["月份"].map(parse_month)
    df[col] = pd.to_numeric(df[col], errors="coerce")
    frames.append(df.set_index("month")[[col]])

macro = pd.concat(frames, axis=1).sort_index()
macro = macro.dropna(how="all")
macro.to_csv(os.path.join(OUT, "macro_monthly.csv"))
print(f"  macro_monthly: {len(macro)} 月 {macro.index[0].date()}..{macro.index[-1].date()}")
print(f"  覆盖(非空): pmi到{macro['pmi'].dropna().index[-1].date()} "
      f"cpi到{macro['cpi_yoy'].dropna().index[-1].date()} "
      f"ppi到{macro['ppi_yoy'].dropna().index[-1].date()} "
      f"m2到{macro['m2_yoy'].dropna().index[-1].date()}")
print(macro.tail(6).round(2).to_string())
print(f"\n缓存到 {OUT}")
