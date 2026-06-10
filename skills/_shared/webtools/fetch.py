#!/usr/bin/env python3
"""原文抓取 fallback —— 替代 Claude Code 的 WebFetch（AGENTS.md §运行环境与工具映射）。

requests 抓 HTML → 正文抽取为纯文本/markdown，输出到 stdout，头部带 URL / 抓取时间戳 /
HTTP 状态。正文抽取优先级：trafilatura（装了才用，质量最佳）→ readability → bs4 兜底
（始终可用，本机 bs4+lxml 已装）。也是 Claude Code 下 WebFetch 403/失败时的纯增益备选。

用法：
  python3 skills/_shared/webtools/fetch.py <url> [--raw] [--timeout 20]
  --raw   不做正文抽取，直接输出抓回的原始 HTML/文本（仍截断到 MAX_CHARS）

退出码：0 成功；2 抓取失败（网络/HTTP/SSL）。
作为库：from webtools.fetch import fetch_url
        → dict(url, status, fetched_at, extractor, text, truncated)
"""
import sys
import time
import argparse
import datetime

TIMEOUT_DEFAULT = 20      # 秒，硬编码上限
RETRIES = 2               # 瞬时网络抖动重试次数（区分抖动 vs 真不可达）
MAX_CHARS = 20000         # 输出正文截断，避免超大页塞爆校验上下文
UA = "Mozilla/5.0 (compatible; invest-wiki-fetch/1.0)"


def _extract(html, url):
    """返回 (text, extractor_name)。优先 trafilatura，缺/失败则逐级降级到 bs4。"""
    # 1) trafilatura（最佳正文识别）
    try:
        import trafilatura
        txt = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=True
        )
        if txt and txt.strip():
            return txt.strip(), "trafilatura"
    except ImportError:
        pass
    except Exception:
        pass
    # 2) readability-lxml
    try:
        from readability import Document
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(Document(html).summary(), "lxml")
        txt = soup.get_text("\n", strip=True)
        if txt and txt.strip():
            return txt.strip(), "readability"
    except ImportError:
        pass
    except Exception:
        pass
    # 3) bs4 兜底（始终可用）
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]):
        tag.decompose()
    lines = [ln for ln in (l.strip() for l in soup.get_text("\n").splitlines()) if ln]
    return "\n".join(lines), "bs4"


def fetch_url(url, raw=False, timeout=TIMEOUT_DEFAULT):
    """抓取并抽取正文。失败抛最后一次异常（调用方决定降档/删断言）。"""
    import requests
    last = None
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
            resp.encoding = resp.apparent_encoding or resp.encoding  # 中文页编码兜底
            html = resp.text
            body, extractor = (html, "raw") if raw else _extract(html, url)
            body = body or ""
            return {
                "url": url,
                "status": resp.status_code,
                "fetched_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds"),
                "extractor": extractor,
                "text": body[:MAX_CHARS],
                "truncated": len(body) > MAX_CHARS,
            }
        except Exception as e:  # noqa: BLE001  网络/SSL/解析统一重试
            last = e
            if attempt < RETRIES:
                time.sleep(2)
    raise last


def main():
    ap = argparse.ArgumentParser(description="原文抓取 → 文本（webtools fallback）")
    ap.add_argument("url")
    ap.add_argument("--raw", action="store_true", help="不抽取正文，输出原始文本")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT)
    args = ap.parse_args()
    try:
        r = fetch_url(args.url, raw=args.raw, timeout=args.timeout)
    except Exception as e:  # noqa: BLE001
        print(f"[fetch 失败] {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
        sys.exit(2)
    print(f"# 抓取: {r['url']}")
    print(
        f"# HTTP {r['status']} | 时间 {r['fetched_at']} | 抽取器 {r['extractor']}"
        + ("（正文已截断）" if r["truncated"] else "")
    )
    print("---")
    print(r["text"])


if __name__ == "__main__":
    main()
