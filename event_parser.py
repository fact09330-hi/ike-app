"""予定名・メモから時刻・場所を抽出するパーサ
Google Calendar を終日予定中心で運用しているため、
「飲み会 19:00」「美容室 14時 @表参道」のような書式から情報を整理する。
"""
import re

# 時刻パターン: 19:00 / 19時 / 19時30分 / 14:30〜16:00 / PM7
TIME_PATTERNS = [
    r'(\d{1,2})[:：](\d{2})\s*[〜~\-－]\s*(\d{1,2})[:：](\d{2})',  # 範囲 19:00-21:00
    r'(\d{1,2})時(\d{1,2})分',                                      # 19時30分
    r'(\d{1,2})[:：](\d{2})',                                       # 19:00
    r'(\d{1,2})時',                                                 # 19時
]

# 場所パターン: @表参道 / ＠○○ / 場所:○○ / （○○にて）
LOCATION_PATTERNS = [
    r'[@＠]\s*([^\s,，、)）]+)',
    r'場所[:：]\s*([^\s,，、]+)',
    r'[(（]([^)）]*(?:にて|店|クリニック|病院|ホール|会議室)[^)）]*)[)）]',
]

# カテゴリ推定キーワード（負荷とは別の、生活シーン分類）
SCENE_KEYWORDS = {
    "飲み会": "🍻 会食", "歓迎会": "🍻 会食", "送別会": "🍻 会食", "懇親会": "🍻 会食",
    "食事": "🍽 食事", "ランチ": "🍽 食事", "ディナー": "🍽 食事",
    "美容室": "💇 美容", "美容院": "💇 美容", "理髪": "💇 美容", "ネイル": "💇 美容",
    "病院": "🏥 通院", "受診": "🏥 通院", "歯医者": "🏥 通院", "歯科": "🏥 通院",
    "当直": "🌙 当直", "外勤": "🚑 外勤", "外来": "🩺 外来", "手術": "🔪 手術",
    "会議": "💼 会議", "meeting": "💼 会議", "打ち合わせ": "💼 会議", "面談": "💼 会議",
    "学会": "🎓 学会", "発表": "🎓 学会", "講演": "🎤 講演", "勉強会": "📚 勉強会",
    "出張": "✈️ 出張", "旅行": "✈️ 旅行",
}


def extract_time(text: str):
    """テキストから時刻情報を抽出。(開始, 終了, 表示文字列) を返す。無ければ None"""
    if not text:
        return None
    # 範囲（19:00-21:00）
    m = re.search(TIME_PATTERNS[0], text)
    if m:
        s = f"{int(m.group(1)):02d}:{m.group(2)}"
        e = f"{int(m.group(3)):02d}:{m.group(4)}"
        return (s, e, f"{s}〜{e}")
    # 19時30分
    m = re.search(TIME_PATTERNS[1], text)
    if m:
        s = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        return (s, None, s)
    # 19:00
    m = re.search(TIME_PATTERNS[2], text)
    if m:
        s = f"{int(m.group(1)):02d}:{m.group(2)}"
        return (s, None, s)
    # 19時
    m = re.search(TIME_PATTERNS[3], text)
    if m:
        s = f"{int(m.group(1)):02d}:00"
        return (s, None, s)
    return None


def extract_location(text: str, memo: str = ""):
    """テキスト/メモから場所を抽出。無ければ None"""
    for src in (text, memo):
        if not src:
            continue
        for pat in LOCATION_PATTERNS:
            m = re.search(pat, src)
            if m:
                return m.group(1).strip()
    return None


def detect_scene(text: str):
    """生活シーンのカテゴリ（絵文字付き）を推定"""
    low = text.lower()
    for kw, scene in SCENE_KEYWORDS.items():
        if kw.lower() in low:
            return scene
    return None


def clean_title(text: str):
    """時刻・場所表記を取り除いたきれいなタイトルを返す"""
    if not text:
        return ""
    t = text
    for pat in TIME_PATTERNS + LOCATION_PATTERNS:
        t = re.sub(pat, '', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' 　-－〜~')
    return t or text


def parse_event(event: dict) -> dict:
    """イベントを解析して整理済み情報を付与した辞書を返す"""
    title = event.get("title", "")
    desc = event.get("description", "")
    location_field = event.get("location", "")

    time_info = extract_time(title) or extract_time(desc)
    location = location_field or extract_location(title, desc)
    scene = detect_scene(title) or detect_scene(desc)  # タイトル優先

    return {
        **event,
        "clean_title": clean_title(title),
        "parsed_time": time_info[2] if time_info else None,
        "parsed_start": time_info[0] if time_info else None,
        "parsed_end": time_info[1] if time_info else None,
        "parsed_location": location,
        "scene": scene,
    }


if __name__ == "__main__":
    tests = [
        {"title": "飲み会 19:00", "description": "", "location": ""},
        {"title": "美容室 14時 @表参道", "description": "", "location": ""},
        {"title": "病院", "description": "10:30 @○○クリニック", "location": ""},
        {"title": "歓迎会 18:30〜21:00", "description": "場所:銀座", "location": ""},
        {"title": "当直", "description": "", "location": ""},
        {"title": "学会発表 13:00", "description": "国際会議場", "location": "パシフィコ横浜"},
    ]
    for t in tests:
        p = parse_event(t)
        print(f"  {t['title']:20s} → 時刻={p['parsed_time']} 場所={p['parsed_location']} "
              f"シーン={p['scene']} clean={p['clean_title']}")
