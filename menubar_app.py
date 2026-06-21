"""Ike App — メニューバー常駐アプリ（画面上のバーに常時表示）
未完了ToDo数・今日のタスクをメニューバーに出し、クリックでウィジェット/本体を開く。

起動: python menubar_app.py
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
os.environ.setdefault("IKE_LOCAL", "1")

# 本体・ウィジェットと同じクラウドDB(Turso)を読む（メニューバーの件数を一致させる）。
# streamlitに依存せず secrets.toml から接続情報だけ環境変数へ（rumpsプロセスを固めない）。
# 失敗・未設定ならローカルSQLiteのまま。
try:
    import tomllib
    _sec_path = os.path.join(DIR, ".streamlit", "secrets.toml")
    if os.path.exists(_sec_path):
        with open(_sec_path, "rb") as _f:
            _sec = tomllib.load(_f)
        for _k in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
            if _sec.get(_k):
                os.environ.setdefault(_k, str(_sec[_k]))
except Exception:
    pass

try:
    import rumps
except ImportError:
    print("rumps が必要です: pip install rumps")
    sys.exit(1)

import database as db
from ui_helpers import parse_dt, JST


def _counts():
    db.init_db()
    todos = db.get_todos(include_completed=False)
    today = datetime.now(JST).date()
    today_n = sum(1 for t in todos if t.get("due_date") and parse_dt(t["due_date"])
                  and parse_dt(t["due_date"]).date() <= today)
    return len(todos), today_n


class IkeBar(rumps.App):
    def __init__(self):
        super().__init__("Ike", quit_button=None)
        self.item_today = rumps.MenuItem("今日のタスク: …")
        self.item_total = rumps.MenuItem("未完了 合計: …")
        self.item_focus = rumps.MenuItem("今日の集中: …")
        self.menu = [
            self.item_today,
            self.item_total,
            self.item_focus,
            None,
            rumps.MenuItem("🍅 ポモドーロ/アプリを開く", callback=self.open_app),
            rumps.MenuItem("🪟 ウィジェットを開く", callback=self.open_widget),
            rumps.MenuItem("🔄 更新", callback=self.refresh),
            None,
            rumps.MenuItem("終了", callback=rumps.quit_application),
        ]
        self.refresh(None)

    @rumps.timer(300)
    def _tick(self, _):
        self.refresh(None)

    def refresh(self, _):
        try:
            total, today_n = _counts()
            focus = db.pomodoro_stats()["today_min"]
            self.title = f"Ike ⚡{today_n}"
            self.item_today.title = f"今日のタスク: {today_n}件"
            self.item_total.title = f"未完了 合計: {total}件"
            self.item_focus.title = f"今日の集中: {focus:.0f}分"
        except Exception:
            self.title = "Ike"

    def open_widget(self, _):
        subprocess.Popen([sys.executable, os.path.join(DIR, "widget_app.py")], cwd=DIR)

    def open_app(self, _):
        subprocess.Popen([sys.executable, os.path.join(DIR, "native_app.py")], cwd=DIR)


if __name__ == "__main__":
    IkeBar().run()
