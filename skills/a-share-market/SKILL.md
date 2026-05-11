---
name: a-share-market
description: A股市场数据获取工具。提供估值（PE/PB）、资金面（融资融券、主力资金、南向资金）、市场情绪（活跃度、涨跌停）、新基金发行等数据，与macro-analysis配合使用判断A股投资环境。
---

# A-Share Market Skill

A股市场层面的数据获取工具。关注估值水位、资金流向、市场情绪等维度，配合 macro-analysis skill 的宏观数据，综合判断A股投资环境。

## When to Use

当用户请求以下操作时调用此 skill：
- 查看A股整体估值水平（PE/PB）
- 查看资金流向（主力、融资融券、南向资金）
- 判断市场情绪和活跃度
- 分析增量资金入市情况（新基金发行）
- 综合判断A股市场环境
- 与 macro-analysis 联动做宏观+市场综合分析

## Prerequisites

```bash
pip install akshare pandas numpy
```

## 数据接口速查表

> 以下接口均于 2026-05-11 实测验证通过。

### 估值

> **优先用指数级 PE/PB**（沪深300 / 上证50）：日频颗粒度细，且剔除 ST/亏损股扭曲，比全市场均值更能代表"主流定价"。全市场口径仅在需要超长历史（1997 起）月级数据时使用。

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| **指数 PE**（推荐）| `stock_index_pe_lg(symbol='沪深300')` | `['日期', '指数', '等权静态市盈率', '静态市盈率', '静态市盈率中位数', '等权滚动市盈率', '滚动市盈率', '滚动市盈率中位数']` | **日频**，正序。5180 行覆盖 2005-至今。**滚动市盈率 = TTM PE，做分位用这列**。`symbol` 可选：上证50/沪深300/上证380/创业板50/中证500/上证180/深证红利/深证100/中证1000/上证红利/中证100/中证800 |
| **指数 PB**（推荐）| `stock_index_pb_lg(symbol='沪深300')` | `['日期', '指数', '市净率', '等权市净率', '市净率中位数']` | **日频**，正序。symbol 同上 |
| 全市场PE（粗）| `stock_market_pe_lg()` | `['日期', '指数', '平均市盈率']` | **月频**（约 350 个观测覆盖 1997-至今），含 ST/亏损扭曲。仅在需要超长历史时用 |
| 全市场PB（粗）| `stock_market_pb_lg()` | `['日期', '指数', '市净率', '等权市净率', '市净率中位数']` | 日频，5181 行覆盖 2005-至今。含 ST/亏损扭曲；通常用指数级 PB 即可，本接口仅作参考 |
| A股总市值 | `macro_china_stock_market_cap()` | `['数据日期', '发行总股本-上海', '发行总股本-深圳', '市价总值-上海', '市价总值-深圳', '成交金额-上海', '成交金额-深圳', '成交量-上海', '成交量-深圳', 'A股最高综合股价指数-上海', 'A股最高综合股价指数-深圳', 'A股最低综合股价指数-上海', 'A股最低综合股价指数-深圳']` | 月频，倒序。最新月份可能部分字段为NaN |

### 资金面

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| 市场资金流向 | `stock_market_fund_flow()` | `['日期', '上证-收盘价', '上证-涨跌幅', '深证-收盘价', '深证-涨跌幅', '主力净流入-净额', '主力净流入-净占比', '超大单净流入-净额', '超大单净流入-净占比', '大单净流入-净额', '大单净流入-净占比', '中单净流入-净额', '中单净流入-净占比', '小单净流入-净额', '小单净流入-净占比']` | 正序，日频。净额单位为元 |
| 融资融券(沪) | `macro_china_market_margin_sh()` | `['日期', '融资买入额', '融资余额', '融券卖出量', '融券余量', '融券余额', '融资融券余额']` | 正序，日频。单位为元 |
| 融资融券(深) | `macro_china_market_margin_sz()` | 同上 | 正序，日频 |
| 沪深港通汇总 | `stock_hsgt_fund_flow_summary_em()` | `['交易日', '类型', '板块', '资金方向', '交易状态', '成交净买额', '资金净流入', '当日资金余额', '上涨数', '持平数', '下跌数', '相关指数', '指数涨跌幅']` | 含沪股通/深股通/港股通，按资金方向分北向/南向 |

**注意**：2024年起北向资金不再披露实时成交净买额，数据为0。南向资金仍正常披露。

### 市场情绪

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| 市场活跃度 | `stock_market_activity_legu()` | `['item', 'value']` | 当日快照：上涨/下跌/涨停/跌停/活跃度等。长表格式，每行一个指标 |

activity 的 item 包含：上涨、涨停、真实涨停、st st*涨停、下跌、跌停、真实跌停、st st*跌停、平盘、停牌、活跃度、统计日期。

### 增量资金

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| 新基金发行 | `fund_new_found_em()` | `['基金代码', '基金简称', '发行公司', '基金类型', '集中认购期', '募集份额', '成立日期', '成立来涨幅', '基金经理', '申购状态', '优惠费率']` | 全量数据。成立日期为 datetime.date，募集份额单位为亿份。可按日期筛选统计发行节奏 |

---

## Workflows

### Workflow 1: 估值水位检查

判断当前A股整体估值处于历史什么位置。

```python
import akshare as ak
import datetime

# 指数级 PE/PB（推荐路径，日频，可改 symbol 切换观察对象）
pe = ak.stock_index_pe_lg(symbol='沪深300')
pb = ak.stock_index_pb_lg(symbol='沪深300')

# 当前值（用滚动 PE = TTM；中位数避开权重股扭曲）
pe_now = pe.iloc[-1]['滚动市盈率']
pe_med_now = pe.iloc[-1]['滚动市盈率中位数']
pb_now = pb.iloc[-1]['市净率']
pb_med_now = pb.iloc[-1]['市净率中位数']

# 历史分位（用全部历史 ~5180 个交易日）
pe_rank = (pe['滚动市盈率'] < pe_now).mean() * 100
pb_rank = (pb['市净率'] < pb_now).mean() * 100

print(f"沪深300 PE_TTM: {pe_now:.1f} (历史分位 {pe_rank:.0f}%, 中位 {pe_med_now:.1f})")
print(f"沪深300 PB:    {pb_now:.2f} (历史分位 {pb_rank:.0f}%, 中位 {pb_med_now:.2f})")

# 近 N 年分位（更有参考价值）
for years in [3, 5, 10]:
    cutoff = datetime.date.today() - datetime.timedelta(days=years*365)
    pe_recent = pe[pe['日期'] >= cutoff]
    pb_recent = pb[pb['日期'] >= cutoff]
    pe_r = (pe_recent['滚动市盈率'] < pe_now).mean() * 100
    pb_r = (pb_recent['市净率'] < pb_now).mean() * 100
    print(f"  近{years}年: PE分位 {pe_r:.0f}%, PB分位 {pb_r:.0f}%")
```

估值判断参考：
- PE/PB < 30%分位 → 低估区域，左侧布局机会
- PE/PB 30~70%分位 → 合理区域
- PE/PB > 70%分位 → 偏高，注意风险

> 阈值原基于全市场口径校准。指数级口径下分位含义类似，但绝对水平区间更窄（如沪深300 PE_TTM 历史 30% 分位约 10x，全市场约 15x）；实战时除了看分位，建议同时与"中位数"和"近 5 年区间"交叉验证。

### Workflow 2: 资金面扫描

```python
import akshare as ak

# 1. 主力资金流向（近5日趋势）
flow = ak.stock_market_fund_flow()
recent = flow.tail(5)
print("=== 近5日主力资金 ===")
for _, r in recent.iterrows():
    net = r['主力净流入-净额'] / 1e8  # 转为亿元
    print(f"  {r['日期']}: 主力净流入 {net:.1f}亿, 占比 {r['主力净流入-净占比']}%")

# 2. 融资余额趋势
margin_sh = ak.macro_china_market_margin_sh()
margin_sz = ak.macro_china_market_margin_sz()
# 两市合计融资余额
sh_latest = margin_sh.iloc[-1]
sz_latest = margin_sz.iloc[-1]
total_margin = (sh_latest['融资余额'] + sz_latest['融资余额']) / 1e8  # 转为亿元
print(f"\n两市融资余额: {total_margin:.0f}亿元 (日期: {sh_latest['日期']})")

# 近期趋势
for i in [-1, -6, -21]:  # 最新、5日前、20日前
    sh = margin_sh.iloc[i]['融资余额']
    sz = margin_sz.iloc[i]['融资余额']
    total = (sh + sz) / 1e8
    d = margin_sh.iloc[i]['日期']
    print(f"  {d}: {total:.0f}亿")

# 3. 南向资金
hsgt = ak.stock_hsgt_fund_flow_summary_em()
south = hsgt[hsgt['资金方向'] == '南向']
south_recent = south.tail(10)
print(f"\n=== 南向资金(近5个交易日) ===")
# 按日汇总
for date in south_recent['交易日'].unique()[-5:]:
    day_data = south_recent[south_recent['交易日'] == date]
    total_net = day_data['成交净买额'].sum()
    print(f"  {date}: 净买入 {total_net:.1f}亿")
```

资金面判断：
- 融资余额持续上升 + 主力净流入 → 市场加杠杆，情绪偏多
- 融资余额下降 + 主力净流出 → 去杠杆，谨慎

### Workflow 3: 市场情绪温度计

```python
import akshare as ak

act = ak.stock_market_activity_legu()
data = dict(zip(act['item'], act['value']))

up = int(data.get('上涨', 0))
down = int(data.get('下跌', 0))
limit_up = int(data.get('涨停', 0))
real_limit_up = int(data.get('真实涨停', 0))
limit_down = int(data.get('跌停', 0))
activity = data.get('活跃度', 'N/A')

total = up + down + int(data.get('平盘', 0))
up_ratio = up / total * 100 if total > 0 else 0

print(f"上涨/下跌: {up}/{down} (上涨占比 {up_ratio:.0f}%)")
print(f"涨停: {limit_up} (真实涨停 {real_limit_up})")
print(f"跌停: {limit_down}")
print(f"活跃度: {activity}")

# 情绪判断
if up_ratio > 70:
    mood = "极度乐观"
elif up_ratio > 55:
    mood = "偏多"
elif up_ratio > 45:
    mood = "中性"
elif up_ratio > 30:
    mood = "偏空"
else:
    mood = "极度悲观"
print(f"市场情绪: {mood}")
```

### Workflow 4: 增量资金追踪

```python
import akshare as ak
import datetime

fund = ak.fund_new_found_em()

# 按月统计新基金发行
for months_ago in [0, 1, 2]:
    today = datetime.date.today()
    if months_ago == 0:
        start = today.replace(day=1)
        label = "本月"
    else:
        m = today.month - months_ago
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        start = datetime.date(y, m, 1)
        end = datetime.date(y, m + 1, 1) if m < 12 else datetime.date(y + 1, 1, 1)
        label = f"{y}-{m:02d}"

    if months_ago == 0:
        period = fund[fund['成立日期'] >= start]
    else:
        period = fund[(fund['成立日期'] >= start) & (fund['成立日期'] < end)]

    count = len(period)
    total_size = period['募集份额'].sum()
    # 股票型基金占比
    equity = period[period['基金类型'].str.contains('股票|偏股', na=False)]
    equity_size = equity['募集份额'].sum()

    print(f"{label}: 新成立{count}只, 募集{total_size:.0f}亿份, 其中权益类{equity_size:.0f}亿份")
```

新基金发行判断：
- 权益基金发行放量 → 增量资金入市，但也可能是市场过热信号
- 权益基金发行冰点 → 市场情绪低迷，但往往是底部特征

### Workflow 5: A股市场环境综合判断

串联所有维度，给出综合判断。建议与 macro-analysis skill 联合使用。

**使用方式**：

1. 先用 macro-analysis 获取宏观数据（GDP/CPI/PPI/PMI/M2/LPR/信贷）
2. 再用本 skill 获取市场数据（PE/PB/资金/情绪/新基金）
3. 综合判断框架如下：

| 维度 | 数据来源 | 看什么 |
|------|---------|--------|
| 经济基本面 | macro-analysis | GDP增速方向、PMI趋势、PPI拐点 |
| 流动性 | macro-analysis | M2增速、LPR/SHIBOR、信贷 |
| M1-M2剪刀差 | macro-analysis → `macro_china_money_supply()` | M1同比-M2同比，上行利好股市 |
| 估值 | 本skill | PE/PB历史分位，低估还是高估 |
| 资金面 | 本skill | 融资余额趋势、主力流向 |
| 市场情绪 | 本skill | 涨跌比、活跃度 |
| 增量资金 | 本skill | 新基金发行节奏 |

**综合判断矩阵**：

| 环境 | 宏观 | 流动性 | 估值 | 资金情绪 | 操作建议 |
|------|------|--------|------|----------|---------|
| 黄金坑 | 见底企稳 | 宽松 | 低估 | 低迷 | 积极布局 |
| 复苏牛 | 改善 | 宽松 | 合理 | 回暖 | 持股为主 |
| 泡沫期 | 过热 | 收紧迹象 | 高估 | 狂热 | 逐步减仓 |
| 杀估值 | 尚可 | 收紧 | 高估 | 恐慌 | 观望 |
| 熊市底 | 恶化 | 宽松转向 | 低估 | 极度悲观 | 左侧建仓 |

---

## Error Handling

### 接口限流
akshare 部分接口有频率限制，分批获取。

### 交易日数据
市场数据仅在交易日更新。周末/节假日获取到的是最近一个交易日的数据。

### 北向资金不可用
2024年起北向资金不再披露实时成交净买额。`stock_hsgt_hist_em` 和 `stock_hsgt_fund_flow_summary_em` 中北向数据均为0。南向资金正常。

## Best Practices

1. **估值要看分位数**：绝对PE/PB值意义有限，历史分位才有参考价值。建议看近5年和近10年两个维度
2. **资金面看趋势**：单日数据波动大，融资余额看5日/20日变化方向
3. **情绪指标是辅助**：涨跌比、活跃度反映短期情绪，不能作为中长期决策依据
4. **与宏观联动**：市场数据反映"市场在想什么"，宏观数据反映"经济在做什么"，两者结合才有价值
5. **M1-M2是桥梁**：这个指标在 macro-analysis 的 `macro_china_money_supply()` 中，是连接宏观和市场的关键指标
