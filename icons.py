"""アウトライン線画アイコン（細線・角丸）。参考のような手描き風アウトライン。
- inline(name): HTMLに埋め込むSVG文字列（currentColorで文字色に追従）
- data_uri(name, color): CSSの content:url() 用
"""
from urllib.parse import quote

# 16x16 viewBox, stroke-based のパス（fill=none, stroke=currentColor）
_PATHS = {
    "dashboard": "<rect x='2' y='2' width='5' height='5' rx='1'/><rect x='9' y='2' width='5' height='5' rx='1'/><rect x='2' y='9' width='5' height='5' rx='1'/><rect x='9' y='9' width='5' height='5' rx='1'/>",
    "calendar": "<rect x='2' y='3' width='12' height='11' rx='1.5'/><path d='M2 6h12M5 1.5v3M11 1.5v3'/>",
    "folder": "<path d='M2 4.5a1 1 0 011-1h3l1.2 1.4H13a1 1 0 011 1V12a1 1 0 01-1 1H3a1 1 0 01-1-1z'/>",
    "todo": "<path d='M6 4h8M6 8h8M6 12h8'/><path d='M2.2 4l1 1 1.4-1.6M2.2 8l1 1 1.4-1.6M2.2 12l1 1 1.4-1.6'/>",
    "clock": "<circle cx='8' cy='8' r='6'/><path d='M8 4.5V8l2.5 1.5'/>",
    "mail": "<rect x='2' y='3.5' width='12' height='9' rx='1.5'/><path d='M2.5 4.5L8 8.5l5.5-4'/>",
    "settings": "<circle cx='8' cy='8' r='2.2'/><path d='M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4'/>",
    "refresh": "<path d='M13 8a5 5 0 11-1.5-3.5'/><path d='M13 2v3h-3'/>",
    "trash": "<path d='M3 4.5h10M6 4.5V3h4v1.5M4.5 4.5l.6 8.5a1 1 0 001 1h3.8a1 1 0 001-1l.6-8.5'/>",
    "edit": "<path d='M11 2.5l2.5 2.5M3 13l-.6-3L10 2.5a1 1 0 011.4 0l1.1 1.1a1 1 0 010 1.4L5 12.4z'/>",
    "plus": "<path d='M8 3v10M3 8h10'/>",
    "check": "<path d='M3 8.5l3.2 3.2L13 4.5'/>",
    "bolt": "<path d='M9 1.5L3.5 9H8l-1 5.5L12.5 7H8z'/>",
    "shield": "<path d='M8 1.8l5 1.8v3.5c0 3-2.2 5.4-5 6.6-2.8-1.2-5-3.6-5-6.6V3.6z'/>",
    "home": "<path d='M2.5 7.5L8 2.8l5.5 4.7M4 6.7V13h8V6.7'/>",
    "chart": "<path d='M2 13h12M4 13V8M7.3 13V4.5M10.6 13V9.5'/>",
}

_VIEWBOX = "0 0 16 16"


def inline(name, size=15, stroke=1.6):
    p = _PATHS.get(name, "")
    if not p:
        return ""
    return (f"<svg width='{size}' height='{size}' viewBox='{_VIEWBOX}' fill='none' "
            f"stroke='currentColor' stroke-width='{stroke}' stroke-linecap='round' "
            f"stroke-linejoin='round' style='vertical-align:-2px'>{p}</svg>")


def data_uri(name, color="#6E6C64", stroke=1.6):
    p = _PATHS.get(name, "")
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='{_VIEWBOX}' "
           f"fill='none' stroke='{color}' stroke-width='{stroke}' stroke-linecap='round' "
           f"stroke-linejoin='round'>{p}</svg>")
    return f"url(\"data:image/svg+xml,{quote(svg)}\")"


# ナビ用: key → アイコン名
NAV_ICONS = {
    "dashboard": "dashboard", "calendar": "calendar", "projects": "folder",
    "todos": "todo", "pomodoro": "clock", "email": "mail", "settings": "settings",
}


# ── ユーザー追加のカスタムSVGアイコン（icon/ ディレクトリ）──
import re as _re
import base64 as _b64
from pathlib import Path as _Path

_ICON_DIR = _Path(__file__).parent / "icon"
CUSTOM_ICONS = {
    "dashboard": "ダッシュボードアイコン.svg",
    "calendar": "カレンダーアイコン8.svg",
    "projects": "プロジェクトアイコン.svg",
    "todos": "ToDoアイコン素材.svg",
    "pomodoro": "ポモドーロアイコン.svg",
    "email": "メールアイコン.svg",
    "settings": "設定アイコン.svg",
    "ai": "AIアイコン.svg",
    "preset": "プリセットアイコン.svg",
    "localml": "ローカルML.svg",
    "delete": "削除アイコン.svg",
    "refresh": "更新アイコン.svg",
    "edit": "編集アイコン.svg",
}

# ユーザー追加のPNGアイコン（ラスター＝塗り/classの問題が起きず確実に描画）。
# SVGより優先して使う（custom_src/custom_data_uri が自動で優先）。
CUSTOM_PNG = {
    "dashboard": "ダッシュボードアイコン２アイコン.png",
    "calendar": "カレンダーアイコン２.png",
    "projects": "プロジェクトアイコン２.png",
    "todos": "タスクトレイアイコン.png",
    "email": "メールボックスアイコン2.png",
}
_custom_cache = {}


def _png_data_uri(filename):
    """PNGを <img src> / url() 両用の data URI（url()無しの素のsrc）に。"""
    cache_key = ("__png__", filename)
    if cache_key in _custom_cache:
        return _custom_cache[cache_key]
    try:
        data = (_ICON_DIR / filename).read_bytes()
        uri = "data:image/png;base64," + _b64.b64encode(data).decode()
    except Exception:
        uri = ""
    _custom_cache[cache_key] = uri
    return uri


def _read_custom_svg(filename, color="#4B4B4B"):
    key = (filename, color)
    if key in _custom_cache:
        return _custom_cache[key]
    try:
        svg = (_ICON_DIR / filename).read_text(encoding="utf-8")
        svg = _re.sub(r"<!--.*?-->", "", svg, flags=_re.DOTALL)
        svg = _re.sub(r"<\?xml.*?\?>", "", svg)
        # <style>ブロックと class / inline style を除去（画像化時に塗りが効かない原因）
        svg = _re.sub(r"<style[^>]*>.*?</style>", "", svg, flags=_re.DOTALL)
        svg = _re.sub(r'\sclass="[^"]*"', "", svg)
        svg = _re.sub(r'\sstyle="[^"]*"', "", svg)
        # ルート<svg>に fill を一律指定（全図形が継承＝確実に単色で描画）
        svg = _re.sub(r"<svg\b", f'<svg fill="{color}"', svg, count=1)
        svg = svg.strip()
    except Exception:
        svg = ""
    _custom_cache[key] = svg
    return svg


def custom_data_uri(key):
    """CSS url() 用の data URI。PNGがあれば優先（確実）、無ければSVG。"""
    pf = CUSTOM_PNG.get(key)
    if pf:
        uri = _png_data_uri(pf)
        if uri:
            return f'url("{uri}")'
    fn = CUSTOM_ICONS.get(key)
    svg = _read_custom_svg(fn) if fn else ""
    if not svg:
        return ""
    b64 = _b64.b64encode(svg.encode("utf-8")).decode()
    return f'url("data:image/svg+xml;base64,{b64}")'


def custom_src(key):
    """<img src=...> 用の data URI（url()無し）。PNGがあれば優先、無ければSVG。"""
    pf = CUSTOM_PNG.get(key)
    if pf:
        uri = _png_data_uri(pf)
        if uri:
            return uri
    uri = custom_data_uri(key)
    return uri[5:-2] if uri else ""


def has_custom(key):
    return bool(custom_src(key))
