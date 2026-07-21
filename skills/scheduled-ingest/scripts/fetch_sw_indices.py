#!/usr/bin/env python3
"""申万一级(31)+二级(131) 指数日收盘缓存 —— 供 chart_industry_rotation 出图.

拉 sw_index_first_info + sw_index_second_info 拿全部代码, 逐个 index_hist_sw 取日收盘,
滚动保留最近 N 交易日, 写 long-format CSV. 幂等全量覆盖(~60s), 纯机械取数无判断.

为何全量而非增量: realtime 二级只覆盖 ~124/131 且偶发慢(实测 32s), 而 162 条 hist 全量
仅 ~60s、永远自洽自愈缺口 —— 简单 > 省那点时间.

用法: python3 fetch_sw_indices.py [--days 150] [--out PATH]
默认 out=~/Downloads/invest-charts/sw_close.csv (仓库外, 不入 git)
"""
import warnings, io, csv, argparse, pathlib, datetime, urllib.request, socket
from contextlib import redirect_stderr
warnings.filterwarnings("ignore")
socket.setdefaulttimeout(30)   # 限时: 慢接口不再无限挂(与 fetch_daily_market 一致)

DEFAULT_OUT = "~/.invest-charts/sw_close.csv"   # 非 TCC 保护目录(Downloads 下 launchd 无写权限)


def _tencent_today():
    """腾讯上证时间戳 → (交易日 'YYYY-MM-DD', 是否已收盘)。失败→(None, False)。"""
    try:
        req = urllib.request.Request("http://qt.gtimg.cn/q=sh000001", headers={"User-Agent": "Mozilla/5.0"})
        ts = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "ignore").split('"')[1].split("~")[30]
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", ts[8:14] >= "150000"
    except Exception:
        return None, False


def _realtime_closes(retries=2):
    """index_realtime_sw 一级+二级 → {6位代码: 最新价}, 补 hist 尚未发布的当日收盘。
    带重试: 该接口间歇性 KeyError 'data'。"""
    import akshare as ak, time
    out = {}
    for sym in ("一级行业", "二级行业"):
        for _ in range(retries):
            try:
                with redirect_stderr(io.StringIO()):
                    df = ak.index_realtime_sw(symbol=sym)
                for _, r in df.iterrows():
                    out[str(r["指数代码"])] = round(float(r["最新价"]), 2)
                break
            except Exception:
                time.sleep(1)
    return out


def _load_existing(path):
    """读已有缓存 CSV → (rows, 最大日期)。无/坏 → ([], "")。"""
    if not path:
        return [], ""
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        return [], ""
    try:
        rows = []
        with p.open(encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            for d, code, name, lv, parent, close in rd:
                rows.append((d, code, name, int(lv), parent, float(close)))
        return rows, max((x[0] for x in rows), default="")
    except Exception:
        return [], ""


def _last_full(path):
    """上次全量拉取日期(sidecar)。无 → ""。"""
    if not path:
        return ""
    try:
        return pathlib.Path(path).expanduser().with_name(".last_full").read_text().strip()
    except Exception:
        return ""


def _mark_full(path):
    if path:
        try:
            pathlib.Path(path).expanduser().with_name(".last_full").write_text(
                datetime.date.today().isoformat())
        except Exception:
            pass


def _full_stale(path, max_age=7):
    """距上次全量是否已超 max_age 天(或从未全量)。
    必要性: realtime 补当日使缓存恒比 hist 快一天 → 增量判据恒真 → 永不全量;
    需周期性全量来复核 realtime 值、补历史洞、发现申万新增/调整行业。"""
    lf = _last_full(path)
    if not lf:
        return True
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(lf)).days >= max_age
    except Exception:
        return True


def _ref_last(ak):
    """参考指数(农林牧渔 801010)hist 末日 —— 判 hist 是否已出新一天。1 call。"""
    try:
        with redirect_stderr(io.StringIO()):
            h = ak.index_hist_sw(symbol="801010", period="day")
        return str(h["日期"].iloc[-1])[:10]
    except Exception:
        return ""


def _full_pull(ak, meta, days):
    """逐指数 index_hist_sw 取最近 days 根收盘 → (rows, fails)。"""
    import time
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
    return rows, fails


def pull(days, cache_path=None):
    """→ (rows, fails, n_total, mode)。
    增量: 参考指数 hist 未出新一天 → 复用缓存, 只补当日 realtime; 否则全量拉 162 条。
    降级/当日重跑时避免几十分钟的全量重拉。"""
    import akshare as ak
    cached, cache_max = _load_existing(cache_path)
    ref_last = _ref_last(ak)
    stale = _full_stale(cache_path)
    if cached and ref_last and ref_last <= cache_max and not stale:
        rows = list(cached)
        meta = sorted({(r[1], r[2], r[3], r[4]) for r in cached})   # 从缓存派生, 省 info 调用
        fails, mode = [], f"增量(hist 未出新, 复用缓存至 {cache_max})"
    else:
        with redirect_stderr(io.StringIO()):
            s1 = ak.sw_index_first_info()
            s2 = ak.sw_index_second_info()
        meta = [(str(r["行业代码"]).split(".")[0], str(r["行业名称"]), 1, "") for _, r in s1.iterrows()]
        meta += [(str(r["行业代码"]).split(".")[0], str(r["行业名称"]), 2, str(r["上级行业"])) for _, r in s2.iterrows()]
        rows, fails = _full_pull(ak, meta, days)
        _mark_full(cache_path)
        mode = "全量拉取" + ("(距上次全量≥7天, 强制)" if stale and cached else "")
    # 当日收盘补丁(realtime 带重试): 今日交易 + 已收盘 + 晚于现有末日
    cur_max = max((r[0] for r in rows), default="")
    tdate, closed = _tencent_today()
    if tdate and closed and tdate > cur_max:
        rt = _realtime_closes()
        hit = sum(1 for m in meta if m[0] in rt)
        # 全有或全无: 覆盖不足(如只回了一级)则整天不补 —— 半补会让缺席序列在图表里被
        # "需覆盖全部日期"规则整体剔除, 且增量模式下永不回来(2026-07-20/21 二级全灭教训)
        if rt and hit >= len(meta) * 0.95:
            for code, name, level, parent in meta:
                if code in rt:
                    rows.append((tdate, code, name, level, parent, rt[code]))
            mode += f" + realtime 补 {tdate}"
        else:
            mode += f" + realtime 覆盖不足({hit}/{len(meta)}) 整天不补 {tdate}"
    # 裁窗(L1 最近 days 交易日; 停更冷门二级自然出局)
    l1_dates = sorted({r[0] for r in rows if r[3] == 1})
    start = l1_dates[-days] if len(l1_dates) >= days else (l1_dates[0] if l1_dates else "")
    rows = [r for r in rows if r[0] >= start]
    return rows, fails, len(meta), mode


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
    rows, fails, n, mode = pull(a.days, cache_path=a.out)
    if not rows:
        raise SystemExit("✗ 无数据, 缓存未写(检查 akshare 可达性)")
    out = write_cache(rows, a.out)
    dates = sorted(set(r[0] for r in rows))
    dt = (datetime.datetime.now() - t0).total_seconds()
    print(f"✅ 缓存 {out}  [{dt:.0f}s | {mode}]")
    print(f"   {n} 指数(成功 {n - len(fails)}, 失败 {len(fails)}{': ' + str(fails) if fails else ''}) "
          f"× {len(dates)} 交易日 ({dates[0]}→{dates[-1]}), {len(rows)} 行")
