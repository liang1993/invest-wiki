#!/usr/bin/env python3
"""marketdata.codes 金标准单测（Phase 2 test-first）

钉死代码转换契约，再实现 codes.py。覆盖 review BLOCKER 4 的 4 处分歧 +
focus 列表真实代码（蜜雪 02097.HK / 招行H 03968.HK / 腾讯 0700↔00700 等）+
北交所(bj)。

用法：python3 skills/_shared/eval/test_codes.py
退出码：全过 0，任一不符 1。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from marketdata import codes  # noqa: E402

# (函数, 输入, 期望)
CASES = [
    # ── is_a_share ──（6 位纯数字 = A 股）
    (codes.is_a_share, "600519", True),
    (codes.is_a_share, "000858", True),
    (codes.is_a_share, "900901", True),     # 沪 B
    (codes.is_a_share, "02097.HK", False),
    (codes.is_a_share, "600519.SS", False),
    (codes.is_a_share, "AAPL", False),
    (codes.is_a_share, " 600519 ", True),   # strip

    # ── is_hk_share ──（带 .HK 后缀 = 港股）
    (codes.is_hk_share, "0700.HK", True),
    (codes.is_hk_share, "02097.HK", True),
    (codes.is_hk_share, "3690.hk", True),    # 大小写不敏感
    (codes.is_hk_share, "600519", False),
    (codes.is_hk_share, "600036.SS", False),
    (codes.is_hk_share, "AAPL", False),

    # ── to_yf_ticker ──（裁决表 4 条规则）
    (codes.to_yf_ticker, "600519", "600519.SS"),    # 茅台 沪 A
    (codes.to_yf_ticker, "000858", "000858.SZ"),    # 五粮液 深 A
    (codes.to_yf_ticker, "002594", "002594.SZ"),    # 比亚迪 中小板
    (codes.to_yf_ticker, "300750", "300750.SZ"),    # 宁德 创业板
    (codes.to_yf_ticker, "688981", "688981.SS"),    # 中芯 科创板
    (codes.to_yf_ticker, "900901", "900901.SS"),    # 规则3：沪 B → .SS（非 .SZ）
    (codes.to_yf_ticker, "600036.SH", "600036.SS"), # 规则1：.SH → .SS
    (codes.to_yf_ticker, "000858.SZ", "000858.SZ"), # 已是 yf 形态，保留
    (codes.to_yf_ticker, "600519.SS", "600519.SS"),
    (codes.to_yf_ticker, "02097.HK", "2097.HK"),    # 规则2：蜜雪，去前导零
    (codes.to_yf_ticker, "00700.HK", "0700.HK"),    # 规则2：腾讯 5 位写法
    (codes.to_yf_ticker, "0700.HK", "0700.HK"),     # 腾讯 4 位写法，幂等
    (codes.to_yf_ticker, "03968.HK", "3968.HK"),    # 招行 H
    (codes.to_yf_ticker, "AAPL", "AAPL"),           # 美股原样
    (codes.to_yf_ticker, "BABA", "BABA"),

    # ── to_tencent_symbol ──（sh/sz/bj 前缀，无点）
    (codes.to_tencent_symbol, "600519", "sh600519"),
    (codes.to_tencent_symbol, "000858", "sz000858"),
    (codes.to_tencent_symbol, "900901", "sh900901"),  # 沪 B
    (codes.to_tencent_symbol, "300750", "sz300750"),
    (codes.to_tencent_symbol, "688981", "sh688981"),
    (codes.to_tencent_symbol, "830799", "bj830799"),  # 北交所

    # ── to_tencent_hk_symbol ──（hk 前缀 + 5 位零填充，接受 .HK 后缀或纯数字）
    (codes.to_tencent_hk_symbol, "0700.HK", "hk00700"),   # 腾讯 4 位写法
    (codes.to_tencent_hk_symbol, "00700.HK", "hk00700"),  # 腾讯 5 位写法
    (codes.to_tencent_hk_symbol, "3690.HK", "hk03690"),   # 美团
    (codes.to_tencent_hk_symbol, "02097.HK", "hk02097"),  # 蜜雪
    (codes.to_tencent_hk_symbol, "9988.HK", "hk09988"),   # 阿里
    (codes.to_tencent_hk_symbol, "9863.HK", "hk09863"),   # 零跑
    (codes.to_tencent_hk_symbol, "700", "hk00700"),       # 纯数字

    # ── to_sina_symbol ──（与 to_tencent_symbol 同前缀规则，复用 _exchange）
    (codes.to_sina_symbol, "600519", "sh600519"),
    (codes.to_sina_symbol, "000858", "sz000858"),
    (codes.to_sina_symbol, "510300", "sh510300"),     # 沪深300 ETF（沪，首位 5）
    (codes.to_sina_symbol, "159995", "sz159995"),     # 芯片 ETF（深，首位 1）
    (codes.to_sina_symbol, "830799", "bj830799"),     # 北交所

    # ── to_baostock_code ──（sh./sz.；bj 与非 A 股返回 None）
    (codes.to_baostock_code, "600519", "sh.600519"),
    (codes.to_baostock_code, "000858", "sz.000858"),
    (codes.to_baostock_code, "900901", "sh.900901"),
    (codes.to_baostock_code, "830799", None),         # 北交所 baostock 不覆盖
    (codes.to_baostock_code, "02097.HK", None),
    (codes.to_baostock_code, "AAPL", None),

    # ── to_a_code ──（反向：yf/带后缀 → 6 位 A 码；非 A 股 None）
    (codes.to_a_code, "600519.SS", "600519"),
    (codes.to_a_code, "000858.SZ", "000858"),
    (codes.to_a_code, "600036.SH", "600036"),
    (codes.to_a_code, "600519", "600519"),            # 已是 A 码，幂等
    (codes.to_a_code, "0700.HK", None),
    (codes.to_a_code, "AAPL", None),

    # ── ETF / 基金（review WARNING 1：6 位非股票码不得抛错炸主流程）──
    (codes.is_a_share, "510300", True),
    (codes.to_yf_ticker, "510300", "510300.SS"),    # 沪深300 ETF（沪，首位 5）
    (codes.to_yf_ticker, "159915", "159915.SZ"),    # 创业板 ETF（深，首位 1）
    (codes.to_tencent_symbol, "510300", "sh510300"),
    (codes.to_baostock_code, "510300", "sh.510300"),
]


def main():
    fails = 0
    for fn, arg, expected in CASES:
        try:
            got = fn(arg)
        except Exception as e:
            got = f"<异常 {type(e).__name__}: {e}>"
        ok = got == expected
        if not ok:
            fails += 1
            print(f"  ❌ {fn.__name__}({arg!r}) = {got!r}，期望 {expected!r}")
    total = len(CASES)
    print(f"\n{'='*50}")
    if fails == 0:
        print(f"test_codes 通过：{total}/{total}")
        sys.exit(0)
    print(f"test_codes 失败：{fails}/{total} 不符")
    sys.exit(1)


if __name__ == "__main__":
    main()
