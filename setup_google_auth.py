"""Google OAuth 認証セットアップ（カレンダー＋Gmail）
使い方: python setup_google_auth.py
※ スコープ追加時はこれを再実行して token.json を再生成する
"""
import os
import sys

from auth_config import SCOPES
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")


def main():
    print("=" * 50)
    print("  Google 認証セットアップ（カレンダー＋Gmail）")
    print("=" * 50)
    print("  ※ Gmail権限を追加するため、既存ユーザーも再認証が必要です")

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"""
❌ credentials.json が見つかりません。

【手順】

1. https://console.cloud.google.com/ を開く

2. 「プロジェクトを作成」→ 名前: IkeApp

3. 「APIとサービス」→「ライブラリ」
   "Google Calendar API" を検索 →「有効にする」

4. 「APIとサービス」→「OAuth同意画面」
   ユーザーの種類: 外部 → 作成
   アプリ名: IkeApp、メールアドレス入力 → 保存して次へ（スコープは追加不要）
   テストユーザーに自分のGmailを追加

5. 「APIとサービス」→「認証情報」
   「認証情報を作成」→「OAuthクライアントID」
   種類: デスクトップアプリ、名前: IkeApp → 作成

6. ダウンロードした JSON を:
   {CREDENTIALS_PATH}
   として保存

7. このスクリプトを再実行
""")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ ライブラリ不足。次を実行してください: pip install -r requirements.txt")
        sys.exit(1)

    print("\nブラウザが開きます。Google アカウントでログインしてください。")
    print("「このアプリは確認されていません」→「詳細設定」→「移動」で続行")
    print("権限画面では カレンダー＋Gmail の閲覧/下書き作成 にチェックして続行\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"✅ 認証完了！ {TOKEN_PATH} を保存しました（カレンダー＋Gmail）。")
    print("次のステップ: アプリのメール画面で「同期」を押してください。")


if __name__ == "__main__":
    main()
