#!/usr/bin/env python3
"""中性宏观量化组合 —— 再平衡计算器(holdings-agnostic 抽象工作流)。

策略 = 中性方案(回测见 ../etf-momentum/research/findings_macro_overlay.md):
  静态大类 E40 / B22 / G21 / C17 + 整组合波动率目标 12%；权益 = etf-momentum 去相关 top3。
  回测(2013-26,独立审计)结论:宏观 regime 择时不加分,收益来自"静态分散 + 波动率目标"两层风控。

本 skill 只做抽象计算(目标权重 + 对照持仓出买卖差额),**自身不含任何持仓数据**。
持仓由调用方运行时传入(--holdings 文件 或 --capital 从零建仓);持仓属个人隐私,数据文件应
存放在本仓库之外的私有位置(勿提交),本 skill 通过参数读取,无隐私耦合 —— 故可公开进 skills/。

用法(联网;若代理干扰:env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY ... python3 rebalance.py):
  python3 rebalance.py --capital 500000                 # 从零建仓:出目标配置 + 下单清单
  python3 rebalance.py --holdings <path>                # 月度再平衡:出买卖调整
  python3 rebalance.py --holdings <path> --weights 50,20,18,12 --vol-target 0.10   # 改档(进取/保守)
"""
from __future__ import annotations
import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "etf-momentum"))
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))
import momentum  # wiki 通用 skill(holdings-agnostic)
from marketdata.etf_hist import get_etf_hist
from marketdata import quote_tencent

DEFAULT_BOND, DEFAULT_GOLD = "511260", "518880"  # 债 / 黄金 桶标的(可 --bond/--gold 改)
CASH_NAMES = {"511990"}                           # 视为现金的场内货币 ETF
BAND = 0.015                                       # 已有仓微调 < 总资产 1.5% 则不动(省零碎换手)


def read_holdings(path):
    hold, cash = {}, 0.0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.split("#")[0].strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 2:
                continue  # 缺金额的行跳过
            code, amt = parts[0], float(parts[1])
            if code.upper() == "CASH" or code in CASH_NAMES:
                cash += amt
            else:
                hold[code] = hold.get(code, 0.0) + amt
    return hold, cash


def exposure_and_prices(eq_codes, extra_codes, vol_target, weights, bond, gold):
    """整组合近 VOL_LB 日已实现波动 → vol 敞口；返回 (敞口, 波动, {code: 现价})。"""
    hist_codes = eq_codes + [bond, gold]
    hist = {}
    for c in hist_codes:
        df = get_etf_hist(c)
        if df is not None and len(df):           # 取数失败的桶跳过(不裸崩)
            hist[c] = df.set_index(pd.to_datetime(df["date"]))["close"]
    price_codes = list(dict.fromkeys(hist_codes + list(extra_codes)))
    q = quote_tencent.get_quotes(price_codes)
    cash_d = (1.018) ** (1 / 252) - 1
    today = pd.Timestamp.now().normalize()
    rets = {}
    for c, s in hist.items():
        p = q.get(c, {}).get("price")
        if p:                                     # 今日去重 + 实时价为准(防历史已含今日K线时重复日污染波动)
            s = pd.concat([s[s.index < today], pd.Series({today: float(p)})])
        rets[c] = s.pct_change()
    r = pd.DataFrame(rets).dropna().iloc[-momentum.VOL_LB:] if rets else pd.DataFrame()
    we = weights[0] / momentum.TOPK              # 固定 1/3：合格不足时权益自动欠配,空缺并入现金(对齐回测,且免除零)
    parts = [we * r[c] for c in eq_codes if c in r.columns]
    if bond in r.columns:
        parts.append(weights[1] * r[bond])
    if gold in r.columns:
        parts.append(weights[2] * r[gold])
    rv = float((sum(parts) + weights[3] * cash_d).std() * np.sqrt(252)) if parts else 0.0
    expo = min(1.0, vol_target / rv) if rv > 0 else 1.0

    def price_of(c):
        p = q.get(c, {}).get("price")
        if p:
            return float(p)
        if c in hist:
            return float(hist[c].iloc[-1])
        df = get_etf_hist(c)
        return float(df["close"].iloc[-1]) if df is not None and len(df) else None
    return expo, rv, {c: price_of(c) for c in price_codes}


def lots(amt, price):
    return round(amt / price / 100) if price else 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--holdings", help="持仓文件路径(每行 `代码 市值元`,现金 `CASH 金额`)")
    g.add_argument("--capital", type=float, help="从零建仓的总资金(元)")
    ap.add_argument("--weights", default="40,22,21,17", help="E,B,G,C 权重(百分比),默认中性 40,22,21,17")
    ap.add_argument("--vol-target", type=float, default=0.12, help="整组合波动率目标,默认 0.12")
    ap.add_argument("--bond", default=DEFAULT_BOND)
    ap.add_argument("--gold", default=DEFAULT_GOLD)
    args = ap.parse_args()

    bond, gold = args.bond, args.gold
    w = [float(x) for x in args.weights.split(",")]
    weights = tuple(x / sum(w) for x in w)  # 归一化 E/B/G/C
    hold, cash = read_holdings(args.holdings) if args.holdings else ({}, args.capital)

    rows = momentum.compute()
    _, eligible = momentum._rank(rows)
    selected = momentum._decorrelate(eligible)
    eq_codes = [r["code"] for r in selected]
    name = {r["code"]: r["name"] for r in rows if not r.get("err")}
    name.update({bond: "10年国债ETF", gold: "黄金ETF"})

    extra = [c for c in hold if c not in eq_codes + [bond, gold]]
    expo, rv, price = exposure_and_prices(eq_codes, extra, args.vol_target, weights, bond, gold)

    total = sum(hold.values()) + cash
    wE = weights[0] / momentum.TOPK  # 固定 1/3：合格不足时权益欠配,空缺自动落入 target_cash(对齐回测)
    target = {c: total * wE * expo for c in eq_codes}
    target[bond] = total * weights[1] * expo
    target[gold] = total * weights[2] * expo
    target_cash = total - sum(target.values())

    print(f"\n=== 中性组合再平衡 | as-of {momentum._asof(rows)} | 整组合波动 {rv:.1%} → vol@{args.vol_target:.0%} 敞口 {expo:.0%} ===")
    print("权益去相关 top3：" + " · ".join(f"{name[c]}({c})" for c in eq_codes))
    print(f"权重档 E/B/G/C = {'/'.join(f'{x:.0%}' for x in weights)} | 总资产 {total:,.0f}"
          + (f"（持仓 {sum(hold.values()):,.0f} + 现金 {cash:,.0f}）" if args.holdings else "（从零建仓）"))
    print(f"\n{'标的':<12}{'代码':<8}{'现价':>9}{'当前额':>11}{'目标额':>11}{'差额':>11}{'操作':>12}")
    actions = []
    for c in list(target) + extra:
        cur, tgt, p = hold.get(c, 0.0), target.get(c, 0.0), price.get(c)
        d = tgt - cur
        n = lots(abs(d), p) if p else None
        if tgt == 0 and cur > 0:
            op = f"清仓 {lots(cur, p)} 手" if p else "清仓"
        elif cur > 0 and tgt > 0 and abs(d) < BAND * total:
            op = "不动"
        elif p and n == 0:
            op = "不动"  # 差额不足 1 手
        elif d > 0:
            op = f"买 {n} 手" if p else f"买 {d:,.0f}"
        else:
            op = f"卖 {n} 手" if p else f"卖 {-d:,.0f}"
        ps = f"{p:.3f}" if p else "—"
        print(f"{name.get(c, c):<12}{c:<8}{ps:>9}{cur:>11,.0f}{tgt:>11,.0f}{d:>+11,.0f}{op:>12}")
        if op != "不动":
            actions.append(f"{op} {name.get(c, c)}")
    print(f"{'现金(货基)':<12}{'CASH':<8}{'':>9}{cash:>11,.0f}{target_cash:>11,.0f}{target_cash-cash:>+11,.0f}")
    print(f"\n目标: 权益 {sum(target[c] for c in eq_codes)/total:.0%} | 债 {target[bond]/total:.0%} "
          f"| 金 {target[gold]/total:.0%} | 现金 {target_cash/total:.0%}")
    print("本月操作：" + ("；".join(actions) if actions else "无（都在缓冲带内）"))


if __name__ == "__main__":
    main()
