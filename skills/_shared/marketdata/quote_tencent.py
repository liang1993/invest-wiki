"""腾讯财经行情接口（qt.gtimg.cn）

A股实时行情快照，比 yfinance 快 ~22x，国内可达，字段更全。
单 HTTP 请求最多支持 50 只代码批量。

字段位置参考：腾讯协议 ~ 分隔，固定列序。
"""
from __future__ import annotations
import os
import sys

import requests

# 作为 marketdata.quote_tencent 被 import 时 marketdata 已在路径上；直接
# `python3 quote_tencent.py` 跑 __main__ 时父目录不在路径，补一下，保证两种入口
# 都能 `from marketdata import codes`。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 别名 _codes 避免与 get_quotes(codes=...) 形参同名遮蔽。
from marketdata import codes as _codes  # noqa: E402

# 关键字段位置（从 0 起）
FIELDS = {
    'name': 1, 'code': 2, 'price': 3, 'prev_close': 4, 'open': 5,
    'volume_lots': 6, 'outer': 7, 'inner': 8,
    'bid1_price': 9, 'bid1_vol': 10, 'bid2_price': 11, 'bid2_vol': 12,
    'bid3_price': 13, 'bid3_vol': 14, 'bid4_price': 15, 'bid4_vol': 16,
    'bid5_price': 17, 'bid5_vol': 18,
    'ask1_price': 19, 'ask1_vol': 20, 'ask2_price': 21, 'ask2_vol': 22,
    'ask3_price': 23, 'ask3_vol': 24, 'ask4_price': 25, 'ask4_vol': 26,
    'ask5_price': 27, 'ask5_vol': 28,
    'time': 30, 'change': 31, 'change_pct': 32, 'high': 33, 'low': 34,
    'amount_w': 37,        # 成交额（万元）
    'turnover_pct': 38,    # 换手率（%）
    'pe_ttm': 39,
    'amplitude_pct': 43,   # 振幅（%）
    'circ_mcap_y': 44,     # 流通市值（亿元）
    'total_mcap_y': 45,    # 总市值（亿元）
    'pb': 46,
    'limit_up': 47, 'limit_down': 48,
    'volume_ratio': 49,
    'avg_price': 51,
    'pe_dynamic': 52,
    'pe_static': 53,
}

NUMERIC_FIELDS = {
    'price', 'prev_close', 'open', 'high', 'low', 'avg_price',
    'change', 'change_pct', 'amount_w', 'turnover_pct',
    'pe_ttm', 'pe_dynamic', 'pe_static', 'pb',
    'amplitude_pct', 'circ_mcap_y', 'total_mcap_y',
    'limit_up', 'limit_down', 'volume_ratio',
    'bid1_price', 'ask1_price',
}


def _market_prefix(code: str) -> str:
    """6 位 A 股代码 → sh/sz/bj 前缀。路由收口到 codes._exchange（唯一来源），
    因此覆盖股票码(60/00/30…)与 ETF/基金码(51/15/56/58…)——后者原实现不认。"""
    return _codes._exchange(code.strip())


def _parse_one(line: str) -> dict | None:
    """解析腾讯返回的单行（v_sh600519="..."）"""
    if '=' not in line or '~' not in line:
        return None
    payload = line.split('=', 1)[1].strip().strip('";')
    parts = payload.split('~')
    if len(parts) < 50:
        return None
    out = {}
    for key, idx in FIELDS.items():
        if idx >= len(parts):
            continue
        val = parts[idx]
        if key in NUMERIC_FIELDS and val:
            try:
                out[key] = float(val)
            except ValueError:
                out[key] = val
        else:
            out[key] = val
    return out


def get_quote(code: str, timeout: float = 5.0) -> dict | None:
    """单股快照。code 为 6 位 A 股代码，如 '600519' / '000858'。

    返回 dict 含 ~30 个字段，关键的有：
      price / pe_ttm / pe_dynamic / pe_static / pb / turnover_pct /
      total_mcap_y(亿) / circ_mcap_y(亿) / volume_ratio / amplitude_pct /
      bid1_price / ask1_price / limit_up / limit_down

    返回 None 表示获取失败。
    """
    url = f'http://qt.gtimg.cn/q={_codes.to_tencent_symbol(code)}'
    try:
        resp = requests.get(url, timeout=timeout)
        resp.encoding = 'gbk'
        return _parse_one(resp.text.strip())
    except Exception:
        return None


def get_quotes(codes: list[str], timeout: float = 5.0) -> dict[str, dict]:
    """批量快照（一次 HTTP 拿多只，最多 50 只一批）。

    返回 {code: quote_dict}，失败的代码不在结果中。
    """
    out: dict[str, dict] = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        symbols = ','.join(_codes.to_tencent_symbol(c) for c in batch)
        url = f'http://qt.gtimg.cn/q={symbols}'
        try:
            resp = requests.get(url, timeout=timeout)
            resp.encoding = 'gbk'
            for line in resp.text.strip().split('\n'):
                parsed = _parse_one(line.strip())
                if parsed and 'code' in parsed:
                    out[parsed['code']] = parsed
        except Exception:
            continue
    return out


# 港股端点（hk 前缀）腾讯校验来源，需带 UA + Referer；A 股端点无此要求，故仅港股用。
_HK_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://gu.qq.com/',
}


def get_hk_quotes(codes: list[str], timeout: float = 5.0) -> dict[str, dict]:
    """批量港股实时快照（绕开 yfinance 延迟，给当日价 + 涨跌幅）。

    codes 为港股代码（'0700.HK' / '00700.HK' / '3690.HK' / '02097.HK'）。
    返回 {输入代码: quote_dict}，失败的代码不在结果中。港股关键字段位与 A 股一致
    （price[3] / prev_close[4] / time[30] / change[31] / change_pct[32]），故复用
    _parse_one；高位字段（PE / 市值等）港股口径不同，本封装仅保证价 / 涨跌幅口径。
    """
    out: dict[str, dict] = {}
    # 腾讯符号 → 输入代码：parsed['code'] 是 5 位零填充（00700），非调用方原形态，
    # 故按行首 v_hk00700= 的符号回填到调用方传入的 key。
    sym_to_input = {_codes.to_tencent_hk_symbol(c): c for c in codes}
    symbols = list(sym_to_input)
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        url = f'http://qt.gtimg.cn/q={",".join(batch)}'
        try:
            resp = requests.get(url, headers=_HK_HEADERS, timeout=timeout)
            resp.encoding = 'gbk'
        except Exception:
            continue
        for line in resp.text.strip().split('\n'):
            line = line.strip()
            if '=' not in line:
                continue
            sym = line.split('=', 1)[0].strip()
            if sym.startswith('v_'):
                sym = sym[2:]
            key = sym_to_input.get(sym)
            parsed = _parse_one(line)
            if key and parsed:
                out[key] = parsed
    return out


if __name__ == '__main__':
    import json
    # 注意：不要用 `codes` 作局部名——会遮蔽模块级 import 的 codes 路由模块。
    argv_codes = sys.argv[1:] or ['600519', '000858', '601318']
    if len(argv_codes) == 1:
        result = get_quote(argv_codes[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = get_quotes(argv_codes)
        for code, q in result.items():
            print(f"{q['name']}({code}): {q['price']} | PE_TTM {q.get('pe_ttm')} | "
                  f"PB {q.get('pb')} | 总市值 {q.get('total_mcap_y')}亿")
