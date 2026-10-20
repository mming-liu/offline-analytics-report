"""生成一份带真实经营特征的订单明细，用于演示离线分析。

刻意埋进数据的「故事」（报告里会被自动识别出来）：
  · 整体同比 +20% 左右，但 3 月因缺货出现明显下跌
  · 数码配件 7 月上新后高速增长，成为同比增幅最大的品类
  · 清洁用品同比下滑，需要复盘
  · 线下门店渠道占比高但客单价低，小程序客单价最高
  · Q4 季节性高峰
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

CATEGORIES = {
    "办公耗材": (18, 240, 0.30),
    "数码配件": (45, 680, 0.34),
    "清洁用品": (12, 160, 0.20),
    "包装材料": (8, 120, 0.16),
}
PRODUCTS = {
    "办公耗材": ["A4 复印纸", "中性笔 0.5mm", "文件夹", "订书机", "便利贴"],
    "数码配件": ["Type-C 数据线", "无线鼠标", "蓝牙键盘", "USB 集线器", "氮化镓充电器"],
    "清洁用品": ["洗手液 500ml", "抽纸 3 层", "垃圾袋", "消毒湿巾"],
    "包装材料": ["气泡膜", "封箱胶带", "瓦楞纸箱", "珍珠棉"],
}
REGIONS = {"华东": 0.34, "华北": 0.22, "华南": 0.21, "西南": 0.13, "华中": 0.10}
CHANNELS = {"线下门店": 0.31, "天猫": 0.24, "京东": 0.20, "官网": 0.15, "小程序": 0.10}
STATUS = [("已支付", 0.82), ("待支付", 0.08), ("已取消", 0.07), ("退款", 0.03)]

# 月度因子：季节性 + 故事线（2026 年 3 月缺货、7 月新品放量）
MONTH_FACTOR_2025 = {1: 0.92, 2: 0.78, 3: 1.02, 4: 0.98, 5: 1.05, 6: 1.10, 7: 1.02, 8: 1.06, 9: 1.15, 10: 1.18, 11: 1.35, 12: 1.42}
MONTH_FACTOR_2026 = {1: 1.10, 2: 0.95, 3: 0.72, 4: 1.05, 5: 1.12, 6: 1.18, 7: 1.32, 8: 1.28, 9: 1.36, 10: 1.30, 11: 1.50, 12: 1.58}


def _weighted(rng: random.Random, mapping: dict[str, float]) -> str:
    items = list(mapping.items())
    total = sum(w for _, w in items)
    point = rng.uniform(0, total)
    acc = 0.0
    for name, weight in items:
        acc += weight
        if point <= acc:
            return name
    return items[-1][0]


def _status(rng: random.Random) -> str:
    point = rng.random()
    acc = 0.0
    for name, weight in STATUS:
        acc += weight
        if point <= acc:
            return name
    return STATUS[-1][0]


def make_dataset(path: str | Path, end_year: int = 2026, end_month: int = 9, seed: int = 20261020) -> dict:
    rng = random.Random(seed)
    rows: list[list] = []
    order_seq = 0
    months: list[tuple[int, int]] = []
    year, month = 2025, 1
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1

    for year, month in months:
        factor = (MONTH_FACTOR_2025 if year == 2025 else MONTH_FACTOR_2026)[month]
        base_count = int(168 * factor * (1.06 if year == 2026 else 1.0))
        days_in_month = (date(year + (month == 12), month % 12 + 1, 1) - date(year, month, 1)).days

        for _ in range(base_count):
            order_seq += 1
            day = rng.randint(1, days_in_month)
            category = _weighted(rng, {k: v[2] for k, v in CATEGORIES.items()})

            # 品类自身的增长节奏：数码配件 2026 年 7 月上新放量（抢占办公耗材预算）；清洁用品逐年走弱
            if category == "办公耗材" and (year, month) >= (2026, 7) and rng.random() < 0.25:
                category = "数码配件"
            if category == "清洁用品" and year == 2026 and rng.random() < 0.15:
                category = "办公耗材"

            low, high, _ = CATEGORIES[category]
            unit_price = round(rng.uniform(low, high), 2)
            qty = max(1, int(rng.gauss(4 if category == "办公耗材" else 2.5, 2)))

            region = _weighted(rng, REGIONS)
            channel = _weighted(rng, CHANNELS)
            status = _status(rng)

            # 小程序客单价更高（买整套的人多）
            if channel == "小程序" and rng.random() < 0.4:
                qty += rng.randint(1, 3)

            rows.append(
                [
                    f"SO{year}{order_seq:06d}",
                    date(year, month, day).isoformat(),
                    region,
                    channel,
                    category,
                    rng.choice(PRODUCTS[category]),
                    qty,
                    f"{unit_price:.2f}",
                    f"{round(qty * unit_price, 2):.2f}",
                    f"C{rng.randint(10000, 12999)}",
                    status,
                ]
            )

    rows.sort(key=lambda r: r[1])
    header = [
        "order_id", "order_date", "region", "channel", "category", "product",
        "qty", "unit_price", "amount", "customer_id", "status",
    ]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)

    return {"path": str(path), "rows": len(rows), "months": len(months), "period": f"{months[0][0]}-{months[0][1]:02d} ~ {months[-1][0]}-{months[-1][1]:02d}"}


if __name__ == "__main__":
    import json

    info = make_dataset(Path(__file__).resolve().parent.parent / "data" / "sales_orders.csv")
    print(json.dumps(info, ensure_ascii=False, indent=2))
