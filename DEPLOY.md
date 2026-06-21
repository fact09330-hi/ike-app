# Ike App クラウド常時公開ガイド（Streamlit Cloud ＋ Turso）

Macを起動していなくても、外出先でもiPhoneから使えるようにする手順です。
**すべて無料**でできます。コード側の対応（DB差し替え・パスワード保護・secrets読み込み）は実装済みなので、
以下は主に「アカウント作成」と「設定の貼り付け」です。

---

## 全体像（3つの無料サービス）

| 役割 | サービス | 何をする |
|---|---|---|
| アプリ置き場 | **Streamlit Community Cloud** | GitHubのコードを常時公開で動かす |
| データ置き場 | **Turso (libSQL)** | クラウド版SQLite。Mac/iPhoneでデータ共有 |
| コード置き場 | **GitHub** | コードを保管（Streamlitが読みに行く） |

> 仕組み: GitHubにコードを置く → Streamlit Cloudがそれを動かす → データはTursoに保存。
> パスワードを知っている人だけがログインできる（個人情報を守る）。

---

## ステップ0：アカウントを3つ作る

1. **GitHub** … https://github.com/signup
2. **Streamlit Community Cloud** … https://share.streamlit.io （上のGitHubアカウントで「Continue with GitHub」）
3. **Turso** … https://turso.tech （GitHubアカウントでサインイン可）

---

## ステップ1：Turso でクラウドDBを作る

### 1-1. Turso CLI を入れる（Macのターミナル）
```bash
curl -sSfL https://get.tur.so/install.sh | bash
```
入ったら、ターミナルを開き直して、GitHubでログイン→DB作成:
```bash
turso auth login
```
```bash
turso db create ike-app
```
（`turso auth login` でbrowserが開きます。`ike-app` が作成するDB名です）

> 💡 コマンドは `#` から後ろの注釈ごとコピーしないでください。zshでは `#` がコメント扱いされず、エラーになります。

### 1-2. 接続情報を2つ控える
**①URL** を取得（`libsql://ike-app-xxxx.turso.io` のような行が出ます）:
```bash
turso db show --url ike-app
```
**②トークン** を取得（長い文字列が出ます）:
```bash
turso db tokens create ike-app
```
この **①URL** と **②トークン** を後で使います（メモ帳に貼っておく）。

---

## ステップ2：今あるデータをTursoへ移す

Macのターミナルで、このフォルダ（`ike_app`）に移動してから:

Turso接続ライブラリを入れます:
```bash
pip install libsql-experimental
```

`ike_app/.streamlit/secrets.toml` を新規作成し、最低限これだけ書きます（①②を貼る）:
```toml
TURSO_DATABASE_URL = "libsql://ike-app-xxxx.turso.io"
TURSO_AUTH_TOKEN = "（②の長いトークン）"
```

そして移行スクリプトを実行:
```bash
python migrate_to_turso.py
```
`✅ 完了: 合計 N 行を Turso にコピーしました。` と出れば成功です。
（※ ここで接続が確認できます。エラーが出たら、その文面を私に貼ってください。）

> `secrets.toml` は `.gitignore` 済みなのでGitHubには上がりません（安全）。

---

## ステップ3：コードをGitHubに上げる

> ⚠️ 機密ファイル（`.env` `credentials.json` `token.json` `ike_app.db` `secrets.toml`）は
> `.gitignore` 済みでアップロードされません。**そのままで安全**です。

`ike_app` フォルダの中で:
```bash
git init
git add .
git commit -m "Ike App initial commit"
```
GitHubで **空のプライベートリポジトリ**（例: `ike-app`）を作り、表示された手順に従って:
```bash
git remote add origin https://github.com/＜あなたのID＞/ike-app.git
git branch -M main
git push -u origin main
```

> 公開/非公開は **必ず Private（非公開）** にしてください。

---

## ステップ4：Streamlit Cloud にデプロイ

1. https://share.streamlit.io → **「Create app」/「New app」**
2. 設定:
   - **Repository**: 先ほどの `＜ID＞/ike-app`
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. **「Advanced settings」→「Secrets」** を開き、次の章の内容を貼り付け
4. **Deploy** を押す（数分でビルド）

---

## ステップ5：Secrets（秘密情報）を貼り付ける

Streamlit Cloud の **Secrets** 欄に、以下を**値を埋めて**貼ります。
（`ike_app/.streamlit/secrets.toml.example` が雛形です）

```toml
# ログインパスワード（公開URLを守る・必須）
app_password = "好きなパスワード"

# クラウドDB（ステップ1の①②）
TURSO_DATABASE_URL = "libsql://ike-app-xxxx.turso.io"
TURSO_AUTH_TOKEN = "（②トークン）"

# カレンダー/メール設定（ローカルの .env と同じ値）
GOOGLE_CALENDAR_IDS = "primary"
UNIVERSITY_EMAIL_DOMAINS = "example-univ1.ac.jp,example-univ2.ac.jp"
# 病院🏥/大学院🎓バッジを出す場合のみ（任意・自分のドメインに置換）
HOSPITAL_EMAIL_DOMAIN = "example-hospital.ac.jp"
GRAD_EMAIL_DOMAIN = "example-grad.ac.jp"

# Google認証（ローカルの2ファイルの中身を丸ごと貼る）
google_credentials_json = """
（credentials.json の中身をそのまま貼り付け）
"""
google_token_json = """
（token.json の中身をそのまま貼り付け）
"""
```

> `credentials.json` / `token.json` の中身は、Macの `ike_app` フォルダにあるファイルを
> テキストエディタで開いてコピーします。アプリは起動時にこの値からファイルを復元します。

---

## ステップ6：完成・確認

- 数分後、`https://＜アプリ名＞.streamlit.app` が発行されます。
- 開くと **パスワード画面** → さきほどの `app_password` を入力 → アプリが表示。
- iPhoneのSafariでも同じURLを開き、**「ホーム画面に追加」**でアプリのように使えます。
- Mac/iPhone/どの端末からでも**同じデータ（Turso）**を見ます。

---

## 日々の更新の仕方

コードを直したら、`ike_app` フォルダで:
```bash
git add . && git commit -m "更新内容" && git push
```
→ Streamlit Cloud が**自動で再ビルド**して反映されます。

---

## メールについての注意

- Gmail連携は `token.json` の refresh_token で自動更新されます（基本は再認証不要）。
- もし「権限が切れた」等で動かなくなったら、**ローカルで** `python setup_google_auth.py` を実行して
  `token.json` を作り直し、その中身を Streamlit Secrets の `google_token_json` に貼り直します。

---

## うまくいかない時

| 症状 | 対処 |
|---|---|
| `migrate_to_turso.py` でエラー | エラー全文を私に共有（libSQLの接続/APIの微調整が要ることがあります） |
| デプロイが赤くなる | Streamlit Cloud の「Manage app」→ ログを確認。requirements不足が多い |
| ログインできない | Secrets の `app_password` と入力値が一致しているか |
| カレンダー/メールが空 | Secrets の `google_token_json` が正しく貼れているか |
| データが古い | ローカル版とクラウド版はDBが別。**クラウド(Turso)を正本**にして、ローカルもTursoに向ける（`.env`にTURSO_*を書く）と統一できます |

---

## 補足：技術メモ（実装済みの対応）

- `database.py`：`TURSO_DATABASE_URL` があればTurso、無ければローカルSQLite（**ローカル動作は不変**）。
- `auth.py`：`app_password` 設定時のみログインゲート（ローカルは素通り）。
- `cloud_bootstrap.py`：secrets→環境変数・認証ファイルを起動時に展開（secrets無しのローカルは無処理）。
- 関連: Obsidian `Decisions/2026-06-18-ike-app-cloud-deployment.md` / `Knowledge/ike-app-multi-device.md`
