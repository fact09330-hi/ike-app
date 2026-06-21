"""Ike App — グローバルスタイル（BRUTUS風 ライトエディトリアルUI / 上部ナビ）

配色:
  キャンバス  = 温かいライトグレー #E7E5E0（微細グレイン）
  サーフェス  = 灰色パネル #DCDAD3（白背景は廃止）
  主役カラー  = 黒 #141414（見出し・アクティブ・主要ボタン）
  差し色      = コバルトブルー #2840E6
"""
import base64
from pathlib import Path

ICON_PNG = Path(__file__).parent / "assets" / "ike_icon_256.png"

# 微細グレイン
_GRAIN = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' "
    "baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E"
    "%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E\")"
)


def logo_data_uri() -> str:
    if ICON_PNG.exists():
        b64 = base64.b64encode(ICON_PNG.read_bytes()).decode()
        return f"data:image/png;base64,{b64}"
    return ""


CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
/* 全ての secondary ボタン（ポップオーバーのトリガー ✏ 含む）を明るく＝見やすく。
   ナビは別ルールで透明上書きされるので影響なし。 */
[data-testid="baseButton-secondary"] {{
    background:#DCDAD3 !important; color:#141414 !important;
    border:1.5px solid #141414 !important; border-radius:5px !important; box-shadow:none !important;
}}
[data-testid="baseButton-secondary"]:hover {{ background:#141414 !important; color:#FCFBF9 !important; }}
[data-testid="baseButton-secondary"] * {{ color:inherit !important; }}
[data-testid="baseButton-secondary"]:hover * {{ color:#FCFBF9 !important; }}

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Hiragino Sans', sans-serif;
}}
html, body, #root, .stApp,
[data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"], .main, .appview-container {{
    background-color: #E7E5E0 !important;
}}
.stApp {{
    background-image: {_GRAIN};
    color: #141414;
}}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1600px; }}
header[data-testid="stHeader"] {{ background: transparent; height:0; }}
#MainMenu, footer {{ visibility: hidden; }}

/* ── サイドバー（格納式メニュー・ライト）── */
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{
    background:#EFEEE9 !important; border-right:1.5px solid #141414;
}}
.side-brand {{ font-size:21px; font-weight:900; color:#141414 !important; letter-spacing:-0.5px; padding:6px 6px 0; }}
.side-sub {{ font-size:9px; font-weight:800; letter-spacing:2.5px; color:#8A887F !important; margin:1px 0 12px 7px; }}
/* サイドバーのナビボタン（左寄せ・縦並び）*/
section[data-testid="stSidebar"] .stButton button {{
    width:100%; text-align:left; justify-content:flex-start;
    background:transparent !important; border:none !important; border-radius:8px !important;
    color:#2A2A26 !important; font-size:15px; font-weight:800; padding:11px 14px !important;
    box-shadow:none !important; margin-bottom:3px;
}}
section[data-testid="stSidebar"] .stButton button * {{ color:#2A2A26 !important; }}
section[data-testid="stSidebar"] .stButton button:hover {{ background:rgba(20,20,20,0.07) !important; }}
section[data-testid="stSidebar"] .stButton button:hover * {{ color:#141414 !important; }}
section[data-testid="stSidebar"] .stButton button[kind="primary"] {{
    background:rgba(40,64,230,0.13) !important; box-shadow:inset 4px 0 0 #2840E6 !important;
}}
section[data-testid="stSidebar"] .stButton button[kind="primary"] * {{ color:#141414 !important; font-weight:900 !important; }}
/* ハンバーガー(≡)とサイドバー開閉ボタンを目立たせる */
[data-testid="stSidebarCollapsedControl"] button, [data-testid="stSidebarCollapseButton"] button {{
    color:#141414 !important; background:#DCDAD3 !important; border:1.5px solid #141414 !important;
    border-radius:7px !important;
}}

/* ── 上部バー（中央寄せ）── */
.topbar {{ display:flex; align-items:center; justify-content:center; gap:13px; margin-bottom:8px; }}
.topbar .logo-img {{ width:46px; height:46px; border-radius:10px; }}
.topbar .bt {{ font-size:24px; font-weight:900; letter-spacing:-0.6px; color:#141414; line-height:1; }}
.topbar .bs {{ font-size:9.5px; color:#7A786F; letter-spacing:2px; font-weight:700; margin-top:4px; }}

/* ナビはサイドバーへ移動（スタイルは上の stSidebar ルールで定義）*/
.nav-divider {{ border-bottom:1.5px solid #141414; margin:2px 0 14px; }}

/* ── PC左上クイックアイコンナビ（5ページ）── */
.element-container:has(.pcnav-marker) + div [data-testid="stHorizontalBlock"] {{ gap:7px; }}
.element-container:has(.pcnav-marker) + div [data-testid="column"] button {{
    background:#EFEEE9 !important; border:1.5px solid rgba(20,20,20,0.18) !important;
    border-radius:9px !important; min-height:44px; box-shadow:none !important; padding:5px !important;
}}
.element-container:has(.pcnav-marker) + div [data-testid="column"] button:hover {{
    border-color:#2840E6 !important; background:#FFFFFF !important;
}}

/* ── 見出し ── */
h1 {{ font-weight:900 !important; letter-spacing:-0.8px; font-size:28px !important; color:#141414 !important; }}
h2 {{ font-weight:800 !important; letter-spacing:-0.3px; color:#141414 !important; }}
h3 {{ font-weight:800 !important; font-size:16px !important; color:#222 !important; }}

/* ── メトリクスカード（濃いパネルで強調・4つ同サイズ）── */
div[data-testid="stMetric"] {{
    background:#1C1C19; border:1.5px solid #141414;
    padding:16px 18px; border-radius:5px; box-shadow:3px 3px 0 rgba(40,64,230,0.30);
    min-height:104px; display:flex; flex-direction:column; justify-content:center;
}}
div[data-testid="stMetric"] label p {{ color:#B6B4AB !important; font-size:12px !important; font-weight:700 !important; letter-spacing:0.5px; }}
div[data-testid="stMetricValue"] {{ font-weight:900 !important; font-size:32px !important; color:#FCFBF9 !important; }}
div[data-testid="stMetric"] svg {{ fill:#B6B4AB !important; }}

/* ── カード枠（ページ地より明るい灰でコントラスト）── */
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    border-color:#141414 !important; background:#F0EFEB; border-radius:5px;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:5px !important; }}
/* 入れ子カード（編集パネル）はさらに白寄りで明確に */
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background:#FBFAF7; border-color:rgba(20,20,20,0.25) !important;
}}

/* ── タブ ── */
button[data-baseweb="tab"] {{ font-weight:800; font-size:13.5px; color:#6E6C64; }}
div[data-baseweb="tab-list"] {{ gap:8px; border-bottom:1.5px solid rgba(20,20,20,0.18); background:transparent; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:#141414; }}
div[data-baseweb="tab-highlight"] {{ background:#141414; }}

/* ── 入力系（灰色）── */
.stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input,
div[data-baseweb="select"] > div, div[data-baseweb="input"] {{
    background:#E2E0DA !important; border:1.5px solid rgba(20,20,20,0.30) !important;
    border-radius:5px !important; color:#141414 !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{ border-color:#2840E6 !important; }}
.stButton > button {{
    border-radius:5px; font-weight:700; border:1.5px solid #141414 !important;
    background:#DCDAD3 !important; color:#141414 !important; transition:all .12s;
}}
.stButton > button p, .stButton > button div, .stButton > button span {{ color:#141414 !important; }}
.stButton > button:hover {{ background:#141414 !important; color:#FCFBF9 !important; }}
.stButton > button:hover p, .stButton > button:hover span {{ color:#FCFBF9 !important; }}
.stButton > button[kind="primary"] {{
    background:#141414 !important; color:#FCFBF9 !important; border:1.5px solid #141414 !important;
    box-shadow:3px 3px 0 rgba(40,64,230,0.25);
}}
.stButton > button[kind="primary"] p, .stButton > button[kind="primary"] span {{ color:#FCFBF9 !important; }}
.stButton > button[kind="primary"]:hover {{ background:#2840E6 !important; border-color:#2840E6 !important; }}

/* ── タスク行（灰色・コンパクト）── */
.task-row {{
    display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:5px;
    margin:2px 0; background:#D7D5CE; border:1.5px solid rgba(20,20,20,0.18); transition:all .12s;
}}
.task-row:hover {{ border-color:#2840E6; }}
.task-done {{ opacity:0.5; }}
.task-done .tt {{ text-decoration:line-through; }}
.tt {{ font-weight:700; font-size:13.5px; color:#1A1A1A; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.tmeta {{ font-size:11px; color:#6E6C64; }}
/* ToDoカードの行間を詰める */
.todo-compact [data-testid="stHorizontalBlock"] {{ gap:0.3rem; margin-bottom:0 !important; }}
.todo-compact div[data-testid="stCheckbox"] {{ margin-top:2px; }}

.pri-dot {{ width:9px;height:9px;border-radius:50%;display:inline-block; flex-shrink:0;}}
.pri-1 {{ background:#E0245E; }}
.pri-2 {{ background:#E8870C; }}
.pri-3 {{ background:#1A9E5B; }}

.chip {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:10.5px; font-weight:700;
    margin-right:4px; background:rgba(40,64,230,0.12); color:#2840E6; border:1px solid rgba(40,64,230,0.30); }}
.chip-gray {{ background:#CFCDC6; color:#5E5C54; border:1px solid rgba(20,20,20,0.18);}}

.sec-label {{ font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:1.5px;
    color:#8A8880; margin:18px 0 8px; }}

/* ── カレンダーグリッド ── */
.cal-grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:5px; }}
.cal-head {{ text-align:center; font-size:11px; font-weight:800; color:#8A8880; padding:6px 0;
    text-transform:uppercase; letter-spacing:0.5px; }}
.cal-cell {{ min-height:104px; border-radius:5px; padding:6px 7px; background:#D7D5CE;
    border:1.5px solid rgba(20,20,20,0.16); position:relative; overflow:hidden; }}
.cal-cell.other {{ opacity:0.4; background:transparent; border-color:rgba(20,20,20,0.08); }}
.cal-daynum {{ font-size:12px; font-weight:800; color:#3A3A36; margin-bottom:4px; }}
.cal-today .cal-daynum {{ background:#141414; color:#FCFBF9; border-radius:5px; padding:1px 7px; display:inline-block; }}
.cal-ev {{ font-size:10.5px; padding:2px 6px; border-radius:4px; margin-bottom:3px; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; font-weight:700; display:flex; align-items:center; gap:3px; }}
.cal-ev svg {{ width:10px; height:10px; flex-shrink:0; }}
.cal-more {{ font-size:10px; color:#8A8880; font-weight:700; }}
.sat .cal-daynum {{ color:#2B6CB0; }}
.sun .cal-daynum {{ color:#C0392B; }}

/* 週間ストリップ */
.wk-grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }}
.wk-cell {{ border-radius:5px; padding:9px; min-height:140px; background:#D7D5CE;
    border:1.5px solid rgba(20,20,20,0.16); }}
.wk-cell.today {{ border:2.5px solid #141414; }}
.wk-dow {{ font-size:11px; font-weight:800; color:#8A8880; }}
.wk-date {{ font-size:20px; font-weight:900; color:#141414; margin-bottom:6px; }}
.wk-ev {{ font-size:11px; padding:3px 7px; border-radius:4px; margin-bottom:4px; font-weight:700;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; gap:4px; }}
.wk-ev svg {{ width:11px; height:11px; flex-shrink:0; }}
.wk-load {{ font-size:10px; color:#8A8880; margin-top:2px; font-weight:700; }}

/* 週/月の境界見出し */
.cal-section {{ font-size:13px; font-weight:900; color:#141414; letter-spacing:1px;
    border-left:5px solid #141414; padding-left:10px; margin:6px 0 10px; text-transform:uppercase; }}

/* プロジェクト */
.proj-head {{ display:flex; align-items:center; gap:10px; }}
.proj-dot {{ width:13px;height:13px;border-radius:3px;flex-shrink:0; border:1px solid rgba(0,0,0,0.25);}}
.proj-name {{ font-weight:800; font-size:15px; color:#141414; }}
.proj-bar-bg {{ height:7px;border-radius:99px;background:#C7C5BE;overflow:hidden; margin-top:7px;}}
.proj-bar-fill {{ height:100%;border-radius:99px; }}

.sb {{ padding:3px 10px;border-radius:4px;font-size:11px;font-weight:800;white-space:nowrap; }}
.sb-not_started {{ background:#FACC15;color:#713F12; }}      /* 未着手=黄 */
.sb-active {{ background:#16A34A;color:#FFFFFF; }}            /* 進行中=緑 */
.sb-onhold {{ background:#7C3AED;color:#FFFFFF; }}            /* 保留=紫 */
.sb-completed {{ background:#2563EB;color:#FFFFFF; }}         /* 完了=青 */

.ai-card {{ background:#DCDAD3; border:1.5px solid #141414; border-radius:5px; padding:14px 16px;
    box-shadow:3px 3px 0 rgba(40,64,230,0.18); }}
.ai-title {{ font-weight:800;font-size:13px;color:#141414;margin-bottom:8px; }}
.ai-item {{ font-size:13px;color:#2A2A26;margin:5px 0;padding-left:18px;position:relative; }}
.ai-item:before {{ content:"›";position:absolute;left:4px;color:#2840E6;font-weight:800; }}

hr {{ border-color:rgba(20,20,20,0.14) !important; margin:14px 0 !important; }}
a {{ color:#2840E6 !important; }}

/* ════════════════ スマホ最適化（横幅768px以下）════════════════ */
@media (max-width: 768px) {{
    .block-container {{ padding-left:0.55rem !important; padding-right:0.55rem !important;
        padding-top:0.5rem !important; }}

    /* PCクイックアイコンナビはスマホでは隠す（メニュー≡を使う）*/
    .element-container:has(.pcnav-marker) + div {{ display:none !important; }}
    .element-container:has(.pcnav-marker) {{ display:none !important; }}

    /* スマホ：横並びカラムは原則すべて縦積み（画面外へのはみ出しを防ぐ）。
       タスク行を“直接”包む最内側の行だけ、後段の例外ルールで1行に戻す。
       ※ :has(.task-row) は子孫を持つ祖先にもマッチするため、祖先の2カラム等が
         横並びのまま残って画面外にはみ出していた。既定で全部縦積みにして根絶する。 */
    [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap !important; }}
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
        flex:1 1 100% !important; min-width:100% !important; width:100% !important;
    }}

    /* 上部バー */
    .topbar {{ gap:9px; margin-bottom:4px; }}
    .topbar .logo-img {{ width:34px; height:34px; }}
    .topbar .bt {{ font-size:19px; }}
    .topbar .bs {{ font-size:7.5px; letter-spacing:1.2px; }}

    h1 {{ font-size:21px !important; }}
    h2 {{ font-size:17px !important; }}
    h3 {{ font-size:15px !important; }}

    /* ナビ＝横スクロールの帯（縦に間延びさせない）*/
    .element-container:has(.nav-wrap) + div [data-testid="stHorizontalBlock"] {{
        flex-direction:row !important; flex-wrap:nowrap !important;
        overflow-x:auto !important; gap:3px !important; padding-bottom:3px;
        -webkit-overflow-scrolling:touch; scrollbar-width:none;
    }}
    .element-container:has(.nav-wrap) + div [data-testid="stHorizontalBlock"]::-webkit-scrollbar {{ display:none; }}
    .element-container:has(.nav-wrap) + div [data-testid="column"] {{
        flex:0 0 auto !important; width:auto !important; min-width:0 !important;
    }}
    .element-container:has(.nav-wrap) + div button {{
        font-size:12.5px !important; padding:9px 13px !important; white-space:nowrap;
        border-radius:7px !important;
    }}
    .nav-divider {{ margin:2px 0 12px; }}

    /* メトリクス／KPI＝大きく読む */
    div[data-testid="stMetric"] {{ min-height:auto; padding:13px 15px; }}
    div[data-testid="stMetricValue"] {{ font-size:26px !important; }}
    /* ダッシュボードのKPI行＝2列で折り返す */
    .kpi-row {{ flex-wrap:wrap !important; gap:8px !important; }}
    .kpi-card {{ flex:1 1 calc(50% - 6px) !important; min-width:calc(50% - 6px) !important;
        height:auto !important; min-height:74px !important; }}

    /* 週間ストリップ＝4列グリッド（7日が2段で全部見える・横スクロール無し）*/
    .wk-grid {{ display:grid !important; grid-template-columns:repeat(4,minmax(0,1fr)) !important;
        gap:6px !important; overflow-x:visible !important; }}
    .wk-cell {{ min-height:92px; padding:7px; overflow:hidden; }}
    .wk-date {{ font-size:17px; margin-bottom:3px; }}
    .wk-ev {{ font-size:10px; padding:2px 5px; margin-bottom:3px; }}
    .wk-dow {{ font-size:10px; }}

    /* ボタン＝タップしやすく */
    .stButton > button {{ padding:10px 12px !important; font-size:14px !important; min-height:44px; }}

    /* 入力欄＝高さ確保＋16px（iOSの自動ズーム防止）*/
    .stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea,
    div[data-baseweb="select"] > div, div[data-baseweb="input"] input {{
        min-height:44px; font-size:16px !important;
    }}

    /* テキスト視認性を底上げ */
    .tt {{ font-size:14px; }}
    .tmeta {{ font-size:11.5px; }}
    .chip {{ font-size:11px; padding:2px 8px; }}
    .proj-name {{ font-size:15px; }}
    .cal-section {{ font-size:12px; }}

    /* 横並びカラムの隙間を詰める（ナビは別ルールで上書き済み）*/
    [data-testid="stHorizontalBlock"] {{ gap:0.4rem; }}

    /* ToDo/締切のタスク行＝チェック｜本文｜✏ を1行に固定（縦積みのデッドスペース解消）。
       “最内側”＝タスク行を直接含み、子に入れ子のHorizontalBlockを持たない行のみ対象。
       （祖先の横並びは上の既定ルールで縦積みになるので、画面外はみ出しが起きない）*/
    [data-testid="stHorizontalBlock"]:has(.task-row):not(:has(> [data-testid="column"] [data-testid="stHorizontalBlock"])) {{
        flex-direction:row !important; flex-wrap:nowrap !important; align-items:center;
        gap:4px !important;
    }}
    /* チェック/ボタン/ポップオーバー等の列＝自然幅を維持（潰れて画面外に押し出されない）*/
    [data-testid="stHorizontalBlock"]:has(.task-row):not(:has(> [data-testid="column"] [data-testid="stHorizontalBlock"])) > [data-testid="column"] {{
        width:auto !important; flex:0 0 auto !important; min-width:0 !important;
    }}
    /* タスク行本体を含む列だけ伸縮（タイトルは…で省略）。列番号ではなく中身で判定＝構成が
       [本文｜ボタン] でも [チェック｜本文｜✏] でも崩れない。 */
    [data-testid="stHorizontalBlock"]:has(.task-row):not(:has(> [data-testid="column"] [data-testid="stHorizontalBlock"])) > [data-testid="column"]:has(.task-row) {{
        flex:1 1 auto !important; min-width:0 !important;
    }}
    /* タスク行内のボタン(✏)とチェックを小さく */
    [data-testid="stHorizontalBlock"]:has(.task-row) .stButton button {{
        padding:6px 8px !important; min-height:36px;
    }}
    /* 本文を省略表示にして1行に収める（はみ出し＆✏画面外を防ぐ）*/
    .task-row {{ min-width:0; max-width:100%; overflow:hidden; gap:5px; }}
    .task-row .tt {{ flex:1 1 auto; min-width:0; }}
    .task-row .chip {{ font-size:9.5px; padding:1px 5px; flex-shrink:0; }}
    .task-row .tmeta {{ flex-shrink:0; }}
}}
</style>
"""


def inject():
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    # （PC左上クイックナビのアイコンは app.py の JS で挿入＝環境差に強い）
    try:
        import icons
        # サイドバーのナビにカスタムSVGアイコン（element-container nth-child 2..8）
        sb_order = ["dashboard", "calendar", "projects", "todos", "pomodoro", "email", "settings"]
        sbsel = ("section[data-testid='stSidebar'] [data-testid='stSidebarUserContent'] "
                 "[data-testid='stVerticalBlock'] > [data-testid='element-container']")
        css2 = (f"<style>{sbsel} button::before{{content:'';display:inline-block;"
                f"width:19px;height:19px;margin-right:11px;flex-shrink:0;background-size:contain;"
                f"background-repeat:no-repeat;background-position:center;}}")
        for i, key in enumerate(sb_order, start=2):
            uri = icons.custom_data_uri(key)
            if uri:
                css2 += f"{sbsel}:nth-child({i}) button::before{{background-image:{uri};}}"
        css2 += "</style>"
        st.markdown(css2, unsafe_allow_html=True)
    except Exception:
        pass


# チャート共通カラー
CHART = {
    "font": "#1F1F1C", "grid": "rgba(20,20,20,0.12)", "paper": "rgba(0,0,0,0)",
    "ink": "#141414", "accent": "#2840E6", "load": "#E0245E", "total": "#FF5A1F",
}
PALETTE = ["#141414", "#2840E6", "#E0245E", "#E8870C", "#1A9E5B",
           "#7C3AED", "#0891B2", "#B45309", "#BE185D", "#4D7C0F"]
