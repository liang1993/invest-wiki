#!/usr/bin/env python3
"""数据可达性探针：为 ETF 趋势止损回测找一个能用的长史行业指数源。

A 股行业 ETF 多数 2020 后成立，长史回测需用 申万一级/中证行业指数 做代理。
本机：东财(eastmoney) 不可达；sina 可达；csindex 官网待测；申万接口待测。

跑法（必须 unset 代理 + 关沙箱）：
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
      python3 skills/etf-momentum/research/probe_sources.py
"""
import akshare as ak


def show(name, fn):
    try:
        df = fn()
        if df is None or len(df) == 0:
            print(f"[EMPTY] {name}")
            return
        cols = list(df.columns)
        print(f"[OK]   {name}: rows={len(df)} cols={cols[:9]}")
        for dc in ("date", "日期", "trade_date"):
            if dc in df.columns:
                print(f"        {dc}: {df[dc].iloc[0]} .. {df[dc].iloc[-1]}")
                break
        else:
            # 可能日期在 index
            try:
                print(f"        index: {df.index[0]} .. {df.index[-1]}")
            except Exception:
                pass
        print(f"        tail1: {df.tail(1).to_dict('records')}")
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:160]}")


print("==== 长史行业指数源可达性探针 ====\n")

# A) 申万一级 历史（新接口，申万官网/镜像）—— 农林牧渔 801010
show("A. index_hist_sw 801010", lambda: ak.index_hist_sw(symbol="801010", period="day"))

# A2) 申万一级 历史（旧 daily 接口）
show("A2. sw_index_daily 801010", lambda: ak.sw_index_daily(symbol="801010", start_date="20200101", end_date="20260603"))

# B) 申万一级 列表
show("B. sw_index_first_info", lambda: ak.sw_index_first_info())

# C) sina 通用指数（沪深300）—— 已知 sina 可达，做正控
show("C. stock_zh_index_daily sh000300", lambda: ak.stock_zh_index_daily(symbol="sh000300"))

# C2) sina 申万一级（部分申万指数有 sina 代码，如 sz399998? 这里测中证全指）
show("C2. stock_zh_index_daily sh000985(中证全指)", lambda: ak.stock_zh_index_daily(symbol="sh000985"))

# D) 中证指数官网直连（csindex.com.cn）—— 沪深300 测可达性
show("D. stock_zh_index_hist_csindex 000300", lambda: ak.stock_zh_index_hist_csindex(symbol="000300", start_date="20140101", end_date="20260603"))

# E) ETF sina 控制组（已知可达）
show("E. fund_etf_hist_sina sh510300", lambda: ak.fund_etf_hist_sina(symbol="sh510300"))

# F) 东财指数（预期 FAIL，确认仍不可达）
show("F. index_zh_a_hist 000300 (expect FAIL)", lambda: ak.index_zh_a_hist(symbol="000300", period="daily", start_date="20140101", end_date="20260603"))

print("\n==== 探针结束 ====")
