#!/usr/bin/env python3
"""探针 3：锁死主面板 = 中证一级 10 行业(000928-937) 全覆盖验证；
并摸主题/细分指数在 sina 的代码格式与覆盖（930/931/H30/980/399 系），供精细面板。
"""
import akshare as ak

PRIMARY = {  # 中证一级行业 10（预期 2009 起，干净）
    "sh000928": "中证能源",
    "sh000929": "中证材料",
    "sh000930": "中证工业",
    "sh000931": "中证可选消费",
    "sh000932": "中证主要消费",
    "sh000933": "中证医药卫生",
    "sh000934": "中证金融地产",
    "sh000935": "中证信息技术",
    "sh000936": "中证电信业务",
    "sh000937": "中证公用事业",
}

THEMATIC = {  # 摸代码格式：sina 对 930/931/H30/980/399 系的覆盖
    "sh930713": "中证人工智能主题(930713 sh)",
    "sz930713": "中证人工智能主题(930713 sz)",
    "sh931151": "中证光伏产业(931151 sh)",
    "sh931087": "中证机器人(931087 sh)",
    "sz980017": "国证半导体芯片(980017 sz)",
    "sh399998": "中证煤炭(399998 sh)",
    "sz399998": "中证煤炭(399998 sz)",
    "sh000819": "国证有色?",
    "sz399808": "中证新能源(399808)",
}


def cov(code):
    try:
        df = ak.stock_zh_index_daily(symbol=code)
        if df is None or len(df) == 0:
            return ("EMPTY", "", "", "")
        return (len(df), str(df["date"].iloc[0]), str(df["date"].iloc[-1]),
                round(float(df["close"].iloc[-1]), 2))
    except Exception as e:
        return (f"FAIL {type(e).__name__}", str(e)[:50], "", "")


def run(title, d):
    print(f"\n## {title}")
    print(f"{'代码':<10}{'名称':<26}{'行数':>7}  {'起':<12}{'止':<12}{'末值':>11}")
    print("-" * 84)
    for code, name in d.items():
        rows, d0, d1, last = cov(code)
        flag = " ✓当前" if str(d1).startswith("2026") else (" ⚠️截断" if isinstance(rows, int) else " ✗")
        print(f"{code:<10}{name:<26}{str(rows):>7}  {d0:<12}{d1:<12}{str(last):>11}{flag}")


run("主面板候选：中证一级 10 行业", PRIMARY)
run("主题/细分代码格式摸底", THEMATIC)
