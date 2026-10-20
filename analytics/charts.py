"""纯 SVG 图表：不依赖任何 JS 图表库，单文件 HTML 可直接打开、可打印。

配色遵循国内习惯：增长用红、下滑用绿（与欧美相反）。
"""
from __future__ import annotations

import math

PRIMARY = "#1d4e89"
UP = "#d64545"
DOWN = "#2e9e6b"
NEUTRAL = "#94a3b8"
PALETTE = ["#1d4e89", "#3d8bfd", "#5fa8d3", "#7bc0a3", "#e0a458", "#c96e6e", "#8e7cc3", "#4aa8a1"]
FONT = "system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif"
GRID = "#e8eef6"
AXIS_TEXT = "#94a3b8"
TEXT = "#334155"


def fmt_short(value: float) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:,.0f}"


def fmt_money(value: float) -> str:
    return "¥" + fmt_short(value)


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for mult in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= mult * exp:
            return mult * exp
    return 10 * exp


def _svg(width: int, height: int, body: list[str], aria: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{aria}" '
        f'style="display:block;font-family:{FONT}">'
        + "".join(body)
        + "</svg>"
    )


def _legend(entries: list[tuple[str, str]], x: int, y: int) -> list[str]:
    out = []
    cursor = x
    for name, color in entries:
        out.append(f'<rect x="{cursor}" y="{y - 9}" width="10" height="10" rx="2.5" fill="{color}"/>')
        out.append(f'<text x="{cursor + 15}" y="{y}" font-size="11.5" fill="{TEXT}">{name}</text>')
        cursor += 18 + len(name) * 12
    return out


def line_chart(
    labels: list[str],
    series: list[dict],
    *,
    width: int = 800,
    height: int = 310,
    y_fmt=fmt_short,
    value_fmt=None,
    legend: bool = True,
) -> str:
    """多系列折线图。series = [{"name","values","color","dashed"}]"""
    pad_l, pad_r, pad_t, pad_b = 68, 30, 34 if legend else 18, 40
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    values = [v for s in series for v in s["values"] if v is not None]
    vmax = _nice_max(max(values) if values else 1)

    def X(i: int) -> float:
        return pad_l + (iw * i / max(len(labels) - 1, 1))

    def Y(v: float) -> float:
        return pad_t + ih - (v / vmax) * ih

    body: list[str] = []
    if legend:
        body += _legend([(s["name"], s["color"]) for s in series], pad_l, 16)

    for k in range(5):
        y = pad_t + ih * k / 4
        body.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        body.append(
            f'<text x="{pad_l - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{AXIS_TEXT}">{y_fmt(vmax * (1 - k / 4))}</text>'
        )

    step = max(1, len(labels) // 8)
    for i, label in enumerate(labels):
        if i % step and i != len(labels) - 1:
            continue
        short = label[2:].replace("-", "/") if len(label) > 7 else label
        body.append(
            f'<text x="{X(i):.1f}" y="{height - pad_b + 20}" text-anchor="middle" font-size="11" fill="{AXIS_TEXT}">{short}</text>'
        )

    for s in series:
        points = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s["values"]) if v is not None)
        dash = ' stroke-dasharray="5 4"' if s.get("dashed") else ""
        body.append(
            f'<polyline points="{points}" fill="none" stroke="{s["color"]}" stroke-width="{s.get("width", 2.4)}" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash}/>'
        )
        for i, v in enumerate(s["values"]):
            if v is None:
                continue
            tip = f'{labels[i]} {s["name"]} {value_fmt(v) if value_fmt else y_fmt(v)}'
            body.append(
                f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.2" fill="#fff" stroke="{s["color"]}" stroke-width="2">'
                f"<title>{tip}</title></circle>"
            )
        # 末尾点标注数值（只标主系列，避免重叠）
        if s is series[0]:
            last = next((i for i in range(len(s["values"]) - 1, -1, -1) if s["values"][i] is not None), None)
            if last is not None:
                body.append(
                    f'<text x="{X(last) - 6:.1f}" y="{Y(s["values"][last]) - 10:.1f}" text-anchor="end" font-size="11.5" '
                    f'font-weight="600" fill="{s["color"]}">{value_fmt(s["values"][last]) if value_fmt else y_fmt(s["values"][last])}</text>'
                )

    return _svg(width, height, body, "趋势折线图")


def bar_h(
    items: list[dict],
    *,
    width: int = 800,
    row_h: int = 30,
    gap: int = 14,
    label_w: int = 92,
    value_w: int = 128,
    color: str = PRIMARY,
    value_fmt=fmt_money,
    share_key: str | None = "share",
    color_by_value: bool = False,
) -> str:
    """横向条形图（适合品类/区域/渠道这类名称较长的维度）。"""
    count = max(len(items), 1)
    height = count * (row_h + gap) + 16
    bar_max = width - label_w - value_w - 24
    vmax = max((abs(i["value"]) for i in items), default=1) or 1
    body: list[str] = []

    for idx, item in enumerate(items):
        y = idx * (row_h + gap) + 8
        if item.get("color"):
            fill = item["color"]
        elif color_by_value:
            fill = UP if item["value"] >= 0 else DOWN
        else:
            fill = color
        body.append(
            f'<text x="{label_w - 12}" y="{y + row_h / 2 + 4:.1f}" text-anchor="end" font-size="12.5" fill="{TEXT}">{item["label"]}</text>'
        )
        body.append(f'<rect x="{label_w}" y="{y}" width="{bar_max}" height="{row_h}" rx="4" fill="#f1f5fa"/>')
        w = max(2.0, bar_max * abs(item["value"]) / vmax)
        body.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{row_h}" rx="4" fill="{fill}"><title>{item["label"]} {value_fmt(item["value"])}</title></rect>')
        text = value_fmt(item["value"])
        if share_key and item.get(share_key) is not None:
            text += f'　{item[share_key]:.1f}%'
        body.append(
            f'<text x="{label_w + bar_max + 12}" y="{y + row_h / 2 + 4:.1f}" font-size="12" fill="#41536b" font-weight="600">{text}</text>'
        )

    return _svg(width, height, body, "横向条形图")


def donut(
    items: list[dict],
    *,
    size: int = 250,
    thickness: int = 32,
    center_top: str = "",
    center_value: str = "",
    legend_cols: int = 1,
) -> str:
    """环形占比图 + 右侧图例。"""
    legend_w = 210
    width = size + legend_w
    height = size
    cx = cy = size / 2
    r = (size - thickness) / 2 - 6
    circumference = 2 * math.pi * r
    total = sum(i["value"] for i in items) or 1
    body: list[str] = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#f1f5fa" stroke-width="{thickness}"/>']

    offset = 0.0
    for idx, item in enumerate(items):
        frac = item["value"] / total
        dash = frac * circumference
        color = item.get("color") or PALETTE[idx % len(PALETTE)]
        body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{thickness}" '
            f'stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})" stroke-linecap="butt">'
            f'<title>{item["label"]} {item["value"]:,.0f}（{frac * 100:.1f}%）</title></circle>'
        )
        offset += dash

    if center_value:
        body.append(f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="18" font-weight="700" fill="{PRIMARY}">{center_value}</text>')
    if center_top:
        body.append(f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="11.5" fill="{AXIS_TEXT}">{center_top}</text>')

    x = size + 6
    for idx, item in enumerate(items[:8]):
        y = 34 + idx * 30
        color = item.get("color") or PALETTE[idx % len(PALETTE)]
        body.append(f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2.5" fill="{color}"/>')
        body.append(f'<text x="{x + 16}" y="{y}" font-size="12.5" fill="{TEXT}">{item["label"]}</text>')
        body.append(
            f'<text x="{width - 6}" y="{y}" text-anchor="end" font-size="12" fill="#41536b" font-weight="600">{item["value"] / total * 100:.1f}%</text>'
        )

    return _svg(width, height, body, "品类占比环形图")


def pareto_chart(
    items: list[dict],
    *,
    width: int = 800,
    height: int = 330,
    value_fmt=fmt_short,
    threshold: float = 80.0,
) -> str:
    """帕累托图：柱为各品类 GMV，折线为累计占比，虚线为 80% 参考线。"""
    pad_l, pad_r, pad_t, pad_b = 68, 56, 26, 52
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    n = max(len(items), 1)
    vmax = _nice_max(max((i["value"] for i in items), default=1))
    slot = iw / n
    bar_w = min(slot * 0.52, 62)

    body: list[str] = []
    for k in range(5):
        y = pad_t + ih * k / 4
        body.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="{GRID}"/>')
        body.append(f'<text x="{pad_l - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{AXIS_TEXT}">{value_fmt(vmax * (1 - k / 4))}</text>')
        body.append(
            f'<text x="{width - pad_r + 10}" y="{y + 4:.1f}" font-size="11" fill="{AXIS_TEXT}">{100 - k * 25}%</text>'
        )

    def Y(v: float) -> float:
        return pad_t + ih - (v / vmax) * ih

    def Yp(p: float) -> float:
        return pad_t + ih - (p / 100) * ih

    # 80% 参考线
    body.append(
        f'<line x1="{pad_l}" y1="{Yp(threshold):.1f}" x2="{width - pad_r}" y2="{Yp(threshold):.1f}" '
        f'stroke="{UP}" stroke-width="1.2" stroke-dasharray="6 4" opacity="0.75"/>'
    )
    body.append(
        f'<text x="{width - pad_r - 4}" y="{Yp(threshold) - 6:.1f}" text-anchor="end" font-size="10.5" fill="{UP}">{threshold:.0f}% 分界线</text>'
    )

    for idx, item in enumerate(items):
        cx = pad_l + slot * idx + slot / 2
        y = Y(item["value"])
        body.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{pad_t + ih - y:.1f}" rx="4" '
            f'fill="{PRIMARY}" opacity="{0.95 - idx * 0.08:.2f}"><title>{item["label"]} {value_fmt(item["value"])}</title></rect>'
        )
        body.append(f'<text x="{cx:.1f}" y="{height - pad_b + 18}" text-anchor="middle" font-size="11.5" fill="{TEXT}">{item["label"]}</text>')
        rank = item.get("abc", "")
        if rank:
            body.append(
                f'<text x="{cx:.1f}" y="{height - pad_b + 34}" text-anchor="middle" font-size="10" fill="{AXIS_TEXT}">{rank} 类</text>'
            )

    # 累计折线
    pts = []
    for idx, item in enumerate(items):
        cx = pad_l + slot * idx + slot / 2
        pts.append(f"{cx:.1f},{Yp(item.get('cum_share', 0)):.1f}")
    body.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{UP}" stroke-width="2.2" stroke-linejoin="round"/>')
    for idx, item in enumerate(items):
        cx = pad_l + slot * idx + slot / 2
        cy = Yp(item.get("cum_share", 0))
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.4" fill="#fff" stroke="{UP}" stroke-width="2"/>')
        body.append(
            f'<text x="{cx:.1f}" y="{cy - 9:.1f}" text-anchor="middle" font-size="10.5" fill="{UP}">{item.get("cum_share", 0):.0f}%</text>'
        )

    body += _legend([("GMV 贡献", PRIMARY), ("累计占比", UP)], pad_l, 16)
    return _svg(width, height, body, "品类帕累托图")


def funnel_chart(stages: list[dict], *, width: int = 800, height: int = 230) -> str:
    """转化漏斗：宽度按数量比例，右侧标转化率。"""
    cx = 300
    layer_h = 42
    gap = 7
    max_w = 400
    min_w = 90
    top = 22
    body: list[str] = []
    count0 = stages[0]["count"] if stages and stages[0]["count"] else 1

    for idx, stage in enumerate(stages):
        ratio = stage["count"] / count0
        w_top = max(min_w, max_w * (ratio + 0.12))
        next_ratio = stages[idx + 1]["count"] / count0 if idx + 1 < len(stages) else ratio * 0.88
        w_bottom = max(min_w, max_w * (next_ratio + 0.12))
        y = top + idx * (layer_h + gap)
        path = (
            f"M{cx - w_top / 2:.1f},{y} L{cx + w_top / 2:.1f},{y} "
            f"L{cx + w_bottom / 2:.1f},{y + layer_h} L{cx - w_bottom / 2:.1f},{y + layer_h} Z"
        )
        color = PALETTE[idx % len(PALETTE)]
        body.append(f'<path d="{path}" fill="{color}" opacity="{0.92 - idx * 0.12:.2f}"><title>{stage["stage"]} {stage["count"]:,}</title></path>')
        body.append(
            f'<text x="{cx}" y="{y + layer_h / 2 + 5:.1f}" text-anchor="middle" font-size="13" font-weight="600" fill="#fff">{stage["stage"]}</text>'
        )
        body.append(f'<text x="{cx + max_w / 2 + 26}" y="{y + layer_h / 2 + 5:.1f}" font-size="13" fill="{TEXT}" font-weight="600">{stage["count"]:,}</text>')
        body.append(
            f'<text x="{width - 20}" y="{y + layer_h / 2 + 5:.1f}" text-anchor="end" font-size="11.5" fill="{AXIS_TEXT}">'
            f'累计 {stage["rate"]:.1f}%'
            + (f'　单步 {stage["step_rate"]:.1f}%' if idx > 0 else "")
            + "</text>"
        )

    return _svg(width, height, body, "订单转化漏斗")


def sparkline(values: list[float], *, width: int = 120, height: int = 34, color: str = PRIMARY) -> str:
    """迷你趋势线，用于 KPI 卡片角落。"""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return ""
    vmax, vmin = max(clean), min(clean)
    span = (vmax - vmin) or 1
    pts = []
    for i, v in enumerate(clean):
        x = 4 + (width - 8) * i / (len(clean) - 1)
        y = height - 4 - ((v - vmin) / span) * (height - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="display:block;font-family:{FONT}">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
        "</svg>"
    )
