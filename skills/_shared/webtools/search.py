#!/usr/bin/env python3
"""网页搜索 fallback —— 替代 Claude Code 的 WebSearch（AGENTS.md §运行环境与工具映射）。

Tavily 单后端（REST，直接 requests 调，不依赖 tavily SDK）；key 走 TAVILY_API_KEY
环境变量。输出 title / url / snippet 列表。多后端（Serper / 自托管 SearXNG）等出现
第二个真实需求再加（方案 v2 裁定：避免投机性灵活度）。

权威源提权：命中交易所/监管/法定信披媒体白名单（巨潮/交易所/SEC/证监会…）的结果
稳定排序上浮（借鉴 daily_stock_analysis），服务数据纪律 [观测] 优先一手源、极端数字
溯源贴权威链接。仅重排不删除，不命中也照常返回。

用法：
  TAVILY_API_KEY=... python3 skills/_shared/webtools/search.py "<query>" [-n 5]

退出码：0 成功；2 请求失败；3 未配置 TAVILY_API_KEY（调用方据此 skip）。
作为库：from webtools.search import search, SearchKeyMissing
        → list[dict(title, url, snippet, authority)]；authority>0=权威源；无 key 抛 SearchKeyMissing。
"""
import os
import sys
import argparse
from urllib.parse import urlparse

ENDPOINT = "https://api.tavily.com/search"
TIMEOUT = 20

# 官方/权威信息源白名单 —— host 命中则结果上浮（借鉴 daily_stock_analysis）。
# 权重 2 = 交易所/监管/官方统计一手发布；权重 1 = 证监会指定法定信披媒体（权威转述）。
_OFFICIAL_SOURCES = {
    "cninfo.com.cn": 2,   # 巨潮资讯网（A股法定信披）
    "sse.com.cn": 2,      # 上交所
    "szse.cn": 2,         # 深交所
    "bse.cn": 2,          # 北交所
    "hkexnews.hk": 2,     # 港交所披露易
    "hkex.com.hk": 2,     # 港交所
    "sec.gov": 2,         # 美国 SEC
    "csrc.gov.cn": 2,     # 证监会
    "pbc.gov.cn": 2,      # 中国人民银行
    "stats.gov.cn": 2,    # 国家统计局
    "mof.gov.cn": 2,      # 财政部
    "cs.com.cn": 1,       # 中国证券报
    "cnstock.com": 1,     # 上海证券报
    "stcn.com": 1,        # 证券时报
    "zqrb.cn": 1,         # 证券日报
}


def _authority(url):
    """URL host 命中权威源白名单返回其权重（1/2），否则 0。子域亦命中。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001  畸形 URL 视为非权威
        return 0
    for domain, weight in _OFFICIAL_SOURCES.items():
        if host == domain or host.endswith("." + domain):
            return weight
    return 0


class SearchKeyMissing(RuntimeError):
    """TAVILY_API_KEY 未配置 —— 与"请求失败"区分，便于调用方 skip 而非报错。"""


def search(query, n=5):
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise SearchKeyMissing("TAVILY_API_KEY 未配置")
    import requests
    payload = {
        "api_key": key,
        "query": query,
        "max_results": n,
        "search_depth": "basic",
    }
    resp = requests.post(ENDPOINT, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    items = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "authority": _authority(item.get("url", "")),
        }
        for item in results[:n]
    ]
    # 权威源提权：稳定排序，同权重保持 Tavily 原始相关性序，仅重排不删除
    items.sort(key=lambda r: r["authority"], reverse=True)
    return items


def main():
    ap = argparse.ArgumentParser(description="网页搜索 → title/url/snippet（Tavily fallback）")
    ap.add_argument("query")
    ap.add_argument("-n", type=int, default=5, help="结果条数（默认 5）")
    args = ap.parse_args()
    try:
        results = search(args.query, n=args.n)
    except SearchKeyMissing as e:
        print(f"[search skip] {e} —— 配置后可用（export TAVILY_API_KEY=...）", file=sys.stderr)
        sys.exit(3)
    except Exception as e:  # noqa: BLE001
        print(f"[search 失败] {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
        sys.exit(2)
    if not results:
        print("（无结果）")
        return
    for i, r in enumerate(results, 1):
        badge = " 〔权威源〕" if r.get("authority") else ""
        print(f"{i}. {r['title']}{badge}")
        print(f"   {r['url']}")
        if r["snippet"]:
            print(f"   {r['snippet'][:300]}")
        print()


if __name__ == "__main__":
    main()
