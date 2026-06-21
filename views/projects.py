"""プロジェクト画面 — 上段ガントチャート（週次＋負荷）／下段 展開式一覧。
タスクの追加・並び替え・ツリー化・優先度・日程指定（アプリ内カレンダーに反映）。
プリセット適用、AI提案。
"""
from datetime import datetime, date, timedelta
from collections import defaultdict

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import database as db
import ai_assistant as ai
from presets import BUILTIN_PRESETS
from ui_helpers import (parse_dt, JST, priority_dot, status_badge,
                        STATUS_LABELS, STATUS_ORDER, PRIORITY_LABELS)
from style import CHART


def render(events, scorer):
    st.markdown("# プロジェクト")

    weekly_load = _weekly_load(events, scorer)

    # ── 上段：ガントチャート（負荷オーバーレイなし）──
    st.markdown("### ガントチャート")
    _gantt()
    # ── その直下：週次負荷の時系列（別グラフで対応）──
    st.markdown("### 週次の負荷（上のガントと同じ時間軸）")
    _load_timeline(weekly_load)

    st.markdown("---")

    with st.expander("＋ 新規プロジェクト作成 ／ プリセットから生成", expanded=False):
        _new_project_form()

    st.markdown("### プロジェクト一覧")
    projects = db.get_projects()
    if not projects:
        st.info("プロジェクトがありません。上の「新規プロジェクト作成」から追加してください。")
        return

    # ドラッグ&ドロップ並び替え
    with st.expander("↕ ドラッグで並び替え"):
        _drag_reorder(projects)

    # ステータスでグルーピング表示
    status_filter = st.radio(
        "表示", ["すべて"] + STATUS_ORDER, horizontal=True,
        format_func=lambda x: "すべて" if x == "すべて" else STATUS_LABELS[x],
        label_visibility="collapsed")

    shown = [p for p in projects if status_filter == "すべて" or p["status"] == status_filter]
    for idx, p in enumerate(shown):
        _project_card(p, idx, len(shown), weekly_load, scorer)


def _drag_reorder(projects):
    """streamlit-sortables でドラッグ&ドロップ並び替え"""
    try:
        from streamlit_sortables import sort_items
    except Exception:
        st.caption("ドラッグ並び替えのコンポーネントが見つかりません。▲▼ボタンをお使いください。")
        return
    # 表示ラベル → id の対応（同名対策でid付き）
    labels = [f"{p['name']}　#{p['id']}" for p in projects]
    id_by_label = {f"{p['name']}　#{p['id']}": p["id"] for p in projects}
    st.caption("項目をドラッグして離すと並びが保存されます。")
    new_order = sort_items(labels, direction="vertical", key="proj_sort")
    new_ids = [id_by_label[l] for l in new_order if l in id_by_label]
    cur_ids = [p["id"] for p in projects]
    if new_ids and new_ids != cur_ids:
        db.set_project_order(new_ids)
        st.rerun()


def _weekly_load(events, scorer):
    wl = defaultdict(float)
    for e in events:
        dt = parse_dt(e["start"])
        if dt:
            y, w, _ = dt.isocalendar()
            wl[f"{y}-W{w:02d}"] += scorer.score_event(e["title"], "", e["description"])
    return dict(wl)


def _gantt_range():
    """ガントと負荷の時間軸を揃えるための共通レンジを返す"""
    projects = [p for p in db.get_projects() if p["status"] != "completed"]
    starts = [p["start_date"][:10] for p in projects if p["start_date"]]
    ends = [p["end_date"][:10] for p in projects if p["end_date"]]
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)


def _gantt():
    projects = [p for p in db.get_projects() if p["status"] != "completed"]
    bars = []
    for p in projects:
        if p["start_date"] and p["end_date"]:
            s = parse_dt(p["start_date"]); e = parse_dt(p["end_date"])
            if not s or not e or e <= s:
                continue
            done, total_t, pct = db.project_progress(p["id"])
            prog_end = s + (e - s) * (pct / 100.0)
            bars.append(dict(name=p["name"], s=s, e=e, prog=prog_end,
                             color=p["color"], pct=pct))
    if not bars:
        st.info("日程が設定されたプロジェクトがありません。")
        return

    names = [b["name"] for b in bars]
    fig = go.Figure()
    for b in bars:
        dur = (b["e"] - b["s"]).total_seconds() * 1000
        prog = (b["prog"] - b["s"]).total_seconds() * 1000
        # 背景バー（薄）
        fig.add_bar(y=[b["name"]], x=[dur], base=[b["s"]], orientation="h",
                    marker=dict(color=b["color"], opacity=0.22, cornerradius=9),
                    width=0.62, showlegend=False, hoverinfo="skip")
        # 進捗バー（濃）
        fig.add_bar(y=[b["name"]], x=[prog], base=[b["s"]], orientation="h",
                    marker=dict(color=b["color"], cornerradius=9), width=0.62,
                    showlegend=False,
                    hovertemplate=f"{b['name']}<br>{b['s']:%-m/%-d}〜{b['e']:%-m/%-d}"
                                  f"<br>進捗 {b['pct']}%<extra></extra>")
        # 終了マイルストーン（ダイヤ）＋進捗ラベル
        fig.add_trace(go.Scatter(
            x=[b["e"]], y=[b["name"]], mode="markers+text",
            marker=dict(symbol="diamond", size=11, color=b["color"],
                        line=dict(color="#FCFBF9", width=1.5)),
            text=[f" {b['pct']}%"], textposition="middle right",
            textfont=dict(size=10, color=CHART["font"]),
            showlegend=False, hoverinfo="skip"))
        # プロジェクト名をバーの始点に重ねて表示（縦軸ラベルの代わり・見切れ防止）
        fig.add_annotation(x=b["s"], y=b["name"], text=" " + b["name"] + " ",
                           showarrow=False, xanchor="left", yanchor="middle", yshift=13,
                           font=dict(size=10.5, color="#141414"),
                           bgcolor="rgba(252,251,249,0.0)", borderpad=0)

    lo, hi = _gantt_range()
    fig.update_layout(
        barmode="overlay", height=max(210, len(bars) * 48 + 56),
        margin=dict(t=8, b=4, l=8, r=14),
        paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=11), showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CHART["grid"], tickformat="%-m/%-d",
                   dtick=604800000 * 2, range=[lo, hi] if lo else None, type="date",
                   tickfont=dict(size=10, color=CHART["font"])),
        yaxis=dict(showgrid=False, automargin=False, autorange="reversed",
                   categoryorder="array", categoryarray=names,
                   showticklabels=False),
    )
    fig.add_vline(x=datetime.now().timestamp() * 1000, line_dash="dot",
                  line_color=CHART["accent"], line_width=2)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("濃いバー＝進捗、薄いバー＝全期間、◆＝完了予定。点線＝今日。")


def _load_timeline(weekly_load):
    """ガントの下に、同じ時間軸で週次負荷を積み上げ棒＋折れ線で表示"""
    if not weekly_load:
        st.caption("負荷データなし")
        return
    from ui_helpers import iso_week_label
    wk_dates, wk_vals, wk_labels = [], [], []
    for wk, v in sorted(weekly_load.items()):
        try:
            yr, w = wk.split("-W")
            d = datetime.fromisocalendar(int(yr), int(w), 1)
            wk_dates.append(d); wk_vals.append(v)
            wk_labels.append(iso_week_label(int(yr), int(w)))
        except Exception:
            pass
    if not wk_dates:
        return
    lo, hi = _gantt_range()
    fig = go.Figure()
    # グラデーション面（スムーズ）
    fig.add_trace(go.Scatter(
        x=wk_dates, y=wk_vals, mode="lines", line_shape="spline",
        line=dict(color=CHART["load"], width=2.8),
        fill="tozeroy",
        fillgradient=dict(type="vertical",
                          colorscale=[(0, "rgba(224,36,94,0.02)"), (1, "rgba(224,36,94,0.45)")]),
        hovertemplate="%{x|%-m/%-d}の週<br>負荷 %{y:.1f}<extra></extra>", name="負荷"))
    # ピーク強調マーカー（ラベルは見切れ防止で左寄せ）
    ymax = max(wk_vals) if wk_vals else 1
    if wk_vals:
        peak_i = max(range(len(wk_vals)), key=lambda i: wk_vals[i])
        fig.add_trace(go.Scatter(
            x=[wk_dates[peak_i]], y=[wk_vals[peak_i]], mode="markers+text",
            marker=dict(size=11, color=CHART["load"], line=dict(color="#FCFBF9", width=2)),
            text=[f"ピーク {wk_vals[peak_i]:.0f}"], textposition="middle right",
            textfont=dict(size=10, color=CHART["load"]), showlegend=False, hoverinfo="skip",
            cliponaxis=False))
    fig.add_vline(x=datetime.now().timestamp() * 1000, line_dash="dot",
                  line_color=CHART["accent"], line_width=2)
    fig.update_layout(
        height=200, margin=dict(t=28, b=10, l=8, r=14),
        paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
        font=dict(color=CHART["font"], size=11), showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CHART["grid"], tickformat="%-m/%-d",
                   dtick=604800000 * 2, range=[lo, hi] if lo else None, type="date",
                   tickfont=dict(size=10, color=CHART["font"])),
        yaxis=dict(showgrid=True, gridcolor=CHART["grid"],
                   title=None, showticklabels=False, automargin=False,
                   range=[0, ymax * 1.25]),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("点線＝今日。上のガントと左端・時間軸を揃えています。山が高い時期に各プロジェクトの締切が重なっていないか確認できます。")


def _new_project_form():
    presets = db.get_presets()
    preset_names = ["（プリセットを使わない）"] + [f"{p['name']}" for p in presets]

    with st.form("new_project_v2", clear_on_submit=True):
        name = st.text_input("プロジェクト名 *")
        c1, c2, c3 = st.columns(3)
        category = c1.text_input("カテゴリ", placeholder="大学院 / 病院 / 起業 / プライベート")
        color = c2.color_picker("カラー", "#2840E6")
        priority = c3.selectbox("優先度", [1, 2, 3],
                                format_func=lambda x: PRIORITY_LABELS[x], index=1)
        c4, c5, c6 = st.columns(3)
        start = c4.date_input("開始日", value=date.today())
        end = c5.date_input("終了予定日", value=date.today() + timedelta(days=90))
        status = c6.selectbox("ステータス", STATUS_ORDER,
                              format_func=lambda x: STATUS_LABELS[x])
        preset_choice = st.selectbox("📋 プリセット（適用すると工程タスクを自動生成）", preset_names)
        desc = st.text_area("説明", height=70)

        if st.form_submit_button("作成", type="primary"):
            if not name:
                st.error("プロジェクト名を入力してください")
            else:
                pid = db.add_project(name, desc, category, color, status, priority,
                                     str(start), str(end))
                # プリセット適用
                if preset_choice != preset_names[0]:
                    preset = next((p for p in presets if p["name"] == preset_choice), None)
                    if preset:
                        for step in preset["steps"]:
                            due = start + timedelta(days=step.get("offset_days", 0))
                            db.add_todo(step["title"], project_id=pid,
                                        due_date=str(due), priority=step.get("priority", 2),
                                        sync_calendar=1)
                        db.log_activity("preset_applied", pid, {"preset": preset["name"]})
                st.success(f"「{name}」を作成しました")
                st.rerun()


def _project_card(p, idx, total, weekly_load, scorer):
    done, total_t, pct = db.project_progress(p["id"])
    open_key = f"proj_open_{p['id']}"
    # ダッシュボードから「開く」で遷移した場合
    if st.session_state.get("open_project") == p["id"]:
        st.session_state[open_key] = True
        st.session_state["open_project"] = None
    is_open = st.session_state.get(open_key, False)

    from ui_helpers import STATUS_COLORS, STATUS_TINT
    scol = STATUS_COLORS.get(p["status"], "#9CA3AF")
    stint = STATUS_TINT.get(p["status"], "transparent")
    with st.container(border=True):
        # 状態色の細いバー（テキストはバッジで表示するので重複させない）
        st.markdown(
            f"<div style='height:5px;background:{scol};border-radius:99px;"
            f"margin:-2px -2px 7px;'></div>", unsafe_allow_html=True)
        # ── ヘッダー行（折りたたみトグル＋ステータス）。並び替えは展開時/ドラッグで ──
        hc = st.columns([7, 2.3])
        arrow = "▼" if is_open else "▶"
        if hc[0].button(f"{arrow}  {p['name']}", key=f"ptoggle_{p['id']}", use_container_width=True):
            st.session_state[open_key] = not is_open
            st.rerun()
        hc[1].markdown(
            f"<div style='padding-top:7px;text-align:right'>{status_badge(p['status'])}"
            f" <span class='tmeta'>{pct}%</span></div>", unsafe_allow_html=True)

        st.markdown(
            f"<div class='proj-bar-bg'><div class='proj-bar-fill' "
            f"style='width:{pct}%;background:{p['color']}'></div></div>",
            unsafe_allow_html=True)

        if not is_open:
            return

        # ── 詳細（展開時のみ・明るいパネルで区別）──
        with st.container(border=True):
            st.markdown("<div class='sec-label' style='margin-top:0'>プロジェクト編集</div>",
                        unsafe_allow_html=True)
            cc1, cc2, cc3 = st.columns([2, 2, 1])
            new_status = cc1.selectbox("ステータス", STATUS_ORDER, index=STATUS_ORDER.index(p["status"]),
                                       format_func=lambda x: STATUS_LABELS[x], key=f"pstat_{p['id']}")
            if new_status != p["status"]:
                db.update_project(p["id"], status=new_status); st.rerun()
            new_pri = cc2.selectbox("優先度", [1, 2, 3], index=p["priority"] - 1,
                                    format_func=lambda x: PRIORITY_LABELS[x], key=f"ppri_{p['id']}")
            if new_pri != p["priority"]:
                db.update_project(p["id"], priority=new_pri); st.rerun()
            if cc3.button("🗑 削除", key=f"pdel_{p['id']}", use_container_width=True):
                db.delete_project(p["id"]); st.rerun()

            # 並び替え（一覧上部のドラッグでも可）
            mc1, mc2 = st.columns(2)
            if mc1.button("▲ 上へ", key=f"pup_{p['id']}", use_container_width=True):
                db.move_project(p["id"], -1); st.rerun()
            if mc2.button("▼ 下へ", key=f"pdn_{p['id']}", use_container_width=True):
                db.move_project(p["id"], 1); st.rerun()

            d1, d2 = st.columns(2)
            ns = d1.date_input("開始", value=parse_dt(p["start_date"]).date() if p["start_date"] else date.today(),
                               key=f"pstart_{p['id']}")
            ne = d2.date_input("終了", value=parse_dt(p["end_date"]).date() if p["end_date"] else date.today(),
                               key=f"pend_{p['id']}")
            if str(ns) != (p["start_date"] or "")[:10] or str(ne) != (p["end_date"] or "")[:10]:
                db.update_project(p["id"], start_date=str(ns), end_date=str(ne)); st.rerun()

        with st.container(border=True):
            st.markdown("<div class='sec-label' style='margin-top:0'>タスク（ツリー）</div>",
                        unsafe_allow_html=True)
            _project_tasks(p)

        if st.button("AIに改善提案をもらう", key=f"ai_{p['id']}"):
            with st.spinner("分析中..."):
                tasks = db.get_todos(project_id=p["id"])
                result = ai.suggest_for_project(p, tasks, weekly_load)
            items = "".join(f"<div class='ai-item'>{s}</div>" for s in result["suggestions"])
            src = "Claude" if result["source"] == "ai" else "ルールベース"
            st.markdown(
                f"<div class='ai-card'><div class='ai-title'>{src} の提案</div>{items}</div>",
                unsafe_allow_html=True)


@st.fragment
def _project_tasks(p):
    """プロジェクト配下のタスクをツリー表示＋編集（fragmentで局所更新＝位置ずれ防止）"""
    all_tasks = db.get_todos(project_id=p["id"])
    children = defaultdict(list)
    for t in all_tasks:
        children[t["parent_id"]].append(t)

    def render_branch(parent_id, depth, is_last_chain):
        kids = sorted(children.get(parent_id, []), key=lambda x: (x["completed"], x["sort_order"]))
        for i, t in enumerate(kids):
            _task_row(t, depth, p["id"], last=(i == len(kids) - 1))
            render_branch(t["id"], depth + 1, is_last_chain + [i == len(kids) - 1])

    if not all_tasks:
        st.caption("タスクがありません。下から追加できます。")
    else:
        render_branch(None, 0, [])

    # タスク追加
    with st.form(f"addtask_{p['id']}", clear_on_submit=True):
        ac1, ac2, ac3, ac4 = st.columns([4, 1.3, 1.5, 1])
        new_title = ac1.text_input("新規タスク", key=f"nt_{p['id']}",
                                   label_visibility="collapsed", placeholder="＋ タスクを追加")
        new_pri = ac2.selectbox("優先", [1, 2, 3], index=1,
                                format_func=lambda x: PRIORITY_LABELS[x],
                                key=f"ntp_{p['id']}", label_visibility="collapsed")
        new_due = ac3.date_input("期日", value=None, key=f"ntd_{p['id']}",
                                label_visibility="collapsed")
        if ac4.form_submit_button("追加", use_container_width=True):
            if new_title:
                db.add_todo(new_title, project_id=p["id"], priority=new_pri,
                            due_date=str(new_due) if new_due else None,
                            sync_calendar=1 if new_due else 0)
                st.rerun(scope="fragment")


def _task_row(t, depth, project_id, last=False):
    cols = st.columns([0.5, 5, 0.6, 0.6, 0.6, 0.6])
    with cols[0]:
        done = st.checkbox("c", value=bool(t["completed"]),
                           key=f"tc_{t['id']}", label_visibility="collapsed")
        if done != bool(t["completed"]):
            db.toggle_todo(t["id"]); st.rerun(scope="fragment")
    with cols[1]:
        # ツリーの接続線（サブタスクは └─ ＋ 左に色付きガイド）
        connector = ""
        if depth > 0:
            connector = (f"<span style='display:inline-block;width:{(depth-1)*18}px'></span>"
                         f"<span style='color:#A8A69E;font-family:monospace'>"
                         f"{'└─' if last else '├─'}</span> ")
        due_html = ""
        if t.get("due_date"):
            due_html = f"<span class='tmeta'>📅 {t['due_date'][5:]}</span>"
        cls = "task-done" if t["completed"] else ""
        border = "border-left:3px solid #2840E6;" if depth > 0 else ""
        st.markdown(
            f"<div style='display:flex;align-items:center'>{connector}"
            f"<div class='task-row {cls}' style='flex:1;{border}'>"
            f"{priority_dot(t['priority'])}"
            f"<span class='tt'>{t['title']}</span>"
            f"<span style='margin-left:auto'>{due_html}</span></div></div>",
            unsafe_allow_html=True)
    with cols[2]:
        if st.button("▲", key=f"tu_{t['id']}", help="上へ"):
            db.move_todo(t["id"], -1); st.rerun(scope="fragment")
    with cols[3]:
        if st.button("▼", key=f"td_{t['id']}", help="下へ"):
            db.move_todo(t["id"], 1); st.rerun(scope="fragment")
    with cols[4]:
        if st.button("↳", key=f"ts_{t['id']}", help="サブタスク追加"):
            st.session_state[f"addsub_{t['id']}"] = not st.session_state.get(f"addsub_{t['id']}", False)
            st.rerun(scope="fragment")
    with cols[5]:
        if st.button("🗑", key=f"tdel_{t['id']}", help="削除"):
            db.delete_todo(t["id"]); st.rerun(scope="fragment")
    # サブタスク追加インライン
    if st.session_state.get(f"addsub_{t['id']}"):
        sc = st.columns([5, 1])
        sub = sc[0].text_input("サブタスク名", key=f"subt_{t['id']}",
                               label_visibility="collapsed", placeholder="サブタスク名")
        if sc[1].button("追加", key=f"subadd_{t['id']}"):
            if sub:
                db.add_todo(sub, project_id=project_id, parent_id=t["id"], priority=t["priority"])
                st.session_state[f"addsub_{t['id']}"] = False
                st.rerun(scope="fragment")
