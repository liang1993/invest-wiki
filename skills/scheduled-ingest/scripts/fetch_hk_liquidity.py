#!/usr/bin/env python3
"""港股流动性周度快照 —— 取数 + 三层信号灯套档 + ⚡回扫 + 渲染。

设计 SSOT：docs/hk-liquidity-plan.md（§4 信号灯与阈值 / §5 架构）。
取数走 skills/_shared/marketdata/hk_liquidity.py；本脚本只做套档、
事件回扫、缺数处理与 md/JSON 渲染，纯函数可单测
（skills/scheduled-ingest/tests/test_hk_liquidity.py）。

用法：
  python3 skills/scheduled-ingest/scripts/fetch_hk_liquidity.py
  可选：--days-back 10（⚡回扫窗口）  --no-json（不落 raw JSON）

输出：
  stdout —— wiki 快照节 md（含逐项来源，兼作 L2 阶段 A 数据声明清单）
  raw/articles/market/hk-liquidity/YYYY-MM-DD.json —— 多源审计
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "skills", "_shared"))

# ── 档位常量（SSOT：docs/hk-liquidity-plan.md §4；⚙ 项待 52 周分位校准）──
MONEY_BALANCE_BANDS = (500, 800)      # 亿：<500 🔴 / 500-800 🟡 / >800 🟢
MONEY_HIBOR_BANDS = (1.5, 4.0)        # %：<1.5 🟢 / 1.5-4 🟡 / >4 🔴
TRADING_BANDS = (1500, 2200, 3500)    # 亿：🔴缩量/🟡清淡/🟢常态-活跃/🟠放量 ⚙
FLOW_BANDS = (-200, 100, 300)         # 亿：🔴/🟡/🟢/🟢⁺ ⚙
SPREAD_TAG_BP = -200                  # 利差 < -200bp → 套息压力积累
AH_TAG_BANDS = (125, 135, 150)        # <125 弱化 / 135-150 中枢 / >150 折价深
VHSI_TAG_BANDS = (20, 30, 35)         # <20 自满 / >30 紧张 / >35 恐慌
SHORT_TAG_BANDS = (10, 18)            # ex-ETP：<10% 空头收缩 / >18% 空压高 ⚙
EVENT_SB_DAILY = 100                  # 南向单日 |净买| > 100 亿 → ⚡
EVENT_HIBOR_JUMP = 0.5                # 1M HIBOR 单日 |Δ| > 50bp → ⚡
STALE_CAL_DAYS = 7                    # 数据日期距今 > 7 自然日 ≈ 5 交易日 → 未评级

TIGHTNESS = {"🔴": 3, "🟠": 2, "🟡": 1, "🟢": 0}


# ── 纯函数：套档 ─────────────────────────────────────────────────────────

def money_light(balance_yi: float | None, hibor_1m: float | None):
    """货币面：总结余/1M HIBOR 各自分档，取紧合成（方案 §4.1）。"""
    if balance_yi is None or hibor_1m is None:
        missing = "总结余" if balance_yi is None else "1M HIBOR"
        return None, f"未评级（缺 {missing}）"
    lo, hi = MONEY_BALANCE_BANDS
    bal = "🔴" if balance_yi < lo else ("🟡" if balance_yi <= hi else "🟢")
    g, r = MONEY_HIBOR_BANDS
    hib = "🟢" if hibor_1m < g else ("🟡" if hibor_1m <= r else "🔴")
    light = bal if TIGHTNESS[bal] >= TIGHTNESS[hib] else hib
    return light, f"结余{bal} × HIBOR{hib} 取紧"


def trading_light(turnover_5d_avg: float | None, vhsi: float | None):
    """交易面：滚动 5 日均成交穷尽分档；🟠放量由 VHSI 定名（方案 §4.2）。"""
    if turnover_5d_avg is None:
        return None, "未评级（缺 成交额）"
    a, b, c = TRADING_BANDS
    if turnover_5d_avg < a:
        return "🔴", "缩量"
    if turnover_5d_avg < b:
        return "🟡", "清淡"
    if turnover_5d_avg <= c:
        return "🟢", "常态-活跃"
    if vhsi is None:
        return "🟠", "放量（VHSI 缺失未定性）"
    if vhsi < VHSI_TAG_BANDS[0]:
        return "🟠", "放量自满（顶部形态⚡）"
    if vhsi > VHSI_TAG_BANDS[2]:
        return "🟠", "放量恐慌（急跌形态⚡）"
    return "🟠", "放量"


def flow_light(sb_5d: float | None, sb_prev_5d: float | None):
    """资金流：南向滚动 5 日净买穷尽分档，连续 2 窗 <0 防频闪升 🔴（§4.3）。"""
    if sb_5d is None:
        return None, "未评级（缺 南向）"
    a, b, c = FLOW_BANDS
    if sb_5d < a:
        return "🔴", "流出"
    if sb_5d < b:
        if sb_5d < 0 and sb_prev_5d is not None and sb_prev_5d < 0:
            return "🔴", "流出（连续 2 窗 <0）"
        return "🟡", "弱/中性"
    if sb_5d <= c:
        return "🟢", "流入"
    return "🟢⁺", "强流入"


def spread_bp(hibor_1m: float | None, sofr: float | None):
    """1M HIBOR − SOFR（bp）。符号约定：负值=套息压力（方案 §2.1#3）。"""
    if hibor_1m is None or sofr is None:
        return None
    return round((hibor_1m - sofr) * 100)


def make_tags(*, spread: float | None, band_pos: float | None,
              vhsi: float | None, short_ex_etp: float | None,
              ah: float | None) -> list[str]:
    """修饰标签（不定灯，缺输入即省略；方案 §4.1-4.3 / §4.7）。"""
    tags = []
    if spread is not None and spread < SPREAD_TAG_BP:
        tags.append(f"套息压力积累（利差 {spread:+d}bp）")
    if band_pos is not None:
        if band_pos >= 90:
            tags.append(f"贴弱方（区间 {band_pos:.0f}%）")
        elif band_pos <= 10:
            tags.append(f"贴强方（区间 {band_pos:.0f}%）")
    if vhsi is not None:
        if vhsi > VHSI_TAG_BANDS[2]:
            tags.append(f"VHSI 恐慌区（{vhsi:.1f}）")
        elif vhsi > VHSI_TAG_BANDS[1]:
            tags.append(f"VHSI 紧张（{vhsi:.1f}）")
        elif vhsi < VHSI_TAG_BANDS[0]:
            tags.append(f"VHSI 自满区（{vhsi:.1f}）")
    if short_ex_etp is not None:
        if short_ex_etp > SHORT_TAG_BANDS[1]:
            tags.append(f"空压高（卖空 {short_ex_etp:.0f}%）")
        elif short_ex_etp < SHORT_TAG_BANDS[0]:
            tags.append(f"空头收缩（卖空 {short_ex_etp:.0f}%）")
    if ah is not None:
        if ah < AH_TAG_BANDS[0]:
            tags.append(f"AH {ah:.1f} 估值吸引力弱化")
        elif ah > AH_TAG_BANDS[2]:
            tags.append(f"AH {ah:.1f} 折价深-南向动能支撑")
    return tags


def scan_events(hkma_rows: list[dict], sb_daily: list[tuple[str, float]],
                days_back: int, today: dt.date | None = None) -> list[str]:
    """⚡事件回扫（回溯口径，方案 §4.5）。

    hkma_rows 新→旧（含 market_activities / hibor_1m）；
    sb_daily 为 (date_iso, net_buy_yi) 列表（任意序）。
    """
    today = today or dt.date.today()
    cutoff = (today - dt.timedelta(days=days_back)).isoformat()
    events = []
    rows = [r for r in hkma_rows if r["date"] >= cutoff]
    for r in rows:
        act = str(r.get("market_activities") or "").replace(",", "").strip()
        try:
            nonzero = act != "" and float(act) != 0
        except ValueError:
            nonzero = False
        if nonzero:
            events.append(f"{r['date']} 金管局操作 {act}（兑换保证触发级干预）")
    rows_old2new = list(reversed(rows))
    for prev, cur in zip(rows_old2new, rows_old2new[1:]):
        if prev.get("hibor_1m") is not None and cur.get("hibor_1m") is not None:
            d = cur["hibor_1m"] - prev["hibor_1m"]
            if abs(d) > EVENT_HIBOR_JUMP:
                events.append(f"{cur['date']} 1M HIBOR 单日 {d:+.2f}pp")
    for date_iso, v in sorted(sb_daily):
        if date_iso >= cutoff and abs(v) > EVENT_SB_DAILY:
            events.append(f"{date_iso} 南向单日 {v:+.0f} 亿")
    return events


def is_stale(date_iso: str | None, today: dt.date | None = None) -> bool:
    """新鲜度：数据日期距今 > STALE_CAL_DAYS 自然日 → stale（≈5 交易日）。"""
    if not date_iso:
        return True
    today = today or dt.date.today()
    d = dt.date.fromisoformat(str(date_iso)[:10])
    return (today - d).days > STALE_CAL_DAYS


# ── 采集 + 渲染 ──────────────────────────────────────────────────────────

def collect(days_back: int) -> dict:
    """拉全部 9 指标 → 结构化 snapshot dict（含缺数清单与来源标注）。"""
    from marketdata import hk_liquidity as hk
    snap: dict = {"date": dt.date.today().isoformat(), "missing": [], "sources": {}}

    def _try(name, fn, source):
        try:
            v = fn()
            if v is None:
                raise ValueError("返回空")
            snap["sources"][name] = source
            return v
        except Exception as e:  # noqa: BLE001 —— 缺数走未评级，不中断
            snap["missing"].append(f"{name}（{type(e).__name__}）")
            return None

    hkma = _try("HKMA", lambda: hk.hkma_daily(max(days_back + 8, 15)),
                "HKMA Open API daily-figures-interbank-liquidity [观测]")
    sofr = _try("SOFR", lambda: hk.sofr_last(5),
                "NY Fed markets API sofr [观测]")
    fx = _try("USDHKD", hk.usdhkd, "新浪 fx_susdhkd [观测·转发源]")
    dayq = _try("成交/卖空", lambda: hk.dayquot_recent(5),
                "HKEX dayquot（近 5 交易日）[观测]")
    vs = _try("VHSI", hk.vhsi_spot, "腾讯 hkVHSI [观测·转发源]")
    sb = _try("南向", hk.southbound_hist,
              "东财 hsgt_hist_em 沪+深成交净买额 [观测·转发源]")
    ah = _try("AH溢价", hk.ah_premium, "东财 push2 100.HSAHP [观测·转发源]")

    latest_hkma = hkma[0] if hkma else {}
    if hkma and is_stale(latest_hkma.get("date")):
        snap["missing"].append(f"HKMA（stale：{latest_hkma.get('date')}）")
        latest_hkma = {}
    snap["hkma"] = latest_hkma
    snap["hkma_rows"] = hkma or []
    snap["sofr"] = sofr[0] if sofr else {}
    snap["fx"] = fx or {}
    snap["dayquot"] = dayq or []
    snap["vhsi"] = vs or {}
    snap["ah"] = ah or {}

    if dayq:
        snap["turnover_5d_avg"] = round(
            sum(r["turnover_yi"] for r in dayq) / len(dayq), 1)
        snap["turnover_window"] = f'{dayq[-1]["date"]}~{dayq[0]["date"]}'
        snap["short_ex_etp"] = dayq[0].get("short_pct_ex_etp")
        snap["short_all"] = dayq[0].get("short_pct_all")
    else:
        snap["turnover_5d_avg"] = None
        snap["short_ex_etp"] = snap["short_all"] = None

    snap["sb_5d"] = snap["sb_prev_5d"] = None
    snap["sb_daily"] = []
    if sb is not None and len(sb) >= 10:
        tail = sb.tail(days_back + 5)
        snap["sb_daily"] = [(str(r.date)[:10], float(r.net_buy_yi))
                            for r in tail.itertuples()]
        snap["sb_5d"] = round(float(sb["net_buy_yi"].tail(5).sum()), 1)
        snap["sb_prev_5d"] = round(float(sb["net_buy_yi"].iloc[-10:-5].sum()), 1)
        snap["sb_window"] = f'{str(sb["date"].iloc[-5])[:10]}~{str(sb["date"].iloc[-1])[:10]}'
        if is_stale(str(sb["date"].iloc[-1])[:10]):
            snap["missing"].append(f'南向（stale：{str(sb["date"].iloc[-1])[:10]}）')
            snap["sb_5d"] = snap["sb_prev_5d"] = None
    return snap


def render(snap: dict, days_back: int) -> str:
    """渲染 wiki 快照节（机器可解析固定表头；兼作 L2 阶段 A 清单）。"""
    hkma, fx, vs, ah = snap["hkma"], snap["fx"], snap["vhsi"], snap["ah"]
    bal = hkma.get("closing_balance_yi")
    h1m = hkma.get("hibor_1m")
    sp = spread_bp(h1m, snap["sofr"].get("rate"))

    m_light, m_note = money_light(bal, h1m)
    t_light, t_note = trading_light(snap["turnover_5d_avg"], vs.get("value"))
    f_light, f_note = flow_light(snap["sb_5d"], snap["sb_prev_5d"])
    tags = make_tags(spread=sp, band_pos=fx.get("band_pos_pct"),
                     vhsi=vs.get("value"), short_ex_etp=snap["short_ex_etp"],
                     ah=ah.get("value"))
    events = scan_events(snap["hkma_rows"], snap["sb_daily"], days_back)

    def fmt(v, pat="{}"):
        return pat.format(v) if v is not None else "—"

    miss = "、".join(snap["missing"]) if snap["missing"] else "无（✓）"
    ev = "；".join(events) if events else "无"
    lines = [
        f'### {snap["date"]} 快照',
        "",
        f"- ⚠️ 缺数：{miss}",
        f"- ⚡ 窗口内事件（近 {days_back} 天回扫）：{ev}",
        "",
        "| 层 | 灯 | 主变量读数 | 辅助读数 |",
        "|---|---|---|---|",
        (f"| 货币面 | {m_light or '⚪'} {m_note} | 总结余 {fmt(bal, '{:.0f} 亿')}"
         f"（{fmt(hkma.get('date'))}）· 1M HIBOR {fmt(h1m, '{:.2f}%')} | "
         f"O/N {fmt(hkma.get('hibor_on'), '{:.2f}%')} · 利差 {fmt(sp, '{:+d}bp')} · "
         f"USDHKD {fmt(fx.get('price'))}（{fmt(fx.get('band_pos_pct'), '{:.0f}%')}）|"),
        (f"| 交易面 | {t_light or '⚪'} {t_note} | 5 日均成交 "
         f"{fmt(snap['turnover_5d_avg'], '{:,.0f} 亿')}"
         f"（{snap.get('turnover_window', '—')}）| VHSI {fmt(vs.get('value'))} · "
         f"卖空 ex-ETP {fmt(snap['short_ex_etp'], '{}%')}/全 {fmt(snap['short_all'], '{}%')} |"),
        (f"| 资金流+估值 | {f_light or '⚪'} {f_note} | 南向 5 日净买 "
         f"{fmt(snap['sb_5d'], '{:+,.0f} 亿')}（{snap.get('sb_window', '—')}）| "
         f"前窗 {fmt(snap['sb_prev_5d'], '{:+,.0f} 亿')} · AH {fmt(ah.get('value'))} |"),
        "",
        f"- 标签：{'；'.join(tags) if tags else '无'}",
        "- 来源：" + "；".join(f"{k}={v}" for k, v in snap["sources"].items()),
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=10, help="⚡回扫窗口（自然日）")
    ap.add_argument("--no-json", action="store_true", help="不落 raw JSON")
    args = ap.parse_args()

    snap = collect(args.days_back)
    print(render(snap, args.days_back))

    if not args.no_json:
        out_dir = os.path.join(REPO, "raw", "articles", "market", "hk-liquidity")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f'{snap["date"]}.json')
        dump = {k: v for k, v in snap.items() if k != "hkma_rows"}
        dump["hkma_rows"] = snap["hkma_rows"][:10]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n[raw] {os.path.relpath(path, REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
