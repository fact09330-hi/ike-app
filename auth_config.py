"""Google OAuth で要求するスコープを一元管理"""

# カレンダー（読み取り）＋ Gmail（読み取り＋下書き作成）
# gmail.compose は下書き作成に必要。自動送信はコード側で行わない方針。
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
