#!/usr/bin/env python3
"""
定期复盘 — 数据获取脚本
用法：python3 fetch_data.py [--stocks] [--forex] [--all]

模块：
  --stocks   关注个股当前价（A 股 + 港股走腾讯实时含当日涨跌幅，其它走 yfinance）
  --forex    人民币汇率（yfinance）
  --all      以上全部（默认）

关注列表从 wiki/stocks/focus/ 目录自动获取，股票代码从文件标题行解析。
"""

import argparse
import datetime
import glob
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "..")
FOCUS_DIR = os.path.join(PROJECT_ROOT, "wiki", "stocks", "focus")

# 共享取数层：codes 代码转换 + 腾讯行情封装（替代旧的跨 skill sys.path reach-in）
sys.path.insert(0, os.path.join(PROJECT_ROOT, "skills", "_shared"))
from marketdata import quote_tencent, codes  # noqa: E402

# 代码转换统一到 marketdata.codes（保留旧名为薄封装，调用点不变）
_code_to_yf_ticker = codes.to_yf_ticker
_yf_ticker_to_a_code = codes.to_a_code


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


def _print_tencent_quote(name, label, q):
    """统一打印腾讯快照：当前价 + 当日涨跌幅（A 股与港股同格式）。"""
    if q and q.get("price") is not None:
        pct = q.get("change_pct")
        pct_str = f"  {pct:+.2f}%" if isinstance(pct, (int, float)) else ""
        print(f"  {name} ({label}): {q['price']:.2f}{pct_str}")
    else:
        print(f"  {name} ({label}): 腾讯无返回")


def fetch_stocks():
    """获取关注个股当前价：A 股 + 港股走腾讯实时（含当日涨跌幅），其它走 yfinance"""
    watchlist = load_focus_list()
    if not watchlist:
        print("  wiki/stocks/focus/ 目录为空或不存在，无关注个股")
        return

    print("=" * 60)
    print(f"关注个股当前价（共 {len(watchlist)} 只）")
    print("=" * 60)

    # 双重上市取第一个代码（在 load_focus_list 完成）：A 主上市 → a_share，
    # 港股主上市（美团/腾讯等 .HK）→ hk，两者均走腾讯实时；美股等其它走 yfinance。
    a_share, hk, others = {}, {}, {}
    for name, ticker in watchlist.items():
        code = _yf_ticker_to_a_code(ticker)
        if code:
            a_share[name] = code
        elif codes.is_hk_share(ticker):
            hk[name] = ticker
        else:
            others[name] = ticker

    if a_share:
        quotes = quote_tencent.get_quotes(list(a_share.values()))
        for name, code in a_share.items():
            _print_tencent_quote(name, code, quotes.get(code))

    if hk:
        quotes = quote_tencent.get_hk_quotes(list(hk.values()))
        for name, ticker in hk.items():
            _print_tencent_quote(name, ticker, quotes.get(ticker))

    if others:
        try:
            import yfinance as yf
        except ImportError:
            print("  错误: 非 A 股 / 港股行情需要 yfinance — pip install yfinance")
            return
        tickers = list(others.values())
        # 单只返回扁平列；多只返回 MultiIndex (字段, 代码)
        # auto_adjust=False 锁定为原始收盘价，避免 yfinance 默认值变更影响显示口径
        df = yf.download(tickers, period="5d", progress=False, auto_adjust=False)
        is_multi = len(tickers) > 1
        for name, ticker in others.items():
            try:
                series = df[("Close", ticker)] if is_multi else df["Close"]
                close = series.dropna().iloc[-1]
                print(f"  {name} ({ticker}): {close:.2f}")
            except (KeyError, IndexError) as e:
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
        fx = yf.download(["CNY=X"], period="5d", progress=False, auto_adjust=False)
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
