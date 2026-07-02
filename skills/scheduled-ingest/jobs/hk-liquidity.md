# 港股流动性周度快照

**Job ID**: hk-liquidity
**触发**: periodic-review 每次复盘（≈周）；或用户说"跑一下港股流动性 / 港股资金面怎么样"
**数据源**: `skills/_shared/marketdata/hk_liquidity.py` —— canonical：HKMA Open API（总结余/HIBOR/干预记录）、NY Fed（SOFR）、HKEX dayquot（成交/卖空）；转发源：新浪（USDHKD）、腾讯（VHSI）、东财（南向 hist / AH 溢价，**间歇**）
**写入目标**: `wiki/macro/港股流动性追踪.md` §一（整节置换）+ §3.2（追加一行）；raw JSON → `raw/articles/market/hk-liquidity/YYYY-MM-DD.json`
**校验级别**: L1 必跑；**高时效红线（美联储利率/汇率）→ L2/L3 全跑不豁免**（脚本输出的来源表 = L2 阶段 A 清单底稿，主 agent 仍须可见输出清单并对转发源项做阶段 B 判断）
**失败处理**: 单源缺数 → 该层灯"未评级（缺 X）"/标签省略，**禁止 stale 值套档**；东财挂 → AH/南向缺数照常出快照；连续 3 个非周末日无 dayquot → 报错人查（防 URL 漂移误当节假日）；HKMA 双路由（代理↔直连）仍失败 → 整层未评级

## 步骤

1. 跑 `python3 skills/scheduled-ingest/scripts/fetch_hk_liquidity.py`（可选 `--days-back N` 调 ⚡ 回扫窗口，默认 10 天，应 ≥ 距上次快照天数）
2. L1 自检脚本输出：量级（总结余数百亿 / 成交数千亿）、缺数清单、窗口日期连续性
3. L2：按 CLAUDE.md 输出数据声明清单（快照全部数字 + 来源；canonical 项以 raw JSON 为证，转发源项注意与上期/官方口径的偏离）
4. 写 wiki：§一 整节置换为脚本输出（保留"主轴一句"由主 agent 按灯与标签改写）；§3.2 追加一行；灯翻转或 ⚡ 时更新 §二 关键判断
5. 复盘报告：只报灯翻转与 ⚡（"变化优先"，无变化一行带过）
6. L3 数据校验 Agent（sonnet 档，commit 前必跑）
7. **月末附加**：AH/VHSI 对恒指官方 Factsheet、5 日均成交对 HKEX Monthly Highlights 校准，偏差 >1% 记入页面 §六 并排查转发源
8. **季度附加**：交易/资金流 ⚙ 档位按滚动 52 周分位数重校准（方案 §4.6），改档同步更新方案 §4 与本页 §五

## 输出格式范例

见 `wiki/macro/港股流动性追踪.md` §一（`### YYYY-MM-DD 快照` 节：缺数行 + ⚡行 + 三层灯表 + 标签行 + 来源行，机器可解析固定表头）。档位/阈值 SSOT：`docs/hk-liquidity-plan.md` §4。
