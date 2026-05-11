#!/usr/bin/env python3
"""个股价值投资 — 数据获取脚本

数据源分工：
  财务摘要：AKShare stock_financial_abstract (新浪源)
  A 股行情快照：腾讯 qt.gtimg.cn (本地 quote_tencent.py)
  A 股历史 K + PE/PB 时序：baostock (含 peTTM/pbMRQ，免手填 EPS)
  港股/美股行情：yfinance (A 股的兜底也是 yfinance)
  研报一致预期：AKShare stock_research_report_em (含未来 3 年 EPS/PE 预测)

用法：python3 fetch_data.py <代码> [同行代码1,同行代码2]
  A 股 6 位：python3 fetch_data.py 600519 300759,002821
  港股 4-5 位：python3 fetch_data.py 0700.HK
"""

import sys
import os
from datetime import datetime, timedelta

import akshare as ak
import yfinance as yf
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quote_tencent


def _section(title: str):
    print(f'\n{"="*60}\n{title}\n{"="*60}')


def is_a_share(code: str) -> bool:
    """6 位纯数字 = A 股；带 .HK / .SS / .SZ 后缀视为非 A 股原生码"""
    return code.isdigit() and len(code) == 6


def get_yf_code(code: str) -> str:
    """A股6位代码转yfinance格式；其它代码原样返回"""
    if not is_a_share(code):
        return code
    if code.startswith(('6', '9')):
        return f'{code}.SS'
    return f'{code}.SZ'


def fetch_financial_summary(symbol: str):
    """获取AKShare财务摘要（新浪源，稳定）"""
    _section(f'财务摘要: {symbol}')

    df = ak.stock_financial_abstract(symbol=symbol)
    key_metrics = [
        '归母净利润', '营业总收入', '营业成本', '基本每股收益',
        '每股净资产', '净资产收益率(ROE)', '毛利率', '销售净利率',
        '资产负债率', '经营现金流量净额', '每股经营现金流',
        '扣非净利润', '期间费用率'
    ]

    year_cols = [c for c in df.columns if c.endswith('1231')]
    quarter_cols = [c for c in df.columns if c.endswith(('0331', '0630', '0930'))]
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
    """A 股优先走腾讯（快+全），港股美股走 yfinance；腾讯失败时 yfinance 兜底"""
    _section(f'行情数据: {code}')

    if is_a_share(code):
        q = quote_tencent.get_quote(code)
        if q:
            print(f'[来源] 腾讯 qt.gtimg.cn')
            print(f'  名称: {q["name"]}  代码: {q["code"]}')
            print(f'  当前价: {q["price"]}  昨收: {q["prev_close"]}  涨跌%: {q.get("change_pct")}%')
            print(f'  总市值: {q.get("total_mcap_y")}亿  流通市值: {q.get("circ_mcap_y")}亿')
            print(f'  PE_TTM: {q.get("pe_ttm")}  PE动态: {q.get("pe_dynamic")}  PE静态: {q.get("pe_static")}')
            print(f'  PB: {q.get("pb")}  换手率: {q.get("turnover_pct")}%  量比: {q.get("volume_ratio")}')
            print(f'  振幅: {q.get("amplitude_pct")}%  涨停: {q.get("limit_up")}  跌停: {q.get("limit_down")}')
            print(f'  买一/卖一: {q.get("bid1_price")} / {q.get("ask1_price")}')
            print(f'  时间戳: {q.get("time")}')
            return q
        print('[腾讯失败，兜底 yfinance]')

    yf_code = get_yf_code(code)
    print(f'[来源] yfinance {yf_code}')
    ticker = yf.Ticker(yf_code)
    info = ticker.info

    keys = ['currentPrice', 'previousClose', 'marketCap',
            'trailingPE', 'forwardPE', 'trailingEps', 'forwardEps',
            'dividendYield', 'bookValue', 'priceToBook',
            'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
            'totalCash', 'totalDebt', 'sharesOutstanding',
            'returnOnEquity', 'debtToEquity']
    for k in keys:
        v = info.get(k, 'N/A')
        if isinstance(v, (int, float)) and abs(v) > 1e9:
            print(f'  {k}: {v/1e8:.2f}亿')
        else:
            print(f'  {k}: {v}')

    print(f'\n--- 分红历史(近10次) ---')
    divs = ticker.dividends
    if len(divs) > 0:
        for dt, amt in divs.tail(10).items():
            print(f'  {dt.strftime("%Y-%m-%d")}: {amt:.4f}')

    return info


def fetch_history_with_pe(code: str, years: int = 10):
    """A 股走 baostock 取日 K + 日级 peTTM/pbMRQ；港股美股走 yfinance"""
    _section(f'历史日K + PE/PB 时序: {code}')

    if is_a_share(code):
        try:
            import baostock as bs
            bs.login()
            prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=years * 366)).strftime('%Y-%m-%d')
            rs = bs.query_history_k_data_plus(
                f'{prefix}.{code}',
                "date,open,high,low,close,volume,amount,turn,pctChg,peTTM,pbMRQ",
                start_date=start, end_date=end,
                frequency="d", adjustflag="2")  # 2=前复权
            data = []
            while (rs.error_code == '0') & rs.next():
                data.append(rs.get_row_data())
            df = pd.DataFrame(data, columns=rs.fields)
            bs.logout()
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount',
                        'turn', 'pctChg', 'peTTM', 'pbMRQ']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['date'] = pd.to_datetime(df['date'])
            print(f'[来源] baostock  行数: {len(df)}  '
                  f'日期: {df["date"].min().date()} → {df["date"].max().date()}')
            return df
        except Exception as e:
            print(f'[baostock 失败 {e}，兜底 yfinance]')

    yf_code = get_yf_code(code)
    print(f'[来源] yfinance {yf_code}')
    ticker = yf.Ticker(yf_code)
    hist = ticker.history(period=f'{years}y')
    df = hist.reset_index().rename(columns={
        'Date': 'date', 'Open': 'open', 'High': 'high',
        'Low': 'low', 'Close': 'close', 'Volume': 'volume',
    })
    print(f'  行数: {len(df)}  日期: {df["date"].min().date()} → {df["date"].max().date()}')
    print(f'  注：yfinance 不带 PE/PB 时序，calc_pe_band 将退化为按年高低价 + 手填 EPS')
    return df


def calc_pe_band(df: pd.DataFrame, eps_data: dict | None = None):
    """计算历史 PE 区间。

    优先级：
      1. df 含 'peTTM' 列（baostock 数据） → 直接算日级中位/分位/区间
      2. df 不含 peTTM 但传入 eps_data={year: eps} → 退化为旧逻辑（年高低价/EPS）
    """
    _section('历史 PE 区间')

    if 'peTTM' in df.columns:
        pe = df['peTTM'].dropna()
        pe = pe[pe > 0]  # 剔除负值（亏损期 PE 无意义）
        if len(pe) == 0:
            print('  无有效 PE 数据')
            return
        print(f'[来源] baostock peTTM (日频，{len(pe)} 个有效观测)')
        print(f'  全样本: 中位 {pe.median():.1f}x  '
              f'P25 {pe.quantile(0.25):.1f}x  P75 {pe.quantile(0.75):.1f}x  '
              f'最低 {pe.min():.1f}x  最高 {pe.max():.1f}x')

        df_pe = df[['date', 'peTTM', 'close']].copy()
        df_pe['year'] = df_pe['date'].dt.year
        df_pe = df_pe[df_pe['peTTM'] > 0]
        for year, grp in df_pe.groupby('year'):
            if len(grp) > 0:
                print(f'  {year}: PE 中位 {grp["peTTM"].median():.1f}x  '
                      f'最低 {grp["peTTM"].min():.1f}x  最高 {grp["peTTM"].max():.1f}x  '
                      f'(收盘 {grp["close"].min():.0f}-{grp["close"].max():.0f})')

        recent = df.tail(120)
        recent_pe = recent['peTTM'].dropna()
        recent_pe = recent_pe[recent_pe > 0]
        if len(recent_pe) > 0:
            print(f'\n  近半年 PE 中枢: {recent_pe.median():.1f}x  '
                  f'(均值 {recent_pe.mean():.1f}x)')
            print(f'  当前 PE: {df["peTTM"].dropna().iloc[-1]:.1f}x')

        if 'pbMRQ' in df.columns:
            pb = df['pbMRQ'].dropna()
            pb = pb[pb > 0]
            if len(pb) > 0:
                print(f'\n[PB 区间] 中位 {pb.median():.2f}x  '
                      f'P25 {pb.quantile(0.25):.2f}x  P75 {pb.quantile(0.75):.2f}x  '
                      f'当前 {df["pbMRQ"].dropna().iloc[-1]:.2f}x')
        return

    # 退化路径：yfinance 数据 + 手填 EPS
    if not eps_data:
        print('  无 peTTM 列且未传 eps_data，跳过')
        return
    print('[来源] yfinance 年度高低 + 手填 EPS（baostock 不可用时退化）')
    df = df.copy()
    df['year'] = pd.to_datetime(df['date']).dt.year
    low_pes, high_pes = [], []
    for year, eps in sorted(eps_data.items()):
        yearly = df[df['year'] == year]
        if len(yearly) > 0 and eps > 0:
            low, high = yearly['close'].min(), yearly['close'].max()
            print(f'  {year}: 收盘 {low:.0f}-{high:.0f}  EPS {eps:.2f}  '
                  f'PE {low/eps:.1f}x ~ {high/eps:.1f}x')
            low_pes.append(low / eps)
            high_pes.append(high / eps)
    if low_pes:
        print(f'\n  低点 PE 中位: {np.median(low_pes):.1f}x')
        print(f'  高点 PE 中位: {np.median(high_pes):.1f}x')


def fetch_research_consensus(code: str, recent_n: int = 20):
    """拉取卖方研报一致预期（含未来 3 年 EPS/PE 预测）"""
    _section(f'卖方研报一致预期: {code}')

    if not is_a_share(code):
        print('  仅支持 A 股，跳过')
        return None

    try:
        df = ak.stock_research_report_em(symbol=code)
    except Exception as e:
        print(f'  接口失败: {e}')
        return None

    if df is None or len(df) == 0:
        print('  无研报数据')
        return None

    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期', ascending=False)

    recent = df.head(recent_n)
    print(f'共 {len(df)} 篇，统计最近 {len(recent)} 篇:')

    eps_cols = [c for c in df.columns if '盈利预测-收益' in c]
    pe_cols = [c for c in df.columns if '盈利预测-市盈率' in c]

    for eps_c, pe_c in zip(eps_cols, pe_cols):
        year = eps_c.split('-')[0]
        eps_vals = pd.to_numeric(recent[eps_c], errors='coerce').dropna()
        pe_vals = pd.to_numeric(recent[pe_c], errors='coerce').dropna()
        if len(eps_vals) > 0:
            print(f'\n  [{year}E] EPS  中位 {eps_vals.median():.2f}  '
                  f'区间 {eps_vals.min():.2f} ~ {eps_vals.max():.2f}  '
                  f'(N={len(eps_vals)})')
            if len(pe_vals) > 0:
                print(f'         PE   中位 {pe_vals.median():.1f}x  '
                      f'区间 {pe_vals.min():.1f}x ~ {pe_vals.max():.1f}x')

    if '东财评级' in recent.columns:
        rating = recent['东财评级'].value_counts()
        print(f'\n  评级分布: {dict(rating)}')

    print(f'\n  最新 3 篇:')
    show_cols = ['日期', '机构', '报告名称', '东财评级', '报告PDF链接']
    show_cols = [c for c in show_cols if c in recent.columns]
    for _, r in recent.head(3).iterrows():
        date = r['日期'].date() if isinstance(r['日期'], pd.Timestamp) else r['日期']
        print(f'    {date}  {r.get("机构", "")}  评级 {r.get("东财评级", "")}')
        print(f'      {r.get("报告名称", "")}')
        if '报告PDF链接' in r and pd.notna(r['报告PDF链接']):
            print(f'      {r["报告PDF链接"]}')

    return df


def calc_quarterly_trend(symbol: str, df: pd.DataFrame | None = None):
    """单季度扣非净利润趋势。传入 df 避免重复调 akshare。"""
    _section(f'单季度扣非净利润趋势: {symbol}')

    if df is None:
        df = ak.stock_financial_abstract(symbol=symbol)
    deducted = df[df['指标'] == '扣非净利润'].iloc[0]

    current_year = datetime.now().year
    for year in range(current_year - 2, current_year + 1):
        periods = [f'{year}1231', f'{year}0930', f'{year}0630', f'{year}0331']
        cum = {}
        for p in periods:
            if p in df.columns and pd.notna(deducted[p]):
                cum[p] = deducted[p] / 1e8

        if len(cum) >= 1:
            q_vals = {}
            q_vals['Q1'] = cum.get(f'{year}0331')
            if f'{year}0630' in cum and f'{year}0331' in cum:
                q_vals['Q2'] = cum[f'{year}0630'] - cum[f'{year}0331']
            if f'{year}0930' in cum and f'{year}0630' in cum:
                q_vals['Q3'] = cum[f'{year}0930'] - cum[f'{year}0630']
            if f'{year}1231' in cum and f'{year}0930' in cum:
                q_vals['Q4'] = cum[f'{year}1231'] - cum[f'{year}0930']

            parts = [f'{q}: {v:.2f}亿' for q, v in q_vals.items() if v is not None]
            if parts:
                print(f'  {year}: {" | ".join(parts)}')


def fetch_peers(peer_codes: list[str]):
    """获取同行财务数据"""
    _section('同行对比')

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

    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', lambda x: f'{x:.2f}')

    symbol = sys.argv[1]
    peer_codes = sys.argv[2].split(',') if len(sys.argv) > 2 else []

    fin_df = fetch_financial_summary(symbol)
    fetch_market_data(symbol)
    hist_df = fetch_history_with_pe(symbol)
    if hist_df is not None and len(hist_df) > 0:
        calc_pe_band(hist_df)
    calc_quarterly_trend(symbol, df=fin_df)
    fetch_research_consensus(symbol)
    if peer_codes:
        fetch_peers(peer_codes)

    _section('数据获取完成')


if __name__ == '__main__':
    main()
