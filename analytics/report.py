"""生成汇报级 HTML 报表：KPI + SVG 图表 + 自动结论 + 口径说明，单文件可离线打开/打印。"""
from __future__ import annotations

import html
import time

from . import charts as C
from .metrics import TARGET_FACTOR

E = html.escape

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f4f6fa;color:#1f2937;font:14px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:26px 20px 64px}
.num{font-variant-numeric:tabular-nums}
.hero{position:relative;background:linear-gradient(120deg,#123a63 0%,#1d5f9c 62%,#2a6fae 100%);color:#fff;border-radius:16px;padding:34px 34px 28px;box-shadow:0 12px 32px rgba(18,58,99,.2);overflow:hidden}
.hero:after{content:"";position:absolute;right:-70px;top:-80px;width:280px;height:280px;border-radius:50%;background:rgba(255,255,255,.06)}
.hero .tag{display:inline-block;font-size:11.5px;letter-spacing:.2em;background:rgba(255,255,255,.16);padding:5px 11px;border-radius:4px}
.hero h1{margin:16px 0 8px;font-size:27px;font-weight:700;letter-spacing:.6px}
.hero .meta{margin:0;color:#c7dcf1;font-size:12.5px;line-height:1.9}
.hero .stamp{position:absolute;right:34px;bottom:26px;text-align:right;font-size:11.5px;color:#a9c6e2;line-height:1.8}
section{background:#fff;border:1px solid #e4eaf2;border-radius:14px;padding:24px 26px;margin-top:18px;box-shadow:0 2px 8px rgba(24,42,66,.045)}
section.tight{padding-bottom:14px}
h2{font-size:16px;margin:0 0 3px;color:#123a63;display:flex;align-items:center;gap:9px}
h2 .idx{width:24px;height:24px;line-height:24px;text-align:center;background:#123a63;color:#fff;border-radius:6px;font-size:12px;font-weight:600}
h2 small{font-weight:400;color:#8a9aae;font-size:12px;margin-left:auto;letter-spacing:.02em}
.sub{color:#7b8a9c;font-size:12.5px;margin:6px 0 18px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:840px){.grid2{grid-template-columns:1fr}}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:14px;margin-top:18px}
.kpi{background:#fff;border:1px solid #e4eaf2;border-radius:13px;padding:16px 18px 13px;box-shadow:0 2px 8px rgba(24,42,66,.045);position:relative;overflow:hidden}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#1d5f9c;opacity:.85}
.kpi .lbl{font-size:12px;color:#7b8a9c;letter-spacing:.02em}
.kpi .val{font-size:25px;font-weight:700;color:#123a63;line-height:1.3;margin-top:3px;letter-spacing:-.5px}
.kpi .val small{font-size:12.5px;font-weight:500;color:#7b8a9c;margin-left:2px}
.kpi .foot{display:flex;align-items:center;justify-content:space-between;margin-top:7px;gap:8px}
.badge{font-size:11.5px;font-weight:600;padding:2px 8px;border-radius:20px;white-space:nowrap}
.badge.flat{color:#7b8a9c;background:#f1f5fa}
.insights{display:grid;gap:11px}
.insight{display:grid;grid-template-columns:4px 1fr;gap:14px;background:#fafcff;border:1px solid #e9eff7;border-radius:10px;padding:13px 16px 13px 0;overflow:hidden}
.insight .bar{background:#1d4e89;border-radius:0 3px 3px 0}
.insight.warn .bar{background:#c2410c}
.insight.good .bar{background:#0f8a4d}
.insight .t{font-size:13.5px;font-weight:600;color:#123a63;margin:0 0 3px}
.insight .d{font-size:12.5px;color:#5b6b7f;margin:0}
.insight.warn .t{color:#9a3412}
.insight.good .t{color:#0f6b3d}
table{width:100%;border-collapse:collapse;font-size:12.8px}
th{background:#f4f7fb;color:#4b5c71;font-weight:600;text-align:right;padding:9px 10px;border-bottom:2px solid #e1e9f2;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
td{padding:8px 10px;border-bottom:1px solid #eff3f8;text-align:right}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fafcff}
.up{color:#d64545;font-weight:600}
.down{color:#2e9e6b;font-weight:600}
.muted{color:#93a3b5}
.tag{display:inline-block;font-size:10.5px;padding:0 6px;border-radius:4px;background:#eef2f7;color:#5b6b7f;font-weight:600}
.tag.a{background:#e8f0fb;color:#123a63}
.tag.b{background:#eef7f0;color:#0f6b3d}
.tag.c{background:#f4f1fa;color:#5b4b8a}
.prog{margin:0}
.prog .row{display:grid;grid-template-columns:72px 1fr 96px;gap:14px;align-items:center;padding:6px 0;font-size:12.5px}
.prog .track{height:10px;background:#f1f5fa;border-radius:6px;overflow:hidden;position:relative}
.prog .fill{height:100%;border-radius:6px}
.prog .mono{font-variant-numeric:tabular-nums;text-align:right;color:#41536b}
.notes{font-size:12.5px;color:#5b6b7f;line-height:2}
.notes b{color:#123a63}
.notes ol{margin:6px 0 0;padding-left:20px}
.notes li{margin-bottom:5px}
footer{margin-top:22px;color:#8a9aae;font-size:11.5px;text-align:center;line-height:1.9}
.chartbox{margin-top:4px}
.legend-inline{font-size:11.5px;color:#8a9aae;margin-top:6px}
@media print{
  body{background:#fff}
  .wrap{max-width:none;padding:0}
  section,.hero,.kpi{box-shadow:none;break-inside:avoid}
  section{margin-top:12px}
}
"""


def _badge(pct: float | None, label: str = "同比") -> str:
    if pct is None:
        return '<span class="badge flat">无同期数据</span>'
    up = pct >= 0
    color = C.UP if up else C.DOWN
    arrow = "▲" if up else "▼"
    return f'<span class="badge" style="color:{color};background:{color}14">{arrow} {label} {abs(pct):.1f}%</span>'


def _delta_cell(pct: float | None) -> str:
    if pct is None:
        return '<span class="muted">—</span>'
    cls = "up" if pct >= 0 else "down"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {abs(pct):.1f}%</span>'


def build_html(m: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    kpi = m["kpi"]
    period = m["period"]
    y = period["current_year"]

    # ---------- KPI
    spark_values = [item["gmv"] for item in m["monthly"][-8:]]
    kpi_cards = [
        ("累计 GMV", f'¥{kpi["gmv"]["value"] / 1e4:,.1f}<small>万</small>', _badge(kpi["gmv"]["yoy"]), True),
        ("累计订单数", f'{kpi["orders"]["value"]:,}<small>单</small>', _badge(kpi["orders"]["yoy"]), True),
        ("客单价", f'¥{kpi["aov"]["value"]:,.0f}', _badge(kpi["aov"]["yoy"]), False),
        ("销量", f'{kpi["qty"]["value"]:,}<small>件</small>', _badge(kpi["qty"]["yoy"]), False),
        (f'{period["end"]} 单月 GMV', f'¥{kpi["last_month_gmv"]["value"] / 1e4:,.1f}<small>万</small>', _badge(kpi["last_month_gmv"]["mom"], "环比"), False),
        ("订单支付率", f'{kpi["paid_rate"]["value"]:.1f}<small>%</small>', '<span class="badge flat">已支付 / 全部下单</span>', False),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="lbl">{E(label)}</div><div class="val num">{value}</div>'
        f'<div class="foot">{badge}{C.sparkline(spark_values) if with_spark else ""}</div></div>'
        for label, value, badge, with_spark in kpi_cards
    )

    # ---------- 执行摘要
    insight_html = "".join(
        f'<div class="insight {i["level"]}"><div class="bar"></div><div><p class="t">{E(i["title"])}</p>'
        f'<p class="d">{E(i["detail"])}</p></div></div>'
        for i in m["insights"]
    )

    # ---------- 趋势图（按月对齐，两年并排）
    monthly = m["monthly"]
    cmp_data = m["monthly_compare"]
    trend = C.line_chart(
        cmp_data["labels"],
        [
            {"name": f"{y} 年", "values": cmp_data["cy"], "color": C.PRIMARY, "width": 2.6},
            {"name": f"{y - 1} 年", "values": cmp_data["ly"], "color": "#9fb6cd", "dashed": True, "width": 1.8},
        ],
        value_fmt=C.fmt_money,
    )

    # ---------- 品类
    cat_items = [{"label": c["name"], "value": c["gmv"]} for c in m["categories"]]
    donut = C.donut(cat_items, center_top="GMV 合计", center_value=C.fmt_money(kpi["gmv"]["value"]))
    cat_rows = "".join(
        f'<tr><td>{E(c["name"])} <span class="tag {c["abc"].lower()}">{c["abc"]}</span></td>'
        f'<td class="num">{c["gmv"]:,.0f}</td><td class="num">{c["share"]:.1f}%</td>'
        f'<td class="num">{c["orders"]:,}</td><td class="num">¥{c["aov"]:,.0f}</td>'
        f'<td>{_delta_cell(c["yoy"])}</td></tr>'
        for c in m["categories"]
    )

    pareto = C.pareto_chart([{"label": c["name"], "value": c["gmv"], "cum_share": c["cum_share"], "abc": c["abc"]} for c in m["categories"]])

    # ---------- 区域 / 渠道
    region_bar = C.bar_h(
        [{"label": r["name"], "value": r["gmv"], "share": r["share"]} for r in m["regions"]],
        value_fmt=C.fmt_money,
    )
    channel_bar = C.bar_h(
        [{"label": c["name"], "value": c["gmv"], "share": c["share"]} for c in m["channels"]],
        value_fmt=C.fmt_money,
        color="#3d8bfd",
    )
    channel_rows = "".join(
        f'<tr><td>{E(c["name"])}</td><td class="num">¥{c["aov"]:,.0f}</td>'
        f'<td class="num">{c["orders"]:,}</td><td>{_delta_cell(c["yoy"])}</td></tr>'
        for c in m["channels"]
    )

    # ---------- 漏斗
    funnel = C.funnel_chart(m["funnel"])

    # ---------- 目标达成
    if m["targets"]:
        prog_rows = []
        for t in m["targets"]:
            rate = t["rate"]
            color = C.UP if rate >= 100 else ("#e0a458" if rate >= 90 else "#c2410c")
            width = min(rate, 118)
            prog_rows.append(
                f'<div class="row"><div class="muted num">{t["month"]}</div>'
                f'<div class="track"><div class="fill" style="width:{width / 1.18:.1f}%;background:{color}"></div></div>'
                f'<div class="mono num">{rate:.0f}% <span class="muted" style="font-weight:400">/ ¥{t["target"] / 1e4:.0f}万</span></div></div>'
            )
        achieved = len([t for t in m["targets"] if t["rate"] >= 100])
        target_section = f"""
  <section>
    <h2><span class="idx">9</span>月度目标达成 <small>{achieved}/{len(m['targets'])} 个月达标（目标 = 去年同月 × {TARGET_FACTOR:g}）</small></h2>
    <p class="sub">红色为超额达成，琥珀色为接近达标（≥90%），橙色为明显缺口。</p>
    <div class="prog">{''.join(prog_rows)}</div>
  </section>"""
    else:
        target_section = """
  <section>
    <h2><span class="idx">9</span>月度目标达成</h2>
    <p class="sub">数据区间内没有去年同期记录，无法测算同比目标；补充上一年明细后本节将自动生成。</p>
  </section>"""

    # ---------- 建议
    suggestions = [
        "对同比下滑的品类做单品级动销诊断，区分「价格问题」「缺货问题」「铺货问题」，不要用整体打折掩盖结构性下滑。",
        "把高客单价渠道的成交路径拆出来（选品组合、连带率、优惠门槛），复制到占比最高但客单价低的渠道。",
        "未达成目标的月份需补齐归因：是流量缺口还是转化缺口，两者对应的动作完全不同。",
        "把复查口径固定下来（GMV 是否含退款、订单数是否含取消），下期报表才能横向对比。",
    ]
    suggestions_html = "".join(f"<li>{E(s)}</li>" for s in suggestions)

    generated = time.strftime("%Y-%m-%d %H:%M:%S")
    source = meta.get("source", "sales_orders.csv")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>经营数据复盘报告 · {E(period['start'])} 至 {E(period['end'])}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="tag">离线数据分析 · 经营复盘</div>
    <h1>订单经营数据复盘报告</h1>
    <p class="meta">
      分析区间：{E(period['start'])} ~ {E(period['end'])}（{period['months']} 个月 / {period['records']:,} 条明细）<br>
      数据来源：{E(source)} ｜ 同比基准：{period['last_year']} 年同期 ｜ 口径：GMV 仅计已支付订单
    </p>
    <div class="stamp">本地离线生成<br>{generated}</div>
  </div>

  <div class="kpis">{kpi_html}</div>

  <section>
    <h2><span class="idx">1</span>执行摘要 <small>结论由数据自动生成，可逐条回溯到下方图表</small></h2>
    <div class="insights">{insight_html}</div>
  </section>

  <section>
    <h2><span class="idx">2</span>月度 GMV 趋势 <small>{y} 年 vs {y - 1} 年 · 按月对齐</small></h2>
    <p class="sub">实线为当年，虚线为去年同期，两者同一月份刻度对比。{y} 年 10-12 月无数据属正常（分析区间截止 {E(period['end'])}）。</p>
    <div class="chartbox">{trend}</div>
  </section>

  <div class="grid2">
    <section>
      <h2><span class="idx">3</span>品类结构</h2>
      <p class="sub">各品类 GMV 占比，用于判断收入是否过度依赖单一品类。</p>
      {donut}
    </section>
    <section>
      <h2><span class="idx">4</span>品类明细与同比</h2>
      <p class="sub">ABC 按帕累托跨线规则分级：把自己累计进 70% 之内的为 A 类核心，90% 之内为 B 类，其余为 C 类。</p>
      <table>
        <thead><tr><th>品类</th><th>GMV</th><th>占比</th><th>订单</th><th>客单价</th><th>同比</th></tr></thead>
        <tbody>{cat_rows}</tbody>
      </table>
    </section>
  </div>

  <section>
    <h2><span class="idx">5</span>品类贡献度（帕累托） <small>累计 80% 分界线</small></h2>
    <p class="sub">柱为各品类 GMV，折线为累计占比。落在 80% 线之前的品类即核心盘，资源应优先保障。</p>
    <div class="chartbox">{pareto}</div>
  </section>

  <div class="grid2">
    <section>
      <h2><span class="idx">6</span>区域表现</h2>
      <p class="sub">按 GMV 排序，右侧为占比。</p>
      {region_bar}
    </section>
    <section>
      <h2><span class="idx">7</span>渠道表现</h2>
      <p class="sub">按 GMV 排序；客单价差异见下表，是渠道策略的关键输入。</p>
      {channel_bar}
      <table style="margin-top:14px">
        <thead><tr><th>渠道</th><th>客单价</th><th>订单</th><th>同比</th></tr></thead>
        <tbody>{channel_rows}</tbody>
      </table>
    </section>
  </div>

  <section>
    <h2><span class="idx">8</span>订单转化漏斗 <small>{y} 年累计</small></h2>
    <p class="sub">从下单到支付的流失环节。取消订单属于可控流失，待支付未转化属于可挽回流失。</p>
    <div class="chartbox">{funnel}</div>
  </section>

  {target_section}

  <section>
    <h2><span class="idx">10</span>下一步建议</h2>
    <p class="sub">基于上面的结论，给出可执行的动作方向，不涉及具体商务判断。</p>
    <div class="notes"><ol>{suggestions_html}</ol></div>
  </section>

  <section>
    <h2><span class="idx">11</span>数据口径与交付说明</h2>
    <div class="notes">
      <b>指标定义</b>
      <ol>
        <li>GMV：status = 已支付 的订单金额合计，不含取消与退款订单。</li>
        <li>订单数：按 order_id 去重计数。</li>
        <li>客单价：GMV ÷ 订单数，保留整数。</li>
        <li>同比：{y} 年累计 vs {y - 1} 年同期；环比：{period['end']} vs 上月。</li>
        <li>目标：去年同月 GMV × {TARGET_FACTOR:g}，仅用于衡量节奏，不代表客户实际预算。</li>
      </ol>
      <b style="display:block;margin-top:10px">技术说明</b>
      <div>本报表由 Python 标准库直接生成静态 HTML，图表为内联 SVG，<b>不依赖任何 JS 图表库与网络资源</b>；
      拷贝单个 HTML 文件即可在任何电脑打开、可直接打印为 PDF。原始明细全程留在本机，未上传。</div>
    </div>
  </section>

  <footer>
    报告生成时间 {generated} ｜ 明细 {period['records']:,} 条 ｜ 分析区间 {E(period['start'])} ~ {E(period['end'])}<br>
    如需调整口径、增加维度或改为周期性自动出报表，可在现有脚本上扩展，无需重做。
  </footer>
</div>
</body>
</html>
"""
