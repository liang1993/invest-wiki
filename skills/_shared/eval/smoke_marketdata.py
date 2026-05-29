#!/usr/bin/env python3
"""数据层 smoke eval — 检测取数接口漂移（Phase 0.2）

把过去靠手工记录的"已知不可用接口"（macro-analysis SKILL.md 里的
macro_china_shrzgm / macro_china_rmb）变成可重跑的回归用例。

两部分：
  A. value-invest 取数函数（封装层）—— 断言可调 + 返回非空 + 关键列/字段在
  B. macro-analysis / a-share-market 的裸 akshare 调用 —— 这两个 skill 无 .py
     模块，直接 import akshare 调；坏接口写成 known-fail（如期失败不阻断退出码）

退出码：非 known-fail 项全过 → 0；任一意外失败 → 1。
known-fail 如期失败报 ⚠️、若本次意外成功报 ℹ️（提示接口可能已恢复）。

用法：python3 skills/_shared/eval/smoke_marketdata.py
"""

import os
import sys
import time
import signal
from contextlib import contextmanager, redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "skills", "value-invest", "scripts"))

import fetch_data as fd  # noqa: E402  （封装层：财报/行情/PE 时序/同业）
import akshare as ak     # noqa: E402  （裸调用：市场层 + 宏观）

n_fail = 0


@contextmanager
def time_limit(seconds):
    def handler(signum, frame):
        raise TimeoutError(f"超过 {seconds}s")
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def check(name, fn, validate, timeout=30, known_fail=False, retries=1):
    """跑一项检查。validate(result) -> (ok: bool, msg: str)。
    非 known-fail 项对异常重试 retries 次（区分瞬时网络抖动 vs 真·接口漂移），
    避免源站（如 legulegu.com）单次超时造成退出码误报。"""
    global n_fail
    last_err = None
    for attempt in range(retries + 1):
        try:
            with time_limit(timeout), open(os.devnull, "w") as dn, redirect_stdout(dn):
                result = fn()
            last_err = None
            break
        except Exception as e:
            last_err = e
            if known_fail or attempt == retries:
                break
            time.sleep(2)

    if last_err is not None:
        if known_fail:
            print(f"  ⚠️  {name}: known-fail（如期失败 {type(last_err).__name__}）")
        else:
            print(f"  ❌ {name}: {type(last_err).__name__}: {str(last_err)[:90]}（重试 {retries} 次仍失败）")
            n_fail += 1
        return

    if known_fail:
        print(f"  ℹ️  {name}: known-fail 但本次成功 —— 接口可能已恢复，建议复核 SKILL.md")
        return

    ok, msg = validate(result)
    if ok:
        print(f"  ✅ {name}: {msg}")
    else:
        print(f"  ❌ {name}: 校验失败 — {msg}")
        n_fail += 1


def has_cols(df, *cols):
    c = getattr(df, "columns", [])
    return all(x in c for x in cols)


# ── A. value-invest 取数封装层（茅台 600519 / 同业五粮液 000858）──────────
print("── A. 取数封装层（marketdata 候选）──")

check("fetch_market_data(600519)", lambda: fd.fetch_market_data("600519"),
      lambda r: (isinstance(r, dict) and bool(r) and "price" in r,
                 f"price={r.get('price')} pe_ttm={r.get('pe_ttm')}"))

check("fetch_financial_summary(600519)", lambda: fd.fetch_financial_summary("600519"),
      lambda r: (r is not None and len(r) > 0 and has_cols(r, "指标"),
                 f"{len(r)} 行指标"))

check("fetch_history_with_pe(600519)", lambda: fd.fetch_history_with_pe("600519"),
      lambda r: (r is not None and len(r) > 0 and has_cols(r, "peTTM", "close"),
                 f"{len(r)} 日, 含 peTTM"), timeout=45)

check("fetch_research_consensus(600519)", lambda: fd.fetch_research_consensus("600519"),
      lambda r: (True, f"{len(r)} 篇" if (r is not None and len(r) > 0) else "无数据（合法）"))

check("fetch_peers([000858])", lambda: fd.fetch_peers(["000858"]),
      lambda r: (True, "运行无异常"))  # 仅 print 无返回值，验"可跑"

# ── B. 裸 akshare 调用（市场层 + 宏观）+ known-fail ──────────────────────
print("── B. 裸 akshare（market / macro）──")

check("stock_index_pe_lg(沪深300)", lambda: ak.stock_index_pe_lg(symbol="沪深300"),
      lambda r: (r is not None and len(r) > 0 and has_cols(r, "滚动市盈率"),
                 f"{len(r)} 行"))

check("macro_china_cpi()", lambda: ak.macro_china_cpi(),
      lambda r: (r is not None and len(r) > 0 and has_cols(r, "全国-同比增长"),
                 f"{len(r)} 行"))

# known-fail（macro-analysis SKILL.md 记录的坏接口）
check("macro_china_shrzgm() [社融]", lambda: ak.macro_china_shrzgm(),
      lambda r: (True, ""), known_fail=True)

check("macro_china_rmb() [汇率]", lambda: ak.macro_china_rmb(),
      lambda r: (True, ""), known_fail=True)

print(f"\n{'='*50}")
if n_fail == 0:
    print("smoke 通过：所有非 known-fail 接口正常")
    sys.exit(0)
else:
    print(f"smoke 失败：{n_fail} 项意外失败（区分网络抖动 vs 真·接口漂移）")
    sys.exit(1)
