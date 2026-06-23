# marketdata —— A 股取数共享层 + 取数源可达性约束

各 skill 的取数统一走这里（`codes.py` 是 A 股代码路由唯一来源；`quote_tencent.py` 实时行情封装）。
确定性取数逻辑放此、由各 skill 脚本 import，不在各 skill 各自维护。

## 取数源可达性约束（本机网络，强约束）

> 教训：调研「场内 ETF 取数」时发现**东财全系列在本机网络挂死**，腾讯 + 新浪才是可靠组合。

本机 `HTTP(S)_PROXY` 已设，**代理对 `eastmoney.com` 不可达**——所有走东财的 akshare 接口
（`fund_etf_spot_em` / `fund_etf_hist_em` / `fund_etf_scale_sse` / `stock_zh_a_hist` 等命中
`push2*.eastmoney.com` 的接口）报 `ProxyError`，**关沙箱直连也不行**（是本机代理而非沙箱限制）。

可达替代（三源价格/成交额互验一致）：

| 用途 | 源 | 封装 / 接口 | 注意 |
|---|---|---|---|
| 实时行情 | 腾讯 `qt.gtimg.cn` | `quote_tencent.py` | ETF「总市值」≈ 规模(AUM) 近似，作流动性闸够用；精确规模以交易所/公告为准 |
| 历史日 K | 新浪 | akshare `fund_etf_hist_sina` | OHLCV 可拉到当日，**不复权**（ETF 分红除息有跳空，对动量相对排名影响小，需标注） |
| 全市场清单 | 新浪 | akshare `fund_etf_category_sina` | 约 1500+ 只实时快照，无 AUM 列 |
| ~~网易~~ | `quotes.money.163.com/chddata` | — | 当前返 502，不可用 |

**How to apply**：A 股 ETF / 行情取数优先腾讯（实时）+ 新浪（历史），绕开东财；用前复验可达性
（代理 / 接口状态会变）。`etf_hist.py:7` 已有 sina 兜底局部说明；`codes.py` 的 `to_tencent_symbol`
已支持 ETF 前缀（51x/15x）。

**指数日线（`index_hist.py`）**：大盘指数逐年 / 近端年化波动取数，沿用同一可达性路由——A 股 /
中证系走新浪 `stock_zh_index_daily`（**非**东财 `_em`）、港股走新浪 `stock_hk_index_daily_sina`、
美股走 yfinance（限流回退 akshare `index_us_stock_sina`）。注册表 `INDICES` 是跟踪指数集合的唯一来源，
被 periodic-review `--indices`（1I 大盘指数波动监测）复用。

另：`macro_china_pmi` / `macro_china_stock_market_cap` 等个别 akshare 接口会返回 2008 陈旧数据，
用前须 WebSearch/WebFetch 兜底（见 [`docs/data-discipline.md`](../../../docs/data-discipline.md) §2「红线时间序列」与 `eval/smoke_marketdata.py`）。
