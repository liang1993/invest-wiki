#!/usr/bin/env python3
"""车企月度销量 + 单车型 Top 变化（懂车帝主源）

直接调用懂车帝内部 API（无需 msToken / 浏览器自动化）：
  GET https://www.dongchedi.com/motor/pc/car/rank_data?...

聚焦输出（三层）：
1. 车企集团合计（市占率分析） — 比亚迪/吉利/长城/长安/奇瑞/鸿蒙智行/新势力
2. 关注品牌矩阵（主力车型变化） — 单品牌下所有 SKU + 同比
3. 全市场 Top N（趋势观察） — 默认 Top 30

详细 API 规范：references/dongchedi-api.md

用法：
    python3 fetch_auto_sales.py --month 202604 --yoy
    python3 fetch_auto_sales.py --month 202604 --saletype wholesale
    python3 fetch_auto_sales.py --month 202604 --raw raw/articles/sectors/汽车/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API_BASE = "https://www.dongchedi.com/motor/pc/car/rank_data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36"
PAGE_SIZE = 100   # 实测 API 上限
MAX_PAGES = 20    # 死循环保护：638 款全榜约 7 页，20 页绰绰有余
SLEEP_SEC = 0.3   # 礼貌间隔
YOY_DISPLAY_CAP = 1000.0  # 同比百分比显示上限（超过 ±1000% 视为基数过小，特殊渲染）

# rank_data_type 映射
SALETYPE_MAP = {
    "retail": 11,     # 零售（默认主榜，含 ICE + NEV）
    "wholesale": 2,   # 批发（≈ 盖世口径，含出口）
}
# new_energy_type 映射（验证过的）
ENERGY_MAP = {
    "all": "",
    "bev": "1",       # 纯电
    "phev": "2",      # 插混
    "reev": "3",      # 增程
}

# 关注品牌（懂车帝 brand_name 原文）—— 决定第二层「关注品牌矩阵」是否纳入
FOCUS_BRANDS = {
    # 新势力（独立车企）
    "小鹏汽车", "理想汽车", "蔚来", "乐道", "firefly萤火虫",
    "零跑汽车", "小米汽车",
    # 比亚迪集团
    "比亚迪", "腾势", "方程豹", "仰望",
    # 吉利集团
    "吉利汽车", "吉利银河", "领克", "极氪",
    # 长城集团
    "哈弗", "魏牌", "坦克", "欧拉",
    # 长安集团
    "长安", "长安启源", "深蓝汽车", "阿维塔",
    # 奇瑞集团
    "奇瑞", "奇瑞QQ", "奇瑞风云", "奇瑞星途", "捷途", "捷途山海", "iCAR",
    # 鸿蒙智行（华为系）
    "AITO", "智界", "享界", "尊界", "尚界",
    # 上汽集团（自主品牌）
    "名爵", "智己汽车", "荣威", "上汽乘用车", "飞凡汽车", "五菱汽车", "宝骏",
    # 广汽集团（自主品牌）
    "广汽传祺", "埃安",
    # 东风集团（自主品牌）
    "岚图", "东风风神", "东风奕派", "东风风行",
    # 一汽集团（自主品牌）
    "红旗", "奔腾",
    # 北汽集团（自主品牌）
    "ARCFOX极狐", "北京越野",
    # 对照
    "特斯拉", "赛力斯",
}

# 车企集团映射（brand_name → OEM 集团名）
# 用于第一层「车企集团合计」视图。未列入的品牌按原 brand_name 显示
OEM_PARENT_MAP: dict[str, str] = {
    # 比亚迪集团
    "比亚迪": "比亚迪集团", "腾势": "比亚迪集团",
    "方程豹": "比亚迪集团", "仰望": "比亚迪集团",
    # 吉利集团
    "吉利汽车": "吉利集团", "吉利银河": "吉利集团",
    "领克": "吉利集团", "极氪": "吉利集团",
    # 长城集团
    "哈弗": "长城集团", "魏牌": "长城集团",
    "坦克": "长城集团", "欧拉": "长城集团",
    # 长安集团
    "长安": "长安集团", "长安启源": "长安集团",
    "深蓝汽车": "长安集团", "阿维塔": "长安集团",
    # 奇瑞集团
    "奇瑞": "奇瑞集团", "奇瑞QQ": "奇瑞集团",
    "奇瑞风云": "奇瑞集团", "奇瑞星途": "奇瑞集团",
    "捷途": "奇瑞集团", "捷途山海": "奇瑞集团",
    "iCAR": "奇瑞集团",
    # 鸿蒙智行（华为系，多家车企代工但统一渠道）
    "AITO": "鸿蒙智行(华为系)", "智界": "鸿蒙智行(华为系)",
    "享界": "鸿蒙智行(华为系)", "尊界": "鸿蒙智行(华为系)",
    "尚界": "鸿蒙智行(华为系)",
    # 上汽集团（自主品牌；合资外资品牌不归集团）
    "名爵": "上汽集团", "智己汽车": "上汽集团",
    "荣威": "上汽集团", "上汽乘用车": "上汽集团",
    "飞凡汽车": "上汽集团", "五菱汽车": "上汽集团",
    "宝骏": "上汽集团",
    # 广汽集团
    "广汽传祺": "广汽集团", "埃安": "广汽集团",
    # 东风集团
    "岚图": "东风集团", "东风风神": "东风集团",
    "东风奕派": "东风集团", "东风风行": "东风集团",
    # 一汽集团
    "红旗": "一汽集团", "奔腾": "一汽集团",
    # 北汽集团
    "ARCFOX极狐": "北汽集团", "北京越野": "北汽集团",
    # 蔚来集团
    "蔚来": "蔚来集团", "乐道": "蔚来集团",
    "firefly萤火虫": "蔚来集团",
    # 独立新势力
    "小鹏汽车": "小鹏汽车", "理想汽车": "理想汽车",
    "零跑汽车": "零跑汽车", "小米汽车": "小米汽车",
    # 赛力斯（独立上市，问界母公司之一，但鸿蒙智行 AITO 一般独立看）
    "赛力斯": "赛力斯",
    # 特斯拉
    "特斯拉": "特斯拉中国",
}


def fetch_page(offset: int, count: int = PAGE_SIZE, month: str = "",
               sale_type: int = 11, energy: str = "",
               timeout: int = 30, retries: int = 3) -> dict:
    params = {
        "aid": "1839", "app_name": "auto_web_pc",
        "count": str(count), "offset": str(offset), "month": month,
        "new_energy_type": energy,
        "rank_data_type": str(sale_type),
        "brand_id": "", "price": "", "manufacturer": "",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.dongchedi.com/sales"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
        except Exception as e:
            last_err = e
            # 指数退避：第 1 次失败等 3s，第 2 次等 9s
            wait = 3 * (3 ** attempt)
            print(f"⚠️  fetch_page offset={offset} month={month} 失败 (尝试 {attempt+1}/{retries}): {type(e).__name__}, {wait}s 后重试",
                  file=sys.stderr)
            time.sleep(wait)
    raise last_err if last_err else RuntimeError("fetch_page failed")


def fetch_all(month: str = "", sale_type: int = 11, energy: str = "",
              max_pages: int = MAX_PAGES) -> list[dict]:
    """翻页拿全榜，返回 series_id 升序的 list[dict]。

    max_pages 是死循环保护——若 API 异常持续返回 has_more=True 但数据未推进，
    最多取 max_pages 次翻页就停止（默认 20 页 = 2000 条，远超 638 款全榜）。
    """
    rows: list[dict] = []
    offset = 0
    seen_ids: set[int] = set()
    for page_idx in range(max_pages):
        d = fetch_page(offset, month=month, sale_type=sale_type, energy=energy).get("data") or {}
        lst = d.get("list", [])
        if not lst:
            break
        # 重复 series_id 检测：若新拉到的全部 series_id 都已见过，说明 API 卡住，退出
        new_ids = {r.get("series_id") for r in lst if r.get("series_id") is not None}
        if new_ids and new_ids.issubset(seen_ids):
            print(f"⚠️  fetch_all: 第 {page_idx+1} 页全部为重复 series_id，提前退出",
                  file=sys.stderr)
            break
        seen_ids.update(new_ids)
        rows.extend(lst)
        if not d.get("paging", {}).get("has_more") or len(lst) < PAGE_SIZE:
            break
        offset += len(lst)
        time.sleep(SLEEP_SEC)
    else:
        # for-else: 跑满 max_pages 没 break
        print(f"⚠️  fetch_all: 翻页达上限 max_pages={max_pages}，停止拉取（可能 API 异常）",
              file=sys.stderr)
    return rows


def derive_yoy(cur: list[dict], prev_year: list[dict]) -> list[dict]:
    """按 series_id join 计算同比，返回带 yoy / prev_count 字段的 cur 副本。"""
    prev_map = {r["series_id"]: r["count"] for r in prev_year}
    enriched = []
    for r in cur:
        row = dict(r)
        sid = r["series_id"]
        prev = prev_map.get(sid)
        row["prev_count"] = prev
        if prev and prev > 0:
            row["yoy"] = (r["count"] - prev) / prev
        else:
            row["yoy"] = None  # 新车型，去年同期无数据
        enriched.append(row)
    return enriched


def prev_year_month(month: str) -> str:
    """202604 → 202504。"""
    if not month or len(month) != 6:
        return ""
    yyyy, mm = int(month[:4]), month[4:]
    return f"{yyyy - 1}{mm}"


def filter_focus(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("brand_name") in FOCUS_BRANDS]


def group_by_brand(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[r.get("brand_name", "未知")].append(r)
    return dict(sorted(grouped.items(), key=lambda kv: -sum(r["count"] for r in kv[1])))


def group_by_oem(rows: list[dict]) -> dict[str, list[dict]]:
    """按车企集团聚合。未列入 OEM_PARENT_MAP 的品牌按原 brand_name 自身分组（多为合资外资）。"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        oem = OEM_PARENT_MAP.get(r.get("brand_name", ""), r.get("brand_name", "未知"))
        grouped[oem].append(r)
    return dict(sorted(grouped.items(), key=lambda kv: -sum(r["count"] for r in kv[1])))


def fmt_yoy(yoy) -> str:
    """渲染同比百分比。超过 ±YOY_DISPLAY_CAP 时用 >+1000% / <-1000% 表示（基数过小特殊标记）。"""
    if yoy is None:
        return "—"
    pct = yoy * 100
    if pct > YOY_DISPLAY_CAP:
        return f">+{YOY_DISPLAY_CAP:.0f}%"
    if pct < -YOY_DISPLAY_CAP:
        return f"<-{YOY_DISPLAY_CAP:.0f}%"
    return f"{pct:+.1f}%"


def fmt_rank_delta(cur: int, prev: int) -> str:
    """rank vs last_rank 变化。last_rank=0 表示上月未上榜（新车型 / 退榜回归）。"""
    if prev is None or prev == 0:
        return "新"   # 上月未上榜
    if prev == cur:
        return "—"
    delta = prev - cur  # 正数=上升
    sign = "↑" if delta > 0 else "↓"
    return f"{sign}{abs(delta)}"


def fmt_last_rank_cell(last_rank, rank_change: str) -> str:
    """组合上月排名 + 变化标识。last_rank=0/None 时显示「新」。"""
    if last_rank is None or last_rank == 0:
        return "新"
    return f"{last_rank} {rank_change}".strip()


def render_top_table(rows: list[dict], title: str, top: int = 30, with_yoy: bool = False) -> str:
    headers = ["排名", "车型", "销量（辆）", "上月排名", "品牌"]
    if with_yoy:
        headers.append("同比")
    headers.append("价格区间")
    lines = [f"### {title}", ""]
    lines.append("| " + " | ".join(headers) + " |")
    aligns = ["---:" if h in ("排名", "销量（辆）", "同比") else "---" for h in headers]
    lines.append("| " + " | ".join(aligns) + " |")
    for r in rows[:top]:
        rank_change = fmt_rank_delta(r["rank"], r.get("last_rank"))
        cells = [
            str(r["rank"]),
            r["series_name"],
            f"{r['count']:,}",
            fmt_last_rank_cell(r.get("last_rank"), rank_change),
            r.get("brand_name", "—"),
        ]
        if with_yoy:
            cells.append(fmt_yoy(r.get("yoy")))
        cells.append(r.get("price", "—"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_oem_summary(rows: list[dict], with_yoy: bool = False, top_oem: int = 20) -> str:
    """车企集团合计销量 + 同比 + 市占率 + 入榜 SKU 数 + 主力车型 Top 3。

    用于回答"各大车企月度销量变化 + 市占率"问题。
    """
    grouped = group_by_oem(rows)
    total_market = sum(r["count"] for r in rows) or 1
    total_market_prev = sum((r.get("prev_count") or 0) for r in rows) if with_yoy else 0

    market_total_yoy = ""
    if total_market_prev > 0:
        market_total_yoy = f"，全市场同比 {fmt_yoy((total_market - total_market_prev) / total_market_prev)}"

    lines = [
        f"### 车企集团合计（市占率分析，全市场 {total_market:,} 辆{market_total_yoy}）",
        "",
    ]
    if with_yoy:
        lines.append("| 排名 | 车企集团 | 当月销量 | 同比 | 市占率 | 入榜 SKU | 主力车型 (top 3) |")
        lines.append("| ---: | --- | ---: | ---: | ---: | ---: | --- |")
    else:
        lines.append("| 排名 | 车企集团 | 当月销量 | 市占率 | 入榜 SKU | 主力车型 (top 3) |")
        lines.append("| ---: | --- | ---: | ---: | ---: | --- |")

    for i, (oem, models) in enumerate(list(grouped.items())[:top_oem], 1):
        total = sum(r["count"] for r in models)
        market_share = total / total_market * 100
        sku_count = len(models)
        top_models = sorted(models, key=lambda x: -x["count"])[:3]
        top_str = " / ".join(f"{m['series_name']} {m['count']:,}" for m in top_models)

        if with_yoy:
            prev_total = sum((r.get("prev_count") or 0) for r in models)
            yoy_str = "—"
            if prev_total > 0:
                yoy_str = fmt_yoy((total - prev_total) / prev_total)
            lines.append(
                f"| {i} | {oem} | {total:,} | {yoy_str} | {market_share:.1f}% | {sku_count} | {top_str} |"
            )
        else:
            lines.append(
                f"| {i} | {oem} | {total:,} | {market_share:.1f}% | {sku_count} | {top_str} |"
            )
    return "\n".join(lines)


def render_focus_matrix(rows: list[dict], with_yoy: bool = False) -> str:
    focus = filter_focus(rows)
    grouped = group_by_brand(focus)
    lines = ["### 关注品牌车型矩阵（按品牌总销量降序）", ""]
    for brand, models in grouped.items():
        total = sum(r["count"] for r in models)
        prev_total = sum((r.get("prev_count") or 0) for r in models) if with_yoy else 0
        brand_yoy = ""
        if with_yoy and prev_total > 0:
            brand_yoy = f"（品牌同比 {fmt_yoy((total - prev_total) / prev_total)}）"
        lines.append(f"\n**{brand}** — {len(models)} 款，合计 {total:,} 辆{brand_yoy}")
        lines.append("")
        # headers 与 cells 顺序必须一一对应
        if with_yoy:
            headers = ["排名", "车型", "销量", "同比", "上月", "价格区间"]
        else:
            headers = ["排名", "车型", "销量", "上月", "价格区间"]
        lines.append("| " + " | ".join(headers) + " |")
        aligns = ["---:" if h in ("排名", "销量", "同比") else "---" for h in headers]
        lines.append("| " + " | ".join(aligns) + " |")
        for r in sorted(models, key=lambda x: -x["count"]):
            rank_change = fmt_rank_delta(r["rank"], r.get("last_rank"))
            last_rank_cell = fmt_last_rank_cell(r.get("last_rank"), rank_change)
            if with_yoy:
                cells = [str(r["rank"]), r["series_name"], f"{r['count']:,}",
                         fmt_yoy(r.get("yoy")), last_rank_cell, r.get("price", "—")]
            else:
                cells = [str(r["rank"]), r["series_name"], f"{r['count']:,}",
                         last_rank_cell, r.get("price", "—")]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_md(rows: list[dict], month: str, sale_type_label: str,
              energy_label: str, with_yoy: bool, top: int) -> str:
    sections = [
        "---",
        f"title: {month or '最新月'} 车企销量月度（懂车帝 {sale_type_label}）",
        f"month: {month or 'latest'}",
        f"saletype: {sale_type_label}",
        f"energy: {energy_label}",
        f"yoy: {with_yoy}",
        f"source: 懂车帝 https://www.dongchedi.com/sales",
        f"fetched_via: dongchedi 内部 API (rank_data)",
        f"tags: [汽车, 销量, 车型, 月度, 懂车帝]",
        "---",
        "",
        f"# {month or '最新月'} 车企销量月度（懂车帝 · {sale_type_label}）",
        "",
        f"**数据源**：懂车帝 API（口径 = 公安部上险 + 中汽数据中心，{len(rows)} 款车型全榜）",
        f"**口径**：{sale_type_label}（{'≈ 盖世批发口径，含出口' if sale_type_label == '批发' else '终端零售上险，国内市场实际销售'}）",
        f"**能源类型筛选**：{energy_label}",
        "**字段说明**：「上月排名」字段已含变化方向标记（↑/↓+N）；价格区间来自懂车帝厂商指导价" + (
            "；**「同比」已 join 上年同月数据自动计算**" if with_yoy else "。"),
        "",
        render_oem_summary(rows, with_yoy=with_yoy),
        "",
        render_focus_matrix(rows, with_yoy=with_yoy),
        "",
        render_top_table(rows, f"全市场车型榜（Top {top}）", top=top, with_yoy=with_yoy),
        "",
        "## 数据说明",
        "",
        "- 销量字段来自懂车帝官方 API，与车主之家同源（公安部上险 + 中汽数据中心）",
        "- 「上月排名」（`last_rank`）是懂车帝原生字段，反映月对月排名变化方向",
        "- 「同比」是 join 上年同月销量自动计算（如有），新车型显示为「—」",
    ]
    return "\n".join(sections) + "\n"


def main():
    ap = argparse.ArgumentParser(description="懂车帝车型榜抓取")
    ap.add_argument("--month", default="", help="YYYYMM 历史月，默认最新")
    ap.add_argument("--saletype", choices=list(SALETYPE_MAP), default="retail",
                    help="零售 retail / 批发 wholesale（默认 retail）")
    ap.add_argument("--energy", choices=list(ENERGY_MAP), default="all",
                    help="能源类型 all/bev/phev/reev（默认 all）")
    ap.add_argument("--yoy", action="store_true", help="自动算同比（拉上年同月数据）")
    ap.add_argument("--top", type=int, default=30, help="总榜显示 Top N（默认 30）")
    ap.add_argument("--raw", type=str, default=None, help="同步写 raw md 到指定目录")
    ap.add_argument("--json", type=str, default=None, help="额外落地 JSON 到指定文件")
    args = ap.parse_args()

    sale_type = SALETYPE_MAP[args.saletype]
    energy = ENERGY_MAP[args.energy]
    sale_label = "零售" if args.saletype == "retail" else "批发"
    energy_label = {"all": "全口径", "bev": "纯电 BEV", "phev": "插混 PHEV", "reev": "增程 REEV"}[args.energy]

    print(f"→ 抓取 {args.month or '最新月'} {sale_label} {energy_label} ...", file=sys.stderr)
    rows = fetch_all(month=args.month, sale_type=sale_type, energy=energy)
    print(f"✅ 共 {len(rows)} 款车型", file=sys.stderr)

    if args.yoy:
        prev_month = prev_year_month(args.month) if args.month else ""
        if not prev_month:
            # 最新月时需要先知道当前是哪月——从首条 rank_info 没暴露月份。
            # 简化：让用户显式传 --month YYYYMM 才能算同比
            print("⚠️  --yoy 需要 --month 显式指定（最新月份口径不暴露月份字符串）", file=sys.stderr)
        else:
            print(f"→ 拉上年同月 {prev_month} 算同比 ...", file=sys.stderr)
            prev_rows = fetch_all(month=prev_month, sale_type=sale_type, energy=energy)
            rows = derive_yoy(rows, prev_rows)
            print(f"   上年同月 {len(prev_rows)} 款，已 join", file=sys.stderr)

    print(render_md(rows, args.month, sale_label, energy_label, args.yoy, top=args.top))

    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ JSON 已写入 {args.json}", file=sys.stderr)

    if args.raw:
        out_dir = Path(args.raw)
        out_dir.mkdir(parents=True, exist_ok=True)
        month_label = args.month or "latest"
        # 转 YYYY-MM 格式
        if len(month_label) == 6 and month_label.isdigit():
            month_label = f"{month_label[:4]}-{month_label[4:]}"
        suffix = []
        if args.saletype != "retail":
            suffix.append(args.saletype)
        if args.energy != "all":
            suffix.append(args.energy)
        if args.yoy:
            suffix.append("yoy")
        suffix_str = ("_" + "_".join(suffix)) if suffix else ""
        out_path = out_dir / f"{month_label}_车企销量月度_懂车帝{suffix_str}.md"
        out_path.write_text(render_md(rows, args.month, sale_label, energy_label, args.yoy, top=args.top),
                            encoding="utf-8")
        print(f"✅ 已写入 {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
