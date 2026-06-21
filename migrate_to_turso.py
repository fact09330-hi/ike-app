"""ローカル ike_app.db のデータを Turso(クラウド) に丸ごとコピーする一度きりの移行スクリプト。

使い方:
  1) .streamlit/secrets.toml に TURSO_DATABASE_URL と TURSO_AUTH_TOKEN を設定
     （または環境変数で渡す）
  2) ターミナルで:  python migrate_to_turso.py

何度実行しても OK（INSERT OR REPLACE で同じidは上書き）。
"""
import os
import re
import sqlite3
from pathlib import Path

_DIR = Path(__file__).parent


def _load_turso_env():
    """secrets.toml から TURSO_* を拾う（依存無しの簡易パース）。"""
    if os.getenv("TURSO_DATABASE_URL"):
        return
    p = _DIR / ".streamlit" / "secrets.toml"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    for k in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
        m = re.search(rf'^{k}\s*=\s*"([^"]*)"', text, re.M)
        if m and not os.getenv(k):
            os.environ[k] = m.group(1)


def main():
    _load_turso_env()
    if not os.getenv("TURSO_DATABASE_URL", "").strip():
        raise SystemExit("TURSO_DATABASE_URL が未設定です。"
                         ".streamlit/secrets.toml か環境変数で設定してください。")

    import database as db  # TURSO env が立っているので get_conn は Turso を使う
    print("→ Turso にスキーマを作成中…")
    db.init_db()

    local_path = _DIR / "ike_app.db"
    if not local_path.exists():
        raise SystemExit(f"ローカルDBが見つかりません: {local_path}")
    src = sqlite3.connect(local_path)
    src.row_factory = sqlite3.Row

    tables = [r["name"] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    print("対象テーブル:", ", ".join(tables))

    total = 0
    with db.get_conn() as dst:
        for t in tables:
            rows = src.execute(f"SELECT * FROM {t}").fetchall()
            if not rows:
                print(f"  {t}: 0 行")
                continue
            cols = list(rows[0].keys())
            sql = (f"INSERT OR REPLACE INTO {t} ({','.join(cols)}) "
                   f"VALUES ({','.join(['?'] * len(cols))})")
            for r in rows:
                dst.execute(sql, tuple(r[c] for c in cols))
            print(f"  {t}: {len(rows)} 行 → コピー")
            total += len(rows)
    print(f"✅ 完了: 合計 {total} 行を Turso にコピーしました。")


if __name__ == "__main__":
    main()
