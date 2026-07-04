#!/usr/bin/env python3
"""每日 A 股市场数据采集 (daily-market job) — 取数 + 轻校验 + 格式化.

设计见 docs/daily-ingest-plan.md。纯机械采集，无判断。
采原始日变信号（大盘指数 / 成交额 / 主力 / 涨跌停 / 两融 / 板块轮动 / 港股 / 隔夜美股）；
每项轻校验（交叉源 / 新鲜度 / sanity）；失败 → 降级 [待核实] + 顶部标记，不阻塞其余。
趋势 Δ：两融用交易所序列（实时）；其余用自身 raw 归档（首日 — ，逐日累积）。

用法:
  python3 fetch_daily_market.py            # 采集今日, 打印校验报告 + markdown 节
  python3 fetch_daily_market.py --write    # 追加写月度日志 + raw JSON 归档
  python3 fetch_daily_market.py --json     # 追加输出 raw JSON
"""
import warnings, socket, sys, os, io, json, re, pathlib, datetime, urllib.request
from contextlib import redirect_stderr
warnings.filterwarnings("ignore")
socket.setdefaulttimeout(30)

TODAY = datetime.date.today()
REPO = pathlib.Path(__file__).resolve().parents[3]   # skills/scheduled-ingest/scripts/ -> repo 根


# ---------- 数据源 helpers ----------
def tx_multi(codes):
    """一次取多只腾讯行情, 返回 {code: fields[]}。"""
    req = urllib.request.Request(f"http://qt.gtimg.cn/q={codes}",
                                 headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk", "ignore")
    out = {}
    for line in raw.strip().split("\n"):
        if '="' not in line:
            continue
        code = line.split("=", 1)[0].split("_")[-1]
        out[code] = line.split('"')[1].split("~")
    return out


def yf_overnight(sym, retries=3):
    import yfinance as yf, time
    for _ in range(retries):
        try:
            h = yf.Ticker(sym).history(period="5d")
            if len(h) >= 2:
                last, prev = h.iloc[-1], h.iloc[-2]
                return float(last["Close"]), (last["Close"] / prev["Close"] - 1) * 100, h.index[-1].date()
        except Exception:
            pass
        time.sleep(1.0)
    raise ValueError("yahoo 无足够数据/多次失败")


# ---------- 信号灯档 (静态阈值, 提案 — 首跑后 ~20 交易日校准) ----------
def L_chengjiaoe(wy):
    return ("🔵 萎靡" if wy < 0.8 else "🟢 正常" if wy < 1.2 else
            "🟡 活跃" if wy < 1.6 else "🔴 过热")

def L_emotion(up, down, zt, dt):
    rate = up / (up + down) if (up + down) else 0
    if zt > dt * 1.5 and rate > 0.55:
        return f"🔴 过热(赚钱{rate:.0%})"
    if dt > zt or rate < 0.35:
        return f"🔵 冰点(赚钱{rate:.0%})"
    return f"⚪ 中性(赚钱{rate:.0%})"

def L_margin(yi):
    return ("🟢 正常" if yi < 25000 else "🟡 警惕" if yi < 30000 else
            "🟠 偏高" if yi < 35000 else "🔴 极端")

def L_pct(p):
    return "🔴 弱" if p < -2 else "🟢 强" if p > 2 else "⚪ 平"


# ---------- 趋势 Δ ----------
def load_history(today, n=6):
    """读本月+上月 raw 归档 (date < today), 新→旧。"""
    months = {today.strftime("%Y-%m"),
              (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")}
    out = []
    for m in months:
        d = REPO / "raw" / "articles" / "market" / m
        if not d.exists():
            continue
        for jf in d.glob("*.json"):
            try:
                o = json.loads(jf.read_text(encoding="utf-8"))
                if o.get("date", "") < str(today):
                    out.append(o)
            except Exception:
                pass
    out.sort(key=lambda o: o["date"], reverse=True)
    return out[:n]


def delta_pass(rows, history):
    """给 val 非空且未内联 Δ 的行补"昨/均5"（来自归档）。"""
    hist = {}
    for o in history:
        for r in o.get("rows", []):
            if r.get("val") is not None:
                hist.setdefault(r["name"], []).append(r["val"])
    for r in rows:
        if r.get("delta") is not None:        # 已内联 (两融)
            continue
        v = r.get("val")
        if v is None:
            r["delta"] = "—"; continue
        prev = hist.get(r["name"], [])
        if not prev:
            r["delta"] = "— 累积中"; continue
        p = 2 if abs(v) < 10 else 0
        last5 = ([v] + prev)[:5]
        r["delta"] = f"昨{v - prev[0]:+.{p}f}·均5 {sum(last5) / len(last5):.{p}f}"


# ---------- 申万一级 31 行业 (index_hist_sw 日频涨跌+成交额 / sw_index_first_info 估值) ----------
def _fnum(x, nd):
    """估值数值格式化: None/NaN/非数 → None。"""
    try:
        v = float(x)
        return None if v != v else round(v, nd)      # v!=v 判 NaN
    except (TypeError, ValueError):
        return None


def fetch_industry(target=None, retries=2):
    """申万一级 31 行业: 涨跌% + 成交额(亿元) + 估值(PE_TTM/PB/股息率%)。
    按涨跌降序返回 (数据日期, [[行业, 涨跌%, 成交额亿, PE, PB, 股息%], ...])。
    - 涨跌%/成交额: 逐行业 `index_hist_sw`（申万宏源指数日 K，成交额单位亿元，Σ31≈全市场）；
      target=None（每日）取最近完整交易日，target=历史日（回填）取截至该日两根收盘。
    - 估值: `sw_index_first_info`（1 call，最新静态快照；回填日按最新估值近似标注）。
    日度与回填同一路径（统一指数日 K，无 realtime 盘前语义风险）。31 call ~20s。"""
    import akshare as ak, time
    with redirect_stderr(io.StringIO()):
        fi = ak.sw_index_first_info()
    val, codes = {}, []
    for _, r in fi.iterrows():
        nm = str(r["行业名称"])
        val[nm] = (_fnum(r.get("TTM(滚动)市盈率"), 1), _fnum(r.get("市净率"), 2),
                   _fnum(r.get("静态股息率"), 2))
        codes.append((str(r["行业代码"]).split(".")[0], nm))   # 801010.SI -> 801010
    rows, ddate = [], None
    for code, nm in codes:
        pair = None
        for _ in range(retries):
            try:
                with redirect_stderr(io.StringIO()):
                    h = ak.index_hist_sw(symbol=code, period="day")
                if target is not None:
                    h = h[h["日期"].astype(str).str[:10] <= str(target)]
                if len(h) >= 2:
                    pair = (h.iloc[-1], h.iloc[-2]); break
            except Exception:
                time.sleep(0.3)
        if pair is None:
            continue
        cur, prev = pair
        pe, pb, div = val.get(nm, (None, None, None))
        rows.append([nm, round((cur["收盘"] / prev["收盘"] - 1) * 100, 2),
                     round(float(cur["成交额"])), pe, pb, div])
        ddate = str(cur["日期"])[:10]
    rows.sort(key=lambda r: r[1], reverse=True)
    return ddate, rows


def industry_block(ind, ddate):
    """申万一级 markdown 块 (行业 | 涨跌% | 成交额亿 | PE_TTM | PB | 股息%)。"""
    lbl = f"截至 {ddate} 收盘" if (ddate and ddate[0].isdigit()) else "最近完整交易日"
    g = lambda x: "—" if x is None else f"{x:g}"
    out = [f"**一级行业（申万 {len(ind)}，{lbl}，按涨跌降序；成交额亿元 · PE_TTM/PB/股息为最新静态）**", "",
           "| 行业 | 涨跌% | 成交额(亿) | PE(TTM) | PB | 股息% |", "|---|--:|--:|--:|--:|--:|"]
    out += [f"| {nm} | {zd:+.1f} | {amt:,.0f} | {g(pe)} | {g(pb)} | {g(div)} |"
            for nm, zd, amt, pe, pb, div in ind]
    return "\n".join(out)


# ---------- 采集 + 校验 ----------
def collect():
    rows, warns, extra = [], [], {}

    def add(grp, name, reading, light, vstatus, vnote, val=None, delta=None):
        rows.append(dict(grp=grp, name=name, reading=reading, light=light,
                         vstatus=vstatus, vnote=vnote, val=val, delta=delta))
        if vstatus == "warn":
            warns.append(f"{name}（{vnote}）")

    # 全市场快照 (涨跌停派生 + 成交额交叉源) —— 新浪; 偶发返 HTML/限流, 重试.
    spot, _spot_err = None, ""
    import time as _time
    for _ in range(3):
        try:
            with redirect_stderr(io.StringIO()):
                import akshare as ak
                spot = ak.stock_zh_a_spot()
            if spot is not None and len(spot):
                break
        except Exception as e:
            _spot_err = str(e)[:60]
        _time.sleep(1.0)

    # 腾讯大盘 + 港股 一次取齐
    tx, _tx_err = {}, ""
    try:
        tx = tx_multi("sh000001,sz399001,sz399006,sh000300,hkHSTECH,hkHSI")
    except Exception as e:
        _tx_err = str(e)[:50]

    # --- 大盘指数行 (上证/深证/创业板/沪深300) ---
    idx_names = [("sh000001", "上证"), ("sz399001", "深成指"),
                 ("sz399006", "创业板"), ("sh000300", "沪深300")]
    idx_line = []
    for code, nm in idx_names:
        f = tx.get(code)
        if f and len(f) > 32:
            try:
                idx_line.append(f"{nm} {float(f[3]):,.0f} {float(f[32]):+.2f}%")
            except Exception:
                pass
    extra["indices"] = idx_line

    # --- 成交额 (腾讯 f37 万元, 交叉 新浪快照成交额求和) ---
    try:
        sh, sz = tx["sh000001"], tx["sz399001"]
        amt = (float(sh[37]) + float(sz[37])) / 1e8                 # 万元 -> 万亿
        vst, vno = "ok", "单源(腾讯)"
        if spot is not None and "成交额" in spot.columns:
            amt2 = spot["成交额"].sum() / 1e12                       # 元 -> 万亿
            dev = abs(amt - amt2) / amt * 100
            vno = f"双源 腾讯{amt:.2f}/快照{amt2:.2f} 偏差{dev:.1f}%"
            if dev > 5:
                vst = "warn"
        if not (0.1 < amt < 6):
            vst, vno = "warn", f"量级异常 {amt:.2f}万亿"
        add("A股", "成交额", f"{amt:.2f} 万亿", L_chengjiaoe(amt), vst, vno, val=round(amt, 3))
    except Exception as e:
        add("A股", "成交额", "—", "—", "warn", f"取数失败 {(_tx_err or str(e))[:40]}")

    # --- 涨跌停情绪 (新浪快照派生) ---
    if spot is not None:
        pct = spot["涨跌幅"]
        up = int((pct > 0).sum()); down = int((pct < 0).sum())
        zt = int((pct >= 9.9).sum()); dt = int((pct <= -9.9).sum())
        vst = "ok" if zt <= up else "warn"
        vno = "派生(新浪全市场)" if zt <= up else "sanity 涨停>上涨"
        add("A股", "涨跌停情绪", f"涨{up}/跌{down} 涨停{zt}/跌停{dt}",
            L_emotion(up, down, zt, dt), vst, vno)
    else:
        add("A股", "涨跌停情绪", "—", "—", "warn", f"快照失败 {_spot_err}")

    # --- 两融余额 (akshare, T+1; Δ 用交易所序列) ---
    try:
        import akshare as ak, pandas as pd
        msh = ak.macro_china_market_margin_sh()[["日期", "融资余额"]]
        msz = ak.macro_china_market_margin_sz()[["日期", "融资余额"]]
        m = pd.merge(msh, msz, on="日期", suffixes=("_sh", "_sz"))   # 沪深序列长度不同, 按日对齐
        m["rz"] = (m["融资余额_sh"] + m["融资余额_sz"]) / 1e8
        rz = m["rz"].iloc[-1]; d = m["日期"].iloc[-1]
        delta = f"昨{rz - m['rz'].iloc[-2]:+.0f}·均5 {m['rz'].iloc[-5:].mean():.0f}"
        add("A股", "两融余额", f"{rz:,.0f} 亿 ({d})", L_margin(rz),
            "ok", "交易所, 占比待 periodic-review", val=round(rz), delta=delta)
    except Exception as e:
        add("A股", "两融余额", "—", "—", "warn", f"取数失败 {str(e)[:40]}")

    # --- 申万一级 31 行业 涨跌% + 成交额 + 估值 (index_hist_sw 日 K, 失败降级) ---
    try:
        extra["industry_date"], extra["industry"] = fetch_industry()
    except Exception as e:
        extra["industry"] = None
        warns.append(f"申万一级行业（取数失败 {str(e)[:24]}）")

    # --- 恒生科技 / 恒生指数 (腾讯港股) ---
    for code, nm in [("hkHSTECH", "恒生科技"), ("hkHSI", "恒生指数")]:
        f = tx.get(code)
        try:
            price = float(f[3]); chg = (price / float(f[4]) - 1) * 100
            add("港股", nm, f"{price:,.0f} {chg:+.2f}%", L_pct(chg), "ok", "腾讯港股")
        except Exception:
            add("港股", nm, "—", "—", "warn", f"取数失败 {_tx_err[:30]}")

    # --- 隔夜美股 (yahoo) ---
    for sym, nm in [("KWEB", "中概金龙(KWEB)"), ("^NDX", "纳指100"), ("^GSPC", "标普500")]:
        try:
            price, chg, d = yf_overnight(sym)
            fmt = f"{price:.2f}" if price < 100 else f"{price:,.0f}"
            note = "单源(^HXC 无数据)" if sym == "KWEB" else f"({d})"
            add("隔夜", nm, f"{fmt} {chg:+.2f}% ({d})", L_pct(chg), "ok", note)
        except Exception as e:
            add("隔夜", nm, "—", "—", "warn", f"取数失败 {str(e)[:40]}")

    delta_pass(rows, load_history(TODAY))
    return rows, warns, extra


# ---------- 格式化 ----------
def render(rows, warns, extra):
    ok = sum(1 for r in rows if r["vstatus"] == "ok")
    out = [f"## {TODAY} (盘前)", "",
           f"> 自动采集 | 校验: ✓ {ok} 通过 / ⚠️ {len(warns)} 待核实"]
    if warns:
        out += [">", "> **⚠️ 待核实**: " + " · ".join(warns)]
    out.append("")

    if extra.get("indices"):
        out += ["**大盘指数**：" + " · ".join(extra["indices"]), ""]

    def table(grp, title, dcol):
        sub = [r for r in rows if r["grp"] == grp]
        if not sub:
            return
        out.append(f"**{title}**"); out.append("")
        head = "| 信号 | 读数 | Δ(昨/均5) | 信号灯 | 校验 |" if dcol else "| 信号 | 读数 | 信号灯 | 校验 |"
        out.append(head)
        out.append("|---|---|---|---|---|" if dcol else "|---|---|---|---|")
        for r in sub:
            mark = "✓" if r["vstatus"] == "ok" else "⚠️"
            d = r.get("delta") or "—"
            if dcol:
                out.append(f"| {r['name']} | {r['reading']} | {d} | {r['light']} | {mark} {r['vnote']} |")
            else:
                out.append(f"| {r['name']} | {r['reading']} | {r['light']} | {mark} {r['vnote']} |")
        out.append("")

    table("A股", "A股层（资金 / 情绪 / 杠杆）", dcol=True)

    ind = extra.get("industry")
    if ind:
        out += [industry_block(ind, extra.get("industry_date", "")), ""]
    elif "industry" in extra:
        out += ["**一级行业**：⚠️ 申万取数失败，本日未取到", ""]

    table("港股", "港股 / 中概层", dcol=False)
    table("隔夜", "隔夜美股层", dcol=False)
    return "\n".join(out)


def write_outputs(rows, warns, extra, section_md, today):
    """写月度日志（当日节置顶，**时间倒序**，最新在最上）+ raw JSON 审计。当日节幂等（重跑替换）。"""
    daily_dir = REPO / "wiki" / "journal" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    mf = daily_dir / f"{today:%Y-%m}.md"
    seg = section_md.strip()
    header = (f"---\ntags: [每日市场, 数据]\nupdated: {today}\n---\n\n"
              f"# {today:%Y-%m} A股每日市场数据\n\n"
              f"> 每交易日盘前自动采集的市场层信号灯。纯数据，无分析（分析见 periodic-review）。")
    if mf.exists():
        content = mf.read_text(encoding="utf-8")
        # 移除已存在的当日节, 再置顶插入 → 最新在最上
        content = re.sub(rf"\n*## {re.escape(str(today))} \(盘前\).*?(?=\n## |\Z)", "", content, flags=re.S)
        m = re.search(r"^## ", content, flags=re.M)
        head = (content[:m.start()] if m else content)
        head = re.sub(r"^updated: .*$", f"updated: {today}", head, count=1, flags=re.M).rstrip()
        body = content[m.start():].strip() if m else ""
        content = "\n\n".join([head, seg] + ([body] if body else [])) + "\n"
    else:
        content = header + "\n\n" + seg + "\n"
    mf.write_text(content, encoding="utf-8")

    raw_dir = REPO / "raw" / "articles" / "market" / f"{today:%Y-%m}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    jf = raw_dir / f"{today}.json"
    jf.write_text(json.dumps({"date": str(today), "rows": rows, "warns": warns, "extra": extra},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    return mf, jf


def backfill_industry(date_str):
    """回填某 `## date (盘前)` 节的申万一级行业块(涨跌%+成交额+估值)，就地替换，不动其它信号；
    同步更新该日 raw JSON 的 extra.industry / industry_date。
    节 D 的大盘/成交额/行业为 D 当日收盘同源快照（两融 T+1 滞后一日属正常），故取 target=D。"""
    d = datetime.date.fromisoformat(date_str)
    ddate, ind = fetch_industry(target=d)
    if not ind:
        raise RuntimeError(f"{date_str} 无行业数据")
    blk = industry_block(ind, ddate)
    mf = REPO / "wiki" / "journal" / "daily" / f"{d:%Y-%m}.md"
    content = mf.read_text(encoding="utf-8")
    sec = re.compile(rf"(## {re.escape(date_str)} \(盘前\).*?)(?=\n## |\Z)", re.S)
    m = sec.search(content)
    if not m:
        raise RuntimeError(f"未找到 {date_str} 节")
    ipat = re.compile(r"\*\*一级行业.*?(?=\n\n\*\*港股)", re.S)
    if not ipat.search(m.group(1)):
        raise RuntimeError(f"{date_str} 节内无一级行业块")
    content = content[:m.start(1)] + ipat.sub(blk, m.group(1)) + content[m.end(1):]
    mf.write_text(content, encoding="utf-8")
    jf = REPO / "raw" / "articles" / "market" / f"{d:%Y-%m}" / f"{date_str}.json"
    if jf.exists():
        o = json.loads(jf.read_text(encoding="utf-8"))
        o.setdefault("extra", {})["industry"] = ind
        o["extra"]["industry_date"] = ddate
        jf.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    return mf, ddate, len(ind)


def merge_prior(rows, extra, today):
    """重跑时: 本次失败(—)的信号/缺失的行业·指数, 用当日已归档的好值补齐,
    使 --write 单调 —— 只改善不丢数据(源瞬断不再抹掉上次好值)。返回 (rows, warns, extra)。"""
    jf = REPO / "raw" / "articles" / "market" / f"{today:%Y-%m}" / f"{today}.json"
    if jf.exists():
        try:
            prior = json.loads(jf.read_text(encoding="utf-8"))
            pr = {r["name"]: r for r in prior.get("rows", [])}
            for i, r in enumerate(rows):
                if r["vstatus"] == "warn" and r.get("reading") == "—":
                    p = pr.get(r["name"])
                    if p and p.get("vstatus") == "ok" and p.get("reading") != "—":
                        rows[i] = {**p, "vnote": (p.get("vnote", "") + " · 沿用上次").lstrip(" ·")}
            pe = prior.get("extra", {})
            if not extra.get("industry") and pe.get("industry"):
                extra["industry"] = pe["industry"]; extra["industry_date"] = pe.get("industry_date")
            if not extra.get("indices") and pe.get("indices"):
                extra["indices"] = pe["indices"]
        except Exception:
            pass
    warns = [f"{r['name']}（{r['vnote']}）" for r in rows if r["vstatus"] == "warn"]
    return rows, warns, extra


if __name__ == "__main__":
    if "--backfill-industry" in sys.argv:
        ds = sys.argv[sys.argv.index("--backfill-industry") + 1]
        mf, dd, n = backfill_industry(ds)
        print(f"✅ 回填 {ds} 节一级行业 ({n} 行, 截至 {dd} 收盘) → {mf.relative_to(REPO)}")
        sys.exit(0)
    rows, warns, extra = collect()
    if "--write" in sys.argv:
        rows, warns, extra = merge_prior(rows, extra, TODAY)
    section = render(rows, warns, extra)
    print("=" * 64); print(section); print("=" * 64)
    if "--write" in sys.argv:
        mf, jf = write_outputs(rows, warns, extra, section, TODAY)
        print(f"\n✅ 已写入: {mf.relative_to(REPO)}")
        print(f"   raw 审计: {jf.relative_to(REPO)}")
    if "--json" in sys.argv:
        print("\n--- raw JSON ---")
        print(json.dumps({"date": str(TODAY), "rows": rows, "warns": warns, "extra": extra},
                         ensure_ascii=False, indent=2))
