#!/usr/bin/env python3
"""构建核心行业指数面板（已验证 sina 可达+当前的代码），缓存为 CSV + manifest。

数据源 sina stock_zh_index_daily（唯一可达长史源）。价格指数无份额折算，不需前复权。
逐代码校验：行数 / 起止 / 最大单日波动(查数据 glitch) / 最大日历缺口(查漏数据)。

跑法（unset 代理 + 关沙箱）。输出 research/data/idx_*.csv + manifest.csv。
"""
import os
import akshare as ak
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

# (code, 名称, 大类, 备注) —— 全部经 probe 验证为 sina 可达+收到 2026-06
PANEL = [
    # 中证一级（2009 长史，干净 5）
    ("sh000928", "中证能源", "周期", "一级"),
    ("sh000932", "中证主要消费", "消费", "一级"),
    ("sh000933", "中证医药卫生", "医药", "一级"),
    ("sh000934", "中证金融地产", "金融", "一级"),
    ("sh000935", "中证信息技术", "科技", "一级"),
    # 中证全指（2011，补 材料/可选消费）
    ("sh000987", "中证全指材料", "周期", "全指"),
    ("sh000989", "中证全指可选消费", "消费", "全指"),
    # 中证行业 399（2014-15，细分，贴 ETF）
    ("sz399986", "中证银行", "金融", "行业"),
    ("sz399975", "中证证券公司", "金融", "行业"),
    ("sz399967", "中证军工", "制造", "行业"),
    ("sz399971", "中证传媒", "科技", "行业"),
    ("sz399976", "中证新能源汽车", "新能源", "行业"),
    ("sz399989", "中证医疗", "医药", "行业"),
    ("sz399998", "中证煤炭", "周期", "行业"),
    ("sz399808", "中证新能源", "新能源", "行业"),
    # 国证（干净）
    ("sz980017", "国证半导体芯片", "科技", "国证"),
    ("sh000819", "国证有色金属", "周期", "国证"),
]


def fetch_validate(code):
    df = ak.stock_zh_index_daily(symbol=code)
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    rows = len(df)
    d0, d1 = df["date"].iloc[0].date(), df["date"].iloc[-1].date()
    ret = df["close"].pct_change()
    max_move = float(ret.abs().max())
    gap = df["date"].diff().dt.days
    max_gap = int(gap.max())
    last = round(float(df["close"].iloc[-1]), 2)
    return df, dict(rows=rows, start=str(d0), end=str(d1),
                    max_daily_move=round(max_move, 4), max_gap_days=max_gap, last=last)


man = []
print(f"{'代码':<10}{'名称':<16}{'行数':>6} {'起':<11}{'止':<11}{'最大单日':>9}{'最大缺口':>7}  flag")
print("-" * 86)
for code, name, grp, note in PANEL:
    try:
        df, m = fetch_validate(code)
        df.to_csv(os.path.join(OUT, f"idx_{code}.csv"), index=False)
        flags = []
        if not m["end"].startswith("2026"):
            flags.append("旧")
        if m["max_daily_move"] > 0.20:
            flags.append(f"跳{m['max_daily_move']:.0%}")
        if m["max_gap_days"] > 15:
            flags.append(f"缺{m['max_gap_days']}d")
        fl = ",".join(flags) if flags else "ok"
        m.update(code=code, name=name, group=grp, note=note, flag=fl)
        man.append(m)
        print(f"{code:<10}{name:<16}{m['rows']:>6} {m['start']:<11}{m['end']:<11}"
              f"{m['max_daily_move']:>8.1%}{m['max_gap_days']:>6}d  {fl}")
    except Exception as e:
        print(f"{code:<10}{name:<16}  FAIL {type(e).__name__}: {str(e)[:50]}")

pd.DataFrame(man).to_csv(os.path.join(OUT, "manifest.csv"), index=False)
print(f"\n缓存 {len(man)} 个指数到 {OUT}")
print("最早共同起点(细分 399 系):约 2015-07；中证一级长史子集回到 2009-07")
