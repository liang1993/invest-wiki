# 懂车帝销量数据 API 工具文档

> 字节系汽车垂直平台懂车帝（dongchedi.com）的销量数据 API 调用规范。**LLM 扩展挖掘新维度前先读本文档**，避免重复探测。

## 一、Endpoint 与基础调用

```
GET https://www.dongchedi.com/motor/pc/car/rank_data
```

**关键事实**：
- 无需 msToken / Cookie / 浏览器自动化（虽然页面有 msToken 参数，但服务端不校验）
- 返回 JSON 直出，含 `paging.has_more` 字段控制翻页
- 单次 `count` 上限 **100**（实测传 200/500/1000 都仅返回 100）
- 全榜约 638 款车型 → 7 次 API 调用拿全，单次约 0.5s

**Python 调用样例**：

```python
import json, urllib.request, urllib.parse

def fetch(month="", sale_type=11, energy="", offset=0, count=100):
    params = {
        "aid": "1839", "app_name": "auto_web_pc",
        "count": str(count), "offset": str(offset), "month": month,
        "new_energy_type": energy, "rank_data_type": str(sale_type),
        "brand_id": "", "price": "", "manufacturer": "",
    }
    url = "https://www.dongchedi.com/motor/pc/car/rank_data?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.dongchedi.com/sales",
    })
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
```

**已封装脚本**：`skills/scheduled-ingest/scripts/fetch_dongchedi.py`

## 二、参数空间

### `rank_data_type`（必传，控制榜单类型）

实测 1-29，**已验证有效**：

| type | 含义 | Top 1 样例（2026-04）| 用途 |
|---|---|---|---|
| **2** | **批发销量榜**（含出口）| Model Y 52,143 | ≈ 盖世口径，与车企财报销量对齐 |
| **11** | **零售销量榜**（终端上险）| 星愿 34,727 | 国内市场真实销售 |
| 1 | 历史累计销量（生涯总销量榜）| 奥迪A6L 1,202,040 | 长期销量冠军 |
| 3 | 类同 type 1 累计榜 | SU7 1,440,117 | 累计销量另一口径 |
| 4 | 微型车细分（？）| 五菱宏光MINIEV 121 | 待验证 |
| 5 | 沃尔沃车系（？） | 沃尔沃XC60 100 | 待验证 |
| 6 | 跑车 / 高端（？）| Taycan 84 | 待验证 |
| 7 | 极高端 / 进口（？）| Model S 2 | 待验证 |
| 9 | 超豪华（？）| 库里南 16 | 待验证 |
| 10 | 国产微型车（？）| 奇瑞QQ冰淇淋 50 | 待验证 |
| 12 | 未启用 | None | — |
| 13-29 | **重复 SU7 数据**，疑似未启用 | SU7 1,440,117 | 不要用 |

**主用**：`type=11`（零售，默认）+ `type=2`（批发）。其余 type 待验证语义后再用。

### `new_energy_type`（可选，能源类型筛选）

| 取值 | 含义 |
|---|---|
| `""` 或 `1` | 全口径（含 ICE + NEV）|
| `2` | PHEV 插混 |
| `3` | REEV 增程 |
| 其他值 | 服务端忽略，返回全口径 |

### `month`（可选，历史月份）

- 格式：`YYYYMM`，如 `202604`
- 留空 = 最新可用月
- ⚠️ **fallback 行为**：传未来月份（如当前 5/21 传 `202605`）**不报错**，返回最新可用月数据。**必须 sanity check** 避免误用
- 实测覆盖至少 2025-04 至今（13+ 月历史可回溯）

### `offset` / `count`（翻页）

- `count` 单次最多 100
- `offset` 从 0 开始
- 终止条件：`paging.has_more = false` 或 返回 `< count` 条

### 其他参数（已知但未深挖）

| 参数 | 用途 | 状态 |
|---|---|---|
| `brand_id` | 按品牌 ID 筛选 | 未验证 ID 空间 |
| `manufacturer` | 按厂商筛选 | 未验证取值 |
| `price` | 按价格段筛选 | 未验证取值（"10-15万" 这种字符串？数字？）|
| `city_name` | 城市榜 | 默认值 "北京"，可改 |

## 三、响应字段（每条车型 25 个字段）

按用途分组：

### 核心销量字段（已用）

| 字段 | 类型 | 含义 |
|---|---|---|
| `series_id` | int | 车型唯一 ID（跨月稳定，用于 join 算同比）|
| `series_name` | str | 车型中文名（如 "小米SU7"）|
| `count` | int | 当月销量（辆）|
| `rank` | int | 当月排名 |
| `last_rank` | int | **上月排名**（直接的环比信号）|
| `brand_name` | str | 品牌名（如 "吉利银河" / "比亚迪" / "理想汽车"）|
| `sub_brand_name` | str | 子品牌（如 "吉利银河" 的 sub 也是 "吉利银河"）|
| `brand_id` / `sub_brand_id` | int | 对应 ID |

### 价格字段（已用）

| 字段 | 类型 | 含义 |
|---|---|---|
| `min_price` / `max_price` | float | 价格区间下/上限（万元，数值）|
| `price` | str | 价格区间文字（如 "21.99-30.39万"）|
| `dealer_price` | str | 经销商报价（同 `price` 通常）|
| `has_dealer_price` | bool | 是否有经销商真实报价 |
| `descender_price` | int | **当月降价幅度**（元，0 表示无降价）|

### 用户口碑字段（**未用，价值高**）

| 字段 | 类型 | 含义 |
|---|---|---|
| `score` | float | **懂车分**（用户综合评分，0-5 分制；销量榜里很多为 0，说明未评分车型）|
| `car_review_count` | int | **用户评论数**（活跃度代理）|
| `series_pic_count` | int | 用户上传图片数（关注热度代理）|
| `review_tag_list` | list/null | 评价标签（可能含正负面词，未深挖）|

### 产品矩阵字段（**未用，价值中**）

| 字段 | 类型 | 含义 |
|---|---|---|
| `online_car_ids` | list[int] | 在售 SKU ID 列表（数量 = 当前在售 SKU 数）|
| `offline_car_ids` | list[int] | 停售 SKU ID 列表 |
| `show_trend` | bool | 懂车帝是否给该车型显示趋势图（可能与人气阈值有关）|

### 其他

| 字段 | 类型 | 含义 |
|---|---|---|
| `image` | str | 车型主图 URL |
| `outter_detail_type` | int | 内部分类，含义不明 |
| `text` | str | 营销文案，通常为空 |
| `part_id` | str | 内部 ID，含义不明 |

## 四、当前场景调用样例（车企销量 + 单车型 Top）

> 这是用户当前重点需求：跟踪 **各车企月度销量变化 + 单车型 Top 变化**，支撑车企市占率 + 主力车型趋势 → 前瞻经营状态判断。

### 场景 A：当月车企销量横评（关注列表）

```bash
# 默认零售口径 + 全部能源 + 关注品牌矩阵
python3 skills/scheduled-ingest/scripts/fetch_dongchedi.py --month 202604 --yoy
```

输出关注品牌的：每个品牌入榜 SKU 数 / 合计销量 / 品牌同比 / 每款车排名变化。

**判断车企状态的信号**：
- **品牌合计同比 < 0** + 多款车型同比 ≤ -30% → 经营恶化（如小鹏 4 月 -20.2%）
- **品牌合计同比 +50%+** + 多款车型 ↑20+ 名 → 高增长期（如零跑 +109.2%）
- **品牌合计同比 ≈ 0 但分车型差异极大** → 产品矩阵在替换（如理想 +0.4%：i6 替代 L 系列）

### 场景 B：单车型 Top 变化（含批发 vs 零售对比）

```bash
# 零售 Top 30
python3 skills/scheduled-ingest/scripts/fetch_dongchedi.py --month 202604 --yoy --top 30

# 批发 Top 30（对比同月批发口径）
python3 skills/scheduled-ingest/scripts/fetch_dongchedi.py --month 202604 --saletype wholesale --top 30
```

**判断主力车型的信号**：
- `rank` 变化 + `last_rank` 字段 → 月对月排名 trajectory
- `count` 同比（自计算） → 真实增长 / 衰退
- 批发 vs 零售 gap → 渠道库存压力（gap > 50% 警告）

### 场景 C：单车型时序跟踪（手动构造）

```python
from scripts.fetch_dongchedi import fetch_all

# 拉过去 12 个月某车型数据
months = ["202505", "202506", ..., "202604"]
trajectory = []
for m in months:
    all_rows = fetch_all(month=m, sale_type=11)
    for r in all_rows:
        if r["series_id"] == TARGET_SERIES_ID:
            trajectory.append({"month": m, "count": r["count"], "rank": r["rank"]})
            break
```

未来若高频用，应在 `fetch_dongchedi.py` 加 `--trajectory <series_id>` 参数。

## 五、局限与陷阱（必读）

### 0. 覆盖范围：**狭义乘用车口径**，不含商用车/皮卡

⚠️ **这是最容易被忽略的边界**。懂车帝 `/sales` 销量榜采用**乘联会狭义乘用车口径**——与国标 GB/T 3730.1-2022 + 中汽协 + 乘联会三方一致。

**包含什么**：
- 轿车（基本型乘用车）/ SUV / MPV
- 含 ICE / BEV / PHEV / REEV 各能源类型

**不包含什么（销量榜）**：
- ❌ **皮卡**（按国标归"多用途货车"N1 类）
- ❌ **微面 / 轻客 / 轻卡 / 中卡 / 重卡**
- ❌ **新能源专用车 / 客车 / 大巴**

**懂车帝内部 series_type 完整分类**（从 /auto/library filter config 拿到）：

| series_type | 含义 | /sales 是否含 |
|---|---|---|
| 0 | 轿车 | ✅ |
| 1 | SUV | ✅ |
| 2 | MPV | ✅ |
| 4 | 跑车 | ⚠️ 部分 |
| 6 | 轻客 | ❌ |
| 7 | 微面 | ❌ |
| 8 | 微卡 | ❌ |
| 13 | 轻卡 | ❌ |
| **3** | **皮卡** | ❌（**关键 trap**——见下方）|

#### 皮卡数据深度调研结论（2026-05-21 三轮实测）

懂车帝**有皮卡车型库**但**销量数据 server-side 主动脱敏**：

**第一轮：urllib 直调 API**

| 探测层 | 结果 |
|---|---|
| `/sales` rank_data API（任何 series_type 参数无效）| ❌ 638 款全榜不含任一皮卡 |
| `/auto/library/x-3-x-...`（series_type=3 车型库）| ✅ **30 款皮卡产品目录 + series_id**——长城炮 3332 / 风骏 5 = 1503 / 山海炮 6098 / 江铃大道 6366 / D-MAX 1297 等 |
| `/auto/series/{series_id}` (rankData.sale 字段)| ⚠️ 结构存在但 `is_show: false` + `month_sell_count: 0` + `series_name=null` |

**第二轮：Playwright PC + Mobile 双端模拟**（彻底验证非"绕过"问题）

| 探测路径 | 结果 |
|---|---|
| PC web `/auto/series/3332` 拦截全 XHR（41 个 API）| ❌ 无销量数据 |
| **Mobile web `m.dongchedi.com/auto/series/3332`** | ❌ 同样隐藏 |
| `/auto/series/{id}/sales` / `/rank` / `/ranking` | ❌ 全部 **404** |
| 滚动 4 次触发懒加载 | ❌ 无新销量 XHR |
| `/motor/searchpage/launcher` (唯一含"sale_count" 关键字)| ⚠️ 那是"搜索热榜"文章标题不是数据 |

**核心证据**：响应里数据**就是空的**（不是前端不展示）：

```json
// 服务端真实返回 - 主动脱敏
{"rankData":{"sale":{"is_show":false,
  "list":[{"series_id":3332,"series_name":null,"count":null,"month_sell_count":0}]}}}
```

**结论**：懂车帝拿得到皮卡**产品维度**（车型名 / series_id / 价格 / 懂车分 / 评论数等），但**销量数据 server-side 拒绝暴露**——这是产品决策（皮卡不在乘联会狭义乘用车口径），不是技术 gap。任何客户端（urllib / Playwright / Chrome 真实用户 / Mobile / 推测 App）都拿不到，除非懂车帝改产品策略。

**节省时间提示**：未来如有人想"绕过"懂车帝拿皮卡销量，**直接看这一节，不要再花时间探**——三轮验证已经穷尽客户端技术。

#### 皮卡数据替代源

| 源 | 颗粒度 | 结构化 | 推荐度 |
|---|---|---|---|
| **中国皮卡网 cnpickups.com** | 全市场月度 + 车企级 | 文章形式（次月上旬发）| ⭐⭐⭐⭐ |
| 长城/江铃/江西五十铃月度公告 | 单车企最权威 | 数字一致 | ⭐⭐⭐⭐⭐ |
| 中汽协月度产销 | 行业大盘 | PDF | ⭐⭐⭐ |
| 盖世车企榜 | 含江铃 / 上汽大通 等厂商 | ⚠️ **皮卡+轻商混算**无法拆 | ⭐⭐ |

**未来扩展建议**：如需皮卡跟踪，新建 `jobs/pickup-monthly-sales.md` runbook（LLM-driven 而非脚本化——cnpickups.com 文章结构不稳定，LLM 抓比脚本健壮），**不要试图"补丁"到 fetch_auto_sales.py**——源头数据被脱敏，补丁也补不出来。

### 1. 仅月度，无周度
- 数据源是公安部上险 + 中汽数据中心，本身就是月度发布
- API 无 week / day 维度
- 见 [auto-monthly-sales 触发时点](../jobs/auto-monthly-sales.md)

### 2. 发布时点 = 次月 10 日左右
- 5/10 前抓 4 月数据可能不完整
- 推荐：**每月 10-15 日跑 ingest**

### 3. month 参数 fallback 陷阱
- 传未来月份不报错，静默返回最新可用月
- **必须 sanity check**：检查返回数据的 Top 1 销量是否与上月一致（一致 = fallback 了）

### 4. 数字与车主之家完全同源
- 实测 byte-for-byte 一致
- 都用公安部上险数据
- **三源选择**：用懂车帝即可，车主之家可作冗余备份

### 5. score（懂车分）很多为 0
- 未达到评分阈值的车型 score = 0
- 不要在缺值上做平均/排序

### 6. 同比需自计算
- API 无原生同比字段
- 自计算方式：`series_id` join 上年同月数据
- 新车型（series_id 上年不存在）→ 同比标记为 "—"，不要写 "+∞%"

### 7. 极端同比百分比
- 老车型去年同期销量 10 辆 → 今年 13,189 辆 → 同比 +131,790%
- 这种数字**绝对值有价值，百分比无效**——`render_md` 显示时考虑设上限或加注释

## 六、待探索能力（Tier 2-4，按需扩展）

### Tier 2（多调几次 API 即可）

- [ ] **批发-零售 gap 跟踪**：跑两遍 `--saletype` 后 join，每月输出"库存健康度"表
- [ ] **能源结构演变**：每月跑三遍 `--energy bev/phev/reev`，追踪 PHEV 替代 BEV / REEV 蚕食 PHEV 的边际
- [ ] **focus 车型时序**：每月在 `auto-monthly-sales` job 末尾，追加跑 focus 车型的过去 12 个月 trajectory

### Tier 3（需进一步验证 API 参数）

- [ ] **rank_data_type 4-10 语义验证**：试 5 个月份看 Top 1 / Top 5 是否稳定属于某细分市场
- [ ] **city_name 参数**：拿区域市场分化数据（蔚来一线 vs 三四线）
- [ ] **price 参数**：高端市场战局（30-50 万 SUV：极氪 9X / 问界 M9 / 理想 L9 / 蔚来 ES8）
- [ ] **brand_id / manufacturer 参数**：精准筛单品牌 / 单厂商榜

### Tier 4（探索性，未确认 API 是否暴露）

- [ ] **二手车保值率**：懂车帝有二手车业务，可能暴露 1/3/5 年保值率 API
- [ ] **车型对比热度**：用户常对比的车型对，反映实际竞品格局
- [ ] **经销商终端折扣**：`dealer_price` vs `min_price` 差额跟踪

### 字段未用清单（可在 fetch_dongchedi.py 加 `--full-fields` 暴露）

- `score`（懂车分）/ `car_review_count`（评论数）/ `series_pic_count`（图片数）
- `descender_price`（当月降价幅度）
- `online_car_ids` / `offline_car_ids` 长度（在售/停售 SKU 数）

## 七、与其他源关系

| 数据源 | 与懂车帝关系 |
|---|---|
| 车主之家（`fetch_vehicle_models.py`） | **数据完全同源**，懂车帝替代之，留作 HTML 兜底 |
| 盖世 akshare（`fetch_auto_sales.py`） | 不同源——盖世是**车企级**批发 + 含同比 + 累计 3 年对比；懂车帝是**车型级**双口径 + 任意月历史。两者互补 |
| 乘联会 akshare | Top 10 厂商 + 仅最新月；懂车帝完全覆盖且更多 |

**主流程定位**：`fetch_dongchedi.py` 为车型级月度榜的**主源**，`fetch_auto_sales.py`（盖世）为车企级批发口径的**校准源**。
