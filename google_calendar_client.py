"""Google Calendar API クライアント（読み取り専用）"""
import os
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 全スコープで読み込む（カレンダー側のtoken更新でGmail権限が消えないように）
from auth_config import SCOPES
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")


class GoogleCalendarClient:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        if not os.path.exists(TOKEN_PATH):
            raise RuntimeError(
                "Google認証トークンがありません。\n"
                "先に次を実行してください: python setup_google_auth.py"
            )
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, "w") as f:
                    f.write(creds.to_json())
            else:
                raise RuntimeError(
                    "トークンが期限切れです。python setup_google_auth.py を再実行してください。"
                )
        return build("calendar", "v3", credentials=creds)

    def get_calendars(self) -> list[dict]:
        """アクセス可能なカレンダー一覧を返す"""
        result = self.service.calendarList().list().execute()
        return result.get("items", [])

    def get_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict]:
        """指定カレンダーのイベントを取得して標準形式で返す"""
        raw_events: list[dict] = []
        page_token = None

        while True:
            resp = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
                maxResults=250,
            ).execute()

            for item in resp.get("items", []):
                raw_events.append(self._parse_event(item, calendar_id))

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return raw_events

    def _parse_event(self, item: dict, calendar_id: str) -> dict:
        start = item.get("start", {})
        end = item.get("end", {})
        return {
            "id": item.get("id", ""),
            "calendar_id": calendar_id,
            "title": item.get("summary", "無題"),
            "description": item.get("description") or "",
            "location": item.get("location") or "",
            "all_day": "date" in start,
            "start": start.get("dateTime") or start.get("date", ""),
            "end": end.get("dateTime") or end.get("date", ""),
            "updated": item.get("updated", ""),
        }
