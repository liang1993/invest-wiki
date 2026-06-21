"""股票代码转换 —— A 股路由的唯一来源。

合并历史上三份分散实现（value-invest 的 get_yf_code/is_a_share、periodic-review
的 _code_to_yf_ticker/_yf_ticker_to_a_code、quote_tencent 的 _market_prefix），
按 review BLOCKER 4 的裁决统一：
  - `.SH` → `.SS`（yfinance 上交所后缀）
  - 港股去前导零归一到 ≥4 位（02097.HK → 2097.HK）
  - 沪 B 900xxx → sh/.SS（非 sz）
  - 入口统一：strip 后 ^\\d{6}$ 判 A 股

交易所归类（6 位 A 股）：沪 6/9（含科创 688、沪 B 900）；深 0/2/3（含中小 002、
创业 300、深 B 200）；北交所 4/8。
"""

from __future__ import annotations

_YF_SUFFIX = {"sh": "SS", "sz": "SZ", "bj": "BJ"}


def is_a_share(code: str) -> bool:
    """6 位纯数字 = A 股原生码。"""
    c = code.strip()
    return c.isdigit() and len(c) == 6


def is_hk_share(code: str) -> bool:
    """带 .HK 后缀 = 港股（与 is_a_share 对称的路由判定）。"""
    return code.strip().upper().endswith(".HK")


def _exchange(c6: str) -> str:
    """6 位 A 股市场代码 → 'sh' / 'sz' / 'bj'。按首位覆盖股票/ETF/基金/债，**永不抛错**
    —— is_a_share 认任意 6 位数字，此处必须覆盖全部首位，否则 ETF(510300)/债券码会
    把 value-invest 主流程炸掉（review WARNING 1）。"""
    head = c6[0]
    if head in "5679":     # 沪：6 股票/科创 · 9 沪B · 5 ETF/LOF/基金 · 7 发行
        return "sh"
    if head in "0123":     # 深：0 股票 · 3 创业 · 2 深B · 1 基金/债
        return "sz"
    return "bj"            # 4/8 北交所


def to_yf_ticker(code: str) -> str:
    """任意代码 → yfinance 形态（A 股 .SS/.SZ/.BJ，港股去前导零，其它原样）。"""
    code = code.strip()
    if is_a_share(code):
        return f"{code}.{_YF_SUFFIX[_exchange(code)]}"
    up = code.upper()
    if up.endswith(".SH"):
        return up[:-3] + ".SS"
    if up.endswith((".SS", ".SZ", ".BJ")):
        return up
    if up.endswith(".HK"):
        digits = code[:-3]
        try:
            return f"{int(digits):04d}.HK"   # 去前导零，补齐到 ≥4 位
        except ValueError:
            return up
    return code  # 美股 / 其它原样


def to_tencent_symbol(code: str) -> str:
    """6 位 A 股代码 → 腾讯 qt.gtimg.cn 符号（sh600519 / sz000858 / bj830799）。
    覆盖股票/ETF/基金码（_exchange 认全部首位），ETF 如 510300 → sh510300。"""
    code = code.strip()
    if not is_a_share(code):
        raise ValueError(f"腾讯行情仅支持 6 位 A 股代码: {code}")
    return f"{_exchange(code)}{code}"


def to_tencent_hk_symbol(code: str) -> str:
    """港股代码 → 腾讯 qt.gtimg.cn 符号（0700.HK / 00700.HK / 3690.HK → hk00700 / hk03690）。
    腾讯港股用 `hk` 前缀 + 5 位零填充；接受带 .HK 后缀或纯数字。"""
    c = code.strip().upper()
    if c.endswith(".HK"):
        c = c[:-3]
    if not c.isdigit():
        raise ValueError(f"腾讯港股行情需要数字港股代码: {code}")
    return f"hk{int(c):05d}"


def to_sina_symbol(code: str) -> str:
    """6 位 A 股代码 → sina 符号（sh600519 / sz000858 / bj830799）。
    与 to_tencent_symbol 同前缀规则，复用 _exchange，覆盖股票/ETF/基金码
    （ETF 如 510300 → sh510300、159995 → sz159995）。"""
    code = code.strip()
    if not is_a_share(code):
        raise ValueError(f"sina 行情仅支持 6 位 A 股代码: {code}")
    return f"{_exchange(code)}{code}"


def to_baostock_code(code: str) -> str | None:
    """6 位 A 股代码 → baostock 形态（sh.600519 / sz.000858）。
    北交所与非 A 股返回 None（baostock 不覆盖）。"""
    code = code.strip()
    if not is_a_share(code):
        return None
    ex = _exchange(code)
    return None if ex == "bj" else f"{ex}.{code}"


def to_a_code(ticker: str) -> str | None:
    """反向：yfinance/带后缀代码 → 6 位 A 股原生码；非 A 股返回 None。"""
    ticker = ticker.strip()
    if is_a_share(ticker):
        return ticker
    up = ticker.upper()
    for suf in (".SS", ".SZ", ".SH", ".BJ"):
        if up.endswith(suf):
            digits = ticker[:-3]
            return digits if (digits.isdigit() and len(digits) == 6) else None
    return None
