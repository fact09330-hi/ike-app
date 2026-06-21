"""カレンダーのカテゴリ別タイル配色＋モノクロのミニアイコン。
ユーザー指定の配色ルールに従う。
"""

# 小さなモノクロSVGアイコン（fill=currentColorでタイル文字色に追従）
_ICONS = {
    "work": "<path d='M3 4h6v1h3v7H0V5h3V4zm1 0h4v1H4V4z'/>",            # 鞄
    "moon": "<path d='M8 1a5 5 0 100 10A6 6 0 018 1z'/>",                  # 月（当直）
    "cross": "<path d='M5 1h2v4h4v2H7v4H5V7H1V5h4V1z'/>",                  # 十字（日直/病院）
    "glass": "<path d='M2 1h8L7 6v4h2v1H3v-1h2V6L2 1z'/>",                # グラス（飲み会）
    "music": "<path d='M10 1v7a2 2 0 11-1-1.7V3L5 4v5a2 2 0 11-1-1.7V2l6-1z'/>",  # 音符（バンド）
    "plane": "<path d='M1 7l10-4-3 9-2-3-3 1 1-2-3-1z'/>",                # 飛行機（旅行）
    "scissors": "<path d='M2 2l5 5 5-5-4 5 4 5-5-5-5 5 4-5z'/>",          # ハサミ（美容室）
    "heart": "<path d='M6 11S1 8 1 4a2.5 2.5 0 015-1 2.5 2.5 0 015 1c0 4-5 7-5 7z'/>",  # ハート（結婚式/誕生日）
    "book": "<path d='M1 2h4a2 2 0 012 1 2 2 0 012-1h2v8H8a2 2 0 00-2 1 2 2 0 00-2-1H1V2z'/>",  # 本（勉強会/学会）
    "bed": "<path d='M0 4h7a3 3 0 013 3v1H0V4zm0 5h12v3h-1v-1H1v1H0V9z'/>",  # ベッド（休み）
}


# (keywords, 背景色, 文字色, アイコンキー)　上から優先的に判定
_RULES = [
    (["当直"], "#7C3AED", "#FFFFFF", "moon"),
    (["日直"], "#15803D", "#FFFFFF", "cross"),
    (["外勤"], "#7DD3FC", "#141414", "work"),
    (["飲み会", "歓迎会", "送別会", "懇親会", "会食"], "#FACC15", "#141414", "glass"),
    (["勉強会", "学会", "講演", "発表", "セミナー", "ワークショップ"], "#22C55E", "#FFFFFF", "book"),
    (["美容室", "美容院", "ネイル", "理髪"], "#A3E635", "#141414", "scissors"),
    (["結婚式", "誕生日", "記念日", "打ち合わせ", "打合せ"], "#A3E635", "#141414", "heart"),
    (["旅行", "出張"], "#A3E635", "#141414", "plane"),
    (["バンド", "ライブ", "練習", "リハ"], "#9CA3AF", "#141414", "music"),
    (["有給", "有休", "振休", "休み", "やすみ", "休暇", "代休"], "#DB2777", "#FFFFFF", "bed"),
    (["仕事", "勤務", "外来", "病院", "手術"], "#2563EB", "#FFFFFF", "work"),
]

_DEFAULT = ("#141414", "#FCFBF9", None)


def category_style(title: str):
    """(背景色, 文字色, アイコンキー) を返す"""
    low = (title or "").lower()
    for keywords, bg, fg, icon in _RULES:
        for kw in keywords:
            if kw.lower() in low:
                return bg, fg, icon
    return _DEFAULT


def icon_svg(icon_key, color="currentColor"):
    if not icon_key or icon_key not in _ICONS:
        return ""
    return (f"<svg viewBox='0 0 12 12' fill='{color}' "
            f"xmlns='http://www.w3.org/2000/svg'>{_ICONS[icon_key]}</svg>")


def is_overnight(title: str) -> bool:
    """当直など、入り＆明けで翌日にもまたがる予定か"""
    low = (title or "").lower()
    return any(k in low for k in ["当直", "夜勤", "宿直"])
