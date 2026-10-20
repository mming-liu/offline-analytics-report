"""offline-analytics-report 命令行入口。

用法：
    python analyze.py --demo                                   生成示例数据并出完整报表
    python analyze.py --input data/sales_orders.csv            分析指定明细
    python analyze.py --input x.csv --out 交付目录 --year 2026  指定输出目录与对比年份
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from analytics import metrics, report  # noqa: E402
from analytics.charts import fmt_money  # noqa: E402


def setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def build_summary(m: dict) -> str:
    """纯文字版结论，可直接粘进方案、周报或微信消息。"""
    kpi = m["kpi"]
    p = m["period"]
    y = p["current_year"]
    def _yoy_text(value: float | None) -> str:
        return f"{value:+.1f}%" if value is not None else "—"

    lines = [
        f"# 经营数据复盘摘要（{p['start']} ~ {p['end']}）",
        "",
        "## 一、核心指标",
        "",
        "| 指标 | 数值 | 同比 |",
        "| --- | --- | --- |",
        f"| 累计 GMV | {fmt_money(kpi['gmv']['value'])} | {_yoy_text(kpi['gmv']['yoy'])} |",
        f"| 累计订单数 | {kpi['orders']['value']:,} 单 | {_yoy_text(kpi['orders']['yoy'])} |",
        f"| 客单价 | ¥{kpi['aov']['value']:,.0f} | {_yoy_text(kpi['aov']['yoy'])} |",
        f"| 销量 | {kpi['qty']['value']:,} 件 | {_yoy_text(kpi['qty']['yoy'])} |",
        f"| {p['end']} 单月 GMV | {fmt_money(kpi['last_month_gmv']['value'])} | 环比 {_yoy_text(kpi['last_month_gmv']['mom'])} |",
        "",
        "## 二、主要结论",
        "",
    ]
    for i, item in enumerate(m["insights"], start=1):
        lines.append(f"{i}. **{item['title']}** —— {item['detail']}")
    lines += [
        "",
        "## 三、品类明细",
        "",
        "| 品类 | GMV | 占比 | 同比 | ABC |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in m["categories"]:
        yoy = f"{c['yoy']:+.1f}%" if c["yoy"] is not None else "—"
        lines.append(f"| {c['name']} | {fmt_money(c['gmv'])} | {c['share']:.1f}% | {yoy} | {c['abc']} |")
    lines += [
        "",
        "## 四、区域与渠道",
        "",
        "| 区域 | GMV | 占比 | 客单价 |",
        "| --- | --- | --- | --- |",
    ]
    for r in m["regions"]:
        lines.append(f"| {r['name']} | {fmt_money(r['gmv'])} | {r['share']:.1f}% | ¥{r['aov']:,.0f} |")
    lines += ["", "| 渠道 | GMV | 占比 | 客单价 |", "| --- | --- | --- | --- |"]
    for c in m["channels"]:
        lines.append(f"| {c['name']} | {fmt_money(c['gmv'])} | {c['share']:.1f}% | ¥{c['aov']:,.0f} |")
    lines += [
        "",
        "## 五、口径说明",
        "",
        f"- 分析区间：{p['start']} ~ {p['end']}，共 {p['months']} 个月、{p['records']:,} 条明细",
        "- GMV 仅统计 status = 已支付 的订单，不含取消与退款",
        "- 订单数按 order_id 去重；客单价 = GMV ÷ 订单数",
        f"- 同比基准：{p['last_year']} 年同期；目标 = 去年同月 × {metrics.TARGET_FACTOR:g}（用于衡量节奏）",
        "",
        "> 完整图表见同目录 report.html，单文件可直接打开或打印为 PDF。",
    ]
    return "\n".join(lines)


def run(input_path: Path, out_dir: Path, year: int | None = None) -> dict:
    header, rows = metrics.read_csv(input_path)
    print(f"[1/3] 读取 {input_path.name}：{len(rows):,} 行 × {len(header)} 列")

    missing = {"order_date", "amount", "status"} - set(header)
    if missing:
        raise SystemExit(f"缺少必需字段：{', '.join(sorted(missing))}")

    m = metrics.analyze(rows, current_year=year)
    p = m["period"]
    print(f"      分析区间 {p['start']} ~ {p['end']}，有效明细 {p['records']:,} 条")
    yoy = m["kpi"]["gmv"]["yoy"]
    yoy_text = f"{yoy:+.1f}%" if yoy is not None else "无同期数据"
    print(
        f"      GMV {fmt_money(m['kpi']['gmv']['value'])}（同比 {yoy_text}），"
        f"订单 {m['kpi']['orders']['value']:,}，客单价 ¥{m['kpi']['aov']['value']:,.0f}"
    )

    print("[2/3] 生成指标与图表")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] 渲染 HTML 报表与摘要")
    html = report.build_html(m, meta={"source": input_path.name})
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    (out_dir / "summary.md").write_text(build_summary(m), encoding="utf-8")

    return {
        "input": str(input_path),
        "report": str(out_dir / "report.html"),
        "summary": str(out_dir / "summary.md"),
        "gmv": m["kpi"]["gmv"]["value"],
        "yoy_pct": m["kpi"]["gmv"]["yoy"],
        "insights": len(m["insights"]),
    }


def main(argv: list[str] | None = None) -> int:
    setup_console()
    parser = argparse.ArgumentParser(
        prog="offline-analytics-report",
        description="离线数据分析与报表：指标拆解 → SVG 图表 → 汇报级 HTML + 结论摘要",
    )
    parser.add_argument("--input", help="订单明细 CSV（需含 order_date / amount / status）")
    parser.add_argument("--out", default=str(ROOT / "out"), help="输出目录")
    parser.add_argument("--year", type=int, default=None, help="同比分析的当年（默认取数据最后一年）")
    parser.add_argument("--demo", action="store_true", help="生成示例数据并完整跑一遍")
    args = parser.parse_args(argv)

    if args.demo and not args.input:
        from demo.make_sales_data import make_dataset

        info = make_dataset(ROOT / "data" / "sales_orders.csv")
        print(f"[0/3] 已生成示例明细 {info['rows']:,} 行（{info['period']}）\n")
        args.input = info["path"]

    if not args.input:
        parser.error("请用 --input 指定明细文件，或加 --demo 一键演示")

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"文件不存在：{input_path}")

    result = run(input_path, Path(args.out), args.year)
    print("\n交付文件：")
    for key in ("report.html", "summary.md", "metrics.json"):
        path = Path(args.out) / key
        if path.exists():
            print(f"  - {path}  ({path.stat().st_size / 1024:.1f} KB)")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
