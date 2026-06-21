"""Ike App — データエクスポート（ローカルML学習用）
プロジェクト・ToDo・カレンダー・メール・行動ログを JSON / CSV で出力する。
定期実行して、出力結果を自前のPython学習スクリプト（train_local.py 等）に渡す。

使い方:
    python export_data.py            # data_exports/ に出力
"""
import os
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path

import database as db

EXPORT_DIR = Path(__file__).parent / "data_exports"


def _flatten_completion_log():
    """activity_log の完了記録を学習向けの行に展開"""
    rows = []
    todos = {t["id"]: t for t in db.get_todos(include_completed=True)}
    with db.get_conn() as conn:
        logs = conn.execute(
            "SELECT * FROM activity_log WHERE kind='todo_completed' ORDER BY ts").fetchall()
    for lg in logs:
        try:
            payload = json.loads(lg["payload"])
        except Exception:
            payload = {}
        t = todos.get(lg["ref_id"], {})
        rows.append({
            "todo_id": lg["ref_id"],
            "title": t.get("title", ""),
            "kind": t.get("kind", ""),
            "priority": t.get("priority", 2),
            "project_id": t.get("project_id"),
            "has_due": 1 if t.get("due_date") else 0,
            "hours_to_complete": payload.get("hours_to_complete"),
            "completed_at": t.get("completed_at", ""),
        })
    return rows


def export_all(out_dir: Path = EXPORT_DIR, include_calendar: bool = True) -> Path:
    db.init_db()
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    projects = db.get_projects()
    todos = db.get_todos(include_completed=True)
    emails = db.get_emails()
    completions = _flatten_completion_log()

    # カレンダー（認証済みなら取得）
    calendar_events = []
    if include_calendar:
        try:
            from calendar_loader import load_events, is_authenticated
            if is_authenticated():
                evs, err = load_events(["primary"], days_past=180, days_future=180)
                calendar_events = evs or []
        except Exception:
            pass

    snapshot = {
        "exported_at": datetime.now().isoformat(),
        "counts": {
            "projects": len(projects), "todos": len(todos),
            "emails": len(emails), "completions": len(completions),
            "calendar_events": len(calendar_events),
        },
        "projects": projects,
        "todos": todos,
        "emails": emails,
        "completions": completions,
        "calendar_events": calendar_events,
    }

    # 1) スナップショットJSON
    snap_path = out_dir / f"ike_export_{ts}.json"
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # 2) 学習に使いやすい「最新版」固定名（上書き）
    with open(out_dir / "latest.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # 3) 完了ログCSV（回帰学習向け）
    if completions:
        with open(out_dir / "completions.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(completions[0].keys()))
            w.writeheader()
            w.writerows(completions)

    # 4) ToDo CSV
    if todos:
        keys = ["id", "title", "kind", "priority", "project_id", "completed",
                "due_date", "created_at", "completed_at"]
        with open(out_dir / "todos.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(todos)

    db.log_activity("data_exported", payload={"file": snap_path.name, **snapshot["counts"]})
    return snap_path


if __name__ == "__main__":
    path = export_all()
    print(f"✅ エクスポート完了: {path}")
    print(f"   最新版（学習用固定名）: {EXPORT_DIR / 'latest.json'}")
    print(f"   CSV: completions.csv / todos.csv")
