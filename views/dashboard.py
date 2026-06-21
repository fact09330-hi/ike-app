"""ダッシュボード画面"""
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

import database as db
import ai_assistant as ai
import components
from event_parser import parse_event
from ui_helpers import parse_dt, JST, priority_dot, status_badge, iso_week_label
from style import PALETTE, CHART


def _iso_week_key(dt):
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _week_label(key):
    """'2026-W23' → '6月1W'"""
    try:
        y, w = key.split("-W")
        return iso_week_label(int(y), int(w))
    except Exception:
        return key


def _fetch_needs_count():
    """要返信メール件数を取得（除外済みを差し引く）。失敗時は None。"""
    try:
        import gmail_client as gc
        if not gc.has_gmail_scope():
            return None
        client = gc.GmailClient()
        emails = client.list_needs_reply(max_results=30, mode="recent")
        dismissed = db.get_dismissed_ids()
        return sum(1 for e in emails if e.get("thread_id") not in dismissed)
    except Exception:
        return None


def render(events, scorer):
    head = st.columns([5, 1.3])
    head[0].markdown("# ダッシュボード")
    if head[1].button("🔄 更新", use_container_width=True, help="カレンダーとメールを再取得"):
        st.cache_data.clear()
        st.session_state["email_needs_count"] = _fetch_needs_count()
        st.rerun()
    sync = st.session_state.get("last_sync", "—")
    st.caption(f"{datetime.now(JST).strftime('%Y年%-m月%-d日 (%a)')} 時点 · 今後90日の負荷とプロジェクト状況　"
               f"｜　🔄 最終同期: {sync}")

    projects = db.get_projects()
    lists = db.get_lists()
    active_projects = [p for p in projects if p["status"] == "active"]
    todos = db.get_todos(include_completed=False)
    summary = scorer.summarize(events)
    total = summary["total"]
    needs = st.session_state.get("email_needs_count")

    # ── KPI（自作カードで5枚を完全に同サイズ固定）──
    cards = [
        ("IKE TASK Volume", f"{total}", "#2840E6"),
        ("負荷レベル", scorer.load_level(total, 90).split()[-1], "#E0245E"),
        ("進行中プロジェクト", f"{len(active_projects)}", "#1A9E5B"),
        ("未完了 ToDo", f"{len(todos)}", "#E8870C"),
        ("要返信メール", ("—" if needs is None else f"{needs}"), "#7C3AED"),
    ]
    html = "<div class='kpi-row' style='display:flex;gap:10px;margin-bottom:6px'>"
    for label, val, col in cards:
        html += (
            f"<div class='kpi-card' style='flex:1;height:96px;background:#1C1C19;border:1.5px solid #141414;"
            f"border-radius:6px;box-shadow:3px 3px 0 rgba(40,64,230,0.25);padding:13px 14px;"
            f"display:flex;flex-direction:column;justify-content:center;overflow:hidden'>"
            f"<div style='font-size:11px;font-weight:700;color:#B6B4AB;letter-spacing:0.3px;"
            f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{label}</div>"
            f"<div style='font-size:26px;font-weight:900;color:#FCFBF9;line-height:1.1;"
            f"margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{val}</div>"
            f"<div style='height:3px;width:34px;background:{col};border-radius:2px;margin-top:6px'></div>"
            f"</div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    if needs is None:
        st.caption("「🔄 更新」を押すと、要返信メール件数も取得されます。")

    st.markdown("")

    # ── 週次 積み上げ棒＋折れ線 ──
    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("### 週次 負荷の内訳と推移")
        _weekly_stacked_line(events, scorer)
    with right:
        st.markdown("### カテゴリ別")
        _category_pie(summary)

    st.markdown("---")

    # ── 進行中プロジェクトの中身 ＋ 直近ToDo（編集可）──
    pcol, tcol = st.columns([1, 1])
    with pcol:
        st.markdown("### 進行中プロジェクト")
        _active_projects(active_projects)
    with tcol:
        st.markdown("### 今日やること")
        components.quick_add_task(lists, projects, key_prefix="dash_qa")
        _today_todos(todos, projects, lists)


def _weekly_stacked_line(events, scorer):
    if not events:
        st.info("カレンダーイベントがありません。")
        return
    # 週 × カテゴリ の負荷を集計
    week_cat = defaultdict(lambda: defaultdict(float))
    week_total = defaultdict(float)
    for e in events:
        dt = parse_dt(e["start"])
        if not dt:
            continue
        wk = _iso_week_key(dt)
        score = scorer.score_event(e["title"], "", e["description"])
        cat = scorer.get_category(e["title"])
        week_cat[wk][cat] += score
        week_total[wk] += score

    weeks = sorted(week_total.keys())
    if not weeks:
        st.info("データなし")
        return
    # 上位カテゴリのみ色分け、それ以外は「その他」
    cat_totals = defaultdict(float)
    for wk in weeks:
        for cat, v in week_cat[wk].items():
            cat_totals[cat] += v
    top_cats = [c for c, _ in sorted(cat_totals.items(), key=lambda x: -x[1])[:6]]

    labels = [_week_label(wk) for wk in weeks]
    fig = go.Figure()
    for i, cat in enumerate(top_cats):
        fig.add_bar(
            x=labels, name=cat,
            y=[week_cat[wk].get(cat, 0) for wk in weeks],
            marker_color=PALETTE[i % len(PALETTE)], marker_line_width=0, opacity=0.5,
        )
    # その他
    other = [sum(v for c, v in week_cat[wk].items() if c not in top_cats) for wk in weeks]
    if any(other):
        fig.add_bar(x=labels, name="その他", y=other, marker_color="#B6B4AC", opacity=0.5)
    # 折れ線（週合計）— 目立つ色＋白フチマーカー
    fig.add_trace(go.Scatter(
        x=labels, y=[week_total[wk] for wk in weeks],
        name="週合計", mode="lines+markers",
        line=dict(color=CHART["total"], width=3.2),
        marker=dict(size=7, color=CHART["total"], line=dict(color="#FCFBF9", width=1.5)),
    ))
    fig.update_layout(
        barmode="stack", height=340,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=11, color=CHART["font"])),
        xaxis=dict(showgrid=False, title=None,
                   tickfont=dict(size=12, color=CHART["font"])),
        yaxis=dict(showgrid=True, gridcolor=CHART["grid"], title="負荷スコア",
                   tickfont=dict(size=11, color=CHART["font"])),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("棒＝カテゴリ別の負荷内訳（薄）　／　オレンジ線＝その週の合計負荷。線が高い週は予定の詰め込みすぎ注意。")


def _category_pie(summary):
    if not summary["by_category"]:
        st.caption("データなし")
        return
    items = list(summary["by_category"].items())[:8]
    df = pd.DataFrame([{"カテゴリ": k, "スコア": round(v, 1)} for k, v in items])
    fig = px.pie(df, values="スコア", names="カテゴリ", hole=0.62,
                 color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="inside", textinfo="percent",
                      insidetextorientation="horizontal",
                      textfont=dict(size=11, color="#FCFBF9"),
                      marker=dict(line=dict(color="#FCFBF9", width=2)))
    fig.update_layout(
        height=340, margin=dict(t=14, b=14, l=10, r=10),
        paper_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=11),
        showlegend=True,
        legend=dict(orientation="v", font=dict(size=10), yanchor="middle", y=0.5),
        annotations=[dict(text=f"{summary['total']}<br><span style='font-size:11px'>合計</span>",
                          x=0.5, y=0.5, font=dict(size=22, color=CHART["ink"]), showarrow=False)],
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _active_projects(active_projects):
    if not active_projects:
        st.caption("進行中のプロジェクトはありません。")
        return
    for p in active_projects[:6]:
        done, total_t, pct = db.project_progress(p["id"])
        with st.container(border=True):
            st.markdown(
                f"<div class='proj-head'>"
                f"<span class='proj-dot' style='background:{p['color']}'></span>"
                f"<span class='proj-name'>{p['name']}</span>"
                f"<span style='margin-left:auto'>{status_badge(p['status'])}</span></div>"
                f"<div class='proj-bar-bg'><div class='proj-bar-fill' "
                f"style='width:{pct}%;background:{p['color']}'></div></div>"
                f"<div class='tmeta' style='margin-top:6px'>進捗 {pct}% ({done}/{total_t})</div>",
                unsafe_allow_html=True)
            if st.button("開く →", key=f"dgo_{p['id']}", use_container_width=True):
                st.session_state.page = "projects"
                st.session_state["open_project"] = p["id"]
                st.rerun()


def _today_todos(todos, projects, lists):
    today = datetime.now(JST).date()
    def bucket(t):
        if t.get("due_date"):
            d = parse_dt(t["due_date"])
            if d and d.date() < today:
                return 0
            if d and d.date() == today:
                return 1
        return 2
    show = sorted(todos, key=lambda t: (bucket(t), t["priority"]))[:8]
    proj_map = {p["id"]: p for p in projects}
    if not show:
        st.caption("ToDo はありません。")
        return
    for t in show:
        rc = st.columns([0.55, 5, 0.7])
        with rc[0]:
            if st.checkbox("c", value=False, key=f"dtc_{t['id']}", label_visibility="collapsed"):
                db.toggle_todo(t["id"]); st.rerun()
        with rc[1]:
            proj = proj_map.get(t["project_id"])
            due = ""
            if t.get("due_date"):
                d = parse_dt(t["due_date"])
                overdue = d and d.date() < today
                due = f"<span style='color:{'#C0392B' if overdue else '#5E5C54'};font-weight:700'>📅 {t['due_date'][5:]}</span>"
            proj_chip = f"<span class='chip'>{proj['name'][:10]}</span>" if proj else ""
            st.markdown(
                f"<div class='task-row'>{priority_dot(t['priority'])}"
                f"<span class='tt'>{t['title']}</span>"
                f"<span style='margin-left:auto' class='tmeta'>{proj_chip}{due}</span></div>",
                unsafe_allow_html=True)
        with rc[2]:
            components.todo_edit_popover(t, projects, lists, key_prefix="dash_")
