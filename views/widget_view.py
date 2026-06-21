"""デスクトップウィジェット用の表示（?view=widget）
負荷の積み上げ棒＋折れ線・カテゴリのドーナツ・月次カレンダーを中心に表示。
"""
import calendar as cal_mod
from datetime import datetime, timedelta, date
from collections import defaultdict

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

import database as db
from event_parser import parse_event
from calendar_style import category_style
from ui_helpers import parse_dt, load_to_tint, JST, iso_week_label
from style import PALETTE, CHART

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def render(events, scorer):
    now = datetime.now(JST)
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
        f"<div style='width:24px;height:24px;border-radius:6px;background:#141414;color:#FCFBF9;"
        f"display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px'>I</div>"
        f"<b style='font-size:15px'>Ike</b>"
        f"<span class='tmeta' style='margin-left:auto'>{now:%-m/%-d (%a) %H:%M}</span></div>",
        unsafe_allow_html=True)

    summary = scorer.summarize(events)

    # ── 今日の集中（ポモドーロ）──
    pstats = db.pomodoro_stats()
    todos_open = len(db.get_todos(include_completed=False))
    st.markdown(
        f"<div style='display:flex;gap:6px;margin-bottom:6px'>"
        f"<div style='flex:1;background:#1C1C19;color:#FCFBF9;border-radius:5px;padding:6px 8px;text-align:center'>"
        f"<div style='font-size:9px;color:#B6B4AB'>今日の集中</div>"
        f"<div style='font-size:15px;font-weight:900'>🍅 {pstats['today_min']:.0f}分</div></div>"
        f"<div style='flex:1;background:#1C1C19;color:#FCFBF9;border-radius:5px;padding:6px 8px;text-align:center'>"
        f"<div style='font-size:9px;color:#B6B4AB'>90日負荷</div>"
        f"<div style='font-size:15px;font-weight:900'>{summary['total']}</div></div>"
        f"<div style='flex:1;background:#1C1C19;color:#FCFBF9;border-radius:5px;padding:6px 8px;text-align:center'>"
        f"<div style='font-size:9px;color:#B6B4AB'>ToDo</div>"
        f"<div style='font-size:15px;font-weight:900'>{todos_open}</div></div></div>",
        unsafe_allow_html=True)

    # ── 週次 積み上げ棒＋折れ線 ──
    st.markdown("<div class='sec-label' style='margin:4px 0 2px'>週次の負荷</div>", unsafe_allow_html=True)
    _weekly(events, scorer)

    # ── カテゴリ ドーナツ ──
    st.markdown("<div class='sec-label' style='margin:8px 0 2px'>カテゴリ別</div>", unsafe_allow_html=True)
    _donut(summary)

    # ── 月次カレンダー ──
    st.markdown(f"<div class='sec-label' style='margin:8px 0 2px'>{now.year}年 {now.month}月</div>",
                unsafe_allow_html=True)
    _mini_month(events, scorer)


def _weekly(events, scorer):
    if not events:
        st.caption("データなし")
        return
    week_cat = defaultdict(lambda: defaultdict(float))
    week_total = defaultdict(float)
    for e in events:
        d = parse_dt(e["start"])
        if not d:
            continue
        y, w, _ = d.isocalendar()
        wk = f"{y}-W{w:02d}"
        sc = scorer.score_event(e["title"], "", e["description"])
        if sc <= 0:
            continue
        week_cat[wk][scorer.get_category(e["title"])] += sc
        week_total[wk] += sc
    weeks = sorted(week_total.keys())[:10]
    if not weeks:
        st.caption("データなし")
        return
    labels = [iso_week_label(int(w.split("-W")[0]), int(w.split("-W")[1])) for w in weeks]
    cat_tot = defaultdict(float)
    for wk in weeks:
        for c, v in week_cat[wk].items():
            cat_tot[c] += v
    top = [c for c, _ in sorted(cat_tot.items(), key=lambda x: -x[1])[:5]]
    fig = go.Figure()
    for i, c in enumerate(top):
        fig.add_bar(x=labels, y=[week_cat[wk].get(c, 0) for wk in weeks],
                    name=c, marker_color=PALETTE[i % len(PALETTE)], opacity=0.5)
    fig.add_trace(go.Scatter(x=labels, y=[week_total[wk] for wk in weeks],
                  mode="lines+markers", line=dict(color=CHART["total"], width=2.5),
                  marker=dict(size=4, color=CHART["total"]), name="合計"))
    fig.update_layout(
        barmode="stack", height=150, margin=dict(t=4, b=4, l=4, r=4),
        paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=9), showlegend=False,
        xaxis=dict(showgrid=False, tickfont=dict(size=9, color=CHART["font"])),
        yaxis=dict(showgrid=True, gridcolor=CHART["grid"], tickfont=dict(size=8)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _donut(summary):
    if not summary["by_category"]:
        st.caption("データなし")
        return
    items = list(summary["by_category"].items())[:6]
    df = pd.DataFrame([{"c": k, "v": round(v, 1)} for k, v in items])
    fig = px.pie(df, values="v", names="c", hole=0.62, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="inside", textinfo="percent",
                      marker=dict(line=dict(color="#E7E5E0", width=1.5)))
    fig.update_layout(
        height=170, margin=dict(t=4, b=4, l=4, r=4), paper_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=9),
        legend=dict(orientation="v", font=dict(size=9), x=1, y=0.5),
        annotations=[dict(text=f"{summary['total']}", x=0.5, y=0.5,
                          font=dict(size=16, color=CHART["ink"]), showarrow=False)])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _mini_month(events, scorer):
    today = datetime.now(JST).date()
    by_day = defaultdict(lambda: {"load": 0.0, "evs": []})
    for e in events:
        d = parse_dt(e["start"])
        if d:
            sc = scorer.score_event(e["title"], "", e["description"])
            by_day[d.date()]["load"] += sc
            by_day[d.date()]["evs"].append(parse_event(e))
    max_load = max((v["load"] for v in by_day.values()), default=1) or 1

    cal_mod.setfirstweekday(cal_mod.MONDAY)
    weeks = cal_mod.monthcalendar(today.year, today.month)
    head = "".join(f"<div style='text-align:center;font-size:8px;color:#8A8880'>{w}</div>"
                   for w in WEEKDAY_JA)
    cells = []
    for week in weeks:
        for i, day in enumerate(week):
            if day == 0:
                cells.append("<div></div>")
                continue
            d = date(today.year, today.month, day)
            info = by_day.get(d, {"load": 0.0, "evs": []})
            tint = load_to_tint(info["load"], max_load)
            is_today = d == today
            # その日の最初の予定の色で小さなドット
            dot = ""
            if info["evs"]:
                bg, _, _ = category_style(info["evs"][0].get("title", ""))
                dot = f"<div style='width:5px;height:5px;border-radius:50%;background:{bg};margin:1px auto 0'></div>"
            dn = (f"<span style='background:#141414;color:#FCFBF9;border-radius:3px;padding:0 3px'>{day}</span>"
                  if is_today else str(day))
            cells.append(
                f"<div style='min-height:26px;border-radius:4px;background:{tint};"
                f"border:1px solid rgba(20,20,20,0.10);text-align:center;font-size:10px;"
                f"font-weight:700;padding-top:2px'>{dn}{dot}</div>")
    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:2px'>{head}</div>"
        f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px'>{''.join(cells)}</div>",
        unsafe_allow_html=True)
    st.caption("赤いほど負荷大 · ●は予定")
