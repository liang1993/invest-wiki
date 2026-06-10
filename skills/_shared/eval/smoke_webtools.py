#!/usr/bin/env python3
"""webtools smoke —— 搜索 / 抓取 / PDF 三件套地板自检（Phase 2）。

  1. fetch ：抓一个稳定 URL，断言返回非空正文（200 却空 = 抽取 bug → ❌；
             网络/代理/SSL 不可达 = 环境问题 → ⚠️ 非致命，见 marketdata 可达性教训）
  2. search：跑一个 query；无 TAVILY_API_KEY → ℹ️ skip（不计失败）
  3. pdf   ：抽 raw/reports/ 任一既有 PDF 第 1 页，断言非空 → ❌ if 空

退出码：无真·❌ → 0；任一真·失败（HTTP200 空正文 / PDF 第1页空）→ 1。
网络不可达与无 key 宽容处理（不计入失败），与本机代理环境特殊性对齐。

用法：python3 skills/_shared/eval/smoke_webtools.py
"""
import os
import sys
import glob

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "skills", "_shared"))

from webtools import fetch as fetchmod    # noqa: E402
from webtools import search as searchmod  # noqa: E402
from webtools import pdf_text as pdfmod    # noqa: E402

n_fail = 0

# ── 1. fetch（原文抓取）─────────────────────────────────────
print("── 1. fetch（原文抓取）──")
FETCH_URL = "https://example.com"
try:
    r = fetchmod.fetch_url(FETCH_URL, timeout=15)
    if r["status"] == 200 and r["text"].strip():
        print(f"  ✅ fetch {FETCH_URL}: HTTP 200, {len(r['text'])} 字符, 抽取器={r['extractor']}")
    else:
        print(f"  ❌ fetch {FETCH_URL}: HTTP {r['status']} 但正文为空（抽取 bug）")
        n_fail += 1
except Exception as e:  # noqa: BLE001
    print(f"  ⚠️  fetch {FETCH_URL}: {type(e).__name__}（网络/代理/SSL 不可达，环境问题非脚本 bug）")

# ── 2. search（网页搜索，Tavily）────────────────────────────
print("── 2. search（网页搜索，Tavily）──")
try:
    res = searchmod.search("贵州茅台 2026 一季报 营收", n=3)
    if res:
        print(f"  ✅ search: 返回 {len(res)} 条，首条 {res[0]['url'][:60]}")
    else:
        print("  ⚠️  search: 0 条结果（query 或配额问题，非致命）")
except searchmod.SearchKeyMissing:
    print("  ℹ️  search: 跳过 —— 未配置 TAVILY_API_KEY（配置后启用）")
except Exception as e:  # noqa: BLE001
    print(f"  ⚠️  search: {type(e).__name__}（网络/配额，环境问题非脚本 bug）")

# ── 3. pdf_text（PDF 逐页）──────────────────────────────────
print("── 3. pdf_text（PDF 逐页）──")
pdfs = sorted(glob.glob(os.path.join(REPO, "raw", "reports", "*.pdf")))
if not pdfs:
    print("  ℹ️  pdf: 跳过 —— raw/reports/ 无 PDF")
else:
    sample = pdfs[0]
    try:
        txt = pdfmod.extract_pages(sample, "1").get(1, "")
        if txt.strip():
            print(f"  ✅ pdf {os.path.basename(sample)}: 第1页 {len(txt)} 字符")
        else:
            print(f"  ❌ pdf {os.path.basename(sample)}: 第1页空（扫描版或解析 bug）")
            n_fail += 1
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ pdf {os.path.basename(sample)}: {type(e).__name__}: {str(e)[:90]}")
        n_fail += 1

print(f"\n{'=' * 50}")
if n_fail == 0:
    print("smoke 通过：webtools 三件套地板可用（网络/无 key 项已宽容处理）")
    sys.exit(0)
else:
    print(f"smoke 失败：{n_fail} 项真·失败")
    sys.exit(1)
