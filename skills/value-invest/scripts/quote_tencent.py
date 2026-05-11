"""腾讯财经行情接口（qt.gtimg.cn）

A股实时行情快照，比 yfinance 快 ~22x，国内可达，字段更全。
单 HTTP 请求最多支持 50 只代码批量。

字段位置参考：腾讯协议 ~ 分隔，固定列序。
"""
from __future__ import annotations
import requests

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
    """6 位 A 股代码 → sh/sz 前缀"""
    if code.startswith(('60', '68', '90')):
        return 'sh'
    if code.startswith(('00', '30', '20')):
        return 'sz'
    if code.startswith('8'):
        return 'bj'
    raise ValueError(f'未知 A 股代码前缀: {code}')


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
    prefix = _market_prefix(code)
    url = f'http://qt.gtimg.cn/q={prefix}{code}'
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
        symbols = ','.join(f'{_market_prefix(c)}{c}' for c in batch)
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


if __name__ == '__main__':
    import json
    import sys
    codes = sys.argv[1:] or ['600519', '000858', '601318']
    if len(codes) == 1:
        result = get_quote(codes[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = get_quotes(codes)
        for code, q in result.items():
            print(f"{q['name']}({code}): {q['price']} | PE_TTM {q.get('pe_ttm')} | "
                  f"PB {q.get('pb')} | 总市值 {q.get('total_mcap_y')}亿")
