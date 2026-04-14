#!/usr/bin/env python3
"""
定期复盘 — 数据获取脚本
用法：python3 fetch_data.py [--stocks] [--forex] [--all]

模块：
  --stocks   关注个股当前价（yfinance）
  --forex    人民币汇率（yfinance）
  --all      以上全部（默认）

关注列表从 wiki/stocks/focus/ 目录自动获取，股票代码从文件标题行解析。
"""

import argparse
import datetime
import glob
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "..")
FOCUS_DIR = os.path.join(PROJECT_ROOT, "wiki", "stocks", "focus")


def _code_to_yf_ticker(code: str) -> str:
    """将文件中的股票代码转换为 yfinance ticker 格式。
    - 600xxx.SH / 601xxx.SH → 600xxx.SS（上交所）
    - 000xxx.SZ / 300xxx.SZ → 保持 .SZ（深交所）
    - xxxx.HK → 保持 .HK（港股）
    - 纯6位数字：6开头→.SS，0/3开头→.SZ
    """
    code = code.strip()
    if ".SH" in code.upper():
        return code.upper().replace(".SH", ".SS")
    if ".HK" in code.upper():
        # 港股标准化为4位：02097.HK → 2097.HK，0700.HK → 0700.HK
        parts = code.upper().split(".")
        return f"{str(int(parts[0])).zfill(4)}.HK"
    if ".SZ" in code.upper() or ".SS" in code.upper():
        return code.upper()
    # 纯数字
    digits = re.sub(r"[^0-9]", "", code)
    if len(digits) == 6:
        if digits[0] == "6":
            return f"{digits}.SS"
        else:
            return f"{digits}.SZ"
    return code


def load_focus_list() -> dict:
    """从 wiki/stocks/focus/ 读取关注列表，返回 {中文名: yfinance_ticker}"""
    watchlist = {}
    pattern = os.path.join(FOCUS_DIR, "*.md")
    for filepath in sorted(glob.glob(pattern)):
        name = os.path.splitext(os.path.basename(filepath))[0]
        # 读标题行提取代码：# 股票名称 (代码)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") and "(" in line:
                        # 提取第一个括号中的代码
                        match = re.search(r"\(([^)]+)\)", line)
                        if match:
                            raw_code = match.group(1)
                            # 处理双重上市：取第一个代码
                            if "/" in raw_code:
                                raw_code = raw_code.split("/")[0].strip()
                            watchlist[name] = _code_to_yf_ticker(raw_code)
                        break
        except Exception:
            pass
    return watchlist


def _extract_close(row):
    """从 yfinance 行中提取标量值（兼容 MultiIndex DataFrame）"""
    val = row["Close"]
    if hasattr(val, "iloc"):
        val = val.iloc[0]
    return val


def fetch_stocks():
    """获取关注个股最新收盘价"""
    try:
        import yfinance as yf
    except ImportError:
        print("  错误: 请先安装 yfinance — pip install yfinance")
        return

    watchlist = load_focus_list()
    if not watchlist:
        print("  wiki/stocks/focus/ 目录为空或不存在，无关注个股")
        return

    codes = list(watchlist.values())

    print("=" * 60)
    print(f"关注个股当前价（共 {len(watchlist)} 只）")
    print("=" * 60)

    # 逐只下载，避免单只/多只时 DataFrame 结构差异
    for name, ticker in watchlist.items():
        try:
            df = yf.download(ticker, period="5d", progress=False)
            latest = df.dropna().iloc[-1]
            close = _extract_close(latest)
            print(f"  {name} ({ticker}): {close:.2f}")
        except Exception as e:
            print(f"  {name} ({ticker}): 获取失败 - {e}")


def fetch_forex():
    """获取人民币汇率"""
    try:
        import yfinance as yf
    except ImportError:
        print("  错误: 请先安装 yfinance — pip install yfinance")
        return

    print()
    print("=" * 60)
    print("人民币汇率 (USD/CNY)")
    print("=" * 60)

    try:
        fx = yf.download(["CNY=X"], period="5d", progress=False)
        fx_clean = fx.dropna()
        if len(fx_clean) >= 1:
            rate = _extract_close(fx_clean.iloc[-1])
            print(f"  USD/CNY: {rate:.4f}")
        else:
            print("  无数据")
    except Exception as e:
        print(f"  获取失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="定期复盘 — 数据获取")
    parser.add_argument("--stocks", action="store_true", help="关注个股当前价")
    parser.add_argument("--forex", action="store_true", help="人民币汇率")
    parser.add_argument("--all", action="store_true", help="全部（默认）")
    args = parser.parse_args()

    if not (args.stocks or args.forex):
        args.all = True

    print(f"数据采集时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.all or args.stocks:
        fetch_stocks()
    if args.all or args.forex:
        fetch_forex()


if __name__ == "__main__":
    main()
