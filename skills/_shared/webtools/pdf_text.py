#!/usr/bin/env python3
"""PDF 逐页文本抽取 fallback —— 替代 Claude Code 的 `Read pages=X`
（AGENTS.md §运行环境与工具映射）。

pypdf 按页抽取文本，页码对齐 PDF 物理页（1-indexed），供财报摘要「逐项回读校对」
按页码比对。文本型 A 股财报 PDF 适用；扫描版（无文本层）报错提示走 OCR（不内置）。

用法：
  python3 skills/_shared/webtools/pdf_text.py <pdf> [--pages 3-5]
  --pages 支持 "5" / "3-5" / "1,3,5"；省略 = 全部页

退出码：0 成功；2 文件/解析错误；4 指定页均无文本（疑似扫描版）。
作为库：from webtools.pdf_text import extract_pages → dict{page_no:int -> text:str}
"""
import os
import sys
import argparse


def parse_pages(spec, total):
    """ "3-5" / "1,3,5" / "5" → 有序 1-indexed 页号列表（去重、夹到 [1,total]）。"""
    if not spec:
        return list(range(1, total + 1))
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(part))
    return [p for p in sorted(pages) if 1 <= p <= total]


def extract_pages(pdf_path, pages=None):
    """按页抽取文本。pages=页规格字符串或 None（全部）。返回 {物理页号: 文本}。"""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    return {
        p: (reader.pages[p - 1].extract_text() or "").strip()
        for p in parse_pages(pages, total)
    }


def main():
    ap = argparse.ArgumentParser(description="PDF 逐页文本抽取（webtools fallback）")
    ap.add_argument("pdf")
    ap.add_argument("--pages", default=None, help='页范围，如 "3-5" / "1,3,5" / "5"')
    args = ap.parse_args()
    if not os.path.exists(args.pdf):
        print(f"[pdf 失败] 文件不存在: {args.pdf}", file=sys.stderr)
        sys.exit(2)
    try:
        result = extract_pages(args.pdf, args.pages)
    except Exception as e:  # noqa: BLE001
        print(f"[pdf 失败] {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
        sys.exit(2)
    for p in sorted(result):
        print(f"\n===== 第 {p} 页 =====")
        print(result[p] if result[p] else "（本页无可抽取文本）")
    if result and not any(result.values()):
        print(
            "\n[提示] 指定页均无文本层 —— 可能是扫描版 PDF，需 OCR（本工具不内置）。",
            file=sys.stderr,
        )
        sys.exit(4)


if __name__ == "__main__":
    main()
