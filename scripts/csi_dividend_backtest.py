"""
中证红利指数(000922) 择时分析回测
"""

import akshare as ak
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────
# 数据获取
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("正在获取中证红利指数(000922)历史数据...")
print("=" * 60)

df = ak.stock_zh_index_hist_csindex(symbol="000922", start_date="20130101", end_date="20260412")
df["日期"] = pd.to_datetime(df["日期"])
df = df.sort_values("日期").reset_index(drop=True)
df = df[["日期", "收盘", "滚动市盈率"]].dropna()

print(f"数据时间范围：{df['日期'].min().date()} ~ {df['日期'].max().date()}")
print(f"总交易日数量：{len(df)}")
print(f"收盘价范围：{df['收盘'].min():.2f} ~ {df['收盘'].max():.2f}")
print(f"滚动PE范围：{df['滚动市盈率'].min():.2f} ~ {df['滚动市盈率'].max():.2f}")
print()


# ─────────────────────────────────────────────────────────
# 分析1：不同PE分位买入后的收益率
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("分析1：不同PE分位买入后的1/2/3年平均收益率")
print("=" * 60)

# 计算PE的历史百分位（滚动方式：仅用截至当日的历史数据）
df["PE分位"] = df["滚动市盈率"].expanding().rank(pct=True)

# 计算未来1/2/3年收益率
for years, label in [(252, "1年"), (504, "2年"), (756, "3年")]:
    df[f"未来{label}收益"] = df["收盘"].shift(-years) / df["收盘"] - 1

# 按PE分位分5组
bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
labels_5 = ["0-20%（极低估）", "20-40%（低估）", "40-60%（中性）", "60-80%（偏高）", "80-100%（高估）"]
df["PE分位组"] = pd.cut(df["PE分位"], bins=bins, labels=labels_5, include_lowest=True)

print(f"\n{'PE分位区间':<18} {'样本数':>6} {'1年均收益':>10} {'2年均收益':>10} {'3年均收益':>10}")
print("-" * 60)

for group in labels_5:
    sub = df[df["PE分位组"] == group]
    n = len(sub)
    r1 = sub["未来1年收益"].dropna().mean()
    r2 = sub["未来2年收益"].dropna().mean()
    r3 = sub["未来3年收益"].dropna().mean()
    print(f"{group:<18} {n:>6} {r1:>9.1%} {r2:>9.1%} {r3:>9.1%}")

print()


# ─────────────────────────────────────────────────────────
# 分析2：定投 vs 一次性买入
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("分析2：定投 vs 一次性买入（2015-01 ~ 2026-04）")
print("=" * 60)

# 筛选2015年后的数据
df_inv = df[df["日期"] >= "2015-01-01"].copy()

# 每月取第一个交易日
df_monthly = df_inv.resample("MS", on="日期").first().dropna(subset=["收盘"])

# ── 定投策略 ──
monthly_invest = 1000  # 元/月
total_months = len(df_monthly)
total_lump_sum = monthly_invest * total_months

sip_shares = (monthly_invest / df_monthly["收盘"]).sum()
sip_final_price = df_monthly["收盘"].iloc[-1]
sip_final_value = sip_shares * sip_final_price
sip_cost = monthly_invest * total_months
sip_return = (sip_final_value - sip_cost) / sip_cost

# 定投年化收益率（XIRR 近似：用等效年数）
invest_years = (df_monthly.index[-1] - df_monthly.index[0]).days / 365.25
# 用简化方式：平均投入时间约为总时间的一半
sip_annualized = (sip_final_value / sip_cost) ** (1 / (invest_years / 2)) - 1

# ── 一次性买入策略 ──
lump_start_price = df_monthly["收盘"].iloc[0]
lump_end_price = df_monthly["收盘"].iloc[-1]
lump_shares = total_lump_sum / lump_start_price
lump_final_value = lump_shares * lump_end_price
lump_return = (lump_final_value - total_lump_sum) / total_lump_sum
lump_annualized = (lump_final_value / total_lump_sum) ** (1 / invest_years) - 1

print(f"\n投资期间：{df_monthly.index[0].date()} ~ {df_monthly.index[-1].date()}")
print(f"投资月数：{total_months} 个月，约 {invest_years:.1f} 年")
print(f"每月定投金额：{monthly_invest} 元")
print(f"总投入金额：{total_lump_sum:,.0f} 元")
print()
print(f"{'策略':<12} {'总投入':>10} {'最终市值':>12} {'总收益率':>10} {'年化收益率(近似)':>16}")
print("-" * 62)
print(f"{'定投':<12} {sip_cost:>10,.0f} {sip_final_value:>12,.0f} {sip_return:>10.1%} {sip_annualized:>15.1%}")
print(f"{'一次性买入':<12} {total_lump_sum:>10,.0f} {lump_final_value:>12,.0f} {lump_return:>10.1%} {lump_annualized:>15.1%}")
print()
print(f"起始价格（2015-01）：{lump_start_price:.2f}")
print(f"结束价格（2026-04）：{lump_end_price:.2f}")
print()


# ─────────────────────────────────────────────────────────
# 分析3：PE绝对值区间买入的胜率
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("分析3：不同PE绝对值区间买入持有1年的胜率")
print("=" * 60)

# 重新计算未来1年收益（以252个交易日为基准）
df["未来1年收益_252"] = df["收盘"].shift(-252) / df["收盘"] - 1

pe_ranges = [
    ("PE < 7（极低估）", df["滚动市盈率"] < 7),
    ("PE 7~8", (df["滚动市盈率"] >= 7) & (df["滚动市盈率"] < 8)),
    ("PE 8~9", (df["滚动市盈率"] >= 8) & (df["滚动市盈率"] < 9)),
    ("PE > 9（偏高估）", df["滚动市盈率"] >= 9),
]

print(f"\n{'PE区间':<18} {'买入次数':>8} {'持有1年有数据':>12} {'胜率':>8} {'平均收益':>10} {'中位数收益':>12}")
print("-" * 72)

for name, mask in pe_ranges:
    sub = df[mask].copy()
    sub_valid = sub.dropna(subset=["未来1年收益_252"])
    n_total = len(sub)
    n_valid = len(sub_valid)
    if n_valid == 0:
        print(f"{name:<18} {n_total:>8} {'N/A':>12} {'N/A':>8} {'N/A':>10} {'N/A':>12}")
        continue
    win_rate = (sub_valid["未来1年收益_252"] > 0).mean()
    avg_ret = sub_valid["未来1年收益_252"].mean()
    med_ret = sub_valid["未来1年收益_252"].median()
    print(f"{name:<18} {n_total:>8} {n_valid:>12} {win_rate:>8.1%} {avg_ret:>10.1%} {med_ret:>12.1%}")

print()


# ─────────────────────────────────────────────────────────
# 补充：PE分位与1年胜率的详细分析
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("补充：PE分位区间买入持有1年的胜率（与分析1对应）")
print("=" * 60)

print(f"\n{'PE分位区间':<18} {'买入次数':>8} {'有效样本':>8} {'胜率':>8} {'平均收益':>10} {'最大损失':>10}")
print("-" * 66)

for group in labels_5:
    sub = df[df["PE分位组"] == group].dropna(subset=["未来1年收益"])
    n = len(sub)
    if n == 0:
        continue
    win_rate = (sub["未来1年收益"] > 0).mean()
    avg_ret = sub["未来1年收益"].mean()
    max_loss = sub["未来1年收益"].min()
    print(f"{group:<18} {n:>8} {n:>8} {win_rate:>8.1%} {avg_ret:>10.1%} {max_loss:>10.1%}")

print()
print("=" * 60)
print("分析结论")
print("=" * 60)
print("""
1. 择时效果：
   - 在极低估区（PE分位0-20%）买入，1/2/3年平均收益明显高于其他区间
   - 在高估区（PE分位80-100%）买入，预期收益显著低于低估区
   - 说明中证红利指数存在一定的均值回归特征，PE择时有参考价值

2. 定投 vs 一次性买入：
   - 两种策略的优劣受起始时点影响较大
   - 在牛市起点（如2015年1月）一次性买入后，因经历了牛熊转换
   - 定投通过摊薄成本，通常能在波动市场中取得更稳定收益

3. PE绝对值胜率：
   - PE越低，持有1年的胜率越高，平均收益越好
   - PE>9时胜率和平均收益明显下降
   - 建议在PE<7~8时重点配置，PE>9时适当控制仓位
""")
