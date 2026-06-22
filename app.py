"""Ike App — メインアプリ (Streamlit / 上部ナビ)
起動: streamlit run app.py
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import cloud_bootstrap
cloud_bootstrap.bootstrap()   # クラウド時のみ: secrets→環境変数・認証ファイルを展開（ローカルは無処理）

import database as db
import style
import ai_assistant as ai
from ike_task_volume import IKETaskVolume
from calendar_loader import load_events, is_authenticated
from views import (dashboard, calendar_view, projects, todos, settings,
                   email_view, widget_view, pomodoro)

st.set_page_config(page_title="Ike App", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")  # 既定は≡で格納（PC/スマホ共通）
style.inject()

import auth
auth.require_login()          # パスワード設定時のみログイン要求（ローカルは素通り）

db.init_db()
db.seed_builtin_presets()
scorer = IKETaskVolume()


@st.cache_data(ttl=600, show_spinner=False)
def _widget_events(cal_ids):
    # ダッシュボードと同じ範囲(30日前〜120日後)にして負荷合計を一致させる
    return load_events(list(cal_ids), 30, 120)


# ── ウィジェット表示（?view=widget の小窓用）──
if st.query_params.get("view") == "widget":
    style.inject()
    st.markdown("<style>.block-container{padding:0.6rem 0.7rem !important;max-width:100% !important}"
                "header,#MainMenu,footer{display:none!important}</style>",
                unsafe_allow_html=True)
    cal_ids = [c.strip() for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",") if c.strip()]
    try:
        wev, _ = _widget_events(tuple(cal_ids))
    except Exception:
        wev = []
    widget_view.render(wev or [], scorer)
    st.stop()

# (key, ラベル)
NAV = [
    ("dashboard", "ダッシュボード"),
    ("calendar", "カレンダー"),
    ("projects", "プロジェクト"),
    ("todos", "ToDo"),
    ("pomodoro", "ポモドーロ"),
    ("email", "メール"),
    ("settings", "設定"),
]

if "page" not in st.session_state:
    st.session_state.page = "dashboard"


@st.cache_data(ttl=600, show_spinner=False)
def cached_events(cal_ids, days_past, days_future):
    from datetime import datetime
    import pytz
    events, err = load_events(list(cal_ids), days_past, days_future)
    synced = datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%-m/%-d %H:%M")
    return events, err, synced


# ─────────── PC用 左上クイックアイコンナビ（PCのみ・5ページへ）───────────
st.markdown("<div class='pcnav-marker'></div>", unsafe_allow_html=True)
_PCNAV = [("dashboard", "ダッシュボード"), ("calendar", "カレンダー"),
          ("projects", "プロジェクト"), ("todos", "ToDo"), ("email", "メール")]
_pc_cols = st.columns([1, 1, 1, 1, 1, 9])
for _col, (_k, _lbl) in zip(_pc_cols, _PCNAV):
    if _col.button("　", key=f"pcnav_{_k}", help=_lbl, use_container_width=True):
        st.session_state.page = _k
        st.rerun()

# ─────────────── 上部バー（ロゴ＋タイトル・中央寄せ）───────────────
st.markdown(
    f"<div class='topbar'>"
    f"<img class='logo-img' src='{style.logo_data_uri()}'/>"
    f"<div><div class='bt'>Ike App</div>"
    f"<div class='bs'>CALENDAR × PROJECT × TODO</div></div>"
    f"</div>",
    unsafe_allow_html=True)

# ─────────────── 上部ナビ（横並び）───────────────
# ── ナビ＝サイドバー（スマホは≡で格納／PCは左に表示）──
with st.sidebar:
    st.markdown("<div class='side-brand'>Ike App</div>"
                "<div class='side-sub'>MENU</div><div class='nav-wrap'></div>",
                unsafe_allow_html=True)
    for key, label in NAV:
        if st.button(label, key=f"nav_{key}", use_container_width=True,
                     type="primary" if st.session_state.page == key else "secondary"):
            st.session_state.page = key
            st.rerun()

# ─────────────── イベント読み込み ───────────────
cal_ids = [c.strip() for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",") if c.strip()]
events, err, synced = cached_events(tuple(cal_ids), 30, 120)
st.session_state["last_sync"] = synced
if err and st.session_state.page in ("dashboard", "calendar"):
    st.info(err)

# ─────────────── ルーティング ───────────────
page = st.session_state.page
if page == "dashboard":
    dashboard.render(events, scorer)
elif page == "calendar":
    calendar_view.render(events, scorer)
elif page == "projects":
    projects.render(events, scorer)
elif page == "todos":
    todos.render(events, scorer)
elif page == "pomodoro":
    pomodoro.render()
elif page == "email":
    email_view.render()
elif page == "settings":
    settings.render(scorer, events)

# ─── メイン画面をクリック/マウス移動したらメニューを自動で閉じる ───
import streamlit.components.v1 as _components
_components.html("""
<script>
try {
  const doc = window.parent.document;
  window.parent.__ikeAutoHideLoaded = true;   // 親に到達できたか確認用
  function ikeClose(e){
    const sb = doc.querySelector('section[data-testid="stSidebar"]');
    if(!sb || sb.offsetWidth <= 100) return;            // 閉じていれば何もしない
    if(e && e.target && e.target.closest){
      if(e.target.closest('section[data-testid="stSidebar"]')) return;   // メニュー内は無視
      if(e.target.closest('[data-testid="collapsedControl"]')) return;   // 開くボタンは無視
      if(e.target.closest('[data-testid="stSidebarCollapseButton"]')) return;
    }
    const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
             || doc.querySelector('[data-testid="stSidebarCollapseButton"]');
    if(btn) btn.click();
  }
  if(!doc.__ikeAutoHideBound){
    doc.__ikeAutoHideBound = true;
    doc.addEventListener('click', ikeClose, true);       // メイン領域クリックで閉じる
    doc.addEventListener('mouseover', ikeClose, true);    // マウスがメインに移動したら閉じる
  }
} catch(err) { /* 親ドキュメントに到達できない場合は何もしない */ }
</script>
""", height=0)

# ─── 編集/削除/更新ボタンの絵文字をカスタムSVGアイコンに置換 ───
import icons as _icons
_btn_js = """
<script>
try {
  const doc = window.parent.document;
  const MAP = [{e:"✏️", u:"__EDIT__"}, {e:"🗑", u:"__DEL__"},
               {e:"🔄", u:"__REF__"}];
  function ikeBtnIcons(){
    doc.querySelectorAll('button').forEach(function(b){
      if(b.__ikeIco) return;
      const t = b.innerText || "";
      for(const m of MAP){
        if(m.u && t.indexOf(m.e) >= 0){
          b.__ikeIco = true;
          b.querySelectorAll('p,span,div').forEach(function(el){
            if(el.children.length===0 && el.textContent.indexOf(m.e)>=0){
              el.textContent = el.textContent.replace(m.e, '').trim();
            }
          });
          const img = doc.createElement('img'); img.src = m.u;
          img.style.cssText = 'width:16px;height:16px;vertical-align:-3px;margin-right:5px;pointer-events:none;flex-shrink:0';
          b.insertBefore(img, b.firstChild);
          break;
        }
      }
    });
  }
  // PC左上クイックナビ：.pcnav-marker の次の列の5ボタンにアイコンを入れる
  const PCNAV = ["__PC0__","__PC1__","__PC2__","__PC3__","__PC4__"];
  function ikePcNav(){
    const mk = doc.querySelector('.pcnav-marker');
    if(!mk) return;
    let ec = mk.closest('[data-testid="stElementContainer"]') || mk.closest('.element-container') || mk.parentElement;
    let row = ec ? ec.nextElementSibling : null;
    if(!row) return;
    const cols = row.querySelectorAll('[data-testid="column"]');
    cols.forEach(function(c, i){
      const b = c.querySelector('button');
      if(!b || i >= 5 || !PCNAV[i] || b.__ikePc) return;
      b.__ikePc = true;
      b.textContent = '';
      b.style.cssText += ';display:flex;align-items:center;justify-content:center;background:#EFEEE9;border:1.5px solid rgba(20,20,20,0.2);border-radius:9px;min-height:44px;padding:5px;box-shadow:none;';
      const img = doc.createElement('img'); img.src = PCNAV[i];
      img.style.cssText = 'width:24px;height:24px;pointer-events:none';
      b.appendChild(img);
    });
  }
  function ikeAll(){ ikeBtnIcons(); ikePcNav(); }
  setInterval(ikeAll, 700); ikeAll();
} catch(err) {}
</script>
"""
_btn_js = (_btn_js.replace("__EDIT__", _icons.custom_src("edit"))
                  .replace("__DEL__", _icons.custom_src("delete"))
                  .replace("__REF__", _icons.custom_src("refresh"))
                  .replace("__PC0__", _icons.custom_src("dashboard"))
                  .replace("__PC1__", _icons.custom_src("calendar"))
                  .replace("__PC2__", _icons.custom_src("projects"))
                  .replace("__PC3__", _icons.custom_src("todos"))
                  .replace("__PC4__", _icons.custom_src("email")))
_components.html(_btn_js, height=0)
