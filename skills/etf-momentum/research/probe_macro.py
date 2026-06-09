#!/usr/bin/env python3
"""数据可达性探针 ②：为"宏观大类层 overlay 回测"找可达的 跨资产价格 + 宏观状态 数据。

复用 probe_sources.py 的结论：本机 东财(eastmoney) 不可达；sina 可达。
本探针重点验两类新数据：
  (1) 跨资产 ETF/指数（债/黄金/货币/宽基）—— 走 sina（fund_etf_hist_sina / stock_zh_index_daily）
  (2) 宏观状态序列（PMI/CPI/PPI/社融）—— 走 akshare 多接口，**重点查 staleness**
      （已知坑：akshare 某些 PMI 接口返 2008 陈旧数据，必须看 tail 日期）

跑法（必须 unset 代理 + 关沙箱）：
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
      python3 skills/etf-momentum/research/probe_macro.py
"""
import akshare as ak
import pandas as pd


def _find_date_col(df):
    for c in ("date", "日期", "trade_date", "月份", "时间"):
        if c in df.columns:
            return c
    return None


def show(name, fn, val_col_hint=None):
    try:
        df = fn()
        if df is None or len(df) == 0:
            print(f"[EMPTY] {name}")
            return
        n = len(df)
        dc = _find_date_col(df)
        cols = list(df.columns)
        if dc is not None:
            d0, d1 = df[dc].iloc[0], df[dc].iloc[-1]
            # staleness：末日期年份
            yr = str(d1)[:4]
            stale = "" if yr >= "2025" else f"  ⚠️STALE(end={d1})"
            print(f"[OK] {name}: rows={n} cols={cols[:8]}")
            print(f"      {dc}: {d0} .. {d1}{stale}")
        else:
            print(f"[OK] {name}: rows={n} cols={cols[:8]} (无显式日期列, index={df.index[0]}..{df.index[-1]})")
        print(f"      tail2: {df.tail(2).to_dict('records')}")
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:140]}")


print("==== ① 跨资产价格（sina，已知可达）====\n")
# 宽基（正控，已知可达）
show("沪深300  sh000300 (index)", lambda: ak.stock_zh_index_daily(symbol="sh000300"))
# 债券：上证国债指数(价格,长史) + 国债ETF(总回报,2013+) + 30年国债ETF(2024+)
show("上证国债指数 sh000012 (index)", lambda: ak.stock_zh_index_daily(symbol="sh000012"))
show("国债ETF  sh511010 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh511010"))
show("10年国债ETF sh511260 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh511260"))
show("30年国债ETF sh511090 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh511090"))
# 黄金：黄金ETF(2013+) + SGE 现货(尝试)
show("黄金ETF  sh518880 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh518880"))
show("SGE Au99.99 现货 (spot_hist_sge)", lambda: ak.spot_hist_sge(symbol="Au99.99"))
# 货币ETF(现金代理) + 有色(商品代理)
show("货币ETF  sh511990 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh511990"))
show("有色金属 sh512400 (ETF)", lambda: ak.fund_etf_hist_sina(symbol="sh512400"))

print("\n==== ② 宏观状态序列（akshare 多接口，重点查 staleness）====\n")
# PMI —— 已知坑：某接口返 2008 陈旧数据，务必看 tail 日期
show("PMI 官方月度 macro_china_pmi", lambda: ak.macro_china_pmi())
show("PMI 年率 macro_china_pmi_yearly", lambda: ak.macro_china_pmi_yearly())
show("PMI 采购经理 macro_china_pmi_man (制造业)", lambda: ak.index_pmi_man_china_sw() if hasattr(ak, "index_pmi_man_china_sw") else None)
# CPI
show("CPI 月度 macro_china_cpi", lambda: ak.macro_china_cpi())
show("CPI 年率 macro_china_cpi_yearly", lambda: ak.macro_china_cpi_yearly())
show("CPI 月率 macro_china_cpi_monthly", lambda: ak.macro_china_cpi_monthly())
# PPI
show("PPI macro_china_ppi", lambda: ak.macro_china_ppi())
show("PPI 年率 macro_china_ppi_yearly", lambda: ak.macro_china_ppi_yearly())
# 社融
show("社融规模 macro_china_shrzgm", lambda: ak.macro_china_shrzgm())
show("社融增量 macro_china_society_financing", lambda: ak.macro_china_society_financing() if hasattr(ak, "macro_china_society_financing") else None)
# M2（备选流动性轴）
show("M2/货币供应 macro_china_money_supply", lambda: ak.macro_china_money_supply() if hasattr(ak, "macro_china_money_supply") else None)

print("\n==== 探针结束 ====")
