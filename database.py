"""Ike App — ローカルデータベース (SQLite)
プロジェクト・ToDo・プリセット・メール・学習ログを保存する。
将来 iCloud / クラウド同期に差し替え可能な設計。
"""
import os
import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "ike_app.db"


# ────────────────────────────────────────────────────────────────
# Turso(libSQL) 対応 — クラウド版SQLite。
#   環境変数 TURSO_DATABASE_URL があればクラウドDB、無ければローカルSQLite。
#   libSQL は SQLite と同じSQL方言なので、全クエリをそのまま使える。
#   行アクセスを sqlite3.Row 互換（辞書）にするための薄いラッパ。
# ────────────────────────────────────────────────────────────────
def _split_sql(script):
    # このスキーマには文字列リテラル内に ';' が無いので単純分割で安全
    return [s for s in script.split(";") if s.strip()]


class _DictCursor:
    """libsql-client の ResultSet を sqlite3.Row 風（キー参照／dict化可）に見せる"""
    def __init__(self, rs):
        cols = list(getattr(rs, "columns", []) or [])
        self._rows = [{c: r[i] for i, c in enumerate(cols)}
                      for r in (getattr(rs, "rows", []) or [])]
        self._i = 0
        self.lastrowid = getattr(rs, "last_insert_rowid", None)

    def fetchone(self):
        if self._i < len(self._rows):
            r = self._rows[self._i]
            self._i += 1
            return r
        return None

    def fetchall(self):
        rest = self._rows[self._i:]
        self._i = len(self._rows)
        return rest

    def __iter__(self):
        return iter(self._rows)


class _TursoConn:
    """libsql-client 接続を sqlite3.Connection 風に見せる（execute/executescript/commit/close）。
    接続タイムアウト/切断時は接続を作り直して自動リトライする（本番のTurso一時不通対策）。"""
    def __init__(self, client, url="", token="", shared=False):
        self._c = client
        self._url = url
        self._token = token
        self._shared = shared  # 使い回しの接続は close で閉じない

    def _run(self, sql, params=()):
        last = None
        for attempt in range(3):
            try:
                return self._c.execute(sql, list(params) if params else [])
            except Exception as e:
                if not _is_conn_error(e):
                    raise
                # 接続確立前のタイムアウト/切断＝作り直せば直る。再送も安全。
                last = e
                import time as _t
                _t.sleep(0.4 * (attempt + 1))
                self._c = _reconnect_turso(self._url, self._token)
        raise last

    def execute(self, sql, params=()):
        return _DictCursor(self._run(sql, params))

    def executescript(self, script):
        for stmt in _split_sql(script):
            if stmt.strip():
                self._run(stmt)

    def commit(self):
        pass  # HTTP API は各 execute が即時反映（明示コミット不要）

    def close(self):
        if self._shared:
            return  # スレッド内で使い回すため閉じない
        try:
            self._c.close()
        except Exception:
            pass


# Turso接続はスレッドごとに1つだけ作って使い回す（毎回作るとHTTPクライアント生成で遅い）
_turso_tls = threading.local()

# 「作り直せば直る」接続/タイムアウト系エラーの手がかり（aiohttp等の文言）
_CONN_ERR_HINTS = ("timeout", "connection", "closed", "disconnect", "reset",
                   "clienterror", "serverdisconnected", "cannot connect", "refused",
                   "broken pipe", "eof")


def _is_conn_error(e):
    """例外チェーンを辿り、接続/タイムアウト系（再接続で回復見込み）かを判定。"""
    cur = e
    for _ in range(6):
        if cur is None:
            break
        s = (type(cur).__name__ + " " + str(cur)).lower()
        if any(h in s for h in _CONN_ERR_HINTS):
            return True
        cur = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
    return False


def _new_turso_client(url, token):
    import libsql_client  # クラウド時のみ必要（純Python＝Streamlit Cloudで確実に入る）
    http = url.replace("libsql://", "https://", 1) if url.startswith("libsql://") else url
    return libsql_client.create_client_sync(http, auth_token=token)


def _reconnect_turso(url, token):
    """スレッドローカルの古いクライアントを捨てて新規接続を作る。"""
    old = getattr(_turso_tls, "client", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    cli = _new_turso_client(url, token)
    _turso_tls.client = cli
    _turso_tls.key = (url, token)
    return cli


def _connect_turso(url, token):
    key = (url, token)
    cli = getattr(_turso_tls, "client", None)
    if cli is None or getattr(_turso_tls, "key", None) != key:
        cli = _new_turso_client(url, token)
        _turso_tls.client = cli
        _turso_tls.key = key
    return _TursoConn(cli, url, token, shared=True)


def using_turso():
    return bool(os.getenv("TURSO_DATABASE_URL", "").strip())

# ステータス定義（4種類）
PROJECT_STATUSES = ["not_started", "active", "onhold", "completed"]
STATUS_LABELS = {
    "not_started": "未着手",
    "active": "進行中",
    "onhold": "保留",
    "completed": "完了",
}


@contextmanager
def get_conn():
    url = os.getenv("TURSO_DATABASE_URL", "").strip()
    if url:  # ── クラウド（Turso/libSQL）──
        token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        conn = _connect_turso(url, token)
    else:    # ── ローカル（SQLite・従来どおり）──
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _column_exists(conn, table, column):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def init_db():
    """テーブルを初期化＋既存DBをマイグレーション"""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            category    TEXT DEFAULT '',
            color       TEXT DEFAULT '#6366F1',
            status      TEXT DEFAULT 'not_started',
            priority    INTEGER DEFAULT 2,
            sort_order  INTEGER DEFAULT 0,
            start_date  TEXT,
            end_date    TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS todos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            project_id  INTEGER,
            parent_id   INTEGER,
            url         TEXT DEFAULT '',
            memo        TEXT DEFAULT '',
            due_date    TEXT,
            due_time    TEXT,
            tags        TEXT DEFAULT '',
            priority    INTEGER DEFAULT 2,
            completed   INTEGER DEFAULT 0,
            completed_at TEXT,
            sort_order  INTEGER DEFAULT 0,
            depth       INTEGER DEFAULT 0,
            sync_calendar INTEGER DEFAULT 0,
            kind        TEXT DEFAULT 'task',
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY (parent_id)  REFERENCES todos(id)    ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS presets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            category    TEXT DEFAULT '',
            steps_json  TEXT DEFAULT '[]',
            is_builtin  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS email_threads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account     TEXT DEFAULT '',
            thread_id   TEXT,
            subject     TEXT DEFAULT '',
            sender      TEXT DEFAULT '',
            snippet     TEXT DEFAULT '',
            needs_reply INTEGER DEFAULT 0,
            draft       TEXT DEFAULT '',
            status      TEXT DEFAULT 'inbox',
            received_at TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT,
            ref_id      INTEGER,
            payload     TEXT DEFAULT '{}',
            ts          TEXT DEFAULT (datetime('now','localtime'))
        );

        -- ローカルML（自前Python学習）の予測結果を反映する受け皿
        CREATE TABLE IF NOT EXISTS predictions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT,          -- 例: completion_hours, weekly_load
            ref_type    TEXT,          -- 例: todo, week
            ref_id      TEXT,          -- 対象ID（todo.id や '2026-W30'）
            value       REAL,
            meta        TEXT DEFAULT '{}',
            model       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_pred_kind ON predictions(kind);
        CREATE INDEX IF NOT EXISTS idx_pred_ref ON predictions(ref_type, ref_id);

        -- 要返信リストから除外したメール（このスレッドのみ今後表示しない）
        CREATE TABLE IF NOT EXISTS email_dismissed (
            thread_id   TEXT PRIMARY KEY,
            subject     TEXT DEFAULT '',
            dismissed_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 差出人アドレス単位で除外（このアドレスからは今後すべて表示しない）
        CREATE TABLE IF NOT EXISTS email_blocked_senders (
            address     TEXT PRIMARY KEY,
            name        TEXT DEFAULT '',
            blocked_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        -- ポモドーロ（集中時間）の記録。プロジェクト/タスク別の時間集計・ML用
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER,
            todo_id     INTEGER,
            label       TEXT DEFAULT '',
            focus_minutes REAL DEFAULT 0,
            cycles      INTEGER DEFAULT 1,
            started_at  TEXT,
            ended_at    TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_pomo_project ON pomodoro_sessions(project_id);

        -- ToDoのグループ（リスト）。ユーザーが自由に追加/編集できる。
        CREATE TABLE IF NOT EXISTS todo_lists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            icon        TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id);
        CREATE INDEX IF NOT EXISTS idx_todos_parent  ON todos(parent_id);
        CREATE INDEX IF NOT EXISTS idx_log_kind ON activity_log(kind);
        """)

        # ── 既存DBのマイグレーション（カラム追加） ──
        migrations = [
            ("projects", "sort_order", "INTEGER DEFAULT 0"),
            ("todos", "completed_at", "TEXT"),
            ("todos", "sort_order", "INTEGER DEFAULT 0"),
            ("todos", "depth", "INTEGER DEFAULT 0"),
            ("todos", "sync_calendar", "INTEGER DEFAULT 0"),
            ("todos", "list_id", "INTEGER"),
        ]
        for table, col, decl in migrations:
            if not _column_exists(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    _seed_default_lists()


# ─────────────────────────── ToDoリスト（グループ）───────────────────────────
DEFAULT_LISTS = [("タスク", "📝"), ("買い物", "🛒"), ("頼まれごと", "🙏")]
# 旧kind → 新リスト名の対応
KIND_TO_LIST = {"task": "タスク", "shopping": "買い物", "request": "頼まれごと"}


def _seed_default_lists():
    with get_conn() as conn:
        cnt = conn.execute("SELECT COUNT(*) AS c FROM todo_lists").fetchone()["c"]
        if cnt == 0:
            for i, (name, icon) in enumerate(DEFAULT_LISTS):
                conn.execute("INSERT INTO todo_lists (name, icon, sort_order) VALUES (?,?,?)",
                             (name, icon, i))
        # 既存ToDoの list_id を kind から補完
        lists = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM todo_lists")}
        for kind, lname in KIND_TO_LIST.items():
            lid = lists.get(lname)
            if lid:
                conn.execute("UPDATE todos SET list_id=? WHERE list_id IS NULL AND kind=?",
                             (lid, kind))


def get_lists():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM todo_lists ORDER BY sort_order, id").fetchall()]


def add_list(name, icon=""):
    with get_conn() as conn:
        mx = conn.execute("SELECT COALESCE(MAX(sort_order),0) AS m FROM todo_lists").fetchone()["m"]
        cur = conn.execute("INSERT INTO todo_lists (name, icon, sort_order) VALUES (?,?,?)",
                           (name, icon, mx + 1))
        return cur.lastrowid


def update_list(list_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE todo_lists SET {cols} WHERE id=?", (*fields.values(), list_id))


def delete_list(list_id):
    """リスト削除。属していたToDoは未分類(NULL)になる。"""
    with get_conn() as conn:
        conn.execute("UPDATE todos SET list_id=NULL WHERE list_id=?", (list_id,))
        conn.execute("DELETE FROM todo_lists WHERE id=?", (list_id,))


# ─────────────────────────── Projects ───────────────────────────
def add_project(name, description="", category="", color="#6366F1",
                status="not_started", priority=2, start_date=None, end_date=None):
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS m FROM projects").fetchone()["m"]
        cur = conn.execute(
            """INSERT INTO projects
               (name, description, category, color, status, priority, sort_order, start_date, end_date)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, description, category, color, status, priority,
             max_order + 1, start_date, end_date),
        )
        return cur.lastrowid


def get_projects(status=None):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status=? ORDER BY sort_order, priority", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY sort_order, priority"
            ).fetchall()
        return [dict(r) for r in rows]


def update_project(project_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE projects SET {cols} WHERE id=?",
                     (*fields.values(), project_id))


def delete_project(project_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))


def _reindex_projects(conn):
    """現在の表示順に 0,1,2... と連番を振り直す（同一sort_order対策）"""
    rows = conn.execute("SELECT id FROM projects ORDER BY sort_order, priority, id").fetchall()
    for i, r in enumerate(rows):
        conn.execute("UPDATE projects SET sort_order=? WHERE id=?", (i, r["id"]))


def move_project(project_id, direction):
    """並び順を上(-1)/下(+1)に移動。まず連番化してから隣と入れ替える。"""
    with get_conn() as conn:
        _reindex_projects(conn)
        rows = conn.execute("SELECT id, sort_order FROM projects ORDER BY sort_order").fetchall()
        ids = [r["id"] for r in rows]
        if project_id not in ids:
            return
        idx = ids.index(project_id)
        swap = idx + direction
        if 0 <= swap < len(ids):
            a_id, b_id = ids[idx], ids[swap]
            conn.execute("UPDATE projects SET sort_order=? WHERE id=?", (swap, a_id))
            conn.execute("UPDATE projects SET sort_order=? WHERE id=?", (idx, b_id))


def set_project_order(ordered_ids):
    """ドラッグ&ドロップ等で渡された順番(idのリスト)で並びを確定する"""
    with get_conn() as conn:
        for i, pid in enumerate(ordered_ids):
            conn.execute("UPDATE projects SET sort_order=? WHERE id=?", (i, int(pid)))


# ─────────────────────────── Todos ───────────────────────────
def add_todo(title, project_id=None, parent_id=None, url="", memo="",
             due_date=None, due_time=None, tags="", priority=2, kind="task",
             sync_calendar=0, list_id=None):
    depth = 0
    if parent_id:
        with get_conn() as conn:
            row = conn.execute("SELECT depth FROM todos WHERE id=?", (parent_id,)).fetchone()
            depth = (row["depth"] + 1) if row else 1
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS m FROM todos").fetchone()["m"]
        cur = conn.execute(
            """INSERT INTO todos
               (title, project_id, parent_id, url, memo, due_date, due_time,
                tags, priority, kind, depth, sync_calendar, sort_order, list_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title, project_id, parent_id, url, memo, due_date, due_time,
             tags, priority, kind, depth, sync_calendar, max_order + 1, list_id),
        )
        return cur.lastrowid


def get_todos(project_id=None, kind=None, include_completed=True, parent_id="__any__"):
    query = "SELECT * FROM todos WHERE 1=1"
    params = []
    if project_id is not None:
        query += " AND project_id=?"
        params.append(project_id)
    if kind:
        query += " AND kind=?"
        params.append(kind)
    if parent_id != "__any__":
        if parent_id is None:
            query += " AND parent_id IS NULL"
        else:
            query += " AND parent_id=?"
            params.append(parent_id)
    if not include_completed:
        query += " AND completed=0"
    query += " ORDER BY completed, sort_order, priority, due_date"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_todo(todo_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE todos SET {cols} WHERE id=?",
                     (*fields.values(), todo_id))


def toggle_todo(todo_id):
    """完了/未完了をトグル。完了時は completed_at を記録（学習用）"""
    with get_conn() as conn:
        row = conn.execute("SELECT completed, created_at FROM todos WHERE id=?",
                           (todo_id,)).fetchone()
        if not row:
            return
        new_completed = 0 if row["completed"] else 1
        if new_completed:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE todos SET completed=1, completed_at=? WHERE id=?",
                         (now, todo_id))
            # 学習ログ：作成→完了の所要時間
            try:
                created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
                hours = (datetime.now() - created).total_seconds() / 3600
                conn.execute(
                    "INSERT INTO activity_log (kind, ref_id, payload) VALUES (?,?,?)",
                    ("todo_completed", todo_id,
                     json.dumps({"hours_to_complete": round(hours, 2)})))
            except Exception:
                pass
        else:
            conn.execute("UPDATE todos SET completed=0, completed_at=NULL WHERE id=?",
                         (todo_id,))


def delete_todo(todo_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))


def move_todo(todo_id, direction):
    """同じ親・プロジェクト内で並び替え"""
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not cur:
            return
        siblings = conn.execute(
            "SELECT * FROM todos WHERE IFNULL(parent_id,-1)=? AND IFNULL(project_id,-1)=? "
            "ORDER BY sort_order",
            (cur["parent_id"] if cur["parent_id"] is not None else -1,
             cur["project_id"] if cur["project_id"] is not None else -1)).fetchall()
        ids = [s["id"] for s in siblings]
        if todo_id not in ids:
            return
        idx = ids.index(todo_id)
        swap = idx + direction
        if 0 <= swap < len(ids):
            a, b = siblings[idx], siblings[swap]
            conn.execute("UPDATE todos SET sort_order=? WHERE id=?", (b["sort_order"], a["id"]))
            conn.execute("UPDATE todos SET sort_order=? WHERE id=?", (a["sort_order"], b["id"]))


def count_todos_by_project():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT project_id, COUNT(*) as cnt
            FROM todos WHERE completed=0 AND project_id IS NOT NULL
            GROUP BY project_id
        """).fetchall()
        return {r["project_id"]: r["cnt"] for r in rows}


def project_progress(project_id):
    """プロジェクトの進捗率（完了タスク/全タスク）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, SUM(completed) AS done "
            "FROM todos WHERE project_id=?", (project_id,)).fetchone()
        total = row["total"] or 0
        done = row["done"] or 0
        return (done, total, round(done / total * 100) if total else 0)


# ─────────────────────────── Presets ───────────────────────────
def add_preset(name, category, steps, is_builtin=0):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO presets (name, category, steps_json, is_builtin) VALUES (?,?,?,?)",
            (name, category, json.dumps(steps, ensure_ascii=False), is_builtin))
        return cur.lastrowid


def get_presets():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM presets ORDER BY is_builtin DESC, name").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["steps"] = json.loads(d["steps_json"])
            result.append(d)
        return result


def update_preset(preset_id, name=None, category=None, steps=None):
    """プリセットを編集（組み込みも編集可）"""
    fields, vals = [], []
    if name is not None:
        fields.append("name=?"); vals.append(name)
    if category is not None:
        fields.append("category=?"); vals.append(category)
    if steps is not None:
        fields.append("steps_json=?"); vals.append(json.dumps(steps, ensure_ascii=False))
    if not fields:
        return
    with get_conn() as conn:
        conn.execute(f"UPDATE presets SET {', '.join(fields)} WHERE id=?", (*vals, preset_id))


def delete_preset(preset_id):
    """プリセット削除（組み込みも削除可に変更）"""
    with get_conn() as conn:
        conn.execute("DELETE FROM presets WHERE id=?", (preset_id,))


def seed_builtin_presets():
    """組み込みプリセットを初回のみ投入（編集/削除しても再追加しない）"""
    if get_presets():  # 既に何かあれば触らない（ユーザー編集を尊重）
        return
    from presets import BUILTIN_PRESETS
    for preset in BUILTIN_PRESETS:
        add_preset(preset["name"], preset["category"], preset["steps"], is_builtin=1)


# ─────────────────────────── Activity / 学習 ───────────────────────────
def log_activity(kind, ref_id=None, payload=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO activity_log (kind, ref_id, payload) VALUES (?,?,?)",
            (kind, ref_id, json.dumps(payload or {}, ensure_ascii=False)))


# ─────────────────────────── ポモドーロ ───────────────────────────
def add_pomodoro(focus_minutes, project_id=None, todo_id=None, label="",
                 cycles=1, started_at=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO pomodoro_sessions
               (project_id, todo_id, label, focus_minutes, cycles, started_at)
               VALUES (?,?,?,?,?,?)""",
            (project_id, todo_id, label, float(focus_minutes), cycles, started_at))
        log_activity("pomodoro_done", project_id,
                     {"focus_minutes": float(focus_minutes), "label": label})
        return cur.lastrowid


def get_pomodoro_sessions(limit=200):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pomodoro_sessions ORDER BY ended_at DESC LIMIT ?", (limit,))]


def pomodoro_by_project():
    """プロジェクト別の合計集中分数を返す {project_id: minutes}"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT project_id, SUM(focus_minutes) m FROM pomodoro_sessions GROUP BY project_id").fetchall()
        return {r["project_id"]: r["m"] for r in rows}


def pomodoro_stats():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(focus_minutes),0) total, "
            "COALESCE(SUM(CASE WHEN date(ended_at)=date('now','localtime') THEN focus_minutes END),0) today "
            "FROM pomodoro_sessions").fetchone()
        return {"count": row["n"], "total_min": row["total"], "today_min": row["today"]}


def activity_summary():
    """記録中データの概要（可視化用）"""
    labels = {
        "todo_completed": "ToDo完了（所要時間つき）",
        "data_exported": "データ書き出し",
        "ml_trained": "ML学習の実行",
        "preset_applied": "プリセット適用",
    }
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT kind, COUNT(*) c, MAX(ts) last FROM activity_log GROUP BY kind").fetchall()
        result = []
        for r in rows:
            result.append({"kind": labels.get(r["kind"], r["kind"]),
                           "count": r["c"], "last": r["last"]})
        return sorted(result, key=lambda x: -x["count"])


def get_completion_stats():
    """完了所要時間の統計（学習用サマリー）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT payload FROM activity_log WHERE kind='todo_completed'").fetchall()
        hours = []
        for r in rows:
            try:
                h = json.loads(r["payload"]).get("hours_to_complete")
                if h is not None:
                    hours.append(h)
            except Exception:
                pass
        if not hours:
            return {"count": 0, "avg_hours": 0, "median_hours": 0}
        hours.sort()
        return {
            "count": len(hours),
            "avg_hours": round(sum(hours) / len(hours), 1),
            "median_hours": round(hours[len(hours) // 2], 1),
        }


# ─────────────────────────── Email ───────────────────────────
def upsert_email(account, thread_id, subject, sender, snippet,
                 needs_reply=0, received_at=None):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM email_threads WHERE thread_id=? AND account=?",
            (thread_id, account)).fetchone()
        if existing:
            conn.execute(
                "UPDATE email_threads SET subject=?, sender=?, snippet=?, needs_reply=? WHERE id=?",
                (subject, sender, snippet, needs_reply, existing["id"]))
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO email_threads
               (account, thread_id, subject, sender, snippet, needs_reply, received_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account, thread_id, subject, sender, snippet, needs_reply, received_at))
        return cur.lastrowid


def dismiss_email(thread_id, subject=""):
    """要返信リストから除外（今後表示しない）"""
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO email_dismissed (thread_id, subject) VALUES (?,?)",
                     (thread_id, subject))


def undismiss_email(thread_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM email_dismissed WHERE thread_id=?", (thread_id,))


def get_dismissed_ids() -> set:
    with get_conn() as conn:
        return {r["thread_id"] for r in conn.execute("SELECT thread_id FROM email_dismissed")}


def get_dismissed_emails():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM email_dismissed ORDER BY dismissed_at DESC")]


def block_sender(address, name=""):
    """この差出人アドレスからのメールを今後リストに表示しない"""
    address = (address or "").strip().lower()
    if not address:
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO email_blocked_senders (address, name) VALUES (?,?)",
            (address, name))


def unblock_sender(address):
    with get_conn() as conn:
        conn.execute("DELETE FROM email_blocked_senders WHERE address=?",
                     ((address or "").strip().lower(),))


def get_blocked_senders() -> set:
    with get_conn() as conn:
        return {r["address"] for r in conn.execute(
            "SELECT address FROM email_blocked_senders")}


def get_blocked_sender_rows():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM email_blocked_senders ORDER BY blocked_at DESC")]


def get_emails(needs_reply_only=False):
    with get_conn() as conn:
        q = "SELECT * FROM email_threads"
        if needs_reply_only:
            q += " WHERE needs_reply=1"
        q += " ORDER BY received_at DESC"
        return [dict(r) for r in conn.execute(q).fetchall()]


# ─────────────────────────── Predictions（ローカルML反映）───────────────────────────
def save_predictions(kind, rows, model=""):
    """予測結果をまとめて保存（同kindは置き換え）。
    rows: [{"ref_type":..,"ref_id":..,"value":..,"meta":{...}}, ...]
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM predictions WHERE kind=?", (kind,))
        for r in rows:
            conn.execute(
                "INSERT INTO predictions (kind, ref_type, ref_id, value, meta, model) "
                "VALUES (?,?,?,?,?,?)",
                (kind, r.get("ref_type", ""), str(r.get("ref_id", "")),
                 float(r.get("value", 0)),
                 json.dumps(r.get("meta", {}), ensure_ascii=False), model))


def get_predictions(kind):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE kind=? ORDER BY created_at DESC", (kind,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(d["meta"])
            except Exception:
                d["meta"] = {}
            result.append(d)
        return result


def get_prediction_map(kind):
    """ref_id → value の辞書を返す（アプリ表示用）"""
    return {p["ref_id"]: p["value"] for p in get_predictions(kind)}


def prediction_meta(kind):
    """予測の最終更新日時とモデル名を返す"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT model, MAX(created_at) AS ts, COUNT(*) AS cnt "
            "FROM predictions WHERE kind=?", (kind,)).fetchone()
        return {"model": row["model"] or "", "updated": row["ts"], "count": row["cnt"] or 0}


if __name__ == "__main__":
    init_db()
    seed_builtin_presets()
    print(f"✅ データベース初期化＋マイグレーション完了: {DB_PATH}")
    print(f"   プリセット: {len(get_presets())}件")
