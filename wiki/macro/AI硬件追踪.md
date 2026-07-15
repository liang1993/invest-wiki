---
tags: [AI硬件, 算力, 半导体, HBM, 电力, 宏观, 信号追踪]
updated: 2026-07-08
---

# AI 硬件追踪

> 追踪 AI 硬件全栈（算力·存储·网络·电力）的周期位置与市场边际变量。**用途**：主题/风险雷达（非选股）——focus 无直接 AI 硬件标的，本页判断 ① AI 硬件周期位置 ② risk-on/off 震源（如 2026-06-23 存储崩 → 港股科技 + 紫金被带）③ 间接传导（铜的电力需求 / 港股科技 β / 阿里 capex 强度）。
> 前身为「半导体周期追踪」，2026-06-23 重构为全栈视角并刷新数据。

## 母变量：从"训练/算力稀缺"切到"推理主导 (inference-led regime)"

2026 年 AI 硬件最根本的边际切换：**需求重心从"训练"转向"推理"**。

- 推理已占 AI 算力需求约 **2/3**（2023 ~1/3 / 2025 ~1/2）[观测 Deloitte 2026 预测]
- 推理/思考模型（test-time compute / 长思考）按"思考长度"换性能：test-time scaling 用 **>100×** 于简单推理的算力；算力总需求 **~4-5×/年** 增长，远超芯片效率年提升 [观测 Deloitte]
- 采购标准随之从"峰值吞吐/带宽"转向 **"每 token 成本·功耗·散热·利用率·TCO"**（Evercore "inference-led regime"）——重排了下面所有变量的权重，是边际之锚
- 效率同步狂奔：Alphabet 2025 把 Gemini 推理服务成本降 **78%** [观测 Futurum]——单位算力变便宜，但总需求增长更快（杰文斯悖论）

> **为什么是"母变量"**：推理主导 → 利好专用硅（ASIC，变量②）、把瓶颈推向电力（变量①）、改变什么硬件能赢（每 token 成本/功耗优先）。下面六个变量都从这里派生。

## 六大边际变量仪表盘

| # | 边际变量 | 旧共识 → 边际正在变的 | 当前读数（2026-07）| 信号/受益方 |
|---|---|---|---|---|
| 1 | **电力/能源**（瓶颈缺芯→缺电）| GPU 是瓶颈 → **电网/电力**是硬顶 | 全球 DC 用电 ~1,000TWh(26)；US 49GW 发电缺口(28,提交 PJM 的分析)；变压器交期 2-4 年/并网 7 年+ | 🔴 趋紧 / 燃机·核电·SMR·**铜与电力设备** |
| 2 | **算力供给结构**（ASIC 抢 GPU）| NVIDIA 通吃 → 定制硅结构性抢份额 | ASIC 44.6% vs GPU 16.1% CAGR(24-33)；NVIDIA 推理份额或降 20-30%(28) | ⚠️ 份额转移 / Broadcom·云厂自研 |
| 3 | **Capex 可持续性/ROI** | Capex 一路向上 → 变现/折旧受审视 | 5 大厂 2026 ~$725B（上修 +64%YoY）；OpenAI ARR≈capex 3%；纯 AI 厂 <$35B | ⚠️ 估值悬顶 / **6-23 杀跌部分即此** |
| 4 | **存储/HBM** | 普涨 → HBM4 量产+DRAM 挤出；股价 vs 合约价背离 | 合约价续涨无见顶（HBM 2027 翻倍级）；存储双雄 7/2 崩 −9/−15% 但 YTD +116/+207%=仓位回吐；三星 Q2 OP 创纪录超 NVIDIA | ⚠️ 高位/背离监控 |
| 5 | **网络/光互联** | 算力为王 → 集群规模化后网络成 DC 内瓶颈 | CPO/硅光 scale-up；NVIDIA vs Broadcom；1.6T→3.2T | 🟢 新兴受益段 |
| 6 | **AI ROI 证伪**（需求尾部）| AI 需求无限 → 企业级 ROI 若不及→砍预算 | 应用付费渗透待观察；效率突破（DeepSeek 式）可杀需求 | ⚠️ 尾部风险 |

### 变量① 电力：AI 时代真正的硬约束

- 全球数据中心用电 **~1,000 TWh（2026）**，约 2023 的 2 倍 [观测 tech-insider 引 Gartner]；US 数据中心 41GW 现负荷、15-20%/年增，**300 TWh by 2028**
- **供给跟不上**：提交 PJM 理事会的分析警示 US **49GW 发电缺口 by 2028**、Morgan Stanley 测 126GW 全球 DC 需求增长；**变压器交期 2-4 年、并网排队 7 年+**（即便有钱也变不出电网）[观测 tech-insider 引 PJM/Morgan Stanley/EPRI]
- 微软 **$80B Azure 订单因缺电无法交付** [观测 Futurum]——需求被电力卡住的硬证据
- 应对：迁往电力富集区（微软 UAE $15.2B / Meta 路州 $10B）、自备电 BYOP、SMR/核电（≥5GW DC by 2030）/氢燃料 [观测 enkiai]
- **对持仓**：电力/电气化是**铜**的结构性需求（紫金长期逻辑之一）；利好电力设备（汇川边际沾边）

### 变量② 算力供给结构：ASIC 在边际抢 GPU

- 定制 ASIC（Google TPU/AWS Trainium/微软 Maia/Meta MTIA/OpenAI·Anthropic Titan）增速 **44.6% CAGR（2024-33）** vs 商用 GPU **16.1% CAGR**（Bloomberg Intelligence）——定制硅是结构性快变量 [观测 Introl]
- NVIDIA 仍统治：SemiAnalysis 称 **>90%** 当前加速器市场（训练口径）；另有口径按**含 ASIC 的总 DC 加速器收入**计约 **70-75%**——差在分母是否计入云厂自研 ASIC 及训练/推理口径（两口径并存）。但 **推理份额或降至 20-30% by 2028**（New Street）——推理主导利好专用硅
- ASIC 收入 ~$18B(24)→~$165B(33)；总加速器 TAM **$604B by 2033** [观测 Bloomberg]
- **设计方**：Broadcom 是云厂自研 ASIC 的主力设计伙伴（TPU/MTIA/Maia/Titan）——ASIC 浪潮的"卖铲人"

### 变量③ Capex 可持续性/ROI：估值悬顶

- 5 大厂（微软/Alphabet/Amazon/Meta/Oracle）2026 capex：Futurum 口径 **$660-690B**（较 2025 ~$380B 近翻倍）[观测 Futurum]；**2026-07 各厂上修后分析师聚合升至 ~$725B（+64% YoY vs 2025 ~$443B）** [观测 AL Capital]——微软领升 ~$190B、Alphabet $180-190B、Meta $125-145B、Amazon $200B、Oracle ~$50B
- 一致口径：**供给约束而非需求约束**（都说算力不够卖）
- **ROI gap（空头核心论点）**：OpenAI 2025 ARR ~$20B ≈ 2026 capex 总额的 **3%**；纯 AI 厂商（OpenAI/Anthropic/Mistral/Cohere/Perplexity）合计 2026 收入 **<$35B**——基建远跑在收入前面 [观测 Futurum]
- 折旧争议：AI 芯片折旧年限被拉长以平滑当期利润（若芯片更快过时 → 减值风险）[定性，未取一手数]
- **融资结构边际（2026-07 新增）**：capex 上修伴随大额债务融资占比上升，市场对高杠杆 + 客户集中（如 Oracle × OpenAI）玩家的偿付/ROI 敏感度升温 [定性，未取一手 CDS 数据]
- **自洽测试**：推理收入增速 > GPU 折旧 → 可持续；否则按折旧表回调——**2026-06-23 杀跌部分即此审视**
- **中国对照**：阿里 ¥380B（~$53B）/3 年 AI+云（管理层称将加码）、字节 ¥160B（~$23B，~$13B 给 AI 芯片）、腾讯偏谨慎（Q4'25 capex 环比降）；中国 AI 投资 2025 ~$125B [观测 Futurum]——**阿里（focus）是中国 AI capex 主力，资本开支强度是其估值变量**

### 变量④ 存储/HBM：结构紧张 vs 股价波动背离（2026-07 刷新）

- HBM4 量产：12-high **>$600**、三星与 SK 价格平价 [观测 TrendForce]；供给紧、滞后需求，DRAM 因产能转 HBM 而挤出涨价
- 份额：**SK 海力士拿下 NVIDIA Vera Rubin 平台 HBM4 约 2/3（份额近 70%）**、三星 HBM 份额 **2026 预计 >30%** [观测 TrendForce]
- **合约价仍上行、无见顶迹象**：DRAM 行业营收 1Q26 +81% QoQ（合约价大涨驱动）[观测 TrendForce 20260601 ✅]；**Jefferies 估 DRAM/NAND Q3 +40-50% QoQ、Q4 +30-40%、2027 +40-45% YoY，2028 前无缓解** [观测 ghacks/Jefferies 2026-06-29 ✅]；HBM 2026 上行、**2027 翻倍级（multiples higher）**、占三大厂 DRAM wafer input 由 2025 末 ~18%→2026 末 ~22%→2027 末 ~30%，对普通 DRAM 挤出加剧
- **存储厂创纪录利润印证周期未见顶**：三星 Q2'26 营业利润 **89.4 万亿₩（~$58.5B）创纪录、季度营业利润首超 NVIDIA 成全球最赚钱公司** [观测 KED 2026-07-07 WebFetch ✅]；美光 fiscal Q3（6/24）**确认 $22B 长约锁定**、三星/SK 类似，毛利率创纪录、供不应求延续多年 [观测 ghacks/Jefferies ✅；营收/毛利具体值因一手 IR 未取到 + 二手冲突不采]
- **关键背离进一步验证（本页核心监控项）**：存储双雄 7/2 单日暴跌 **三星 −9.1% / SK 海力士 −14.6%** [自算 yfinance，与 CNBC −9.06%/−14.57% 交叉一致]，自 6 月中峰值回撤 **三星 −23%（峰 6/18）/ SK 海力士 −29%（峰 6/22）** 至 7/8——但 YTD 仍 **+116% / +207%**（翻倍级）且**合约价未跌**：本轮是**仓位/获利了结、非合约价拐点**（与近日 KOSPI / 港股科技分化同源，均 AI 硬件拥挤交易回吐）。**硬信号仍未触发**——须见 TrendForce 月报合约价转跌方为周期见顶

### 变量⑤ 网络/光互联：scale-up 新战场

- 集群规模化后，**网络成数据中心内瓶颈**；CPO（co-packaged optics，共封装光）把互联功耗大幅压低，是 scale-up 关键 [观测·搜索]
- NVIDIA（Spectrum-X/Quantum-X 硅光交换）vs Broadcom（以太网交换 + CPO）；NVIDIA/AMD/Broadcom 结盟标准化光 scale-up；路线 1.6T → 3.2T 光模块
- 受益段：光模块/CPO/交换 ASIC（新兴，弹性大但波动大）

### 变量⑥ AI ROI 证伪：需求侧尾部风险

- 把上面所有变量"反过来"的尾部：若**企业级 AI ROI 不及预期** → 削减预算 → 杀需求逻辑（原半导体页"中概率高冲击"事件，在 capex 翻倍后权重上升）
- 触发形态：企业付费渗透停滞 / 出现"DeepSeek 式效率突破"证明不需要这么多算力 / hyperscaler 财报下调 capex 指引
- 与变量③互补：③看"钱花得起否"，⑥看"花了有没有回报"
- **低概率高冲击尾部**：台海 → TSMC 停产（全球芯片链断裂）、主要国家限制 AI 训练规模（需求骤降）

## 周期位置与见顶信号（原 5 信号框架，作为"算力供需"维度保留）

> 这套 5 信号是本页前身的核心，继续用于回答"在周期哪个位置"。映射：信号 2→变量④、信号 3→变量③、信号 1/4/5→变量②供给侧。**数据刷新至 2026-07-08**。

**当前阶段：上行中后期**（AI 结构性需求拉长上行期）；最可能转折时点 **2026Q4-2027Q2**（维持）。

| 信号 | 当前状态（2026-06）| 读数 |
|------|---------|------|
| 1.GPU 交货周期 | ⚠️ 微松 | B200/B300 交期较 2025Q4 缩短；积压仍高 |
| 2.存储价格（HBM/DRAM）| ⚠️ 高位续涨 | 合约价未转跌：DRAM Q3 估 +40-50% QoQ（降速）、HBM 2027 翻倍级；**7/2 存储股崩 −9/−15% 属仓位非合约价**（YTD 仍 +116/+207%）|
| 3.云 Capex 指引 | 🟢 安全 | 2026 capex 上修至 ~$725B 仍加速、供给约束；**待看变现**（变量③）|
| 4.TSMC 利用率 | 🟢 走强 | 5 月营收 +30.1%（最新）；6 月营收约 7/10、Q2 财报 7/16；CoWoS 满配 |
| 5.NVIDIA 指引 | 🟢 安全 | Q1FY27 DC $75.2B +92% YoY；财报 8 月 |

**综合预警：🟡 黄色（关注，尚不需行动）**。**2026-07 刷新：基本面更强**——合约价续涨无见顶、存储厂创纪录利润（三星 Q2 OP 超 NVIDIA）、HBM 售罄至 2027+，信号 3/4/5 仍 🟢、周期未见顶。**边际风险从"基本面"移向"仓位/估值"**：存储双雄 7 月自峰值 −23%/−29% 属拥挤交易回吐（合约价未跌，"股价 vs 合约价"背离监控项进一步验证），叠加变量③ capex 上修至 ~$725B + 债务融资关注令估值悬顶更高。预测转折 2026Q4-2027Q2 维持。

## 周期转折后的行动预案

| 预警级别 | 条件 | 行动 |
|----------|------|------|
| 🟢 绿色 | 信号全绿 | 维持，不追高 |
| 🟡 黄色（当前）| 1-2 信号黄 / ROI 审视升温 | 不加仓 AI 硬件链，警惕 risk-off 传导到港股科技 |
| 🟠 橙色 | 3 信号黄或 1 红 / capex 指引下调 | 风险偏好转向，降低高 β 敞口 |
| 🔴 红色 | 云 Capex 砍单 / NVIDIA miss / HBM 合约价转跌 | 全面 risk-off，AI 链系统性下杀 |

## 与持仓的关联

| 标的 | 关联 | 机制 |
|---|---|---|
| **阿里巴巴**（focus）| 直接（需求侧）| 中国 AI capex 主力（¥380B/3yr），资本开支强度 + AI 云增速是估值变量 |
| **紫金矿业**（focus）| 间接（电力链）| AI 数据中心/电气化是铜的结构性需求，长期价托底 |
| **腾讯/美团等港股科技**（focus）| 间接（风险 β）| AI 硬件是全球风险偏好震源，存储/AI 杀跌当日港股科技高 β 跟跌（如 6-23）|
| 汇川技术（focus）| 弱间接 | 工控/电力电子边际沾电力·算力基建，非纯 AI 硬件 |

> **结论**：focus 无直接 AI 硬件标的，本页是**主题/风险雷达**——主要价值是预判 risk-on/off 震源 + 铜的电力需求 + 阿里 capex 强度，不是直接选股。

## 复盘节奏

- **每月**：存储合约价（TrendForce/变量④）、电力进展（变量①）
- **每财报季（1/4/7/10 月）**：云 Capex 指引（变量③）、ASIC 份额（变量②）、NVIDIA/TSMC（信号 4/5）
- **触发加密**：任一信号转橙 → 每两周；capex 指引下调或 HBM 合约价转跌 → 每周

## 信息来源

- 推理需求：[Deloitte TMT 2026 Predictions](https://www.deloitte.com/us/en/insights/industry/technology/technology-media-and-telecom-predictions/2026/compute-power-ai.html)（WebFetch ✅）
- 电力：[tech-insider AI 数据中心 1000TWh](https://tech-insider.org/ai-data-center-power-crisis-2026/) / [enkiai 电网约束](https://enkiai.com/data-center/ai-data-center-grid-strain-power-halts-growth-in-2026/)（fetch.py ✅，引 PJM/Morgan Stanley/EPRI）
- ASIC：[Introl 定制硅拐点](https://introl.com/blog/custom-silicon-inflection-2026-hyperscaler-asics-nvidia-gpu)（WebFetch ✅，引 Bloomberg Intelligence/SemiAnalysis/New Street）
- Capex：[Futurum AI Capex 2026 $690B](https://futurumgroup.com/insights/ai-capex-2026-the-690b-infrastructure-sprint/)（fetch.py ✅）
- HBM：[TrendForce SK 海力士 HBM4](https://www.trendforce.com/news/2026/01/28/news-sk-hynix-reportedly-to-supply-about-two-thirds-of-nvidia-hbm4-samsung-targets-early-delivery/)（WebFetch ✅）
- HBM/DRAM 合约价 2026-07 展望：[TrendForce HBM 2027 翻倍级](https://www.trendforce.com/presscenter/news/20260602-13074.html)（WebFetch ✅，2026 上行 / 2027 multiples / 无见顶）；DRAM 行业 1Q26 +81% QoQ 出自 [TrendForce 20260601](https://www.trendforce.com/presscenter/news/20260601-13070.html)
- 三星 Q2'26 创纪录 OP 超 NVIDIA：[KED Global](https://www.kedglobal.com/earnings/newsView/ked202607070001)（WebFetch ✅，89.4 万亿₩ / $58.5B）
- Capex 上修 ~$725B：[AL Capital AI Infrastructure](https://alcapitaladvisory.com/research/intelligence/ai-infrastructure.html)（WebFetch ✅，各厂上修分项，微软领升）
- Jefferies 存储涨价展望：[ghacks 转 Jefferies](https://www.ghacks.net/2026/06/29/memory-prices-expected-to-rise-up-to-50-in-q3-with-no-relief-until-2028-jefferies-predicts/)（WebFetch ✅，Q3 +40-50% / Q4 +30-40% / 2027 +40-45% YoY / 2028 前无缓解；美光 $22B 长约）
- 存储双雄 7/2 暴跌 + YTD：[自算 yfinance] 005930.KS / 000660.KS（三星 7/2 −9.1% / SK −14.6%、YTD@7/8 +116% / +207%，与 [CNBC 2026-07-02](https://www.cnbc.com/2026/07/02/samsung-sk-hynix-shares-slide-kospi-tech-selloff-nasdaq.html) −9.06%/−14.57% 交叉一致；CNBC 正文 403 未直取，数字以 yfinance 为准）
- 光网络：WebSearch（Broadcom/IDTechEx/SDxCentral，定性）
- 个股关联数字（DRAM Q2 +58-63% / TSMC 5 月 +30.1% / NVDA DC $75.2B / 6-23 存储跌幅）：见 [journal 2026-06-18](../journal/2026-06-18.md) / [2026-06-23](../journal/2026-06-23.md) 已校

## 更新记录

- **2026-07-08 刷新（变量④存储为主）**：合约价续涨无见顶（TrendForce：DRAM Q3 +40-50% QoQ、HBM 2027 翻倍级）+ 存储厂创纪录利润（三星 Q2 OP 89.4 万亿₩/$58.5B 首超 NVIDIA；美光 Q3 毛利创纪录、HBM 售罄）→ 周期未见顶；存储双雄 7/2 暴跌（三星 −9.1%/SK 海力士 −14.6% [自算 yfinance]）、自峰值 −23%/−29% 但 YTD +116%/+207% = **仓位回吐非合约价拐点**，"股价 vs 合约价"背离监控项进一步验证（与近日 KOSPI/港股科技分化同源）。变量③ capex 上修至 ~$725B（微软领升）+ [定性] 债务融资关注；信号 2/4 + 综合预警刷新。高时效红线走 L1/L2（清单 7 组）/L3，逐条 WebFetch（TrendForce/KED/AL Capital/Jefferies-ghacks ✅；CNBC 403 → 股价改 [自算] yfinance 交叉验证；Micron 营收/毛利一手 IR socket 断 + 二手冲突 → 具体值不采，改用已核 $22B 长约）。**执行**：claude-code/opus-4.8
- **2026-06-23 重构**：由「半导体周期追踪」（5 信号窄框架，updated 2026-04-18）重构为「AI 硬件追踪」全栈视角——新增"推理主导母变量 + 六大边际变量仪表盘"（电力/ASIC/Capex-ROI/HBM/光网络/ROI 证伪），原 5 信号保留为"周期位置"维度并刷新到 6 月。数据走 L1/L2/L3，逐源 WebFetch/fetch.py 核（Deloitte/tech-insider/Introl/Futurum/TrendForce）；Goldman/DCF/Tom's 因 403/受限改用一手可达替代源。git mv 保留历史，9 处入链路径已修。**执行**：claude-code/opus-4.8
- 2026-04-18 / 2026-04-14：见前身「半导体周期追踪」（5 信号框架建立，综合预警 🟡）
