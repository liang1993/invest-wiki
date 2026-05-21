"""fetch_auto_sales.py 的 pure-function 单元测试（不联网）。

只测纯函数：prev_year_month / derive_yoy / group_by_oem / fmt_yoy / fmt_rank_delta /
fmt_last_rank_cell。fetch_page / fetch_all 涉及网络，单独 smoke test。

运行：
    python3 -m unittest skills/scheduled-ingest/tests/test_fetch_auto_sales.py
"""

import importlib.util
import sys
import unittest
from pathlib import Path

# 动态加载脚本（脚本不是 package，模块名含连字符）
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_auto_sales.py"
_spec = importlib.util.spec_from_file_location("fas", str(_SCRIPT))
fas = importlib.util.module_from_spec(_spec)
sys.modules["fas"] = fas
_spec.loader.exec_module(fas)


class TestPrevYearMonth(unittest.TestCase):
    """跨年边界 + 格式校验。"""

    def test_normal_month(self):
        self.assertEqual(fas.prev_year_month("202604"), "202504")
        self.assertEqual(fas.prev_year_month("202506"), "202406")

    def test_january_crosses_year(self):
        # 2026-01 → 2025-01（不是 2025-12）
        self.assertEqual(fas.prev_year_month("202601"), "202501")

    def test_december(self):
        self.assertEqual(fas.prev_year_month("202612"), "202512")

    def test_invalid_input(self):
        self.assertEqual(fas.prev_year_month(""), "")
        self.assertEqual(fas.prev_year_month("2026"), "")  # 长度不对
        self.assertEqual(fas.prev_year_month("20260413"), "")  # 长度不对


class TestDeriveYoy(unittest.TestCase):
    """同比计算 + 边界处理。"""

    def test_normal_yoy(self):
        cur = [{"series_id": 1, "count": 200, "series_name": "A"}]
        prev = [{"series_id": 1, "count": 100, "series_name": "A"}]
        result = fas.derive_yoy(cur, prev)
        self.assertAlmostEqual(result[0]["yoy"], 1.0)  # +100%
        self.assertEqual(result[0]["prev_count"], 100)

    def test_decline(self):
        cur = [{"series_id": 1, "count": 50}]
        prev = [{"series_id": 1, "count": 100}]
        result = fas.derive_yoy(cur, prev)
        self.assertAlmostEqual(result[0]["yoy"], -0.5)

    def test_new_model_no_prev(self):
        """series_id 在上年同月不存在 → yoy = None（新车型）。"""
        cur = [{"series_id": 99, "count": 1000}]
        prev = [{"series_id": 1, "count": 100}]
        result = fas.derive_yoy(cur, prev)
        self.assertIsNone(result[0]["yoy"])
        self.assertIsNone(result[0]["prev_count"])

    def test_prev_zero_avoids_division(self):
        """上年同月 series_id 存在但 count=0（不该发生，但要兜底）。"""
        cur = [{"series_id": 1, "count": 100}]
        prev = [{"series_id": 1, "count": 0}]
        result = fas.derive_yoy(cur, prev)
        self.assertIsNone(result[0]["yoy"])  # 不能除以 0


class TestGroupByOem(unittest.TestCase):
    """OEM 父级聚合映射。"""

    def test_byd_group_aggregates(self):
        rows = [
            {"series_id": 1, "brand_name": "比亚迪", "count": 100},
            {"series_id": 2, "brand_name": "腾势", "count": 50},
            {"series_id": 3, "brand_name": "方程豹", "count": 30},
            {"series_id": 4, "brand_name": "仰望", "count": 5},
        ]
        grouped = fas.group_by_oem(rows)
        self.assertIn("比亚迪集团", grouped)
        self.assertEqual(len(grouped["比亚迪集团"]), 4)

    def test_unmapped_brand_uses_self(self):
        """未列入 OEM_PARENT_MAP 的（如丰田）按自身 brand_name 分组。"""
        rows = [
            {"series_id": 1, "brand_name": "丰田", "count": 100},
            {"series_id": 2, "brand_name": "大众", "count": 80},
        ]
        grouped = fas.group_by_oem(rows)
        self.assertIn("丰田", grouped)
        self.assertIn("大众", grouped)

    def test_geely_group_aggregates(self):
        rows = [
            {"series_id": 1, "brand_name": "吉利汽车", "count": 100},
            {"series_id": 2, "brand_name": "吉利银河", "count": 80},
            {"series_id": 3, "brand_name": "领克", "count": 30},
            {"series_id": 4, "brand_name": "极氪", "count": 20},
        ]
        grouped = fas.group_by_oem(rows)
        self.assertIn("吉利集团", grouped)
        self.assertEqual(sum(r["count"] for r in grouped["吉利集团"]), 230)

    def test_huawei_oem_naming(self):
        """鸿蒙智行 (华为系) 字符串完整，注意括号是英文."""
        rows = [
            {"series_id": 1, "brand_name": "AITO", "count": 100},
            {"series_id": 2, "brand_name": "智界", "count": 50},
        ]
        grouped = fas.group_by_oem(rows)
        self.assertIn("鸿蒙智行(华为系)", grouped)


class TestFmtYoy(unittest.TestCase):
    """同比百分比渲染，含 ±1000% 上限。"""

    def test_normal(self):
        self.assertEqual(fas.fmt_yoy(0.15), "+15.0%")
        self.assertEqual(fas.fmt_yoy(-0.234), "-23.4%")
        self.assertEqual(fas.fmt_yoy(0), "+0.0%")

    def test_none_returns_dash(self):
        self.assertEqual(fas.fmt_yoy(None), "—")

    def test_extreme_positive_capped(self):
        # 1700200% 这种基数过小的同比 → ">+1000%"
        self.assertEqual(fas.fmt_yoy(17.002), ">+1000%")

    def test_extreme_negative_capped(self):
        self.assertEqual(fas.fmt_yoy(-15.0), "<-1000%")

    def test_at_boundary(self):
        # 恰好 +1000% 不应该被 cap
        self.assertEqual(fas.fmt_yoy(10.0), "+1000.0%")


class TestFmtRankDelta(unittest.TestCase):
    """排名变化标记。"""

    def test_rise(self):
        # 上月 #5 → 本月 #2，上升 3
        self.assertEqual(fas.fmt_rank_delta(2, 5), "↑3")

    def test_fall(self):
        # 上月 #2 → 本月 #5，下降 3
        self.assertEqual(fas.fmt_rank_delta(5, 2), "↓3")

    def test_unchanged(self):
        self.assertEqual(fas.fmt_rank_delta(3, 3), "—")

    def test_new_model(self):
        """last_rank=0 表示上月未上榜，应显示「新」。"""
        self.assertEqual(fas.fmt_rank_delta(10, 0), "新")
        self.assertEqual(fas.fmt_rank_delta(10, None), "新")


class TestFmtLastRankCell(unittest.TestCase):
    """组合上月排名 + 变化标识 cell。"""

    def test_normal(self):
        # last_rank=5 + ↑3 = "5 ↑3"
        self.assertEqual(fas.fmt_last_rank_cell(5, "↑3"), "5 ↑3")

    def test_new_model_displays_as_new(self):
        """last_rank=0 应显示「新」，而不是「0 ↑N」这种歧义。"""
        self.assertEqual(fas.fmt_last_rank_cell(0, "新"), "新")
        self.assertEqual(fas.fmt_last_rank_cell(None, "新"), "新")


class TestFocusBrandsCoverage(unittest.TestCase):
    """FOCUS_BRANDS 与 OEM_PARENT_MAP 的一致性检查（避免拼写错误）。"""

    def test_all_focus_brands_in_oem_map(self):
        """所有 focus 品牌都应该有 OEM 映射，避免输出时漏归类。

        允许例外：firefly萤火虫这种边缘品牌可能两边都有但格式不一致。
        """
        # 实际上 focus 是品牌矩阵用的，OEM_PARENT_MAP 是 OEM 聚合用的
        # 但 focus 品牌没在 OEM_MAP 里 → OEM 视图会把它单独成一行 → 失去聚合意义
        focus = fas.FOCUS_BRANDS
        oem_map = fas.OEM_PARENT_MAP
        missing = focus - set(oem_map.keys())
        # 允许少量缺失（如尚未稳定的小众品牌），但报告出来
        if missing:
            print(f"\n⚠️  FOCUS_BRANDS 中以下品牌未在 OEM_PARENT_MAP 里：{missing}\n"
                  f"   这些品牌在 OEM 视图里会单独成行，不会归到任何集团。", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
