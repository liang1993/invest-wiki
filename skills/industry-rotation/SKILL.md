---
name: industry-rotation
description: "看申万行业近期涨跌/波动的图表与读数——只观察、不算动量、不给交易信号。用户问'近期行业波动/最近哪些行业涨了跌了/行业强弱/申万行业最近表现/看下行业轮动图'时：刷新本地缓存（增量秒级）→ 渲染自包含 HTML 折线图（申万一级31·二级123，可切换/搜索/前N强后N弱）→ 配 1/5/20 日领涨领跌读数。与 etf-momentum 分工：那个是 ETF 动量计算器、出买卖与再平衡信号；本 skill 只看行业指数涨跌与图，要动量打分/选ETF/交易信号请走 etf-momentum。只读展示、不写 wiki，数据生产在 scheduled-ingest。"
version: 1.0.0
author: Invest Wiki Team
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: ['a-share', 'industry-rotation', 'chart', 'visualization', 'shenwan']
    category: finance-invest
    related_skills: ['scheduled-ingest', 'periodic-review', 'a-share-market']
---

# 申万行业轮动展示 Skill

用户问"近期行业波动 / 哪些行业强 / 看下行业轮动图"→ **刷新 + 出图 + 读数**，三步，任何会话都能跑，无需记 URL。

## When to Use

- "近期行业波动怎么样" / "最近哪些行业强、哪些弱" / "看下行业轮动图" / "申万行业最近表现"
- 想看**归一化累计收益**的行业折线图（一级 31 / 二级 123 可切换、可搜索、前 N 强 / 后 N 弱）
- **不适用（易混淆，重点）**：要 ETF **动量打分 / 买卖信号 / 选哪个 ETF / 再平衡** → 走 `etf-momentum`（本 skill 只看行业指数涨跌与图，**不给交易信号**）；要把结论写进 wiki → 走 `periodic-review` / `value-invest`；要改采集/调度逻辑 → 走 `scheduled-ingest`

## 数据从哪来（本 skill 只消费不生产）

| 文件 | 说明 |
|---|---|
| `~/.invest-charts/sw_close.csv` | 缓存，long-format：`date,code,name,level,parent,close` |
| `~/.invest-charts/sw_industry_rotation.html` | 自包含折线图（数据已 inline，离线可开） |
| `~/.invest-charts/refresh.log` | 每次刷新末尾有健康行 |

生产者是 `scheduled-ingest/scripts/`，**launchd 每工作日 15:15 自动刷新**——所以多数时候缓存已是最新，本 skill 只需渲染。

## 三步 Runbook

**1. 保新鲜**（增量，hist 未出新时 ~4-11s；跑不跑都安全，重跑很便宜）：
```
sh skills/scheduled-ingest/scripts/refresh_rotation.sh
```

**2. 展示图**：用 `SendUserFile` 渲染，`display=render`（自包含，离线）：
```
~/.invest-charts/sw_industry_rotation.html
```

**3. 配读数**（把 1/5/20 日领涨领跌翻成一句话给用户；二级加 `--level 2`）：
```
python3 skills/scheduled-ingest/scripts/summarize_rotation.py --level 1
```

## 健康校验（每次必看，别只看日期）

**"数据日期新" ≠ "数据完整"**（2026-07-20/21 二级全灭教训）。刷新后看 `refresh.log` 末尾必须是 **一级 31 + 二级 123**：

| 现象 | 处置 |
|---|---|
| 二级掉到个位数 / 0 | realtime 半失败留洞。跑 `python3 skills/scheduled-ingest/scripts/fetch_sw_indices.py`（内置周期性强制全量，~3-6min）补齐再出图 |
| 一级 < 31 | akshare 可达性问题，重试或检查网络（本机东财不可达，走腾讯/新浪/申万宏源） |

## 报给用户

图（render）+ 一句话读数（谁领涨谁领跌，1/5/20 日）+ asof 日期 + 健康数（31/123）。

**极端读数先核对**：单一行业 20 日 ±25% 这类，先 `grep ',<行业>,1,' ~/.invest-charts/sw_close.csv` 看是平滑轨迹还是单日跳变，确认非数据毛刺再报（2026-07-27 建筑材料 -25% 经核实为真实"冲高—回落"）。
