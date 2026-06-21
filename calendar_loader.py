"""カレンダー読み込みのラッパー（認証未完了・オフラインでも安全に動く）"""
import os
import json
from datetime import datetime, timedelta

import pytz

JST = pytz.timezone("Asia/Tokyo")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "events_cache.json")

# ネットワーク/DNS系のエラーを表す文字列
_NET_HINTS = ("NameResolution", "Failed to resolve", "Max retries", "Connection",
              "Temporary failure", "getaddrinfo", "timed out", "Errno 8", "Errno -")


def is_authenticated() -> bool:
    return os.path.exists(TOKEN_PATH)


def _save_cache(events):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"saved_at": datetime.now(JST).isoformat(), "events": events},
                      f, ensure_ascii=False)
    except Exception:
        pass


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("events", []), d.get("saved_at", "")
    except Exception:
        return [], ""


def load_events(calendar_ids, days_past=7, days_future=90):
    """認証済みならイベントを取得。失敗時は前回キャッシュにフォールバック。

    戻り値: (events, error_message)
    """
    if not is_authenticated():
        return [], "Google Calendar 未認証です。setup_google_auth.py を実行してください。"

    try:
        from google_calendar_client import GoogleCalendarClient
        gc = GoogleCalendarClient()

        now = datetime.now(JST)
        time_min = (now - timedelta(days=days_past)).astimezone(pytz.UTC)
        time_max = (now + timedelta(days=days_future)).astimezone(pytz.UTC)

        all_events = []
        for cal_id in calendar_ids:
            all_events.extend(gc.get_events(cal_id, time_min, time_max))
        _save_cache(all_events)  # 成功したらキャッシュ更新
        return all_events, None
    except Exception as e:
        msg = str(e)
        is_net = any(h in msg for h in _NET_HINTS)
        cached, saved_at = _load_cache()
        if cached:
            when = saved_at[5:16].replace("T", " ") if saved_at else "前回"
            note = ("📡 ネットワークに接続できません。" if is_net else "取得に失敗しました。")
            return cached, f"{note} {when} 時点のデータを表示中（接続が戻ると自動更新されます）"
        if is_net:
            return [], "📡 ネットワーク（DNS）に接続できません。Wi-Fiや接続を確認してください。接続後に再読み込みされます。"
        return [], f"カレンダー取得エラー: {e}"


def list_calendars():
    """利用可能なカレンダー一覧を返す"""
    if not is_authenticated():
        return []
    try:
        from google_calendar_client import GoogleCalendarClient
        gc = GoogleCalendarClient()
        return [
            {"id": c["id"], "name": c.get("summary", c["id"]),
             "primary": c.get("primary", False)}
            for c in gc.get_calendars()
        ]
    except Exception:
        return []
