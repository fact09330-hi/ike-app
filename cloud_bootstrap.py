"""クラウド(Streamlit Cloud)起動時に st.secrets から
   環境変数・Google認証ファイル(credentials.json/token.json)を用意する。

ローカルで secrets.toml が無い場合は st.secrets に一切触れない
（触れると「No secrets files found」の赤いエラーが出るため）。
これにより、既存のファイル読み込みコードを一切変えずにクラウドでも動く。
"""
import os
import json
from pathlib import Path

import streamlit as st

_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# secrets → 環境変数 に流し込むキー（同名コピー）
_ENV_KEYS = (
    "TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN",
    "GOOGLE_CALENDAR_IDS", "UNIVERSITY_EMAIL_DOMAINS", "ANTHROPIC_API_KEY",
)


def _secrets_available():
    """Streamlit が実際に探すパスに secrets.toml がある時だけ True。
    （_DIR を含めると、実行ディレクトリ(CWD)と一致しない時に st.secrets が
      読めず「No secrets files found」の赤エラーになるため、CWDとhomeのみ確認）"""
    for p in (Path.cwd() / ".streamlit" / "secrets.toml",
              Path.home() / ".streamlit" / "secrets.toml"):
        try:
            if p.exists():
                return True
        except Exception:
            pass
    return False


def _secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default


def bootstrap():
    if not _secrets_available():
        return  # ローカル（secrets無し）＝何もしない

    # 1) 環境変数へ（DB接続・カレンダーID 等）
    for k in _ENV_KEYS:
        v = _secret(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)

    # パスワードは app_password → IKE_APP_PASSWORD に揃える
    pw = _secret("app_password")
    if pw and not os.getenv("IKE_APP_PASSWORD"):
        os.environ["IKE_APP_PASSWORD"] = str(pw)

    # 2) Google認証ファイルを secrets から書き出す（無ければ何もしない）
    cred = _secret("google_credentials_json")
    if cred:
        _write_json(_DIR / "credentials.json", cred)
    token = _secret("google_token_json")
    if token:
        _write_json(_DIR / "token.json", token)


def _write_json(path, value):
    """value は dict でも JSON文字列でも受ける。既存と同じなら書かない。"""
    try:
        text = value if isinstance(value, str) else json.dumps(dict(value))
        path = Path(path)
        if path.exists() and path.read_text(encoding="utf-8").strip() == text.strip():
            return
        path.write_text(text, encoding="utf-8")
    except Exception:
        pass
