"""指标计算与图表的边界测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics import charts as C  # noqa: E402
from analytics import metrics as M  # noqa: E402

HEADER = ["order_id", "order_date", "region", "channel", "category", "qty", "unit_price", "amount", "customer_id", "status"]


def row(oid, y, m, d, amount, status="已支付", category="办公耗材", channel="天猫", region="华东", qty=2):
    return dict(
        zip(
            HEADER,
            [oid, f"{y}-{m:02d}-{d:02d}", region, channel, category, qty, "10.00", f"{amount:.2f}", f"C{oid[-4:]}", status],
        )
    )


class TestMetrics(unittest.TestCase):
    def test_gmv_counts_paid_only_and_orders_dedup(self):
        rows = [
            row("SO1", 2026, 1, 5, 100),
            row("SO2", 2026, 1, 6, 200, status="已取消"),
            row("SO3", 2026, 1, 7, 300, status="退款"),
            row("SO4", 2026, 1, 8, 50, status="待支付"),
        ]
        m = M.analyze(rows, current_year=2026)
        self.assertEqual(m["kpi"]["gmv"]["value"], 100)      # 只有已支付计入
        self.assertEqual(m["kpi"]["orders"]["value"], 1)
        self.assertEqual(m["kpi"]["paid_rate"]["value"], 25.0)
        # 漏斗：4 下单 → 3 有效（排除取消） → 1 支付
        self.assertEqual([s["count"] for s in m["funnel"]], [4, 3, 1])

    def test_yoy_aligns_by_month_not_by_total(self):
        """2026 只有 1-3 月数据时，同比必须对齐 2025 的 1-3 月，而不是拿全年比。"""
        rows = [
            row(f"S{i}", 2025, month, 10, 100) for month in range(1, 13) for i in range(1)
        ] + [row(f"T{i}", 2026, month, 10, 150) for month in range(1, 4) for i in range(1)]
        m = M.analyze(rows, current_year=2026)
        self.assertAlmostEqual(m["kpi"]["gmv"]["yoy"], 50.0)  # 450 vs 300，只比 1-3 月
        cmp_data = m["monthly_compare"]
        self.assertEqual(len(cmp_data["cy"]), 12)
        self.assertIsNone(cmp_data["cy"][9])   # 10 月无数据
        self.assertIsNotNone(cmp_data["ly"][9])

    def test_dimension_breakdown_and_abc(self):
        rows = []
        for i in range(10):
            rows.append(row(f"A{i}", 2026, 2, 3, 500, category="数码配件"))
        for i in range(5):
            rows.append(row(f"B{i}", 2026, 2, 3, 100, category="办公耗材"))
        m = M.analyze(rows, current_year=2026)
        cats = m["categories"]
        self.assertEqual(cats[0]["name"], "数码配件")
        self.assertAlmostEqual(cats[0]["cum_share"], 5000 / 5500 * 100, places=1)
        self.assertEqual(cats[0]["abc"], "A")
        self.assertEqual(cats[-1]["abc"], "C")

    def test_targets_use_ly_same_month(self):
        rows = [row(f"S{i}", 2025, 3, 10, 2000) for i in range(1)] + [row("T1", 2026, 3, 10, 1150)]
        m = M.analyze(rows, current_year=2026)
        t = m["targets"][2]  # 3 月
        self.assertAlmostEqual(t["target"], 2300.0)
        self.assertAlmostEqual(t["rate"], 50.0)

    def test_bad_dates_are_skipped_not_crash(self):
        rows = [dict(zip(HEADER, ["SO1", "not-a-date", "华东", "天猫", "办公耗材", 1, "10", "10", "C1", "已支付"]))]
        rows.append(row("SO2", 2026, 1, 5, 100))
        m = M.analyze(rows, current_year=2026)
        self.assertEqual(m["kpi"]["gmv"]["value"], 100)

    def test_insights_generated(self):
        rows = [
            [row(f"A{i}", 2026, m, 10, 400) for m in range(1, 10) for i in range(5)]
            + [row(f"B{i}", 2025, m, 10, 300) for m in range(1, 10) for i in range(5)]
        ]
        m = M.analyze(rows[0], current_year=2026)
        self.assertGreaterEqual(len(m["insights"]), 3)
        for item in m["insights"]:
            self.assertIn("title", item)
            self.assertIn("detail", item)


class TestCharts(unittest.TestCase):
    def test_nice_max(self):
        self.assertEqual(C._nice_max(9999), 10000)
        self.assertEqual(C._nice_max(1234), 1500)

    def test_fmt(self):
        self.assertEqual(C.fmt_short(123456), "12.3万")
        self.assertEqual(C.fmt_money(1.2e8), "¥1.20亿")
        self.assertEqual(C.fmt_short(None), "-")

    def test_line_chart_handles_none(self):
        svg = C.line_chart(
            ["1月", "2月", "3月"],
            [
                {"name": "2026", "values": [10, None, 30], "color": "#000"},
                {"name": "2025", "values": [5, 8, None], "color": "#999", "dashed": True},
            ],
        )
        self.assertIn("viewBox", svg)
        self.assertIn("polyline", svg)

    def test_donut_sums_to_full_circle(self):
        svg = C.donut([{"label": "A", "value": 3}, {"label": "B", "value": 1}], center_value="¥4")
        self.assertEqual(svg.count("<circle"), 3)  # 底环 + 2 个分段
        self.assertIn("stroke-dasharray", svg)

    def test_pareto_and_funnel_render(self):
        p = C.pareto_chart([{"label": "A", "value": 500, "cum_share": 62.5, "abc": "A"}, {"label": "B", "value": 300, "cum_share": 100, "abc": "B"}])
        self.assertIn("80% 分界线", p)
        f = C.funnel_chart([{"stage": "下单", "count": 100, "rate": 100, "step_rate": 100}, {"stage": "支付", "count": 80, "rate": 80, "step_rate": 80}])
        self.assertIn("下单", f)


if __name__ == "__main__":
    unittest.main(verbosity=2)
