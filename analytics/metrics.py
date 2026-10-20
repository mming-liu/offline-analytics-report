"""指标计算：把订单明细拆成经营复盘需要的那几层数字。

口径说明（会同步写进报告，避免客户对不上账）：
  · GMV 只统计 status = 已支付 的订单金额
  · 订单数按 order_id 去重计数
  · 客单价 = GMV / 订单数
  · 同比 = 当年累计 vs 去年同月累计；环比 = 最近月 vs 上月
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

# 月度目标系数：目标 = 去年同月 GMV × TARGET_FACTOR。
# 1.15 表示按年增 15% 排产；客户有正式预算时只改这一处，报告与结论会同步更新。
TARGET_FACTOR = 1.15


def read_csv(path: str | Path) -> tuple[list[str], list[dict]]:
    path = Path(path)
    for enc in ("utf-8-sig", "gbk"):
        try:
            with path.open("r", encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                return list(reader.fieldnames or []), [dict(r) for r in reader]
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别编码：{path}")


def _pct(new: float, old: float) -> float | None:
    if not old:
        return None
    return (new - old) / old * 100


def _month_key(value: str) -> str:
    """统一成 YYYY-MM。"""
    text = (value or "").strip().replace("/", "-").replace(".", "-")
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}"
    return text[:7]


def _parse_day(value: str) -> date | None:
    text = (value or "").strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            if fmt == "%Y%m%d":
                return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            parts = text.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2][:2]))
        except (ValueError, IndexError):
            continue
    return None


def analyze(rows: list[dict], current_year: int | None = None) -> dict:
    records = []
    for row in rows:
        day = _parse_day(row.get("order_date", ""))
        if day is None:
            continue
        try:
            amount = float(row.get("amount", 0) or 0)
            qty = int(float(row.get("qty", 0) or 0))
        except ValueError:
            continue
        records.append(
            {
                "order_id": (row.get("order_id") or "").strip(),
                "day": day,
                "month": f"{day.year}-{day.month:02d}",
                "region": (row.get("region") or "未标注").strip() or "未标注",
                "channel": (row.get("channel") or "未标注").strip() or "未标注",
                "category": (row.get("category") or "未分类").strip() or "未分类",
                "qty": qty,
                "amount": amount,
                "status": (row.get("status") or "").strip(),
                "customer_id": (row.get("customer_id") or "").strip(),
            }
        )

    if not records:
        raise ValueError("没有可用记录，请检查 order_date / amount 字段")

    months_all = sorted({r["month"] for r in records})
    last_month = months_all[-1]
    c_year = current_year or int(last_month[:4])
    ly_year = c_year - 1
    last_month_num = int(last_month[5:7])

    # 逐月 GMV（已支付），供同比对齐、目标测算复用
    month_gmv: dict[tuple[int, int], float] = {}
    for r in records:
        if r["status"] != "已支付":
            continue
        key = (r["day"].year, r["day"].month)
        month_gmv[key] = month_gmv.get(key, 0.0) + r["amount"]

    # ---------- 分组汇总
    def agg(subset: list[dict]) -> dict:
        paid = [r for r in subset if r["status"] == "已支付"]
        gmv = sum(r["amount"] for r in paid)
        orders = len({r["order_id"] for r in paid})
        return {
            "gmv": gmv,
            "orders": orders,
            "qty": sum(r["qty"] for r in paid),
            "aov": gmv / orders if orders else 0.0,
            "all_orders": len({r["order_id"] for r in subset}),
        }

    cy = [r for r in records if r["day"].year == c_year]
    # 同比必须同月对齐：当年只到 9 月，去年也只能取 1-9 月，否则会算出假下滑
    ly = [r for r in records if r["day"].year == ly_year and r["day"].month <= last_month_num]
    last_month_records = [r for r in records if r["month"] == last_month]
    prev_month_key = months_all[-2] if len(months_all) > 1 else None
    prev_month_records = [r for r in records if r["month"] == prev_month_key] if prev_month_key else []

    cy_agg, ly_agg = agg(cy), agg(ly)
    lm_agg, pm_agg = agg(last_month_records), agg(prev_month_records)

    kpi = {
        "gmv": {"value": cy_agg["gmv"], "yoy": _pct(cy_agg["gmv"], ly_agg["gmv"]), "label": f"{c_year} 年累计 GMV"},
        "orders": {"value": cy_agg["orders"], "yoy": _pct(cy_agg["orders"], ly_agg["orders"]), "label": "累计订单数"},
        "aov": {"value": cy_agg["aov"], "yoy": _pct(cy_agg["aov"], ly_agg["aov"]), "label": "客单价"},
        "qty": {"value": cy_agg["qty"], "yoy": _pct(cy_agg["qty"], ly_agg["qty"]), "label": "销量（件）"},
        "last_month_gmv": {
            "value": lm_agg["gmv"],
            "mom": _pct(lm_agg["gmv"], pm_agg["gmv"]),
            "label": f"{last_month} 单月 GMV",
        },
        "paid_rate": {
            "value": (len([r for r in cy if r["status"] == "已支付"]) / len(cy) * 100) if cy else 0.0,
            "label": "订单支付率",
        },
    }

    # ---------- 月度趋势（最近 14 个月连续序列，用于迷你趋势线）
    monthly = []
    for key in months_all[-14:]:
        subset = [r for r in records if r["month"] == key]
        monthly.append({"month": key, **agg(subset)})

    # ---------- 同比按月对齐：x 轴固定 1-12 月，当年与去年并排，避免「拿 9 个月比 12 个月」
    monthly_compare = {
        "labels": [f"{m} 月" for m in range(1, 13)],
        "cy": [month_gmv.get((c_year, m)) for m in range(1, 13)],
        "ly": [month_gmv.get((ly_year, m)) for m in range(1, 13)],
    }

    # ---------- 维度拆解
    def by_dimension(field: str) -> list[dict]:
        names = sorted({r[field] for r in records})
        out = []
        for name in names:
            cur = agg([r for r in cy if r[field] == name])
            prev = agg([r for r in ly if r[field] == name])
            out.append(
                {
                    "name": name,
                    "gmv": cur["gmv"],
                    "ly_gmv": prev["gmv"],
                    "orders": cur["orders"],
                    "qty": cur["qty"],
                    "aov": cur["aov"],
                    "share": (cur["gmv"] / cy_agg["gmv"] * 100) if cy_agg["gmv"] else 0.0,
                    "yoy": _pct(cur["gmv"], prev["gmv"]),
                }
            )
        out.sort(key=lambda x: -x["gmv"])
        return out

    categories = by_dimension("category")
    regions = by_dimension("region")
    channels = by_dimension("channel")

    # ---------- ABC 分析（帕累托跨线规则：把自己累计进 70%/90% 线内的品类分别归为 A/B）
    total = sum(c["gmv"] for c in categories) or 1
    acc = 0.0
    for item in categories:
        prev_cum = acc / total * 100
        acc += item["gmv"]
        item["cum_share"] = acc / total * 100
        item["abc"] = "A" if prev_cum < 70 else ("B" if prev_cum < 90 else "C")

    # ---------- 订单转化漏斗
    total_orders = len({r["order_id"] for r in cy})
    cancelled = len({r["order_id"] for r in cy if r["status"] == "已取消"})
    paid_orders = kpi["orders"]["value"]
    funnel = [
        {"stage": "提交订单", "count": total_orders},
        {"stage": "有效订单（未取消）", "count": total_orders - cancelled},
        {"stage": "完成支付", "count": paid_orders},
    ]
    for i, stage in enumerate(funnel):
        stage["rate"] = stage["count"] / funnel[0]["count"] * 100 if funnel[0]["count"] else 0.0
        stage["step_rate"] = (
            stage["count"] / funnel[i - 1]["count"] * 100 if i > 0 and funnel[i - 1]["count"] else 100.0
        )

    # ---------- 月度目标达成（去年同月 × TARGET_FACTOR）；去年完全无数据时按当年反推，避免目标虚高
    ly_has_data = any(year_num == ly_year for year_num, _ in month_gmv)
    targets = []
    if ly_has_data:
        for month_num in range(1, last_month_num + 1):
            cur = month_gmv.get((c_year, month_num), 0.0)
            base = month_gmv.get((ly_year, month_num))
            if base is None:  # 去年个别月份无数据时，按当年反推，避免目标虚高或为 0
                base = cur / TARGET_FACTOR if cur else 0.0
            target = base * TARGET_FACTOR
            targets.append(
                {
                    "month": f"{c_year}-{month_num:02d}",
                    "gmv": cur,
                    "target": target,
                    "rate": (cur / target * 100) if target else 0.0,
                }
            )

    metrics = {
        "period": {
            "start": months_all[0],
            "end": last_month,
            "current_year": c_year,
            "last_year": ly_year,
            "months": len(months_all),
            "records": len(records),
        },
        "kpi": kpi,
        "monthly": monthly,
        "monthly_compare": monthly_compare,
        "categories": categories,
        "regions": regions,
        "channels": channels,
        "funnel": funnel,
        "targets": targets,
        "totals": {
            "gmv_cy": cy_agg["gmv"],
            "gmv_ly": ly_agg["gmv"],
            "paid_orders_cy": cy_agg["orders"],
            "customers_cy": len({r["customer_id"] for r in cy if r["status"] == "已支付"}),
        },
    }
    metrics["insights"] = build_insights(metrics)
    return metrics


def build_insights(m: dict) -> list[dict]:
    """从数字里长出结论 —— 每条都可回溯到上面的指标，不是套话。"""
    out: list[dict] = []
    kpi = m["kpi"]
    yoy = kpi["gmv"]["yoy"]

    if yoy is not None:
        trend = "增长" if yoy >= 0 else "下滑"
        out.append(
            {
                "level": "info" if yoy >= 0 else "warn",
                "title": f"整体规模同比{trend} {abs(yoy):.1f}%",
                "detail": (
                    f"{m['period']['current_year']} 年累计 GMV ¥{kpi['gmv']['value']:,.0f}，"
                    f"去年同期 ¥{m['totals']['gmv_ly']:,.0f}；"
                    f"客单价同比 {(kpi['aov']['yoy'] or 0):+.1f}%，"
                    f"订单量同比 {(kpi['orders']['yoy'] or 0):+.1f}%。"
                ),
            }
        )

    cats = [c for c in m["categories"] if c["yoy"] is not None]
    if cats:
        best = max(cats, key=lambda c: c["yoy"])
        worst = min(cats, key=lambda c: c["yoy"])
        out.append(
            {
                "level": "good",
                "title": f"{best['name']} 是同比增幅最大的品类（{best['yoy']:+.1f}%）",
                "detail": (
                    f"贡献 GMV ¥{best['gmv']:,.0f}，占比 {best['share']:.1f}%。"
                    + (f"同期 {worst['name']} 同比 {worst['yoy']:+.1f}%，是需要单独复盘的对象。" if worst["yoy"] < 0 else "")
                ),
            }
        )
        if worst["yoy"] < 0:
            out.append(
                {
                    "level": "warn",
                    "title": f"{worst['name']} 同比下滑 {abs(worst['yoy']):.1f}%",
                    "detail": (
                        f"GMV 由去年同期 ¥{worst['ly_gmv']:,.0f} 降至 ¥{worst['gmv']:,.0f}，占比 {worst['share']:.1f}%。"
                        f"建议核查单价、动销 SKU 数与渠道铺货情况。"
                    ),
                }
            )

    weak = [t for t in m["targets"] if t["rate"] < 100]
    if weak:
        weakest = min(weak, key=lambda t: t["rate"])
        out.append(
            {
                "level": "warn",
                "title": f"{weakest['month']} 目标达成率最低（{weakest['rate']:.0f}%）",
                "detail": (
                    f"当月 GMV ¥{weakest['gmv']:,.0f}，目标 ¥{weakest['target']:,.0f}，缺口 ¥{weakest['target'] - weakest['gmv']:,.0f}；"
                    f"{len(m['targets']) - len(weak)}/{len(m['targets'])} 个月已达标，缺口集中在 {len(weak)} 个月。"
                ),
            }
        )

    if m["regions"]:
        top = m["regions"][0]
        out.append(
            {
                "level": "info",
                "title": f"{top['name']} 是最大市场，占比 {top['share']:.1f}%",
                "detail": (
                    f"前两大区域合计占 {sum(r['share'] for r in m['regions'][:2]):.1f}%，"
                    + ("区域集中度偏高，建议评估长尾市场的投入产出。" if top["share"] > 30 else "区域分布相对均衡。")
                ),
            }
        )

    if m["channels"]:
        high_aov = max(m["channels"], key=lambda c: c["aov"])
        biggest = m["channels"][0]
        out.append(
            {
                "level": "good",
                "title": f"{high_aov['name']} 客单价最高（¥{high_aov['aov']:,.0f}）",
                "detail": (
                    f"是 {biggest['name']}（¥{biggest['aov']:,.0f}）的 "
                    f"{high_aov['aov'] / biggest['aov']:.1f} 倍。"
                    f"但 {high_aov['name']} 仅占 GMV {high_aov['share']:.1f}%，存在提升空间。"
                ),
            }
        )

    funnel = m["funnel"]
    if len(funnel) >= 3 and funnel[0]["count"]:
        lost = funnel[0]["count"] - funnel[2]["count"]
        out.append(
            {
                "level": "info" if funnel[2]["rate"] > 75 else "warn",
                "title": f"下单到支付的转化率 {funnel[2]['rate']:.1f}%",
                "detail": (
                    f"{m['period']['current_year']} 年共 {lost:,} 笔订单未完成支付，"
                    f"其中取消 {funnel[0]['count'] - funnel[1]['count']:,} 笔。"
                    "若转化率提升 5 个百分点，按当前客单价可多出约 "
                    f"¥{(funnel[0]['count'] * 0.05 * m['kpi']['aov']['value']):,.0f} GMV。"
                ),
            }
        )

    return out
