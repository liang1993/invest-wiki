#!/usr/bin/env python3
"""审计脚本：离线单测 momentum.py 的 _decorrelate / _suggest_exposure / _ret_frame /
MA-skipna 修复 / compute 的 ret 对齐。用 data_etf/ 缓存 + 合成收益造 rec，不联网。

跑法: env -u HTTP_PROXY -u HTTPS_PROXY ... python3 research/audit_skill_overlays.py
（其实不联网，但 import momentum 会拉 _shared，保险起见。）
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, SKILL)
import momentum as M  # noqa: E402

DATA_ETF = os.path.join(HERE, "data_etf")

PASS, FAIL = [], []


def ok(cond, msg):
    (PASS if cond else FAIL).append(msg)
    print(("PASS " if cond else "FAIL ") + msg)


def mk_rec(code, ret_series, mom6=0.0, name=None):
    """造一个最小 rec（含 _decorrelate/_suggest_exposure 用到的字段）。"""
    return {"code": code, "name": name or code, "mom6": mom6, "ret": ret_series}


def load_ret(code, n=200):
    f = os.path.join(DATA_ETF, f"etf_{code}.csv")
    df = pd.read_csv(f, parse_dates=["date"]).sort_values("date")
    r = df["close"].pct_change()
    r.index = pd.to_datetime(df["date"])
    return r.iloc[-n:]


# ============================================================
# 1. 合成「已知答案」: 3 个高相关 + 1 个低相关 → 去相关必须把低相关那个挑进来
# ============================================================
print("\n=== 1. 合成已知答案：3 高相关 + 1 低相关 ===")
np.random.seed(7)
N = 160
idx = pd.bdate_range("2025-01-01", periods=N)
base = np.random.normal(0, 0.01, N)
# A,B,C 高度相关（共享 base，加微噪）；D 独立
a = base + np.random.normal(0, 0.0008, N)
b = base + np.random.normal(0, 0.0008, N)
c = base + np.random.normal(0, 0.0008, N)
d = np.random.normal(0, 0.01, N)
recs = [
    mk_rec("A", pd.Series(a, index=idx), mom6=0.50),  # 动量最强 → 锚定
    mk_rec("B", pd.Series(b, index=idx), mom6=0.40),
    mk_rec("C", pd.Series(c, index=idx), mom6=0.30),
    mk_rec("D", pd.Series(d, index=idx), mom6=0.20),  # 动量最弱，但与 A/B/C 低相关
]
# 朴素 top3 = A,B,C（全高相关）。去相关 top3 应锚 A 后挑 D（低相关），再补一个。
sel = M._decorrelate(recs)
picked = [r["code"] for r in sel]
print("  动量序:", [r["code"] for r in recs], " 朴素 top3:", ["A", "B", "C"])
print("  去相关 top3:", picked)
ok(picked[0] == "A", "1a 锚定动量第1(A)")
ok("D" in picked, "1b 低相关的 D 被挑进 top3（核心：去相关真生效）")
ok(len(picked) == M.TOPK, f"1c 返回 TOPK={M.TOPK} 个")
# 校验 book 内平均相关：去相关 book 应 < 朴素 ABC book
fr_corr = M._ret_frame(recs)
abc = fr_corr[["A", "B", "C"]].corr().values
abc_avg = (abc.sum() - 3) / 6
sel_corr = fr_corr[picked].corr().values
sel_avg = (sel_corr.sum() - 3) / 6
print(f"  朴素ABC平均相关={abc_avg:.2f}  去相关book平均相关={sel_avg:.2f}")
ok(sel_avg < abc_avg, "1d 去相关 book 平均相关 < 朴素 book（机制确认）")


# ============================================================
# 2. 与 crowding_overlay.greedy_lowcorr 逐项对齐（同输入同输出）
# ============================================================
print("\n=== 2. _decorrelate 内核 vs 验证过的 greedy_lowcorr ===")
sys.path.insert(0, HERE)
import crowding_overlay as CO  # noqa: E402

# 用真实 data_etf 6 只造候选（动量任意降序），各取 160 日收益
codes6 = ["159611", "159638", "159566", "159326", "159558", "159316"]
ret_map = {c: load_ret(c, 160) for c in codes6}
recs6 = [mk_rec(c, ret_map[c], mom6=1.0 - i * 0.1) for i, c in enumerate(codes6)]

# momentum._decorrelate 的相关阵口径：_ret_frame(cand).dropna() 后 iloc[-VOL_LB:].corr()
frame6 = M._ret_frame(recs6)
# greedy_lowcorr 期望 ordered=代码列表, corr=相关阵(abs 在内部取)
co_corr = frame6.iloc[-M.VOL_LB:].corr()  # CO.greedy_lowcorr 内部对 corr 取 abs
co_pick = CO.greedy_lowcorr([r["code"] for r in recs6], co_corr)
m_pick = [r["code"] for r in M._decorrelate(recs6)]
print("  CO.greedy_lowcorr:", co_pick[:M.TOPK])
print("  M._decorrelate   :", m_pick)
ok(co_pick[: M.TOPK] == m_pick, "2a 与 crowding_overlay 选券完全一致")


# ============================================================
# 3. 边界：候选≤TOPK / 数据<20行 / 相关阵列缺失 → 退化朴素 top-K 不崩
# ============================================================
print("\n=== 3. _decorrelate 边界退化 ===")
# 3a 候选 == TOPK
two_plus = recs6[:M.TOPK]
ok([r["code"] for r in M._decorrelate(two_plus)] == [r["code"] for r in two_plus[:M.TOPK]],
   "3a 候选==TOPK 直接 top-K")
# 3b 候选 < TOPK
one = recs6[:1]
ok([r["code"] for r in M._decorrelate(one)] == ["159611"], "3b 候选<TOPK 返回全部(1个)")
# 3c 数据 <20 行：每只只给 10 个点
short = [mk_rec(c, load_ret(c, 10), mom6=1 - i * .1) for i, c in enumerate(codes6)]
sp = M._decorrelate(short)
ok([r["code"] for r in sp] == codes6[:M.TOPK], "3c 历史<20行 退化朴素 top-K(不崩)")
# 3d ret 缺失（None）：候选多但相关阵列<TOPK
nofeat = [mk_rec(c, None, mom6=1 - i * .1) for i, c in enumerate(codes6)]
nf = M._decorrelate(nofeat)
ok([r["code"] for r in nf] == codes6[:M.TOPK], "3d ret 全 None 退化朴素 top-K(不崩)")
# 3e 空 eligible
ok(M._decorrelate([]) == [], "3e 空输入返回空")


# ============================================================
# 4. _suggest_exposure：敞口∈[0,1]、不加杠杆、数据不足返回 (1.0, nan)
# ============================================================
print("\n=== 4. _suggest_exposure ===")
expo, rv = M._suggest_exposure(recs6[:3])
print(f"  真实3只: 敞口={expo:.2%} 已实现波动={rv:.2%}")
ok(0.0 <= expo <= 1.0, "4a 敞口∈[0,1]")
ok(rv > 0, "4b 已实现波动>0")
# 手算复核：等权 book 的 std*sqrt(252)，敞口=min(1,0.15/rv)
fr = M._ret_frame(recs6[:3]).iloc[-M.VOL_LB:]
book = fr.mean(axis=1)
rv_man = float(book.std() * np.sqrt(252))
expo_man = min(1.0, M.VOL_TARGET / rv_man) if rv_man > 0 else 1.0
ok(abs(rv - rv_man) < 1e-9 and abs(expo - expo_man) < 1e-9, "4c 手算复核一致")
# 4d 低波 book → 敞口应 = 1.0（不加杠杆，clip 到 1）
calm = pd.Series(np.random.normal(0, 0.0005, 160), index=idx)  # 年化 ~0.8%
e2, rv2 = M._suggest_exposure([mk_rec("X", calm), mk_rec("Y", calm * 0 + calm.values[::-1])])
print(f"  低波book: 敞口={e2:.2%} 波动={rv2:.2%}")
ok(e2 == 1.0, "4d 低波 book 敞口封顶 1.0（不加杠杆）")
# 4e 数据不足 → (1.0, nan)
e3, rv3 = M._suggest_exposure([mk_rec("Z", load_ret("159611", 10))])
ok(e3 == 1.0 and np.isnan(rv3), "4e 数据<20行 返回 (1.0, nan)")
e4, rv4 = M._suggest_exposure([])
ok(e4 == 1.0 and np.isnan(rv4), "4f 空 selected 返回 (1.0, nan)")


# ============================================================
# 5. _ret_frame：不同长度对齐 + 无重叠 guard
# ============================================================
print("\n=== 5. _ret_frame 对齐 / 无重叠 ===")
# 5a 不同长度：内连接后行数 = 最短重叠
long_r = load_ret("159611", 200)  # 老
short_r = load_ret("159316", 100)  # 年轻，日期是 long 的子集尾部
f2 = M._ret_frame([mk_rec("L", long_r), mk_rec("S", short_r)])
ok(not f2.empty and f2.shape[1] == 2, "5a 不同长度 ETF 内连接成 2 列")
ok(len(f2) <= len(short_r.dropna()), "5b 对齐行数 ≤ 较短序列")
# 5c 完全无日期重叠 → 空表
ra = pd.Series([0.01, 0.02], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
rb = pd.Series([0.01, 0.02], index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
f3 = M._ret_frame([mk_rec("A", ra), mk_rec("B", rb)])
ok(f3.empty, "5c 无日期重叠 → 空表（被 dropna 清空）")
# 5d 空表喂给下游不崩
ok(M._decorrelate([mk_rec("A", ra, 0.5), mk_rec("B", rb, 0.4),
                   mk_rec("C", ra, 0.3), mk_rec("D", rb, 0.2)]) is not None,
   "5d 无重叠候选喂 _decorrelate 不崩")
ee, rr = M._suggest_exposure([mk_rec("A", ra), mk_rec("B", rb)])
ok(ee == 1.0 and np.isnan(rr), "5e 无重叠喂 _suggest_exposure → (1.0, nan)")


# ============================================================
# 6. MA-skipna 修复：年轻 ETF（<MA 历史）不算"在均线上"
# ============================================================
print("\n=== 6. MA skipna 修复 ===")
# 直接重放 compute() 里的均线/above 逻辑（不联网）
def above_flag(close: pd.Series):
    last = float(close.iloc[-1])
    ma_n = len(close) >= M.MA
    ma = float(close.iloc[-M.MA:].mean()) if ma_n else float("nan")
    return bool(ma_n and last > ma), ma_n

# 6a 年轻 ETF：159316 仅 287 行 > 200，其实满 MA。换个 <200 的合成：120 单调上涨
young = pd.Series(np.linspace(1.0, 2.0, 120))  # 一路涨，现价远高于任何短均线
ab, mn = above_flag(young)
ok(mn is False and ab is False, "6a <MA 历史(120<200) above=False（修复点：不假合格）")
# 6b 旧版 skipna 行为对照：c.iloc[-200:].mean() 对 120 行=全段均值，单调涨→last>mean→假合格
old_ma = float(young.iloc[-M.MA:].mean())  # skipna 默认，对 120 行取这 120 的均值
ok(float(young.iloc[-1]) > old_ma, "6b 旧 skipna 写法确会假合格（确认 bug 真实存在）")
# 6c 满 MA 且在线上：250 行单调涨 → above=True（不误伤）
mature_up = pd.Series(np.linspace(1.0, 3.0, 250))
ab2, mn2 = above_flag(mature_up)
ok(mn2 and ab2, "6c 满 MA 且现价>均线 above=True（不误伤合格票）")
# 6d 满 MA 但跌破：250 行先涨后崩，现价 < 200日均
mature_dn = pd.Series(list(np.linspace(1.0, 3.0, 200)) + list(np.linspace(3.0, 1.2, 50)))
ab3, mn3 = above_flag(mature_dn)
ok(mn3 and (ab3 == (float(mature_dn.iloc[-1]) > float(mature_dn.iloc[-M.MA:].mean()))),
   "6d 满 MA 跌破时 above 反映真实关系")


# ============================================================
# 7. ret 字段长度/索引对齐（compute 里 ret.index = to_datetime(df['date'])）
# ============================================================
print("\n=== 7. ret 索引对齐 ===")
f = os.path.join(DATA_ETF, "etf_159611.csv")
df = pd.read_csv(f, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
cc = df["close"]
ret = cc.pct_change()
ret.index = pd.to_datetime(df["date"])  # 与 momentum.compute 同写法
ok(len(ret) == len(df), "7a ret 长度==df（pct_change 同长，赋索引不改长）")
ok(ret.index.is_monotonic_increasing, "7b ret 索引升序（去相关 .corr 对齐前提）")
ok(pd.isna(ret.iloc[0]), "7c 首行 NaN（pct_change），会被 _ret_frame.dropna 清掉")


# ============================================================
print("\n" + "=" * 50)
print(f"audit_skill_overlays: {len(PASS)} PASS / {len(FAIL)} FAIL")
if FAIL:
    print("FAILED:")
    for m in FAIL:
        print("  -", m)
    sys.exit(1)
