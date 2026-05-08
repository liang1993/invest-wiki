# 示例：wiki-review 后的目标页面结构

> 这是 wiki-review 整理后的标准个股页面结构示例。**章节顺序对齐 value-invest 模板**，过期内容归档到「历史观察」附录。

```markdown
---
tags: [...]
updated: YYYY-MM-DD   ← wiki-review 会更新这一项
---

# 公司名 (代码)

## 基本信息
- 市场 / 行业 / 市值 / 当前股价

## TL;DR / 一句话总结
（如有，wiki 自有，前置）

## 投资结论
（含价格区间四档表，对应 value-invest 模板第 1 章节）

| 指标 | 价格 | 说明 |
|---|---|---|
| 清仓价 | ... | |
| 减仓价 | ... | |
| 合理价值 | ... | |
| **当前股价** | **...** | **← 当前位置** |
| 安全边际买入价 | ... | |

## 合理PE推导
（value-invest 第 2）

## 多模型估值
（value-invest 第 3）

## 远期分析（如适用）
（value-invest 第 4）

## 利润分解与交叉验证（如适用）
（value-invest 第 5）

## 安全边际与买卖价
（value-invest 第 6）

## 核心财务数据
（value-invest 第 7）

## 同行对比
（value-invest 第 8）

## 风险提示
（value-invest 第 9）

## 关键关注点
（value-invest 第 10）

## 业务结构 / 业务画像
（stock-deep-dive 输出，放 value-invest 之后）

## 竞争格局 / 国际同行 / A股同行
## 护城河 / 产业链
## 资本运作 / 海外业务 / 子公司分拆等深度章节
## 详细数据 / 资产负债表细项

## 相关链接

## 信息来源

## 更新记录
- YYYY-MM-DD CREATE ...
- YYYY-MM-DD INGEST ...
- YYYY-MM-DD LINT ...
- YYYY-MM-DD REVIEW 对齐 value-invest 模板章节顺序 + 归档 X 处过期内容 + 删除 Y 处错误信息

## 历史观察（附录）

> 本章节归档已被替代或已触发完成的内容，便于回看历史决策演化。所有内容默认折叠。

<details><summary>YYYY-MM-DD v1 估值（已被 v2 替代，原因：通用自动化毛利率年报 verified 39.42% vs 估算 30%）</summary>

[原内容]

</details>

<details><summary>YYYY-MM-DD 已触发的催化剂：Q1 季报存货验证</summary>

[原内容]

</details>
```

> ⚠️ **错误信息不进归档**：被证伪的内容（如旧的"激增超百亿"错误表述）由 wiki-review 直接删除，不放入「历史观察」。git log 已能追溯。

## 关键规则

1. **value-invest 模板的 11 个章节按模板顺序保持不变**（投资结论 → 合理PE → 多模型 → 远期 → 利润分解 → 安全边际 → 核心财务 → 同行 → 风险 → 关注点 → 格雷厄姆）
2. **wiki 自有/stock-deep-dive 输出的章节插在 value-invest 章节之后**（业务结构、竞争格局、护城河等）
3. **元数据章节固定位置**：相关链接 → 信息来源 → 更新记录 → 历史观察（最后）
4. **过期但仍有信号的内容归档到「历史观察」**（A 被替代版本 / B 已触发催化剂 / C 被新季度覆盖的旧数据）；**错误信息直接删除**（git log 兜底，不污染历史观察附录）
5. **frontmatter 仅更新 `updated` 字段**，其他不动
