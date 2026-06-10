#!/usr/bin/env python3
"""网页搜索 fallback —— 替代 Claude Code 的 WebSearch（AGENTS.md §运行环境与工具映射）。

Tavily 单后端（REST，直接 requests 调，不依赖 tavily SDK）；key 走 TAVILY_API_KEY
环境变量。输出 title / url / snippet 列表。多后端（Serper / 自托管 SearXNG）等出现
第二个真实需求再加（方案 v2 裁定：避免投机性灵活度）。

用法：
  TAVILY_API_KEY=... python3 skills/_shared/webtools/search.py "<query>" [-n 5]

退出码：0 成功；2 请求失败；3 未配置 TAVILY_API_KEY（调用方据此 skip）。
作为库：from webtools.search import search, SearchKeyMissing
        → list[dict(title, url, snippet)]；无 key 抛 SearchKeyMissing。
"""
import os
import sys
import argparse

ENDPOINT = "https://api.tavily.com/search"
TIMEOUT = 20


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
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        }
        for item in results[:n]
    ]


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
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}")
        if r["snippet"]:
            print(f"   {r['snippet'][:300]}")
        print()


if __name__ == "__main__":
    main()
