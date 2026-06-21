"""ToDo画面 — カスタムグループ(リスト)で一画面把握。
タスクの編集・完了戻し・削除を明確に分離。グループはユーザーが追加/編集可能。
"""
from datetime import datetime, date, timedelta

import streamlit as st

import database as db
import components
from ui_helpers import parse_dt, JST, priority_dot, tag_chips, PRIORITY_LABELS


def _smart_sort_key(t):
    today = datetime.now(JST).date()
    if t.get("due_date"):
        d = parse_dt(t["due_date"])
        if d:
            dd = d.date()
            bucket = 0 if dd < today else 1 if dd == today else 2 if dd <= today + timedelta(days=7) else 3
            return (bucket, t["priority"], t["due_date"])
    return (4, t["priority"], "9999")


def recommend_soon(t, pred_hours=None):
    """『早くやった方が良い』度をローカルロジックで判定（優先度は表示のみで変えない）。
    戻り値: True=⚡推奨。締切の近さ・優先度・想定所要時間から算出。"""
    today = datetime.now(JST).date()
    score = 0.0
    if t.get("due_date"):
        d = parse_dt(t["due_date"])
        if d:
            days = (d.date() - today).days
            if days < 0:
                score += 3
            elif days == 0:
                score += 2.2
            elif days == 1:
                score += 1.6
            elif days <= 3:
                score += 1.0
            elif days <= 7:
                score += 0.4
            # 締切が近く、想定所要時間が長い大物は早めに着手
            h = (pred_hours or {}).get(str(t["id"]))
            if h and days <= 5 and h >= 12:
                score += 1.0
    score += {1: 1.4, 2: 0.5, 3: 0.0}.get(t["priority"], 0)
    return score >= 2.4


def _due_label(t):
    today = datetime.now(JST).date()
    if not t.get("due_date"):
        return ""
    d = parse_dt(t["due_date"])
    if not d:
        return ""
    dd = d.date(); days = (dd - today).days
    if days < 0:
        color, txt = "#C0392B", f"{abs(days)}日超過"
    elif days == 0:
        color, txt = "#B45309", "今日"
    elif days == 1:
        color, txt = "#B45309", "明日"
    else:
        color, txt = "#5E5C54", f"{dd.month}/{dd.day}"
    return f"<span style='color:{color};font-size:11.5px;font-weight:700'>📅 {txt}</span>"


def render(events, scorer):
    st.markdown("# ToDo")

    projects = db.get_projects()
    proj_map = {p["id"]: p for p in projects}
    lists = db.get_lists()
    all_open = db.get_todos(include_completed=False)
    pred_hours = db.get_prediction_map("completion_hours")
    today = datetime.now(JST).date()

    # サマリー
    overdue = sum(1 for t in all_open if t.get("due_date") and parse_dt(t["due_date"]) and parse_dt(t["due_date"]).date() < today)
    todays = sum(1 for t in all_open if t.get("due_date") and parse_dt(t["due_date"]) and parse_dt(t["due_date"]).date() == today)
    week = sum(1 for t in all_open if t.get("due_date") and parse_dt(t["due_date"]) and today < parse_dt(t["due_date"]).date() <= today + timedelta(days=7))
    kpis = [("期限超過", overdue, "#E0245E"), ("今日", todays, "#E8870C"),
            ("今週", week, "#2563EB"), ("未完了 合計", len(all_open), "#2840E6")]
    khtml = "<div class='kpi-row' style='display:flex;gap:10px;margin-bottom:6px'>"
    for label, val, col in kpis:
        khtml += (
            f"<div class='kpi-card' style='flex:1;height:88px;background:#1C1C19;border:1.5px solid #141414;"
            f"border-radius:6px;box-shadow:3px 3px 0 rgba(40,64,230,0.25);padding:12px 14px;"
            f"display:flex;flex-direction:column;justify-content:center;overflow:hidden'>"
            f"<div style='font-size:11px;font-weight:700;color:#B6B4AB;white-space:nowrap;"
            f"overflow:hidden;text-overflow:ellipsis'>{label}</div>"
            f"<div style='font-size:26px;font-weight:900;color:#FCFBF9;line-height:1.1;margin-top:4px'>{val}</div>"
            f"<div style='height:3px;width:30px;background:{col};border-radius:2px;margin-top:5px'></div>"
            f"</div>")
    khtml += "</div>"
    st.markdown(khtml, unsafe_allow_html=True)

    st.caption("⚡ = 早めの着手がおすすめ（締切・優先度・想定所要時間からローカルAIが判定。優先度は変わりません）")

    # クイック追加
    components.quick_add_task(lists, projects, key_prefix="todo_qa")

    # グループ管理
    with st.expander("＋ グループを追加 / 編集"):
        _manage_lists(lists)

    st.markdown("---")

    # ── グループをタブで表示（フラグメント化＝チェック操作で全体を再実行しない）──
    @st.fragment
    def _todo_lists():
        open_now = db.get_todos(include_completed=False)   # フラグメント再実行時も最新を取得
        buckets = {l["id"]: [] for l in lists}
        unl = []
        for t in open_now:
            (buckets[t["list_id"]] if t.get("list_id") in buckets else unl).append(t)
        disp = [(l, buckets[l["id"]]) for l in lists]
        if unl:
            disp.append(({"id": None, "name": "未分類", "icon": "📥"}, unl))
        labels = [f"{l['icon']} {l['name']}（{len(it)}）" for l, it in disp]
        if not labels:
            return
        for tab, (lst, items) in zip(st.tabs(labels), disp):
            with tab:
                items.sort(key=_smart_sort_key)
                if not items:
                    st.caption("このグループにタスクはありません。")
                for t in items:
                    _todo_card(t, proj_map, lists, projects, pred_hours)

    _todo_lists()

    # 完了済み
    st.markdown("---")
    done_items = [t for t in db.get_todos(include_completed=True) if t["completed"]]
    stats = db.get_completion_stats()
    with st.expander(f"完了済み {len(done_items)}件"
                     f"（平均 {stats['avg_hours']}h / 中央値 {stats['median_hours']}h · ✏️から未完了に戻せます）"):
        for t in sorted(done_items, key=lambda x: x.get("completed_at") or "", reverse=True)[:50]:
            cc = st.columns([5, 0.7])
            with cc[0]:
                done_at = (t.get("completed_at") or "")[:16]
                st.markdown(
                    f"<div class='task-row task-done'>{priority_dot(t['priority'])}"
                    f"<span class='tt'>{t['title']}</span>"
                    f"<span style='margin-left:auto' class='tmeta'>✔ {done_at}</span></div>",
                    unsafe_allow_html=True)
            with cc[1]:
                components.todo_edit_popover(t, projects, lists, key_prefix="done_")


def _manage_lists(lists):
    st.caption("ToDoのグループ（リスト）を自由に追加・編集・削除できます。")
    # 追加
    ac = st.columns([1, 3, 1])
    new_icon = ac[0].text_input("アイコン", value="📌", key="newlist_icon", max_chars=2)
    new_name = ac[1].text_input("グループ名", key="newlist_name", placeholder="例: 病院・研究・家族")
    if ac[2].button("追加", key="addlist", use_container_width=True):
        if new_name:
            db.add_list(new_name, new_icon or "📌")
            st.rerun()
    # 既存編集
    for l in lists:
        ec = st.columns([1, 3, 1])
        ic = ec[0].text_input("i", value=l["icon"], key=f"li_{l['id']}",
                              label_visibility="collapsed", max_chars=2)
        nm = ec[1].text_input("n", value=l["name"], key=f"ln_{l['id']}",
                              label_visibility="collapsed")
        if ic != l["icon"] or nm != l["name"]:
            db.update_list(l["id"], icon=ic, name=nm); st.rerun()
        if ec[2].button("🗑", key=f"ld_{l['id']}", use_container_width=True):
            db.delete_list(l["id"]); st.rerun()


def _todo_card(t, proj_map, lists, projects, pred_hours=None):
    """1行コンパクト表示（チェック｜優先度＋タイトル＋締切｜✏️）"""
    proj = proj_map.get(t["project_id"])
    edit_key = f"inline_edit_{t['id']}"
    cc = st.columns([0.42, 5, 0.5])
    with cc[0]:
        if st.checkbox("c", value=False, key=f"tdc_{t['id']}", label_visibility="collapsed"):
            db.toggle_todo(t["id"]); st.rerun(scope="fragment")
    with cc[1]:
        right = _due_label(t)
        if proj:
            right += f" <span class='chip'>{proj['name'][:8]}</span>"
        # ⚡ = 早くやった方が良い（ローカルAI判定。優先度は変えず表示のみ）
        flag = ("<span title='早めの着手がおすすめ' style='color:#E8870C;font-weight:900'>⚡</span> "
                if recommend_soon(t, pred_hours) else "")
        st.markdown(
            f"<div class='task-row'>{priority_dot(t['priority'])}"
            f"{flag}<span class='tt'>{t['title']}</span>"
            f"<span style='margin-left:auto;white-space:nowrap'>{right}</span></div>",
            unsafe_allow_html=True)
    with cc[2]:
        if st.button("✏️", key=f"ttl_{t['id']}", help="クリックで編集"):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun(scope="fragment")
    if st.session_state.get(edit_key):
        with st.container(border=True):
            components.todo_editor_body(t, projects, lists, key_prefix="inline_")
