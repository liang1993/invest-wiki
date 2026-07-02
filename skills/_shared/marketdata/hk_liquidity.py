"""港股流动性取数封装（HKMA / NY Fed / HKEX / 新浪 / 腾讯 / 东财）

设计 SSOT：docs/hk-liquidity-plan.md（§3 数据源实测矩阵 + 踩坑）。
canonical 源（HKMA / NY Fed / HKEX dayquot）= [观测]；新浪 USDHKD、腾讯 VHSI、
东财南向/AH 为**转发源** = [观测·转发源]，须配官方月末校准（恒指 Factsheet /
HKEX Monthly Highlights / Stock Connect 官方页），不得自动继承 canonical 待遇。

已知坑（2026-07-02 实测，详见方案 §3 踩坑清单）：
- HKMA API `from`/`to` 参数不生效，翻页只能 pagesize(≤100)+offset
- HKMA API 有脏数据（2019 某记录 1M HIBOR=199.29）→ sanity 区间过滤为 None
- HKMA 经本机代理慢/抖（60s 超时曾复现）→ timeout 60s + 重试 2 次
- 港股节假日无 dayquot 文件（404）→ 逐日回退，连续缺 3 个非周末日报错
- python urllib 经代理对 HKMA 会 SSL EOF → 必须 requests
"""
from __future__ import annotations

import datetime as _dt
import re
import time

import requests

HKMA_URL = ("https://api.hkma.gov.hk/public/market-data-and-statistics/"
            "daily-monetary-statistics/daily-figures-interbank-liquidity")
SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/{n}.json"
SINA_FX_URL = "https://hq.sinajs.cn/list=fx_susdhkd"
TENCENT_HK_URL = "http://qt.gtimg.cn/q={symbols}"
DAYQUOT_URL = "https://www.hkex.com.hk/eng/stat/smstat/dayquot/d{yymmdd}e.htm"
EM_PUSH2_URL = ("https://push2.eastmoney.com/api/qt/stock/get"
                "?secid=100.HSAHP&fields=f43,f57,f58,f60,f86,f170")

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SINA_HEADERS = {**_HEADERS, "Referer": "https://finance.sina.com.cn"}
_TENCENT_HEADERS = {**_HEADERS, "Referer": "https://gu.qq.com/"}

# sanity 区间（越界 → 置 None 并由调用方计入缺数，防脏数据静默套档）
HIBOR_RANGE = (0.0, 12.0)
SOFR_RANGE = (0.0, 12.0)
USDHKD_RANGE = (7.5, 8.0)
TURNOVER_RANGE_YI = (200.0, 20000.0)   # 主板日成交额（亿港元）
AH_RANGE = (80.0, 220.0)
VHSI_RANGE = (5.0, 100.0)


def _get(url: str, *, headers: dict | None = None, timeout: float = 30.0,
         retries: int = 2, backoff: float = 3.0) -> requests.Response:
    """带重试的双路由 GET：先走环境代理，失败切直连再试。

    实测（2026-07-02）：HKMA/NYFed 经本机代理间歇 502/SSL EOF，绕代理直连
    稳定 200（港/美站直连可达）；HKEX 29MB 大页则代理更快。故路由顺序
    env → direct 交替重试，兼顾两种故障面。
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        for route in ("env", "direct"):
            try:
                if route == "env":
                    resp = requests.get(url, headers=headers or _HEADERS,
                                        timeout=timeout)
                else:
                    s = requests.Session()
                    s.trust_env = False  # 绕过 HTTP(S)_PROXY
                    resp = s.get(url, headers=headers or _HEADERS,
                                 timeout=timeout)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                # 4xx 是确定性结果（如 dayquot 404=节假日），不换路由重试
                if e.response is not None and e.response.status_code < 500:
                    raise
                last = e
            except Exception as e:  # noqa: BLE001 —— 统一重试语义
                last = e
        if attempt < retries:
            time.sleep(backoff)
    raise last  # type: ignore[misc]


def _in_range(val, lo_hi) -> bool:
    return val is not None and lo_hi[0] <= val <= lo_hi[1]


# ── 货币面（canonical）────────────────────────────────────────────────


def hkma_daily(n: int = 30) -> list[dict]:
    """HKMA 银行体系流动性日频（新→旧，n ≤ 100 单页拉齐）。

    返回字段：date / closing_balance_yi（总结余，亿港元）/ hibor_on /
    hibor_1m / base_rate / market_activities（金管局当日操作，非 0 =
    兑换保证触发级干预，是 ⚡ 事件传感器）。
    HIBOR 越界（脏数据）置 None。
    """
    resp = _get(f"{HKMA_URL}?pagesize={min(n, 100)}", timeout=60)
    out = []
    for r in resp.json()["result"]["records"][:n]:
        hibor_on = r.get("hibor_overnight")
        hibor_1m = r.get("hibor_fixing_1m")
        cb = r.get("closing_balance")
        out.append({
            "date": r["end_of_date"],
            "closing_balance_yi": cb / 100.0 if cb is not None else None,
            "hibor_on": hibor_on if _in_range(hibor_on, HIBOR_RANGE) else None,
            "hibor_1m": hibor_1m if _in_range(hibor_1m, HIBOR_RANGE) else None,
            "base_rate": r.get("disc_win_base_rate"),
            "market_activities": r.get("market_activities"),
        })
    return out


def sofr_last(n: int = 5) -> list[dict]:
    """NY Fed SOFR 最近 n 日（新→旧）。字段：date / rate。"""
    resp = _get(SOFR_URL.format(n=n), timeout=30)
    out = []
    for r in resp.json()["refRates"]:
        rate = r.get("percentRate")
        out.append({"date": r["effectiveDate"],
                    "rate": rate if _in_range(rate, SOFR_RANGE) else None})
    return out


def usdhkd() -> dict | None:
    """USD/HKD 即期（新浪，转发源）。字段：price / date / band_pos_pct
    （区间位置 %：0=贴 7.75 强方，100=贴 7.85 弱方）。"""
    resp = _get(SINA_FX_URL, headers=_SINA_HEADERS, timeout=15)
    m = re.search(r'"([^"]+)"', resp.text)
    if not m or not m.group(1):
        return None
    parts = m.group(1).split(",")
    try:
        price = float(parts[8]) if parts[8] else float(parts[1])
    except (ValueError, IndexError):
        return None
    if not _in_range(price, USDHKD_RANGE):
        return None
    return {"price": price, "date": parts[-1],
            "band_pos_pct": round((price - 7.75) / 0.10 * 100, 1)}


# ── 交易面 ──────────────────────────────────────────────────────────────


def hkex_dayquot(date: _dt.date, *, timeout: float = 90.0) -> dict | None:
    """HKEX 每日行情报告（canonical）：主板总成交额 + 卖空占比。

    页面 ~29MB，流式正则只取 3 个值，不整页落盘。404 = 非交易日 → None。
    返回：date / turnover_yi（亿港元）/ short_pct_ex_etp / short_pct_all。
    """
    url = DAYQUOT_URL.format(yymmdd=date.strftime("%y%m%d"))
    try:
        resp = _get(url, timeout=timeout, retries=1)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    text = resp.text
    m_turn = re.search(r"Total market turnover\s*:\s*HKD\s*([\d,]+)", text)
    if not m_turn:
        return None
    turnover_yi = int(m_turn.group(1).replace(",", "")) / 1e8
    if not _in_range(turnover_yi, TURNOVER_RANGE_YI):
        return None
    m_ex = re.search(r"\(excluding ETP\) as % total turnover\s*:\s*(\d+)%", text)
    m_all = re.search(r"all Designated Securities as % total turnover\s*:\s*(\d+)%", text)
    return {"date": date.isoformat(), "turnover_yi": round(turnover_yi, 1),
            "short_pct_ex_etp": int(m_ex.group(1)) if m_ex else None,
            "short_pct_all": int(m_all.group(1)) if m_all else None}


def dayquot_recent(days: int = 5, *, end: _dt.date | None = None,
                   max_gap: int = 3) -> list[dict]:
    """回收最近 days 个交易日的 dayquot（新→旧）。

    节假日 guard：非周末日缺文件按节假日跳过；连续 max_gap 个非周末日
    无数据则 RuntimeError（防 URL 格式漂移被当节假日吞掉）。
    """
    out: list[dict] = []
    d = end or (_dt.date.today() - _dt.timedelta(days=1))
    gap = 0
    while len(out) < days:
        if d.weekday() < 5:
            rec = hkex_dayquot(d)
            if rec is not None:
                out.append(rec)
                gap = 0
            else:
                gap += 1
                if gap >= max_gap:
                    raise RuntimeError(
                        f"连续 {max_gap} 个非周末日无 dayquot（最后尝试 {d}），"
                        "疑似 URL 格式漂移而非节假日")
        d -= _dt.timedelta(days=1)
        if (len(out) == 0 and ( _dt.date.today() - d).days > 15) or \
           ((_dt.date.today() - d).days > 30):
            raise RuntimeError("dayquot 回溯超限（>30 天），中止")
    return out


def vhsi_spot() -> dict | None:
    """VHSI 实时（腾讯，转发源）。字段：value / date / high_52w / low_52w。"""
    resp = _get(TENCENT_HK_URL.format(symbols="hkVHSI"),
                headers=_TENCENT_HEADERS, timeout=15)
    resp.encoding = "gbk"
    if "=" not in resp.text or "~" not in resp.text:
        return None
    parts = resp.text.split("=", 1)[1].strip().strip('";').split("~")
    try:
        val = float(parts[3])
    except (ValueError, IndexError):
        return None
    if not _in_range(val, VHSI_RANGE):
        return None
    # 指数行(ZS)的 52 周高/低在 48/49（与个股行布局不同）；0 视为缺失
    def _pos(i):
        try:
            v = float(parts[i])
            return v if v > 0 else None
        except (ValueError, IndexError):
            return None
    return {"value": val, "date": parts[30],
            "high_52w": _pos(48), "low_52w": _pos(49)}


def vhsi_hist():
    """VHSI 历史日线（新浪 via akshare，2020-06 起 ~1500+ 行）。
    用于本地算滚动 52 周分位；官方 Factsheet 仅月末校准。"""
    import akshare as ak
    df = ak.stock_hk_index_daily_sina(symbol="VHSI")
    return df[["date", "close"]]


# ── 资金流 + 估值面（转发源为主，官方月末校准）─────────────────────────


def southbound_hist():
    """南向日频历史序列（东财 via akshare，T+1，转发源）。

    列：date / net_buy_yi（沪+深 当日成交净买额合计，亿港元）。
    年度求和已与公开口径核对（2023 精确一致，见方案 §8.2）。
    canonical = HKEX Stock Connect Historical Daily（月末校准 + 兜底）。
    """
    import akshare as ak
    import pandas as pd
    frames = []
    for sym in ("港股通沪", "港股通深"):
        df = ak.stock_hsgt_hist_em(symbol=sym)
        df["日期"] = pd.to_datetime(df["日期"])
        frames.append(df.set_index("日期")["当日成交净买额"].rename(sym))
    m = pd.concat(frames, axis=1).fillna(0)
    out = m.sum(axis=1).reset_index()
    out.columns = ["date", "net_buy_yi"]
    return out


def ah_premium() -> dict | None:
    """恒生 AH 溢价指数实时（东财 push2，唯一实时免费源、间歇）。

    字段：value / prev_close / ts。挂掉返回 None——调用方必须走
    "未评级/标签缺失"路径，禁止拿官方月度 Factsheet 的 stale 值套档。
    """
    try:
        resp = _get(EM_PUSH2_URL, timeout=20, retries=1)
        data = resp.json().get("data")
    except Exception:  # noqa: BLE001 —— 间歇源，失败即 None
        return None
    if not data or data.get("f43") is None:
        return None
    val = data["f43"] / 100.0
    if not _in_range(val, AH_RANGE):
        return None
    return {"value": val,
            "prev_close": data["f60"] / 100.0 if data.get("f60") else None,
            "ts": data.get("f86")}


if __name__ == "__main__":
    import json
    print("HKMA 最近 3 日:", json.dumps(hkma_daily(3), ensure_ascii=False))
    print("SOFR:", sofr_last(2))
    print("USDHKD:", usdhkd())
    print("VHSI:", vhsi_spot())
    print("AH:", ah_premium())
