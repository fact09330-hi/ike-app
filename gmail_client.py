"""Gmail API クライアント — 受信取得・要返信抽出・下書き作成。
※ 送信は行わない（下書き作成まで）。token.json はカレンダーと共用。
"""
import os
import base64
import re
from email.mime.text import MIMEText
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from auth_config import SCOPES

TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")

# 自動配信・宣伝・SNSを除外する共通フィルタ
# 件名キーワードは個人/業務メールにはまず現れない宣伝語のみ（誤除外を避ける）
_EXCLUDE = (
    "-category:promotions -category:social -category:updates -category:forums "
    "-from:noreply -from:no-reply -from:notifications -from:donotreply "
    "-from:newsletter -from:mailmag -from:mailer -from:marketing "
    "-subject:newsletter -label:newsletter "
    "-subject:OFF -subject:セール -subject:キャンペーン -subject:ポイント "
    "-subject:プレゼント -subject:クーポン -subject:お得 -subject:【PR】 "
    "-subject:自動応答 -subject:入荷 -subject:特集 -subject:新作 -subject:配信"
)
# モード別クエリ
QUERY_MODES = {
    # 未読のみ（厳しめ）
    "unread": f"is:unread in:inbox {_EXCLUDE}",
    # 最近30日に直接届いた人からのメール（既読含む・あぶり出し向き）
    "recent": f"in:inbox newer_than:30d to:me {_EXCLUDE}",
    # 重要マーク付き
    "important": f"in:inbox is:important newer_than:60d {_EXCLUDE}",
}
NEEDS_REPLY_QUERY = QUERY_MODES["unread"]  # 後方互換


# 大学ドメイン（.env の UNIVERSITY_EMAIL_DOMAINS で設定、カンマ区切り）
UNIVERSITY_DOMAINS = [
    d.strip().lower()
    for d in os.getenv("UNIVERSITY_EMAIL_DOMAINS", "").split(",") if d.strip()
]

# ドメイン → 表示ラベル（バッジ）。所属を公開コードに残さないため設定値で与える。
#   .env / secrets:  HOSPITAL_EMAIL_DOMAIN, GRAD_EMAIL_DOMAIN
# 未設定なら下の UNIVERSITY_DOMAINS で「🏫 大学」、それも無ければ「📨 個人」になる。
DOMAIN_LABELS = {}
_hosp_dom = os.getenv("HOSPITAL_EMAIL_DOMAIN", "").strip().lower()
_grad_dom = os.getenv("GRAD_EMAIL_DOMAIN", "").strip().lower()
if _hosp_dom:
    DOMAIN_LABELS[_hosp_dom] = ("hospital", "🏥 大学病院")
if _grad_dom:
    DOMAIN_LABELS[_grad_dom] = ("grad", "🎓 大学院")


def classify_source(route_text: str):
    """転送経路から発生元を判定。(source_key, ラベル) を返す。
    source_key: 'hospital' / 'grad' / 'univ' / 'personal'
    """
    low = route_text.lower()
    for dom, (key, label) in DOMAIN_LABELS.items():
        if dom in low:
            return key, label
    for dom in UNIVERSITY_DOMAINS:
        if dom in low:
            return "univ", "🏫 大学"
    return "personal", "📨 個人"


def has_gmail_scope() -> bool:
    """token.json が Gmail スコープを含むか"""
    if not os.path.exists(TOKEN_PATH):
        return False
    try:
        import json
        with open(TOKEN_PATH) as f:
            data = json.load(f)
        scopes = data.get("scopes", [])
        return any("gmail" in s for s in scopes)
    except Exception:
        return False


class GmailClient:
    def __init__(self):
        self.service = self._authenticate()
        self._email = None

    def _authenticate(self):
        if not os.path.exists(TOKEN_PATH):
            raise RuntimeError("認証トークンがありません。python setup_google_auth.py を実行してください。")
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, "w") as f:
                    f.write(creds.to_json())
            else:
                raise RuntimeError("トークンが無効です。再認証してください。")
        if not has_gmail_scope():
            raise RuntimeError(
                "token.json に Gmail 権限がありません。\n"
                "python setup_google_auth.py を再実行して Gmail を許可してください。")
        return build("gmail", "v1", credentials=creds)

    @property
    def email_address(self) -> str:
        if self._email is None:
            profile = self.service.users().getProfile(userId="me").execute()
            self._email = profile.get("emailAddress", "")
        return self._email

    # ── 受信取得 ──
    def list_needs_reply(self, max_results: int = 20, mode: str = "unread") -> list[dict]:
        """要返信候補メールを取得。mode: unread / recent / important"""
        query = QUERY_MODES.get(mode, NEEDS_REPLY_QUERY)
        resp = self.service.users().messages().list(
            userId="me", q=query, maxResults=max_results).execute()
        messages = resp.get("messages", [])
        result = []
        for m in messages:
            detail = self._get_message(m["id"])
            if detail:
                result.append(detail)
        return result

    def unread_count(self) -> int:
        """Gmailの「メイン」タブの未読件数を正確に数える。
        概算(resultSizeEstimate)や全カテゴリ合算ではなく、
        category:primary の未読メッセージIDを実際に数えるので表示と一致する。"""
        try:
            total = 0
            token = None
            for _ in range(20):  # 最大 ~10000件まで正確にカウント
                resp = self.service.users().messages().list(
                    userId="me", q="is:unread in:inbox category:primary",
                    maxResults=500, pageToken=token,
                    fields="messages/id,nextPageToken").execute()
                total += len(resp.get("messages", []))
                token = resp.get("nextPageToken")
                if not token:
                    break
            return total
        except Exception:
            return -1

    def list_spam(self, max_results: int = 25) -> list[dict]:
        """迷惑メール(SPAM)フォルダのメールを取得"""
        try:
            resp = self.service.users().messages().list(
                userId="me", labelIds=["SPAM"], maxResults=max_results).execute()
        except Exception:
            return []
        result = []
        for m in resp.get("messages", []):
            d = self._get_message(m["id"])
            if d:
                result.append(d)
        return result

    def _get_message(self, msg_id: str) -> dict | None:
        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full").execute()
        except Exception:
            return None
        headers = {h["name"].lower(): h["value"]
                   for h in msg.get("payload", {}).get("headers", [])}
        body = self._extract_body(msg.get("payload", {}))
        ts = int(msg.get("internalDate", "0")) / 1000
        # 転送経路の判定材料（大学院→Gmail転送の識別用）
        route = " ".join([headers.get("to", ""), headers.get("delivered-to", ""),
                          headers.get("x-forwarded-to", ""), headers.get("x-forwarded-for", "")])
        source_key, source_label = classify_source(route)
        return {
            "msg_id": msg_id,
            "thread_id": msg.get("threadId", ""),
            "subject": self._sanitize(headers.get("subject", "(件名なし)")),
            "sender": self._sanitize(headers.get("from", "")),
            "to": headers.get("to", ""),
            "route": route,
            "source": source_key,
            "source_label": source_label,
            "message_id_header": headers.get("message-id", ""),
            "references": headers.get("references", ""),
            "snippet": self._sanitize(msg.get("snippet", "")),
            "body": self._sanitize(body[:3000]),
            "received_at": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
        }

    def _extract_body(self, payload: dict) -> str:
        """本文（text/plain優先）を抽出"""
        if payload.get("body", {}).get("data"):
            return self._decode(payload["body"]["data"])
        for part in payload.get("parts", []):
            mime = part.get("mimeType", "")
            if mime == "text/plain" and part.get("body", {}).get("data"):
                return self._decode(part["body"]["data"])
        # plainが無ければ再帰
        for part in payload.get("parts", []):
            sub = self._extract_body(part)
            if sub:
                return sub
        return ""

    @staticmethod
    def _sanitize(text: str) -> str:
        """制御文字・サロゲートを除去（表示エラー防止）"""
        if not text:
            return ""
        return "".join(
            ch for ch in text
            if ch in "\n\t" or (ord(ch) >= 32 and not 0xD800 <= ord(ch) <= 0xDFFF))

    @staticmethod
    def _decode(data: str) -> str:
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    # ── 送信済み（文体学習用）──
    def get_sent_samples(self, n: int = 15) -> list[str]:
        """自分の送信済みメール本文を取得（文体学習用）"""
        try:
            resp = self.service.users().messages().list(
                userId="me", q="in:sent", maxResults=n).execute()
        except Exception:
            return []
        samples = []
        for m in resp.get("messages", []):
            d = self._get_message(m["id"])
            if d and d["body"].strip():
                samples.append(d["body"][:1500])
        return samples

    # ── 下書き作成 ──
    def create_reply_draft(self, original: dict, reply_body: str) -> str:
        """元メールへの返信下書きを Gmail に作成。draft_id を返す。送信はしない。"""
        to_addr = self._parse_addr(original.get("sender", ""))
        subject = original.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        mime = MIMEText(reply_body, "plain", "utf-8")
        mime["To"] = to_addr
        mime["From"] = self.email_address
        mime["Subject"] = subject
        if original.get("message_id_header"):
            mime["In-Reply-To"] = original["message_id_header"]
            refs = original.get("references", "") + " " + original["message_id_header"]
            mime["References"] = refs.strip()

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = self.service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": original.get("thread_id")}}).execute()
        return draft.get("id", "")

    @staticmethod
    def _parse_addr(from_header: str) -> str:
        m = re.search(r'<([^>]+)>', from_header)
        return m.group(1) if m else from_header.strip()
