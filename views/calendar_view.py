"""カレンダー画面 — Googleカレンダー風 月表示 ＋ 週間ストリップ。
カテゴリ別タイル配色、当直は入り＆明けで2日表示、日マス背景は負荷で着色。
"""
import calendar as cal_mod
from datetime import datetime, timedelta, date
from collections import defaultdict

import streamlit as st

import database as db
from event_parser import parse_event
from calendar_style import category_style, icon_svg, is_overnight
from ui_helpers import parse_dt, load_to_tint, JST, priority_dot

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _add_task_deadlines(by_day):
    """due_date付きの未完了ToDoを締切としてカレンダーに追加（負荷には含めない）"""
    projects = {p["id"]: p for p in db.get_projects()}
    for t in db.get_todos(include_completed=False):
        if not t.get("due_date"):
            continue
        d = parse_dt(t["due_date"])
        if not d:
            continue
        proj = projects.get(t["project_id"])
        marker = {
            "title": t["title"], "clean_title": t["title"],
            "parsed_time": None, "parsed_location": None,
            "_score": 0.0, "_overnight_next": False, "_deadline": True,
            "_proj_color": proj["color"] if proj else "#6E6C64",
        }
        by_day[d.date()]["events"].append(marker)


def _events_by_day(events, scorer):
    by_day = defaultdict(lambda: {"events": [], "load": 0.0})
    overnight = []  # (date, parsed) 翌日に明けを足す用
    for e in events:
        dt = parse_dt(e["start"])
        if not dt:
            continue
        d = dt.date()
        parsed = parse_event(e)
        parsed["_score"] = scorer.score_event(e["title"], "", e["description"])
        parsed["_overnight_next"] = False
        by_day[d]["events"].append(parsed)
        by_day[d]["load"] += parsed["_score"]
        if is_overnight(e["title"]):
            overnight.append((d, parsed))
    # 当直の「明け」を翌日に表示（負荷は加算しない＝表示のみ）
    for d, parsed in overnight:
        nxt = d + timedelta(days=1)
        ake = dict(parsed)
        ake["_overnight_next"] = True
        ake["_score"] = 0.0
        by_day[nxt]["events"].append(ake)
    for d in by_day:
        by_day[d]["events"].sort(key=lambda x: (x.get("parsed_start") or "00:00" if not x["_overnight_next"] else "z"))
    return by_day


def render(events, scorer):
    st.markdown("# カレンダー")

    if "cal_year" not in st.session_state:
        now = datetime.now(JST)
        st.session_state.cal_year = now.year
        st.session_state.cal_month = now.month

    by_day = _events_by_day(events, scorer)
    _add_task_deadlines(by_day)
    max_load = max((v["load"] for v in by_day.values()), default=1.0) or 1.0

    # ── 週間ストリップ ──
    st.markdown("<div class='cal-section'>今週の予定</div>", unsafe_allow_html=True)
    _weekly_strip(by_day, max_load)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='cal-section'>月間カレンダー（タスクはドラッグで締切変更・クリックで完了）</div>",
                unsafe_allow_html=True)
    st.caption("🟥 日付の背景が赤いほど、その日の負荷が高いことを表します。")
    _interactive_month(events, scorer)

    # 凡例
    st.markdown(_legend(), unsafe_allow_html=True)

    # ── カレンダーに入っているタスク（左の□をチェックで完了）──
    st.markdown("---")
    _deadline_checklist()


def _deadline_checklist():
    today = datetime.now(JST).date()
    projects = {p["id"]: p for p in db.get_projects()}
    items = []
    for t in db.get_todos(include_completed=False):
        if not t.get("due_date"):
            continue
        d = parse_dt(t["due_date"])
        if d:
            items.append((d.date(), t))
    items.sort(key=lambda x: x[0])
    st.markdown(
        f"<div class='cal-section'>📅 カレンダーのタスク {len(items)}件 "
        f"<span style='font-weight:600;font-size:11px;color:#6E6C64'>"
        f"— 左の□をチェックすると完了（カレンダーからも消えます）</span></div>",
        unsafe_allow_html=True)
    if not items:
        st.caption("締切（日付）が設定されたタスクはありません。ToDoで日付を入れると、こことカレンダーに表示されます。")
        return
    for d, t in items:
        proj = projects.get(t["project_id"])
        c = st.columns([0.5, 9])
        with c[0]:
            if st.checkbox("c", value=False, key=f"caldone_{t['id']}",
                           label_visibility="collapsed"):
                db.toggle_todo(t["id"]); st.rerun()
        with c[1]:
            days = (d - today).days
            if days < 0:
                badge = f"<span style='color:#C0392B;font-weight:700'>{abs(days)}日超過</span>"
            elif days == 0:
                badge = "<span style='color:#B45309;font-weight:700'>今日</span>"
            elif days == 1:
                badge = "<span style='color:#B45309;font-weight:700'>明日</span>"
            else:
                badge = f"<span class='tmeta'>{d.month}/{d.day}（あと{days}日）</span>"
            proj_chip = f"<span class='chip'>{proj['name'][:14]}</span>" if proj else ""
            st.markdown(
                f"<div class='task-row' style='margin:2px 0'>{priority_dot(t['priority'])}"
                f"<span class='tt'>{t['title']}</span>"
                f"<span style='margin-left:auto'>{proj_chip} {badge}</span></div>",
                unsafe_allow_html=True)


def _interactive_month(events, scorer):
    """FullCalendar(streamlit-calendar)で月表示。Google予定=表示のみ、タスク=ドラッグ/クリック可。"""
    from streamlit_calendar import calendar as fc

    projects = {p["id"]: p for p in db.get_projects()}
    cal_events = []
    # Google予定（編集不可）。複数日は横バーをまたがせる（TimeTree風）
    for e in events:
        dt = parse_dt(e["start"])
        if not dt:
            continue
        parsed = parse_event(e)
        bg, fg, _ = category_style(e.get("title", ""))
        ev = {
            "id": f"gcal_{e.get('id','')}",
            "title": parsed.get("clean_title") or e.get("title", ""),
            "start": dt.date().isoformat(), "allDay": True,
            "backgroundColor": bg, "borderColor": bg, "textColor": fg,
            "editable": False,
        }
        # 終日の複数日イベントは end を入れてバーをまたがせる（Google all-day end は排他的）
        end_dt = parse_dt(e.get("end", "")) if e.get("end") else None
        if e.get("all_day") and end_dt and end_dt.date() > dt.date():
            ev["end"] = end_dt.date().isoformat()
        cal_events.append(ev)
    # タスク（ドラッグで締切変更・クリックで完了）
    for t in db.get_todos(include_completed=True):
        if not t.get("due_date"):
            continue
        d = parse_dt(t["due_date"])
        if not d:
            continue
        done = bool(t["completed"])
        proj = projects.get(t["project_id"])
        pcol = proj["color"] if proj else "#2840E6"
        cal_events.append({
            "id": f"task_{t['id']}",
            "title": ("☑ " if done else "☐ ") + t["title"],
            "start": d.date().isoformat(), "allDay": True,
            "backgroundColor": "#EDEBE6" if not done else "#D7D5CE",
            "borderColor": pcol, "textColor": "#9A988F" if done else "#141414",
            "editable": True,
        })

    # ── 日マスを「負荷が強いほど赤く」着色（FullCalendarの背景イベント）──
    by_day = _events_by_day(events, scorer)
    loads = [v["load"] for v in by_day.values() if v["load"] > 0]
    max_load = max(loads) if loads else 1.0
    for d, info in by_day.items():
        load = info["load"]
        if load <= 0:
            continue
        intensity = min(1.0, (load / max_load) ** 0.7)   # 低負荷も少し見えるよう緩く
        alpha = round(0.08 + intensity * 0.44, 2)         # 薄(0.08)〜濃(0.52)
        cal_events.append({
            "start": d.isoformat(), "allDay": True, "display": "background",
            "backgroundColor": f"rgba(224,36,94,{alpha})",
        })

    options = {
        "initialView": "dayGridMonth", "locale": "ja", "firstDay": 1,
        "editable": True, "selectable": False,
        "eventDisplay": "block",     # 予定を横バー（ブロック）で表示＝TimeTree風
        "displayEventTime": False,
        "dayMaxEvents": 4,           # 1日4件まで表示、超過は「+N」
        "fixedWeekCount": True,      # 常に6週表示＝毎月同じ行数で安定
        "showNonCurrentDates": True,
        "handleWindowResize": True,
        "height": "auto",            # 内容に高さを自動追従（スマホで下側が切れない）
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "buttonText": {"today": "今日"},
    }
    # TimeTree風：予定を色付きの横バーで表示。複数日は端をつなげる。
    css = """
        .fc { background:#FCFBF9; border-radius:6px; padding:6px; }
        .fc .fc-toolbar-title { font-size:1.1rem; font-weight:900; color:#141414; }
        .fc .fc-daygrid-day-number { color:#3A3A36; font-weight:700; font-size:12px; }
        .fc .fc-day-today { background:rgba(40,64,230,0.06) !important; }
        .fc .fc-daygrid-day-frame { padding:2px; }
        .fc-daygrid-event {
            font-weight:700; cursor:pointer; font-size:11px;
            padding:2px 6px; margin:1px 1px; border:none !important; border-radius:5px;
            line-height:1.5; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
        }
        .fc-daygrid-event .fc-event-title { overflow:hidden; text-overflow:ellipsis; font-weight:700; }
        .fc-daygrid-block-event { box-shadow:none; }
        .fc-daygrid-more-link { font-size:10.5px; font-weight:800; color:#2840E6; }
        .fc-event[data-editable] { cursor:grab; }
    """
    state = fc(events=cal_events, options=options, custom_css=css, key="ical_month")

    # ── 操作の反映（同一stateの再処理を避ける）──
    import json as _json
    if state:
        sig = _json.dumps(state, sort_keys=True, default=str)
        if sig != st.session_state.get("_cal_sig"):
            st.session_state["_cal_sig"] = sig
            cb = state.get("callback")
            ev = (state.get(cb) or {}).get("event") if cb else None
            if ev and str(ev.get("id", "")).startswith("task_"):
                tid = int(ev["id"][5:])
                if cb == "eventChange":
                    new_date = (ev.get("start") or "")[:10]
                    if new_date:
                        db.update_todo(tid, due_date=new_date, sync_calendar=1)
                        st.toast(f"締切を {new_date} に変更しました")
                        st.rerun()
                elif cb == "eventClick":
                    db.toggle_todo(tid)
                    st.rerun()


def _shift_month(delta):
    y, m = st.session_state.cal_year, st.session_state.cal_month
    m += delta
    if m < 1:
        m = 12; y -= 1
    elif m > 12:
        m = 1; y += 1
    st.session_state.cal_year, st.session_state.cal_month = y, m


def _ev_html(parsed, compact=False):
    title = parsed.get("clean_title") or parsed.get("title", "")
    cls = "cal-ev" if compact else "wk-ev"
    # タスク締切は枠線スタイルで区別
    if parsed.get("_deadline"):
        col = parsed.get("_proj_color", "#6E6C64")
        return (f"<div class='{cls}' style='background:transparent;color:#141414;"
                f"border:1.5px dashed {col}'>▢ 締切: {title}</div>")
    time_str = parsed.get("parsed_time")
    loc = parsed.get("parsed_location")
    bg, fg, icon_key = category_style(parsed.get("title", ""))

    if parsed.get("_overnight_next"):
        label = f"{title}明け"
        prefix = ""
    else:
        label = title
        prefix = f"{time_str} " if time_str else ""
    icon = icon_svg(icon_key, fg)
    loc_html = f" <span style='opacity:.7'>@{loc}</span>" if (loc and not compact) else ""
    return (f"<div class='{cls}' style='background:{bg};color:{fg}'>"
            f"{icon}<span>{prefix}{label}{loc_html}</span></div>")


def _weekly_strip(by_day, max_load):
    today = datetime.now(JST).date()
    monday = today - timedelta(days=today.weekday())
    cells = []
    for i in range(7):
        d = monday + timedelta(days=i)
        info = by_day.get(d, {"events": [], "load": 0.0})
        tint = load_to_tint(info["load"], max_load)
        is_today = (d == today)
        evs = "".join(_ev_html(e) for e in info["events"][:4])
        more = f"<div class='cal-more'>＋{len(info['events'])-4}件</div>" if len(info["events"]) > 4 else ""
        load_txt = f"<div class='wk-load'>負荷 {info['load']:.1f}</div>" if info["load"] > 0 else ""
        cells.append(
            f"<div class='wk-cell {'today' if is_today else ''}' style='background:{tint}'>"
            f"<div class='wk-dow'>{WEEKDAY_JA[i]}</div>"
            f"<div class='wk-date'>{d.day}</div>{evs}{more}{load_txt}</div>")
    st.markdown(f"<div class='wk-grid'>{''.join(cells)}</div>", unsafe_allow_html=True)


def _month_grid(by_day, max_load):
    y, m = st.session_state.cal_year, st.session_state.cal_month
    today = datetime.now(JST).date()
    cal_mod.setfirstweekday(cal_mod.MONDAY)
    weeks = cal_mod.monthcalendar(y, m)

    head = "".join(
        f"<div class='cal-head {'sat' if i==5 else 'sun' if i==6 else ''}'>{w}</div>"
        for i, w in enumerate(WEEKDAY_JA))

    cells = []
    for week in weeks:
        for i, day in enumerate(week):
            if day == 0:
                cells.append("<div class='cal-cell other'></div>")
                continue
            d = date(y, m, day)
            info = by_day.get(d, {"events": [], "load": 0.0})
            tint = load_to_tint(info["load"], max_load)
            is_today = (d == today)
            cls = "sat" if i == 5 else "sun" if i == 6 else ""
            evs = "".join(_ev_html(e, compact=True) for e in info["events"][:4])
            more = f"<div class='cal-more'>＋{len(info['events'])-4}</div>" if len(info["events"]) > 4 else ""
            cells.append(
                f"<div class='cal-cell {cls} {'cal-today' if is_today else ''}' "
                f"style='background:{tint}'>"
                f"<div class='cal-daynum'>{day}</div>{evs}{more}</div>")

    st.markdown(
        f"<div class='cal-grid'>{head}</div>"
        f"<div class='cal-grid' style='margin-top:6px'>{''.join(cells)}</div>",
        unsafe_allow_html=True)


def _legend():
    items = [("仕事", "#2563EB", "#fff"), ("当直", "#7C3AED", "#fff"),
             ("日直", "#15803D", "#fff"), ("飲み会", "#FACC15", "#141414"),
             ("外勤", "#7DD3FC", "#141414"), ("勉強会/学会", "#22C55E", "#fff"),
             ("家の用事", "#A3E635", "#141414"), ("バンド", "#9CA3AF", "#141414"),
             ("休み/有給", "#DB2777", "#fff")]
    chips = "".join(
        f"<span style='background:{bg};color:{fg};padding:2px 8px;border-radius:4px;"
        f"font-size:10.5px;font-weight:700;margin:2px'>{n}</span>" for n, bg, fg in items)
    return ("<div style='margin-top:12px'>" + chips +
            "<div class='tmeta' style='margin-top:8px'>"
            "マスの赤みが濃いほど負荷大。当直は入り＆明けで2日表示。予定名から時刻・場所を自動抽出。</div></div>")
