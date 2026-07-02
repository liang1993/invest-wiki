"""marketdata/hk_liquidity 取数层单测（离线，无网络）。

覆盖 plan P1 验证标准点名项：dayquot 正则 / 节假日 guard / sanity 过滤，
外加 collect→render 全源缺数路径（stub 注入）。活网连通性归 smoke A3。

运行：python3 -c "见 repo 内联 runner 约定"（无 pytest 依赖，纯 assert）。
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "scheduled-ingest", "scripts"))

from marketdata import hk_liquidity as hkl  # noqa: E402
import fetch_hk_liquidity as fhk  # noqa: E402


# ── dayquot 正则（固定 HTML 片段，守漂移）────────────────────────────────

DAYQUOT_SNIPPET = """
<pre>
Total market turnover                                         : HKD    308,049,565,239
Short Selling of Designated Securities (excluding ETP) as % total turnover :       14%
Short Selling of all Designated Securities as % total turnover             :       19%
</pre>
"""


def test_parse_dayquot():
    r = hkl._parse_dayquot(DAYQUOT_SNIPPET, dt.date(2026, 6, 30))
    assert r == {"date": "2026-06-30", "turnover_yi": 3080.5,
                 "short_pct_ex_etp": 14, "short_pct_all": 19}


def test_parse_dayquot_no_match_and_sanity():
    assert hkl._parse_dayquot("<html>improved page</html>", dt.date(2026, 6, 30)) is None
    # 量级越界（如正则错抓到子表数字）→ None 而非带错值返回
    bad = "Total market turnover : HKD 1,239"
    assert hkl._parse_dayquot(bad, dt.date(2026, 6, 30)) is None


# ── HKMA 记录解析：sanity 过滤脏数据（2019 realdata 199.29 教训）─────────

def test_parse_hkma_records_sanity():
    recs = hkl._parse_hkma_records([
        {"end_of_date": "2026-06-30", "closing_balance": 53981,
         "hibor_overnight": 3.62, "hibor_fixing_1m": 2.93976,
         "disc_win_base_rate": 4, "market_activities": "+0"},
        {"end_of_date": "2019-06-11", "closing_balance": 54200,
         "hibor_overnight": 2.0, "hibor_fixing_1m": 199.29,   # 官方 API 真实脏数据
         "disc_win_base_rate": 2.75, "market_activities": "+0"},
    ])
    assert recs[0]["closing_balance_yi"] == 539.81
    assert recs[0]["hibor_1m"] == 2.93976
    assert recs[1]["hibor_1m"] is None          # 越界置 None，不带错值下行
    assert recs[1]["closing_balance_yi"] == 542.0


# ── 节假日 guard（monkeypatch hkex_dayquot，无网络）──────────────────────

def test_dayquot_recent_holiday_skip_and_gap():
    # 2026-07-01（周三，回归纪念日）无数据 → 跳过取到 6/30、6/29…
    calendar = {"2026-07-01": None,
                "2026-06-30": {"date": "2026-06-30", "turnover_yi": 3080.5},
                "2026-06-29": {"date": "2026-06-29", "turnover_yi": 3153.8}}
    orig = hkl.hkex_dayquot
    hkl.hkex_dayquot = lambda d, **kw: calendar.get(d.isoformat())
    try:
        out = hkl.dayquot_recent(2, end=dt.date(2026, 7, 1))
        assert [r["date"] for r in out] == ["2026-06-30", "2026-06-29"]

        # 连续 4 个非周末日无数据 → RuntimeError（URL 漂移防线）
        hkl.hkex_dayquot = lambda d, **kw: None
        try:
            hkl.dayquot_recent(1, end=dt.date(2026, 7, 1))
            raise AssertionError("应触发连续缺数 RuntimeError")
        except RuntimeError as e:
            assert "dayquot" in str(e)
    finally:
        hkl.hkex_dayquot = orig


# ── collect→render 全源缺数路径（stub 注入，§4.7 禁静默）────────────────

class _AllDownStub:
    """全部取数函数抛异常的 stub 模块。"""
    def __getattr__(self, name):
        def _boom(*a, **kw):
            raise ConnectionError("stub down")
        return _boom


def test_collect_render_all_sources_down():
    snap = fhk.collect(10, hk=_AllDownStub())
    text = fhk.render(snap, 10)
    assert len(snap["missing"]) == 7            # 7 个 _try 源全部记入缺数
    assert "未评级" in text                      # 三层灯不得套档
    assert "⚠️ 缺数" in text and "无（✓）" not in text
    # 任何一层都不允许出现真实灯色（无数据）
    for light in ("🔴", "🟠", "🟢", "🟡"):
        assert f"| {light}" not in text.replace("⚪", "")
