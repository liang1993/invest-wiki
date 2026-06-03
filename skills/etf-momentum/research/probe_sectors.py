#!/usr/bin/env python3
"""探针 2：找一批覆盖完整(到 2026-06)的 sina 行业指数代码，组装长史板块面板。

sina 唯一可达，但逐代码可靠性不一(sh000985 截断在 2016)。本探针逐个验覆盖。
跑法同 probe_sources.py（unset 代理 + 关沙箱）。
"""
import akshare as ak

CANDIDATES = {
    # 中证全指 十大一级行业（GICS 式，2011 起）
    "sh000986": "中证全指能源",
    "sh000987": "中证全指材料",
    "sh000988": "中证全指工业",
    "sh000989": "中证全指可选消费",
    "sh000990": "中证全指主要消费",
    "sh000991": "中证全指医药卫生",
    "sh000992": "中证全指金融地产",
    "sh000993": "中证全指信息技术",
    "sh000994": "中证全指电信业务",
    "sh000995": "中证全指公用事业",
    # 中证行业（SZSE 399 系，ETF 常跟踪）
    "sz399986": "中证银行",
    "sz399975": "中证证券公司",
    "sz399967": "中证军工",
    "sz399971": "中证传媒",
    "sz399976": "中证新能源汽车(CNI?)",
    "sz399989": "中证医疗?",
    # 中证主题（SH 000 系）
    "sh000932": "中证主要消费",
    "sh000933": "中证医药卫生",
    "sh000935": "中证信息技术",
    "sh000928": "中证能源",
    # 申万一级 via sina（测 sina 是否carry申万）
    "sh801010": "申万农林牧渔?",
    "sz801010": "申万农林牧渔?z",
    # 控制组
    "sh000300": "沪深300(控制)",
}


def cov(code):
    try:
        df = ak.stock_zh_index_daily(symbol=code)
        if df is None or len(df) == 0:
            return ("EMPTY", "", "", "")
        d0 = df["date"].iloc[0]
        d1 = df["date"].iloc[-1]
        last = round(float(df["close"].iloc[-1]), 2)
        return (len(df), str(d0), str(d1), last)
    except Exception as e:
        return (f"FAIL {type(e).__name__}", str(e)[:60], "", "")


print(f"{'代码':<10}{'名称':<22}{'行数':>7}  {'起':<12}{'止':<12}{'末值':>10}")
print("-" * 78)
for code, name in CANDIDATES.items():
    rows, d0, d1, last = cov(code)
    # 标记是否当前（止日含 2026）
    flag = " ✓当前" if str(d1).startswith("2026") else (" ⚠️截断" if isinstance(rows, int) else "")
    print(f"{code:<10}{name:<22}{str(rows):>7}  {d0:<12}{d1:<12}{str(last):>10}{flag}")
