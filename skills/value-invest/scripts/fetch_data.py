#!/usr/bin/env python3
"""
药明康德投资分析 — 数据获取脚本
用法：python3 fetch_data.py <A股6位代码> [同行代码1,同行代码2]
示例：python3 fetch_data.py 603259 300759,002821,300347

输出：财务摘要、行情数据、历史PE区间、单季度趋势、同行对比
"""

import sys
import akshare as ak
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', lambda x: f'{x:.2f}')


def get_yf_code(code: str) -> str:
    """A股6位代码转yfinance格式"""
    if code.startswith('6'):
        return f'{code}.SS'
    elif code.startswith('0') or code.startswith('3'):
        return f'{code}.SZ'
    else:
        return code  # 港股等直接传入


def fetch_financial_summary(symbol: str):
    """获取AKShare财务摘要"""
    print(f'\n{"="*60}')
    print(f'财务摘要: {symbol}')
    print(f'{"="*60}')

    df = ak.stock_financial_abstract(symbol=symbol)
    # 取最近5年年报 + 最新季报的关键指标
    key_metrics = [
        '归母净利润', '营业总收入', '营业成本', '基本每股收益',
        '每股净资产', '净资产收益率(ROE)', '毛利率', '销售净利率',
        '资产负债率', '经营现金流量净额', '每股经营现金流',
        '扣非净利润', '期间费用率'
    ]

    # 识别可用的年报列
    year_cols = [c for c in df.columns if c.endswith('1231')]
    quarter_cols = [c for c in df.columns if c.endswith(('0331', '0630', '0930'))]

    # 取最近5个年报 + 最新2个季报
    use_cols = sorted(year_cols, reverse=True)[:5] + sorted(quarter_cols, reverse=True)[:2]
    use_cols = sorted(use_cols, reverse=True)

    for _, row in df.iterrows():
        if row['指标'] in key_metrics:
            vals = []
            for col in use_cols:
                if col in df.columns and pd.notna(row[col]):
                    v = row[col]
                    if abs(v) > 1e8:
                        vals.append(f'{col}: {v/1e8:.2f}亿')
                    else:
                        vals.append(f'{col}: {v:.2f}')
                else:
                    vals.append(f'{col}: N/A')
            print(f'  {row["指标"]}: {" | ".join(vals)}')

    return df


def fetch_market_data(code: str):
    """获取yfinance行情数据"""
    yf_code = get_yf_code(code)
    print(f'\n{"="*60}')
    print(f'行情数据: {yf_code}')
    print(f'{"="*60}')

    ticker = yf.Ticker(yf_code)
    info = ticker.info

    keys = [
        'currentPrice', 'previousClose', 'marketCap',
        'trailingPE', 'forwardPE', 'trailingEps', 'forwardEps',
        'dividendYield', 'bookValue', 'priceToBook',
        'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
        'totalCash', 'totalDebt', 'sharesOutstanding',
        'returnOnEquity', 'debtToEquity'
    ]
    for k in keys:
        v = info.get(k, 'N/A')
        if isinstance(v, (int, float)) and abs(v) > 1e9:
            print(f'  {k}: {v/1e8:.2f}亿')
        else:
            print(f'  {k}: {v}')

    # 历史行情：近5年年度高低
    print(f'\n--- 年度高低价 ---')
    hist = ticker.history(period='10y')
    current_year = datetime.now().year
    for year in range(current_year - 5, current_year + 1):
        yearly = hist[hist.index.year == year]
        if len(yearly) > 0:
            print(f'  {year}: 最低 {yearly["Close"].min():.2f}  '
                  f'最高 {yearly["Close"].max():.2f}  '
                  f'最新 {yearly["Close"].iloc[-1]:.2f}')

    # 分红历史
    print(f'\n--- 分红历史(近10次) ---')
    divs = ticker.dividends
    if len(divs) > 0:
        for dt, amt in divs.tail(10).items():
            print(f'  {dt.strftime("%Y-%m-%d")}: {amt:.4f}')

    return info, hist


def calc_quarterly_trend(symbol: str):
    """计算单季度扣非净利润趋势"""
    print(f'\n{"="*60}')
    print(f'单季度扣非净利润趋势: {symbol}')
    print(f'{"="*60}')

    df = ak.stock_financial_abstract(symbol=symbol)
    deducted = df[df['指标'] == '扣非净利润'].iloc[0]

    current_year = datetime.now().year
    for year in range(current_year - 2, current_year):
        periods = [f'{year}1231', f'{year}0930', f'{year}0630', f'{year}0331']
        cum = {}
        for p in periods:
            if p in df.columns and pd.notna(deducted[p]):
                cum[p] = deducted[p] / 1e8

        if len(cum) >= 2:
            q_vals = {}
            q_vals['Q1'] = cum.get(f'{year}0331', None)
            if f'{year}0630' in cum and f'{year}0331' in cum:
                q_vals['Q2'] = cum[f'{year}0630'] - cum[f'{year}0331']
            if f'{year}0930' in cum and f'{year}0630' in cum:
                q_vals['Q3'] = cum[f'{year}0930'] - cum[f'{year}0630']
            if f'{year}1231' in cum and f'{year}0930' in cum:
                q_vals['Q4'] = cum[f'{year}1231'] - cum[f'{year}0930']

            parts = [f'{q}: {v:.2f}亿' for q, v in q_vals.items() if v is not None]
            print(f'  {year}: {" | ".join(parts)}')


def calc_historical_pe(code: str, eps_data: dict):
    """计算历史PE区间
    eps_data: {year: eps} 字典
    """
    yf_code = get_yf_code(code)
    ticker = yf.Ticker(yf_code)
    hist = ticker.history(period='10y')

    print(f'\n{"="*60}')
    print(f'历史PE区间: {yf_code}')
    print(f'{"="*60}')

    low_pes, high_pes = [], []
    for year, eps in sorted(eps_data.items()):
        yearly = hist[hist.index.year == year]
        if len(yearly) > 0 and eps > 0:
            low = yearly['Close'].min()
            high = yearly['Close'].max()
            low_pe = low / eps
            high_pe = high / eps
            print(f'  {year}: 最低 {low:.2f} 最高 {high:.2f} | '
                  f'EPS {eps:.2f} | 低PE {low_pe:.1f}x 高PE {high_pe:.1f}x')
            low_pes.append(low_pe)
            high_pes.append(high_pe)

    if low_pes:
        print(f'\n  低点PE中位数: {np.median(low_pes):.1f}x')
        print(f'  高点PE中位数: {np.median(high_pes):.1f}x')

    # 近半年PE中枢
    recent = hist.tail(120)
    if len(recent) > 0 and eps_data:
        latest_eps = eps_data[max(eps_data.keys())]
        avg_price = recent['Close'].mean()
        current_price = hist['Close'].iloc[-1]
        print(f'\n  近半年均价: {avg_price:.2f} → PE中枢: {avg_price/latest_eps:.1f}x')
        print(f'  当前价: {current_price:.2f} → 当前PE: {current_price/latest_eps:.1f}x')


def fetch_peers(peer_codes: list[str]):
    """获取同行财务数据"""
    print(f'\n{"="*60}')
    print(f'同行对比')
    print(f'{"="*60}')

    key_metrics = ['归母净利润', '营业总收入', '基本每股收益',
                   '净资产收益率(ROE)', '毛利率', '销售净利率', '资产负债率']

    for code in peer_codes:
        print(f'\n--- {code} ---')
        try:
            df = ak.stock_financial_abstract(symbol=code)
            year_cols = sorted([c for c in df.columns if c.endswith('1231')], reverse=True)[:3]
            for _, row in df.iterrows():
                if row['指标'] in key_metrics:
                    vals = []
                    for col in year_cols:
                        if col in df.columns and pd.notna(row[col]):
                            v = row[col]
                            if abs(v) > 1e8:
                                vals.append(f'{col[:4]}: {v/1e8:.2f}亿')
                            else:
                                vals.append(f'{col[:4]}: {v:.2f}')
                    if vals:
                        print(f'  {row["指标"]}: {" | ".join(vals)}')
        except Exception as e:
            print(f'  Error: {e}')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    symbol = sys.argv[1]
    peer_codes = sys.argv[2].split(',') if len(sys.argv) > 2 else []

    # 1. 财务摘要
    fin_df = fetch_financial_summary(symbol)

    # 2. 行情数据
    info, hist = fetch_market_data(symbol)

    # 3. 单季度趋势
    calc_quarterly_trend(symbol)

    # 4. 同行对比
    if peer_codes:
        fetch_peers(peer_codes)

    print(f'\n{"="*60}')
    print('数据获取完成。请根据以上数据填入 EPS 字典后调用 calc_historical_pe() 计算PE区间。')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
