# 研究：A 股 ETF 动量轮动的趋势止损/风控设置（回测验证）

目的：用回测+数据验证回答"A 股 ETF 动量轮动的趋势止损点该怎么设"。多 agent 并行 + 主 agent 自核 + 独立审计（双门 review）。

## 复现
```bash
# 数据已缓存（data/，17 个 sina 行业价格指数，无需联网/复权）。重抓数据：
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    python3 build_panel.py
# 回测（数据已缓存，plain python3 即可，~5s 各）：
python3 btlib.py            # 共享库自测
python3 _xcheck_rotation.py # 主 agent 独立锚定
python3 champion.py         # vol-scaling / TSMOM / MA扫描 / 成本
python3 bt1_single_asset.py # 单标的趋势止损
python3 bt2_rotation.py     # 轮动趋势止损网格
```

## 文件地图
| 层 | 文件 | 说明 |
|---|---|---|
| 数据探针 | `probe_sources.py` / `probe_sectors.py` / `probe_primary.py` | sina 唯一可达长史源；逐代码验覆盖（中证一级/全指一半坏在 2016，必须逐验） |
| 数据构建 | `build_panel.py` → `data/idx_*.csv` + `data/manifest.csv` | 17 个干净行业指数（2009/2011/2014-15 交错起点，全截面 2019-08 后齐） |
| 引擎 | `btlib.py` | 指标(CAGR/回撤/Sharpe/Calmar/ATR) + **防前视 `apply_signal` shift(1)** |
| 锚定 | `_xcheck_rotation.py` | 主 agent 独立实现，锚 champion 引擎一致性 |
| 研究① 单标的 | `bt1_single_asset.py` + `findings_bt1.md` + `bt1_results_long*.csv` | MA过滤>移动止损；单标的 SMA50 最优；移动止损最差 |
| 研究② 轮动 | `bt2_rotation.py` + `findings_bt2.md` + `out_bt2.txt` | 慢MA边际；**分散是主杠杆(-15.5pts)**；固定%止损无效 |
| 研究③ 冠军 | `champion.py` + `findings_champion.md` + `out_champion.txt` | **vol-scaling 腰斩回撤**；MA长度二阶；成本后赢家不变 |
| 文献 | `findings_literature.md` | 已 WebFetch/pdftotext 核原文（Barroso/湘财/银河/Daniel-Moskowitz…） |
| 审计综合 | `findings_bt3_synthesis.md` | **（BT-3 独立审计中，待回填）** |

## 收敛结论（四路一致，待 BT-3 终审）
回撤压制层级：**分散(top1→top3) ≈ 去相关(抗拥挤) > 波动率缩放 >> 趋势止损 MA 长度 > 移动/固定止损(有害)**。

- 你问"趋势止损点设多长"——数据答：**MA 长度是二阶问题(单用各长度 Calmar 0.08–0.10 几乎不变)**。
- **一阶杠杆是仓位层**：① 先做对分散(top-3 等权+现金规则)；② **去相关/抗拥挤**(top-6 里挑互相关最低的 3 个，回撤 -65.6%→-50.1% 且收益不降，机制：book内相关 0.64→0.47)；③ 波动率缩放(锚定组合波动 12–15%，危机前自动减仓，回撤再到 -31%)。
- **全研究最优**：低相关 top3 + vol@15 → Calmar 0.22 / 回撤 -31.4% / Sharpe 0.51。
- 趋势止损 MA：有了 vol-scaling 用**慢线 SMA200~250**（单用价值小，可叠加）。
- **不要**用固定%/ATR 移动止损（A 股全行业同跌+假突破反复 → 普遍有害，仅纯急跌样本偶有效，不稳健）。
- 诚实 caveat：最优**具体参数跨样本漂移**（长史偏好快、近年偏好慢），可外推的是**族级结论**；样本~10-16 年、单一政策市、17 指数代理 38 ETF。

## 候选后续
- 拥挤度叠加在 **38 ETF 细粒度 universe** 上复测（聚集更重，效果可能更大）。
- 把"分散+去相关+vol-scaling"做进可部署 skill（需引入持仓状态机；wiki 通用版 vs private 个人版分离）。
