#!/usr/bin/env python3
"""申万一级(31)+二级(131) 指数日收盘缓存 —— 供 chart_industry_rotation 出图.

拉 sw_index_first_info + sw_index_second_info 拿全部代码, 逐个 index_hist_sw 取日收盘,
滚动保留最近 N 交易日, 写 long-format CSV. 幂等全量覆盖(~60s), 纯机械取数无判断.

为何全量而非增量: realtime 二级只覆盖 ~124/131 且偶发慢(实测 32s), 而 162 条 hist 全量
仅 ~60s、永远自洽自愈缺口 —— 简单 > 省那点时间.

用法: python3 fetch_sw_indices.py [--days 150] [--out PATH]
默认 out=~/Downloads/invest-charts/sw_close.csv (仓库外, 不入 git)
"""
import warnings, io, csv, argparse, pathlib, datetime
from contextlib import redirect_stderr
warnings.filterwarnings("ignore")

DEFAULT_OUT = "~/Downloads/invest-charts/sw_close.csv"


def pull(days):
    """→ (rows[(date,code,name,level,parent,close)], fails[code], n_total)。"""
    import akshare as ak, time
    with redirect_stderr(io.StringIO()):
        s1 = ak.sw_index_first_info()
        s2 = ak.sw_index_second_info()
    meta = [(str(r["行业代码"]).split(".")[0], str(r["行业名称"]), 1, "") for _, r in s1.iterrows()]
    meta += [(str(r["行业代码"]).split(".")[0], str(r["行业名称"]), 2, str(r["上级行业"])) for _, r in s2.iterrows()]
    rows, fails = [], []
    for code, name, level, parent in meta:
        ok = False
        for _ in range(2):
            try:
                with redirect_stderr(io.StringIO()):
                    h = ak.index_hist_sw(symbol=code, period="day")
                h = h.tail(days)
                if len(h) < 2:
                    break
                for _, x in h.iterrows():
                    rows.append((str(x["日期"])[:10], code, name, level, parent, round(float(x["收盘"]), 2)))
                ok = True
                break
            except Exception:
                time.sleep(0.3)
        if not ok:
            fails.append(code)
    # 按 L1(31 个干净指数)最近 days 交易日裁窗 —— 停更的冷门二级(数据停在旧日期)自然出局
    l1_dates = sorted({r[0] for r in rows if r[3] == 1})   # r=(date,code,name,level,parent,close)
    start = l1_dates[-days] if len(l1_dates) >= days else (l1_dates[0] if l1_dates else "")
    rows = [r for r in rows if r[0] >= start]
    return rows, fails, len(meta)


def write_cache(rows, out):
    out = pathlib.Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")                      # 原子写: 先写 tmp 再 rename, 避免出图读到半截
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "code", "name", "level", "parent", "close"])
        w.writerows(rows)
    tmp.replace(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    t0 = datetime.datetime.now()
    rows, fails, n = pull(a.days)
    if not rows:
        raise SystemExit("✗ 无数据, 缓存未写(检查 akshare 可达性)")
    out = write_cache(rows, a.out)
    dates = sorted(set(r[0] for r in rows))
    dt = (datetime.datetime.now() - t0).total_seconds()
    print(f"✅ 缓存 {out}  [{dt:.0f}s]")
    print(f"   {n} 指数(成功 {n - len(fails)}, 失败 {len(fails)}{': ' + str(fails) if fails else ''}) "
          f"× {len(dates)} 交易日 ({dates[0]}→{dates[-1]}), {len(rows)} 行")
