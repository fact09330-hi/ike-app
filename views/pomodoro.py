"""ポモドーロ画面 — タスクを選んで集中タイマー。時間を記録しプロジェクト別に集計。
円形カウントダウン（JS）で滑らかに表示。作業/休憩/繰り返しを設定可能。
"""
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px

import database as db
from style import PALETTE, CHART
from ui_helpers import JST


def render():
    st.markdown("# ポモドーロ")
    stats = db.pomodoro_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("今日の集中", f"{stats['today_min']:.0f} 分")
    c2.metric("累計集中", f"{stats['total_min']/60:.1f} 時間")
    c3.metric("セッション数", stats["count"])

    projects = db.get_projects()
    proj_map = {p["id"]: p for p in projects}

    if st.session_state.get("pomo_running"):
        _active_timer(proj_map)          # 実行中は全幅でタイマーに集中
        return

    # Focus風：タイマー / 統計 / 設定 のタブ
    tab1, tab2, tab3 = st.tabs(["⏱ タイマー", "📊 統計", "⚙️ 設定"])
    with tab3:
        _time_settings()
    with tab1:
        _setup_focus(projects)
    with tab2:
        _analytics(proj_map)


def _time_settings():
    st.markdown("#### 時間設定")
    t = st.columns(2)
    t[0].number_input("作業(分)", 1, 120, 25, key="pomo_work")
    t[1].number_input("休憩(分)", 1, 60, 5, key="pomo_break")
    t2 = st.columns(2)
    t2[0].number_input("繰り返し", 1, 12, 4, key="pomo_cycles")
    t2[1].number_input("長休憩(分)", 1, 60, 15, key="pomo_long")
    st.caption("ここで設定した時間で「タイマー」タブから開始します。")


def _setup_focus(projects):
    st.markdown("#### 何に取り組む？")
    proj_opts = [None] + [p["id"] for p in projects]
    pname = {p["id"]: p["name"] for p in projects}
    pid = st.selectbox("プロジェクト", proj_opts,
                       format_func=lambda x: "（指定なし）" if x is None else pname.get(x, ""),
                       key="pomo_pid")
    todo_id = None
    label = ""
    if pid:
        tasks = db.get_todos(project_id=pid, include_completed=False)
        topts = [None] + [t["id"] for t in tasks]
        tname = {t["id"]: t["title"] for t in tasks}
        todo_id = st.selectbox("タスク（任意）", topts,
                               format_func=lambda x: "（プロジェクト全体）" if x is None else tname.get(x, ""),
                               key="pomo_tid")
        label = pname.get(pid, "") + (f" / {tname.get(todo_id)}" if todo_id else "")
    else:
        label = st.text_input("ラベル（自由入力）", placeholder="例: 読書・勉強", key="pomo_label")

    work = int(st.session_state.get("pomo_work", 25))
    brk = int(st.session_state.get("pomo_break", 5))
    cycles = int(st.session_state.get("pomo_cycles", 4))
    longbrk = int(st.session_state.get("pomo_long", 15))
    # Focus風の大きな時間プレビュー
    st.markdown(
        f"<div style='text-align:center;font-size:54px;font-weight:900;color:#1A9E5B;"
        f"margin:14px 0 2px;letter-spacing:1px'>{work:02d}:00</div>"
        f"<div class='tmeta' style='text-align:center;margin-bottom:12px'>"
        f"作業{work}分 ・ 休憩{brk}分 ・ {cycles}セット（変更は「設定」タブ）</div>",
        unsafe_allow_html=True)
    if st.button("▶ スタート", type="primary", use_container_width=True):
        st.session_state.pomo_running = True
        st.session_state.pomo_data = {
            "project_id": pid, "todo_id": todo_id, "label": label or "集中",
            "work": work, "break": brk, "cycles": cycles,
            "long": longbrk, "start": datetime.now(JST).isoformat(),
        }
        st.rerun()


def _active_timer(proj_map):
    d = st.session_state.pomo_data
    st.markdown(f"### 🎯 {d['label']}")
    _timer_component(d["work"], d["break"], d["long"], d["cycles"])

    started = datetime.fromisoformat(d["start"])
    elapsed = (datetime.now(JST) - started).total_seconds() / 60
    planned = d["work"] * d["cycles"]

    cc = st.columns([2, 2, 2])
    if cc[0].button("✓ 完了して記録", type="primary", use_container_width=True):
        focus = round(min(max(elapsed, 0), planned), 1)
        db.add_pomodoro(focus, d["project_id"], d["todo_id"], d["label"],
                        d["cycles"], d["start"])
        st.session_state.pomo_running = False
        st.success(f"{focus:.0f}分の集中を記録しました 🎉")
        st.rerun()
    if cc[1].button("⏹ 中断して記録", use_container_width=True):
        focus = round(min(max(elapsed, 0), planned), 1)
        if focus >= 1:
            db.add_pomodoro(focus, d["project_id"], d["todo_id"], d["label"],
                            d["cycles"], d["start"])
        st.session_state.pomo_running = False
        st.rerun()
    if cc[2].button("✕ 破棄", use_container_width=True):
        st.session_state.pomo_running = False
        st.rerun()
    st.caption("タイマーはこの画面内で動きます。完了時に押すと集中時間が記録されます。")


def _timer_component(work, brk, longbrk, cycles):
    html = """
<div id="pomo" style="font-family:'Inter',-apple-system,sans-serif;text-align:center;padding:6px">
  <svg width="240" height="240" viewBox="0 0 240 240">
    <circle cx="120" cy="120" r="104" fill="none" stroke="rgba(20,20,20,0.12)" stroke-width="14"/>
    <circle id="ring" cx="120" cy="120" r="104" fill="none" stroke="#141414" stroke-width="14"
      stroke-linecap="round" stroke-dasharray="653" stroke-dashoffset="0"
      transform="rotate(-90 120 120)"/>
    <text id="time" x="120" y="118" text-anchor="middle" font-size="46" font-weight="900" fill="#141414">25:00</text>
    <text id="phase" x="120" y="150" text-anchor="middle" font-size="15" font-weight="700" fill="#6E6C64">集中</text>
    <text id="cyc" x="120" y="172" text-anchor="middle" font-size="12" fill="#8A8880"></text>
  </svg>
  <div style="margin-top:8px">
    <button id="pp" onclick="toggle()" style="font-size:14px;font-weight:700;padding:7px 22px;border-radius:8px;border:1.5px solid #141414;background:#141414;color:#FCFBF9;cursor:pointer">一時停止</button>
  </div>
</div>
<script>
const WORK=%d*60, BREAK=%d*60, LONG=%d*60, CYCLES=%d;
let phase='work', cyc=1, remain=WORK, paused=false, ring=document.getElementById('ring');
const C=653;
function fmt(s){let m=Math.floor(s/60),x=s%%60;return (m<10?'0':'')+m+':'+(x<10?'0':'')+x;}
function beep(){try{let a=new(window.AudioContext||window.webkitAudioContext)();let o=a.createOscillator();let g=a.createGain();o.connect(g);g.connect(a.destination);o.frequency.value=660;o.start();g.gain.setValueAtTime(0.18,a.currentTime);g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+0.5);o.stop(a.currentTime+0.5);}catch(e){}}
function total(){return phase==='work'?WORK:(phase==='long'?LONG:BREAK);}
function render(){
  document.getElementById('time').textContent=fmt(remain);
  document.getElementById('phase').textContent=phase==='work'?'集中':'休憩';
  document.getElementById('phase').setAttribute('fill', phase==='work'?'#141414':'#1A9E5B');
  document.getElementById('cyc').textContent=cyc+' / '+CYCLES+' セット';
  ring.setAttribute('stroke', phase==='work'?'#141414':'#1A9E5B');
  ring.setAttribute('stroke-dashoffset', C*(1-remain/total()));
}
function tick(){
  if(paused) return;
  remain--;
  if(remain<0){
    beep();
    if(phase==='work'){
      if(cyc>=CYCLES){ phase='done'; document.getElementById('time').textContent='完了'; document.getElementById('phase').textContent='お疲れ様！'; return; }
      phase=(cyc%%4===0)?'long':'break'; remain=total();
    } else { phase='work'; cyc++; remain=WORK; }
  }
  render();
}
function toggle(){paused=!paused;document.getElementById('pp').textContent=paused?'再開':'一時停止';document.getElementById('pp').style.background=paused?'#2840E6':'#141414';}
render(); setInterval(tick,1000);
</script>
""" % (work, brk, longbrk, cycles)
    components.html(html, height=320)


def _theme_of(s, proj_map):
    if s.get("project_id") and s["project_id"] in proj_map:
        return proj_map[s["project_id"]]["name"]
    return s.get("label") or "（指定なし）"


def _analytics(proj_map):
    import plotly.graph_objects as go
    from collections import defaultdict
    st.markdown("## 記録")
    sessions = db.get_pomodoro_sessions(limit=500)
    if not sessions:
        st.caption("まだ記録がありません。ポモドーロを完了すると、ここに日々の集中時間が溜まります。")
        return

    # ── 日次の集中時間（直近10日）棒グラフ ──
    daily = defaultdict(float)
    for s in sessions:
        d = (s.get("ended_at") or "")[:10]
        if d:
            daily[d] += s["focus_minutes"]
    days = sorted(daily.keys())[-10:]
    if days:
        labels = [f"{int(d[5:7])}/{int(d[8:10])}" for d in days]
        hrs = [daily[d] / 60 for d in days]
        fig = go.Figure(go.Bar(
            x=labels, y=hrs, marker_color=CHART["accent"], marker_line_width=0,
            text=[f"{h:.1f}h" for h in hrs], textposition="outside",
            textfont=dict(size=11, color=CHART["font"])))
        fig.update_layout(
            height=230, margin=dict(t=24, b=8, l=8, r=8),
            paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
            font=dict(color=CHART["font"], size=11), showlegend=False,
            xaxis=dict(showgrid=False, tickfont=dict(size=12, color=CHART["font"])),
            yaxis=dict(showgrid=True, gridcolor=CHART["grid"], title="集中(時間)",
                       rangemode="tozero"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── テーマ(プロジェクト)別ドーナツ ──
    by_theme = defaultdict(float)
    for s in sessions:
        by_theme[_theme_of(s, proj_map)] += s["focus_minutes"]
    items = sorted(by_theme.items(), key=lambda x: -x[1])
    df = pd.DataFrame([{"テーマ": k, "時間": round(v / 60, 1)} for k, v in items])
    fig2 = px.pie(df, values="時間", names="テーマ", hole=0.6,
                  color_discrete_sequence=PALETTE)
    fig2.update_traces(textposition="outside",
                       texttemplate="%{label} %{value:.1f} h",
                       marker=dict(line=dict(color="#E7E5E0", width=2)))
    fig2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10),
                       paper_bgcolor=CHART["paper"], font=dict(color=CHART["font"], size=11),
                       showlegend=True, legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── 直近10件の集中実績テーブル ──
    st.markdown("### 直近10件の集中実績")
    rows = []
    for s in sessions[:10]:
        m = int(s["focus_minutes"]); sec = round((s["focus_minutes"] - m) * 60)
        rows.append({"日付": (s.get("ended_at") or "")[:10],
                     "テーマ": _theme_of(s, proj_map),
                     "集中時間": f"{m}分{sec}秒"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("これらの記録は機械学習用データ(activity_log/pomodoro_sessions)にも蓄積され、"
               "プロジェクトごとの時間配分の分析に使われます。")
