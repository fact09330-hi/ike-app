"""再利用UIコンポーネント（タスク編集ポップオーバー・クイック追加）
ダッシュボードとToDo画面で共用。タスクの改変・修正・完了戻し・削除を一箇所に集約。
"""
from datetime import date, datetime

import streamlit as st

import database as db
from ui_helpers import parse_dt, PRIORITY_LABELS


def todo_editor_body(t, projects, lists, key_prefix=""):
    """編集フォーム本体（ポップオーバー/インライン両用）。列は使わない（ネスト制限対策）。"""
    k = f"{key_prefix}{t['id']}"
    proj_opts = [None] + [p["id"] for p in projects]
    proj_name = {p["id"]: p["name"] for p in projects}
    list_opts = [l["id"] for l in lists] + [None]
    list_name = {l["id"]: f"{l['icon']} {l['name']}" for l in lists}

    new_title = st.text_input("タスク名", value=t["title"], key=f"et_{k}")
    new_list = st.selectbox("グループ", list_opts,
                            index=list_opts.index(t.get("list_id")) if t.get("list_id") in list_opts else len(list_opts) - 1,
                            format_func=lambda x: list_name.get(x, "（なし）"), key=f"el_{k}")
    new_pri = st.selectbox("優先度", [1, 2, 3], index=t["priority"] - 1,
                           format_func=lambda x: PRIORITY_LABELS[x], key=f"ep_{k}")
    cur_due = parse_dt(t["due_date"]).date() if t.get("due_date") else None
    new_due = st.date_input("期日", value=cur_due, key=f"ed_{k}")
    new_proj = st.selectbox("プロジェクト", proj_opts,
                            index=proj_opts.index(t["project_id"]) if t["project_id"] in proj_opts else 0,
                            format_func=lambda x: "（なし）" if x is None else proj_name.get(x, ""),
                            key=f"epr_{k}")
    new_url = st.text_input("URL", value=t.get("url", ""), key=f"eu_{k}")
    new_tags = st.text_input("タグ", value=t.get("tags", ""), key=f"eg_{k}")
    new_memo = st.text_area("メモ", value=t.get("memo", ""), height=68, key=f"em_{k}")

    if st.button("💾 保存", key=f"es_{k}", type="primary", use_container_width=True):
        db.update_todo(t["id"], title=new_title, list_id=new_list, priority=new_pri,
                       due_date=str(new_due) if new_due else None,
                       project_id=new_proj, url=new_url, tags=new_tags, memo=new_memo,
                       sync_calendar=1 if new_due else 0)
        st.session_state[f"inline_edit_{t['id']}"] = False
        st.rerun()
    if t["completed"]:
        if st.button("↩️ 未完了に戻す", key=f"er_{k}", use_container_width=True):
            db.toggle_todo(t["id"]); st.rerun()
    if st.button("🗑 削除", key=f"ex_{k}", use_container_width=True):
        db.delete_todo(t["id"]); st.rerun()


def todo_edit_popover(t, projects, lists, key_prefix=""):
    """タスク編集ポップオーバー。✏️ボタンで開く。"""
    with st.popover("✏️", use_container_width=False):
        st.markdown("**タスクを編集**")
        todo_editor_body(t, projects, lists, key_prefix)


def quick_add_task(lists, projects, key_prefix="qa", default_list_id=None):
    """1行クイック追加。グループ・優先度・期日を選んで追加。"""
    list_opts = [l["id"] for l in lists]
    list_name = {l["id"]: f"{l['icon']} {l['name']}" for l in lists}
    with st.form(f"{key_prefix}_form", clear_on_submit=True):
        c = st.columns([4, 1.5, 1.3, 1.4, 1])
        title = c[0].text_input("t", label_visibility="collapsed", placeholder="＋ タスクを追加…")
        lst = c[1].selectbox("g", list_opts,
                             index=list_opts.index(default_list_id) if default_list_id in list_opts else 0,
                             format_func=lambda x: list_name.get(x, ""),
                             label_visibility="collapsed", key=f"{key_prefix}_l")
        pri = c[2].selectbox("p", [1, 2, 3], index=1,
                            format_func=lambda x: f"優先{PRIORITY_LABELS[x]}",
                            label_visibility="collapsed", key=f"{key_prefix}_p")
        due = c[3].date_input("d", value=None, label_visibility="collapsed", key=f"{key_prefix}_d")
        if c[4].form_submit_button("追加", type="primary", use_container_width=True):
            if title:
                db.add_todo(title, list_id=lst, priority=pri,
                            due_date=str(due) if due else None,
                            sync_calendar=1 if due else 0)
                st.rerun()
