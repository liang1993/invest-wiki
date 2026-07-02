#!/usr/bin/env python3
"""行业 ETF 动量轮动 —— 计算当前动量状态 + 信号。

策略见 wiki/strategies/行业ETF动量轮动.md：
  6 月动量(横截面排名) + 200 日均线趋势过滤(回撤刹车) + top-K + 流动性闸。

升级(回测验证,见 research/findings_champion.md / findings_bt3_synthesis.md)：
  风控层级 分散 ≈ 去相关 > 波动率缩放 ≫ 趋势止损MA长度 > 移动止损(有害)。本 skill 在
  "动量 top-K + 慢线过滤" 基础上加两层经验证的风控:
    ① 去相关选择:从动量前 TOPN 合格里挑 TOPK 个互相关最低的(抗主题聚集/拥挤)
    ② 波动率目标:给出建议敞口 = min(1, 15%/组合已实现波动)(危机自动减仓)
  二者都只用市场数据、holdings-agnostic。buffer 出场状态机属个人版。

跑法:
  python3 momentum.py          # 打印当前状态表 + 信号
  python3 momentum.py --md     # 输出 wiki 快照用 markdown

数据源: sina 日线(_shared/marketdata/etf_hist)。国内直连;若代理干扰:
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY ... python3 momentum.py
"""
from __future__ import annotations

import os
import sys
import time
import datetime as dt

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "_shared"))
from marketdata.etf_hist import get_etf_hist  # noqa: E402
from marketdata import quote_tencent  # noqa: E402
from universe import UNIVERSE  # noqa: E402

# ---- 参数（与 wiki 策略默认一致：流动性闸 = 规模≥20亿 且 日均成交≥1亿）----
LOOKBACK = 126     # 6 月 ≈ 126 交易日
MA = 200           # 趋势过滤均线
TOPK = 3           # 持有数
LIQ_MIN_YI = 1.0   # 日均成交额下限(亿)；低于此=流动性警示，剔出合格池
AUM_MIN_YI = 20    # 规模下限(亿)；用腾讯 total_mcap_y 近似，低于此剔出合格池
SLEEP = 0.25       # 每只之间，给数据源喘息
# ---- 升级层(回测验证):去相关选择 + 波动率目标 ----
TOPN = 6           # 去相关候选池:从动量前 TOPN 里挑 TOPK 个互相关最低的(抗主题聚集)
VOL_TARGET = 0.15  # 波动率目标(年化):建议敞口 = min(1, VOL_TARGET / 组合已实现波动)
VOL_LB = 126       # 已实现波动 / 相关阵 回看(交易日)


def _fetch_aum() -> dict[str, float]:
    """批量拿快照取 total_mcap_y(亿) 作 AUM 近似。{code: aum}，取不到的不在结果中。
    total_mcap_y 是腾讯"总市值"近似，非 f10 基金净资产口径；作 ≥20亿 粗闸够用
    （量级实测吻合，如 510300≈1391.92亿）。get_quotes 已按 ≤50/批分块。"""
    quotes = quote_tencent.get_quotes([c for c, *_ in UNIVERSE])
    aum = {}
    for code, q in quotes.items():
        v = q.get("total_mcap_y")
        if isinstance(v, (int, float)):
            aum[code] = float(v)
    return aum


def compute() -> list[dict]:
    aum_map = _fetch_aum()
    out = []
    for code, name, group, index, theme in UNIVERSE:
        df = get_etf_hist(code)
        time.sleep(SLEEP)
        rec = {"code": code, "name": name, "group": group, "theme": theme}
        if df is None or len(df) < LOOKBACK + 1:
            rec["err"] = "取数失败/历史不足"
            out.append(rec)
            continue
        c = df["close"]
        amt = df["amount"] if "amount" in df.columns else None
        last = float(c.iloc[-1])
        prev = float(c.iloc[-LOOKBACK - 1])
        ma_n = len(c) >= MA
        ma = float(c.iloc[-MA:].mean()) if ma_n else float("nan")  # 不足 MA 历史不强算均线
        liq = (float(amt.iloc[-20:].mean()) / 1e8) if amt is not None else float("nan")
        ret = c.pct_change()
        ret.index = pd.to_datetime(df["date"])
        rec.update(
            err=None,
            date=str(df["date"].iloc[-1]),
            close=last,
            mom6=last / prev - 1,
            above=bool(ma_n and last > ma),  # 修:未满 MA 历史的票不算"在均线上"(原 skipna 会假合格)
            ma_n=ma_n,
            liq=liq,
            aum=aum_map.get(code),  # 亿；取不到为 None
            ret=ret.iloc[-(VOL_LB + 10):],  # 近端收益,供去相关 + 波动率目标
        )
        out.append(rec)
    return out


def _eligible(r) -> bool:
    """合格 = 在 200 日线上 且 日均成交≥LIQ_MIN_YI 且 规模≥AUM_MIN_YI。
    AUM 取不到（None）视为不合格（流动性闸宁缺毋滥）。"""
    aum = r.get("aum")
    return (
        r["above"]
        and r["liq"] >= LIQ_MIN_YI
        and aum is not None
        and aum >= AUM_MIN_YI
    )


def _rank(rows):
    ok = [r for r in rows if not r["err"]]
    eligible = [r for r in ok if _eligible(r)]
    eligible.sort(key=lambda r: r["mom6"], reverse=True)
    return ok, eligible


def _ret_frame(recs) -> pd.DataFrame:
    """一组 rec 的近端收益拼成对齐 DataFrame(按日期内连接,去 NaN)。"""
    d = {r["code"]: r["ret"] for r in recs if r.get("ret") is not None}
    return pd.DataFrame(d).dropna() if d else pd.DataFrame()


def _decorrelate(eligible):
    """从动量前 TOPN 合格里贪心挑 TOPK 个互相关最低的(锚定动量第1,抗主题聚集)。
    候选不足 / 数据不足时退化为朴素 top-K。"""
    cand = eligible[:TOPN]
    if len(cand) <= TOPK:
        return eligible[:TOPK]
    frame = _ret_frame(cand)
    if frame.shape[1] < TOPK or len(frame) < 20:
        return eligible[:TOPK]
    corr = frame.iloc[-VOL_LB:].corr().abs()
    picked = [cand[0]["code"]]  # 锚定动量最强
    pool = [r["code"] for r in cand[1:] if r["code"] in corr.columns]
    while len(picked) < TOPK and pool:
        best, bestc = pool[0], 9.0
        for code in pool:
            avg = float(corr.loc[code, picked].mean())
            if avg < bestc:
                best, bestc = code, avg
        picked.append(best)
        pool.remove(best)
    by_code = {r["code"]: r for r in cand}
    return [by_code[c] for c in picked]


def _suggest_exposure(selected):
    """波动率目标:等权所选 book 近 VOL_LB 已实现波动 → 建议敞口 min(1, VOL_TARGET/RV)。
    返回 (敞口, 已实现年化波动)。数据不足返回 (1.0, nan)。"""
    frame = _ret_frame(selected)
    if frame.empty or len(frame) < 20:
        return 1.0, float("nan")
    book = frame.iloc[-VOL_LB:].mean(axis=1)
    rv = float(book.std() * np.sqrt(252))
    expo = min(1.0, VOL_TARGET / rv) if rv > 0 else 1.0
    return expo, rv


def _asof(rows):
    ds = [r["date"] for r in rows if not r["err"]]
    return max(ds) if ds else "NA"


def _fmt_aum(aum) -> str:
    return f"{aum:.0f}" if isinstance(aum, (int, float)) else "—"


def print_plain(rows):
    ok, eligible = _rank(rows)
    asof = _asof(rows)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n=== 行业 ETF 动量状态 | 数据 as-of {asof} | 生成 {now} ===")
    print(f"参数: 6月动量({LOOKBACK}td) / {MA}日均线过滤 / 去相关top{TOPK}(候选{TOPN}) / 波动目标{VOL_TARGET:.0%} / 规模≥{AUM_MIN_YI}亿且日均成交≥{LIQ_MIN_YI}亿\n")
    sk = sorted(ok, key=lambda r: r["mom6"], reverse=True)
    print(f"{'板块':<10}{'代码':<8}{'6月%':>8}{'均线上':>7}{'AUM亿':>8}{'日均额亿':>9}  {'合格':>4}")
    for r in sk:
        elig = "✓" if _eligible(r) else ""
        tag = "·赛道" if r["theme"] else ""
        print(f"{r['name']+tag:<10}{r['code']:<8}{r['mom6']*100:>7.1f}%{'是' if r['above'] else '否':>7}{_fmt_aum(r.get('aum')):>8}{r['liq']:>9.2f}  {elig:>4}")
    fails = [r for r in rows if r["err"]]
    if fails:
        print("\n取数失败:", ", ".join(f"{r['name']}({r['code']})" for r in fails))

    naive = eligible[:TOPK]
    print(f"\n--- 朴素动量 top{TOPK}(参考) ---")
    for i, r in enumerate(naive, 1):
        print(f"  {i}. {r['name']}({r['code']})  6月 {r['mom6']*100:+.1f}%")

    selected = _decorrelate(eligible)
    expo, rv = _suggest_exposure(selected)
    print(f"\n--- 推荐持仓(去相关 top{TOPK} + 波动率目标{VOL_TARGET:.0%}) ---")
    for i, r in enumerate(selected, 1):
        print(f"  {i}. {r['name']}({r['code']})  6月 {r['mom6']*100:+.1f}%")
    if len(selected) < TOPK:
        print(f"  现金: {TOPK - len(selected)}/{TOPK} 仓位(合格不足)")
    if not np.isnan(rv):
        print(f"  建议敞口: {expo:.0%}(组合已实现波动 {rv:.0%} vs 目标 {VOL_TARGET:.0%}),其余 {1 - expo:.0%} 现金")


def print_md(rows):
    ok, eligible = _rank(rows)
    asof = _asof(rows)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    sk = sorted(ok, key=lambda r: r["mom6"], reverse=True)
    selected = _decorrelate(eligible)
    expo, rv = _suggest_exposure(selected)
    naive = eligible[:TOPK]
    L = []
    L.append("> ⚙️ **本页由 `etf-momentum` skill 自动生成,请勿手改。重跑刷新。**")
    L.append(f"> 数据 as-of **{asof}**(sina 日线) · 生成时间 {now} · 代码源 `skills/etf-momentum/universe.py`")
    L.append("")
    L.append(f"参数:6 月动量({LOOKBACK} 交易日) · {MA} 日均线趋势过滤 · 去相关 top-{TOPK}(候选 {TOPN}) · 波动率目标 {VOL_TARGET:.0%} · 流动性闸 规模≥{AUM_MIN_YI} 亿 且 日均成交≥{LIQ_MIN_YI} 亿")
    L.append("")
    L.append("> AUM 列取腾讯「总市值」(`total_mcap_y`)近似,非 f10 基金净资产口径;作 ≥20 亿 粗闸够用(量级实测吻合,如 510300≈1391.92 亿)。")
    L.append("")
    L.append(f"## 当前信号(推荐持仓 = 去相关 top-{TOPK} + 波动率目标)")
    L.append("")
    if selected:
        L.append("| # | 板块 | 代码 | 6月动量 | AUM(亿) | 日均成交(亿) |")
        L.append("|---|---|---|---|---|---|")
        for i, r in enumerate(selected, 1):
            L.append(f"| {i} | {r['name']} | {r['code']} | {r['mom6']*100:+.1f}% | {_fmt_aum(r.get('aum'))} | {r['liq']:.2f} |")
    cash = TOPK - len(selected)
    if cash > 0:
        L.append(f"\n> ⚠️ 合格板块不足,**{cash}/{TOPK} 仓位转现金**(趋势刹车触发)。")
    if not np.isnan(rv):
        L.append(f"\n> **建议敞口 {expo:.0%}**(组合已实现波动 {rv:.0%} vs 目标 {VOL_TARGET:.0%}),其余 {1 - expo:.0%} 现金 — 波动率目标减仓。")
    if [r["code"] for r in naive] != [r["code"] for r in selected]:
        L.append("> 朴素动量 top-%d(未去相关,仅参考):%s。" % (
            TOPK, "、".join(f"{r['name']}({r['code']})" for r in naive)))
    L.append("")
    L.append("## 全量状态(按 6 月动量降序)")
    L.append("")
    L.append("| 板块 | 代码 | 6月动量 | 在200日线上 | AUM(亿) | 日均成交(亿) | 合格 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in sk:
        elig = "✓" if _eligible(r) else ""
        nm = r["name"] + ("·赛道" if r["theme"] else "")
        L.append(f"| {nm} | {r['code']} | {r['mom6']*100:+.1f}% | {'是' if r['above'] else '否'} | {_fmt_aum(r.get('aum'))} | {r['liq']:.2f} | {elig} |")
    fails = [r for r in rows if r["err"]]
    if fails:
        L.append("")
        L.append("取数失败(本次跳过):" + "、".join(f"{r['name']}({r['code']})" for r in fails))
    print("\n".join(L))


if __name__ == "__main__":
    rows = compute()
    if "--md" in sys.argv:
        print_md(rows)
    else:
        print_plain(rows)
