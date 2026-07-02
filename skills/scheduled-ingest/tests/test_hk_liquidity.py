"""fetch_hk_liquidity 纯函数单测（套档 / 防频闪 / ⚡回扫 / 新鲜度）。

档位语义 SSOT：docs/hk-liquidity-plan.md §4。历史四情形回测（§4.1）在
test_money_light_historical 固化，阈值改动时此处必须同步过。

运行：python3 -m pytest skills/scheduled-ingest/tests/test_hk_liquidity.py -q
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fetch_hk_liquidity import (  # noqa: E402
    flow_light, is_stale, make_tags, money_light, scan_events, spread_bp,
    trading_light,
)


# ── 货币面：方案 §4.1 历史四情形回测 ─────────────────────────────────────

def test_money_light_historical():
    assert money_light(445, 5.66)[0] == "🔴"      # 2023 钱荒地板
    assert money_light(1700, 0.8)[0] == "🟢"      # 2025-05~07 注资极宽
    assert money_light(961, 5.08)[0] == "🔴"      # 2022H2：结余不低但利率紧 → 取紧
    assert money_light(540, 2.94)[0] == "🟡"      # 2026 新常态


def test_money_light_missing():
    light, note = money_light(None, 2.9)
    assert light is None and "总结余" in note
    light, note = money_light(540, None)
    assert light is None and "1M HIBOR" in note


# ── 交易面：穷尽分档 + 放量定性 ──────────────────────────────────────────

def test_trading_light_bands():
    assert trading_light(1000, 25)[0] == "🔴"
    assert trading_light(2000, 25)[0] == "🟡"
    assert trading_light(2929, 25)[0] == "🟢"     # 2026-05 官方 ADT
    assert trading_light(3500, 25)[0] == "🟢"     # 边界含入常态
    assert trading_light(None, 25)[0] is None


def test_trading_light_high_volume_naming():
    assert trading_light(3600, 18) == ("🟠", "放量自满（顶部形态⚡）")
    assert trading_light(3600, 40) == ("🟠", "放量恐慌（急跌形态⚡）")   # 2025-04 式
    assert trading_light(3600, 25)[1] == "放量"
    assert "未定性" in trading_light(3600, None)[1]


# ── 资金流：防频闪 ───────────────────────────────────────────────────────

def test_flow_light_bands():
    assert flow_light(-250, 50)[0] == "🔴"
    assert flow_light(150, 0)[0] == "🟢"
    assert flow_light(350, 0)[0] == "🟢⁺"
    assert flow_light(None, 0)[0] is None


def test_flow_light_anti_flicker():
    # 单窗小幅为负 → 🟡；连续两窗 <0 → 升 🔴
    assert flow_light(-50, 30)[0] == "🟡"
    assert flow_light(-50, -100)[0] == "🔴"
    # 2026-07-02 实况：本窗 -178、前窗为正 → 🟡
    assert flow_light(-178, 55)[0] == "🟡"


# ── 派生与标签 ──────────────────────────────────────────────────────────

def test_spread_bp():
    assert spread_bp(2.94, 3.68) == -74
    assert spread_bp(None, 3.68) is None


def test_make_tags():
    tags = make_tags(spread=-250, band_pos=93.6, vhsi=36.0,
                     short_ex_etp=19, ah=123.87)
    joined = "；".join(tags)
    assert "套息压力" in joined and "贴弱方" in joined
    assert "恐慌" in joined and "空压高" in joined and "弱化" in joined
    # 中性读数不产标签
    assert make_tags(spread=-74, band_pos=50, vhsi=25, short_ex_etp=14,
                     ah=140) == []


# ── ⚡回扫 ───────────────────────────────────────────────────────────────

def test_scan_events():
    today = dt.date(2026, 7, 2)
    hkma = [
        {"date": "2026-07-02", "market_activities": "+0", "hibor_1m": 2.79},
        {"date": "2026-06-30", "market_activities": "-0", "hibor_1m": 2.94},
        {"date": "2026-06-29", "market_activities": "+11,660", "hibor_1m": 2.95},
        {"date": "2026-06-26", "market_activities": "+0", "hibor_1m": 2.30},
        {"date": "2026-06-01", "market_activities": "+99,999", "hibor_1m": 2.30},
    ]
    sb = [("2026-06-29", -103.4), ("2026-06-30", 58.9), ("2026-06-01", -300.0)]
    ev = "\n".join(scan_events(hkma, sb, days_back=10, today=today))
    assert "2026-06-29 金管局操作 +11660" in ev
    assert "2026-06-29 南向单日 -103" in ev
    assert "1M HIBOR 单日 +0.65pp" in ev        # 6/26 2.30 → 6/29 2.95
    assert "2026-06-01" not in ev               # 窗口外
    assert "金管局操作 +0" not in ev            # 零操作不算事件


def test_is_stale():
    today = dt.date(2026, 7, 2)
    assert is_stale("2026-06-24", today) is True    # 8 自然日
    assert is_stale("2026-06-29", today) is False
    assert is_stale(None, today) is True
