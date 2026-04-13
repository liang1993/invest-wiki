---
name: macro-analysis
description: 宏观经济数据获取与分析工具。基于akshare获取中国、美国及全球宏观经济指标（GDP、CPI、PMI、社融、利率、汇率等），支持趋势分析和跨指标对比，辅助投资决策中的宏观判断。
---

# Macro Analysis Skill

基于 akshare 的宏观经济数据获取与分析工具，面向需要宏观视角辅助投资决策的个人投资者。

## When to Use

当用户请求以下操作时调用此 skill：
- 查看宏观经济指标（GDP、CPI、PMI、M2、社融等）
- 分析宏观经济趋势
- 对比中美或多国经济指标
- 判断当前经济周期位置
- 查看利率、汇率、货币政策变化
- 分析宏观环境对投资的影响
- 获取航运指数（BDI）、大宗商品等全球经济风向标

## Prerequisites

```bash
pip install akshare pandas numpy
```

验证安装：
```bash
python -c "import akshare; print(akshare.__version__)"
```

## 接口验证状态

> 以下所有接口均于 2026-04-12 实测验证通过，除标注 ⚠️ 的接口外。

## 数据格式说明

中国数据使用**统计局源**（格式B），列名各不相同，数据按时间**倒序**排列（`iloc[0]`=最新），下方速查表中标注了每个接口的具体列名。

美国/欧洲/全球利率使用**东财/英为财情源**（格式A）：
- 列名：`['商品', '日期', '今值', '预测值', '前值']`
- 日期为 `datetime.date` 类型
- 最新一行的"今值"可能为 `NaN`（尚未发布），取最新已发布数据：`df[df['今值'].notna()].iloc[-1]`

**重要**：调用任何接口后，先执行 `print(df.columns.tolist())` 和 `print(df.head(3))` 确认字段结构，再做后续处理。

## 数据接口速查表

### 中国核心指标（统计局源，数据最新）

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| GDP | `macro_china_gdp()` | `['季度', '国内生产总值-绝对值', '国内生产总值-同比增长', '第一产业-绝对值', '第一产业-同比增长', '第二产业-绝对值', '第二产业-同比增长', '第三产业-绝对值', '第三产业-同比增长']` | 倒序 |
| CPI | `macro_china_cpi()` | `['月份', '全国-当月', '全国-同比增长', '全国-环比增长', '全国-累计', '城市-当月', '城市-同比增长', '城市-环比增长', '城市-累计', '农村-当月', '农村-同比增长', '农村-环比增长', '农村-累计']` | 倒序 |
| PPI | `macro_china_ppi()` | `['月份', '当月', '当月同比增长', '累计']` | 倒序。当月>100为涨价，当月同比增长即PPI同比% |
| PMI | `macro_china_pmi()` | `['月份', '制造业-指数', '制造业-同比增长', '非制造业-指数', '非制造业-同比增长']` | 倒序，含制造业+非制造业 |
| 财新PMI | `macro_china_cx_pmi_yearly()` | 格式A | 财新制造业PMI |
| 财新服务业PMI | `macro_china_cx_services_pmi_yearly()` | 格式A | 财新服务业PMI |
| 货币供应 | `macro_china_money_supply()` | `['月份', '货币和准货币(M2)-数量(亿元)', '货币和准货币(M2)-同比增长', '货币和准货币(M2)-环比增长', '货币(M1)-数量(亿元)', '货币(M1)-同比增长', '货币(M1)-环比增长', '流通中的现金(M0)-数量(亿元)', '流通中的现金(M0)-同比增长', '流通中的现金(M0)-环比增长']` | 倒序，M0/M1/M2 |
| ⚠️ 社融 | `macro_china_shrzgm()` | — | SSL连接失败，改用新增信贷 |
| 新增信贷 | `macro_china_new_financial_credit()` | `['月份', '当月', '当月-同比增长', '当月-环比增长', '累计', '累计-同比增长']` | 倒序 |
| 人民币贷款 | `macro_rmb_loan()` | `['月份', '新增人民币贷款-总额', '新增人民币贷款-同比', '新增人民币贷款-环比', '累计人民币贷款-总额', '累计人民币贷款-同比']` | 近30月 |
| 人民币存款 | `macro_rmb_deposit()` | `['月份', '新增存款-数量', '新增存款-同比', '新增存款-环比', '新增企业存款-数量', ...]` | 近30月 |
| LPR | `macro_china_lpr()` | `['TRADE_DATE', 'LPR1Y', 'LPR5Y', 'RATE_1', 'RATE_2']` | 正序，TRADE_DATE为datetime.date |
| 存款准备金率 | `macro_china_reserve_requirement_ratio()` | `['公布时间', '生效时间', '大型金融机构-调整前', '大型金融机构-调整后', '大型金融机构-调整幅度', '中小金融机构-调整前', '中小金融机构-调整后', '中小金融机构-调整幅度', ...]` | 倒序，历次调整记录 |
| SHIBOR | `macro_china_shibor_all()` | `['日期', 'O/N-定价', 'O/N-涨跌幅', '1W-定价', '1W-涨跌幅', '2W-定价', ..., '1Y-定价', '1Y-涨跌幅']` | 正序，日频 |
| 央行资产负债表 | `macro_china_central_bank_balance()` | `['统计时间', '国外资产', '外汇', ..., '储备货币', ..., '总负债']` 共28列 | |
| 进出口 | `macro_china_hgjck()` | `['月份', '当月出口额-金额', '当月出口额-同比增长', '当月出口额-环比增长', '当月进口额-金额', '当月进口额-同比增长', '当月进口额-环比增长', '累计出口额-金额', '累计出口额-同比增长', '累计进口额-金额', '累计进口额-同比增长']` | 倒序 |
| FDI | `macro_china_fdi()` | `['月份', '当月', '当月-同比增长', '当月-环比增长', '累计', '累计-同比增长']` | 倒序，2023年后可能缺失 |
| 固定资产投资 | `macro_china_gdzctz()` | `['月份', '当月', '同比增长', '环比增长', '自年初累计']` | 倒序 |
| 工业增加值 | `macro_china_gyzjz()` | `['月份', '同比增长', '累计增长', '发布时间']` | **正序！用 `iloc[-1]` 取最新** |
| 社会消费品零售 | `macro_china_consumer_goods_retail()` | `['月份', '当月', '同比增长', '环比增长', '累计', '累计-同比增长']` | 倒序 |
| 财政收入 | `macro_china_czsr()` | `['月份', '当月', '当月-同比增长', '当月-环比增长', '累计', '累计-同比增长']` | 倒序 |
| 税收 | `macro_china_national_tax_receipts()` | `['季度', '税收收入合计', '较上年同期', '季度环比']` | |
| 城镇失业率 | `macro_china_urban_unemployment()` | `['date', 'item', 'value']` | 长表格式，item含"全国城镇调查失业率"等分类，date格式YYYYMM |
| 房地产 | `macro_china_real_estate()` | `['日期', '最新值', '涨跌幅', '近3月涨跌幅', ...]` | |
| 新房价格 | `macro_china_new_house_price()` | `['日期', '城市', '新建商品住宅价格指数-同比', '新建商品住宅价格指数-环比', '新建商品住宅价格指数-定基', '二手住宅价格指数-同比', '二手住宅价格指数-环比', '二手住宅价格指数-定基']` | 70城 |
| ⚠️ 人民币汇率 | `macro_china_rmb()` | — | 接口报错（akshare内部TypeError），暂不可用 |
| 企业景气指数 | `macro_china_enterprise_boom_index()` | `['季度', '企业景气指数-指数', '企业景气指数-同比', '企业景气指数-环比', '企业家信心指数-指数', '企业家信心指数-同比', '企业家信心指数-环比']` | |
| 物流指数 | `macro_china_lpi_index()` | `['日期', '最新值', '涨跌幅', ...]` | |
| A股市值 | `macro_china_stock_market_cap()` | `['数据日期', '发行总股本-上海', '发行总股本-深圳', '市价总值-上海', '市价总值-深圳', '成交金额-上海', '成交金额-深圳', ...]` | |

### 美国核心指标（格式A）

列名统一为 `['商品', '日期', '今值', '预测值', '前值']`，除特别标注外。

| 指标 | akshare 函数 | 说明 |
|------|-------------|------|
| GDP | `macro_usa_gdp_monthly()` | 美国GDP |
| CPI(月率) | `macro_usa_cpi_monthly()` | CPI月率 |
| CPI(同比) | `macro_usa_cpi_yoy()` | **列名不同**：`['时间', '发布日期', '现值', '前值']` |
| 核心CPI | `macro_usa_core_cpi_monthly()` | 核心CPI月率 |
| PPI | `macro_usa_ppi()` | 生产者物价指数 |
| 核心PPI | `macro_usa_core_ppi()` | 核心PPI |
| 核心PCE | `macro_usa_core_pce_price()` | 核心PCE（美联储首选通胀指标） |
| Markit PMI | `macro_usa_pmi()` | Markit制造业PMI |
| ISM PMI | `macro_usa_ism_pmi()` | ISM制造业PMI |
| 非制造业PMI | `macro_usa_ism_non_pmi()` | ISM非制造业PMI |
| 服务业PMI | `macro_usa_services_pmi()` | Markit服务业PMI |
| 非农就业 | `macro_usa_non_farm()` | 非农就业人数变化（千人） |
| 失业率 | `macro_usa_unemployment_rate()` | 失业率(%) |
| ADP就业 | `macro_usa_adp_employment()` | ADP就业人数变化（小非农，千人） |
| 初请失业金 | `macro_usa_initial_jobless()` | 初请失业金人数（周频，千人） |
| 联邦基金利率 | `macro_bank_usa_interest_rate()` | 美联储利率决议 |
| 零售销售 | `macro_usa_retail_sales()` | 零售销售月率(%) |
| CB消费者信心 | `macro_usa_cb_consumer_confidence()` | 谘商会消费者信心指数 |
| 密歇根消费信心 | `macro_usa_michigan_consumer_sentiment()` | 密歇根大学消费者信心 |
| 贸易差额 | `macro_usa_trade_balance()` | 贸易帐（亿美元） |
| 工业产出 | `macro_usa_industrial_production()` | 工业产出月率(%) |
| 新屋销售 | `macro_usa_new_home_sales()` | 新屋销售 |
| 成屋销售 | `macro_usa_exist_home_sales()` | 成屋销售 |
| 房价指数 | `macro_usa_house_price_index()` / `macro_usa_spcs20()` | 房价指数/标普CS20城 |
| 耐用品订单 | `macro_usa_durable_goods_orders()` | 耐用品订单月率(%) |
| EIA原油库存 | `macro_usa_eia_crude_rate()` | EIA原油库存变化（周频） |
| API原油库存 | `macro_usa_api_crude_stock()` | API原油库存 |
| CFTC持仓 | `macro_usa_cftc_nc_holding()` | **列名不同**：`['日期', '美元-多头/空头/净仓位', '瑞郎-...', '日元-...', '欧元-...', ...]` |

### 全球利率（格式A）

| 国家/地区 | akshare 函数 |
|-----------|-------------|
| 美国 | `macro_bank_usa_interest_rate()` |
| 欧元区 | `macro_bank_euro_interest_rate()` |
| 日本 | `macro_bank_japan_interest_rate()` |
| 英国 | `macro_bank_english_interest_rate()` |
| 澳大利亚 | `macro_bank_australia_interest_rate()` |
| 印度 | `macro_bank_india_interest_rate()` |
| 俄罗斯 | `macro_bank_russia_interest_rate()` |
| 巴西 | `macro_bank_brazil_interest_rate()` |
| 瑞士 | `macro_bank_switzerland_interest_rate()` |
| 新西兰 | `macro_bank_newzealand_interest_rate()` |

### 全球风向标

| 指标 | akshare 函数 | 返回列 | 说明 |
|------|-------------|--------|------|
| BDI | `macro_shipping_bdi()` | `['日期', '最新值', '涨跌幅', '近3月涨跌幅', ...]` | 波罗的海干散货指数（日频） |
| BCI | `macro_shipping_bci()` | 同上 | 波罗的海海岬型指数 |
| BPI | `macro_shipping_bpi()` | 同上 | 波罗的海巴拿马型指数 |
| BCTI | `macro_shipping_bcti()` | 同上 | 波罗的海清洁油轮指数 |
| SOX | `macro_global_sox_index()` | 同上 | 费城半导体指数（日频） |
| 黄金 | `macro_cons_gold()` | `['商品', '日期', '总库存', '增持/减持', '总价值']` | SPDR黄金ETF持仓（非金价） |
| 白银 | `macro_cons_silver()` | 同上 | iShares白银ETF持仓（非银价） |
| OPEC | `macro_cons_opec_month()` | `['日期', '阿尔及利亚', ..., '沙特', ..., '欧佩克产量']` | OPEC各国月度产量 |
| LME库存 | `macro_euro_lme_stock()` | `['日期', '铜-库存', '铜-注册仓单', '铜-注销仓单', '锡-...', '铅-...', '锌-...', '铝-...', '镍-...']` | |
| LME持仓 | `macro_euro_lme_holding()` | `['日期', '铜-多头仓位', '铜-空头仓位', '铜-净仓位', '锌-...', '镍-...', ...]` | |

### 欧元区（格式A）

| 指标 | akshare 函数 |
|------|-------------|
| GDP | `macro_euro_gdp_yoy()` |
| CPI(月) | `macro_euro_cpi_mom()` |
| CPI(年) | `macro_euro_cpi_yoy()` |
| PPI | `macro_euro_ppi_mom()` |
| 制造业PMI | `macro_euro_manufacturing_pmi()` |
| 服务业PMI | `macro_euro_services_pmi()` |
| 失业率 | `macro_euro_unemployment_rate_mom()` |
| 贸易帐 | `macro_euro_trade_balance()` |
| 零售销售 | `macro_euro_retail_sales_mom()` |
| ZEW经济景气 | `macro_euro_zew_economic_sentiment()` |
| Sentix投资信心 | `macro_euro_sentix_investor_confidence()` |

---

## Workflows

### Workflow 1: 单指标查询

用户询问某个具体宏观指标时使用。

**Step 1: 识别指标** — 匹配上方速查表中的函数。

**Step 2: 获取数据**

```python
import akshare as ak

# 示例：获取中国CPI（统计局源，倒序）
df = ak.macro_china_cpi()
print(df.columns.tolist())
print(df.head(3))  # 倒序，head=最新

latest = df.iloc[0]
print(f"最新CPI: {latest['月份']}, 同比 {latest['全国-同比增长']}%, 环比 {latest['全国-环比增长']}%")
```

**Step 3: 呈现结果** — 表格展示最近数据，标注趋势判断。

### Workflow 2: 经济仪表盘（多指标概览）

```python
import akshare as ak

# 增长
gdp = ak.macro_china_gdp()              # 倒序
industrial = ak.macro_china_gyzjz()      # 正序！

# 物价
cpi = ak.macro_china_cpi()               # 倒序
ppi = ak.macro_china_ppi()               # 倒序

# 景气
pmi = ak.macro_china_pmi()               # 倒序

# 货币与信用
m2 = ak.macro_china_money_supply()       # 倒序
new_credit = ak.macro_china_new_financial_credit()  # 倒序
lpr = ak.macro_china_lpr()               # 正序

# 外贸
trade = ak.macro_china_hgjck()           # 倒序

# 就业与消费
unemployment = ak.macro_china_urban_unemployment()
retail = ak.macro_china_consumer_goods_retail()  # 倒序

# 取最新值
print(f"GDP: {gdp.iloc[0]['季度']}, 同比 {gdp.iloc[0]['国内生产总值-同比增长']}%")
print(f"CPI: {cpi.iloc[0]['月份']}, 同比 {cpi.iloc[0]['全国-同比增长']}%")
print(f"PPI: {ppi.iloc[0]['月份']}, 同比 {ppi.iloc[0]['当月同比增长']}%")
print(f"PMI: {pmi.iloc[0]['月份']}, 制造业 {pmi.iloc[0]['制造业-指数']}, 非制造业 {pmi.iloc[0]['非制造业-指数']}")
print(f"M2: {m2.iloc[0]['月份']}, 同比 {m2.iloc[0]['货币和准货币(M2)-同比增长']}%")
print(f"LPR: 1Y={lpr.iloc[-1]['LPR1Y']}%, 5Y={lpr.iloc[-1]['LPR5Y']}%")
print(f"工业: {industrial.iloc[-1]['月份']}, 同比 {industrial.iloc[-1]['同比增长']}%")  # 正序用iloc[-1]
```

### Workflow 3: 经济周期定位

美林投资时钟 + 中国信用周期：

| 阶段 | GDP | CPI | 货币政策 | 信用 | 利好资产 |
|------|-----|-----|----------|------|----------|
| 衰退期 | ↓ | ↓ | 宽松 | 收缩→企稳 | 债券 |
| 复苏期 | ↑ | ↓ | 宽松 | 扩张 | 股票 |
| 过热期 | ↑ | ↑ | 收紧 | 扩张 | 商品 |
| 滞胀期 | ↓ | ↑ | 收紧 | 收缩 | 现金 |

获取GDP/CPI/PPI/PMI/M2/LPR/信贷数据，判断当前所处阶段，给出资产配置建议。

### Workflow 4: 中美对比

```python
import akshare as ak

def latest_a(df):
    """从格式A取最新已发布数据"""
    return df[df['今值'].notna()].iloc[-1]

# 中国（统计局源）
cn_cpi = ak.macro_china_cpi()
cn_pmi = ak.macro_china_pmi()
cn_lpr = ak.macro_china_lpr()

# 美国（格式A）
us_gdp = ak.macro_usa_gdp_monthly()
us_cpi = ak.macro_usa_cpi_monthly()
us_pmi = ak.macro_usa_ism_pmi()
us_rate = ak.macro_bank_usa_interest_rate()

# 利差
cn_rate = cn_lpr.iloc[-1]['LPR1Y']
us_rate_val = latest_a(us_rate)['今值']
print(f"中美利差: {cn_rate - us_rate_val:.2f}%")
```

### Workflow 5: 利率与流动性监控

```python
import akshare as ak

lpr = ak.macro_china_lpr()
rrr = ak.macro_china_reserve_requirement_ratio()
shibor = ak.macro_china_shibor_all()          # 正序，日频
m2 = ak.macro_china_money_supply()            # 倒序
new_credit = ak.macro_china_new_financial_credit()  # 倒序
rmb_loan = ak.macro_rmb_loan()
rmb_deposit = ak.macro_rmb_deposit()
central_bank = ak.macro_china_central_bank_balance()
```

---

## Error Handling

### 接口限流
akshare 部分接口有频率限制。如果报错，等待几秒后重试，或分批获取。

### 数据缺失
部分指标更新有滞后（GDP季度更新、PMI月度更新等）。获取数据后检查最新日期，告知用户数据时效性。

### 已知不可用接口（2026-04-12验证）
- `macro_china_shrzgm()` — SSL连接失败（商务部数据源），用 `macro_china_new_financial_credit()` 替代
- `macro_china_rmb()` — akshare内部TypeError，汇率数据暂不可用

---

## Best Practices

1. **数据时效性**：获取数据后始终检查并告知最新数据的日期
2. **先验证后分析**：调用接口后先打印 columns 和 head，确认数据结构正确
3. **注意排序方向**：大部分中国统计局源是倒序（`iloc[0]`=最新），但 `macro_china_gyzjz()`（工业增加值）是正序（`iloc[-1]`=最新），`macro_china_lpr()` 和 `macro_china_shibor_all()` 也是正序
4. **适度获取**：仪表盘模式下分批获取接口，避免一次调用过多触发限流
5. **结合投资**：宏观分析的落脚点是对投资决策的启示，避免纯数据罗列
6. **周期视角**：单个数据点意义有限，关注趋势变化和拐点信号
7. **交叉验证**：用多个指标交叉验证同一判断（如PMI+工业增加值验证经济景气）
8. **投资建议免责**：所有分析仅供参考，不构成投资建议
