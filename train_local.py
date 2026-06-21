"""Ike App — ローカル学習スクリプト（API課金なし・自前Python）

エクスポート(data_exports/latest.json)を読み、
  ① タスク完了所要時間の予測（scikit-learn 回帰）
  ② 週次負荷のトレンド予測（numpy 線形）
を学習し、結果を predictions テーブルに書き戻す。アプリに自動反映される。

使い方:
    python export_data.py && python train_local.py

★深層学習へ拡張する場合は「EXTEND HERE」を参照（PyTorch例あり）。
"""
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import numpy as np

import database as db
from ike_task_volume import IKETaskVolume

EXPORT = Path(__file__).parent / "data_exports" / "latest.json"
MIN_SAMPLES = 6  # 完了時間予測に必要な最小サンプル数


def load_export():
    if not EXPORT.exists():
        raise SystemExit("latest.json がありません。先に python export_data.py を実行してください。")
    with open(EXPORT, encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════
# ① タスク完了所要時間の予測（回帰）
# ════════════════════════════════════════════════════════
def train_completion_time(data) -> int:
    comps = data.get("completions", [])
    comps = [c for c in comps if c.get("hours_to_complete") is not None]
    projects = {p["id"]: p for p in data.get("projects", [])}

    if len(comps) < MIN_SAMPLES:
        print(f"① 完了時間予測: 学習データ不足（{len(comps)}/{MIN_SAMPLES}件）。"
              "タスクを完了していくと自動で学習されます。")
        return 0

    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline

    import pandas as pd
    df = pd.DataFrame(comps)
    df["category"] = df["project_id"].map(
        lambda pid: projects.get(pid, {}).get("category", "none") if pid else "none")
    df["hours_to_complete"] = df["hours_to_complete"].clip(0, 24 * 30)  # 異常値クリップ

    X = df[["priority", "has_due", "kind", "category"]]
    y = df["hours_to_complete"]

    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["kind", "category"]),
    ], remainder="passthrough")
    model = Pipeline([
        ("pre", pre),
        ("reg", GradientBoostingRegressor(n_estimators=120, max_depth=3, random_state=0)),
    ])
    model.fit(X, y)

    # ── 未完了タスクに対して予測 ──
    open_todos = [t for t in data.get("todos", []) if not t["completed"]]
    rows = []
    for t in open_todos:
        cat = projects.get(t["project_id"], {}).get("category", "none") if t["project_id"] else "none"
        feat = pd.DataFrame([{
            "priority": t["priority"], "has_due": 1 if t.get("due_date") else 0,
            "kind": t.get("kind", "task"), "category": cat}])
        pred = float(model.predict(feat)[0])
        rows.append({"ref_type": "todo", "ref_id": t["id"],
                     "value": round(max(pred, 0.1), 1), "meta": {"title": t["title"]}})

    db.save_predictions("completion_hours", rows, model="sklearn:GBR")
    score = model.score(X, y)
    print(f"① 完了時間予測: 学習{len(comps)}件 / R²={score:.2f} / "
          f"{len(rows)}件の未完了タスクを予測 → アプリ反映")
    return len(rows)


# ════════════════════════════════════════════════════════
# ② 週次負荷のトレンド予測（線形外挿）
# ════════════════════════════════════════════════════════
def train_weekly_load(data) -> int:
    scorer = IKETaskVolume()
    events = data.get("calendar_events", [])
    if not events:
        print("② 週次負荷予測: カレンダーデータなし。スキップ。")
        return 0

    weekly = defaultdict(float)
    for e in events:
        s = e.get("start", "")[:10]
        if not s:
            continue
        try:
            d = datetime.fromisoformat(s)
        except Exception:
            continue
        y, w, _ = d.isocalendar()
        weekly[(y, w)] += scorer.score_event(e.get("title", ""), "", e.get("description", ""))

    if len(weekly) < 4:
        print("② 週次負荷予測: 週数が少ないためスキップ。")
        return 0

    keys = sorted(weekly.keys())
    vals = np.array([weekly[k] for k in keys], dtype=float)
    x = np.arange(len(vals))
    # 線形トレンド + 直近平均でブレンド
    slope, intercept = np.polyfit(x, vals, 1)
    recent_mean = vals[-4:].mean()

    rows = []
    # 直近週の翌週から8週先までを予測
    last_y, last_w = keys[-1]
    for i in range(1, 9):
        w = last_w + i
        y = last_y
        while w > 52:
            w -= 52; y += 1
        trend = slope * (len(vals) + i) + intercept
        pred = max(0.0, 0.5 * trend + 0.5 * recent_mean)
        rows.append({"ref_type": "week", "ref_id": f"{y}-W{w:02d}",
                     "value": round(pred, 1), "meta": {}})

    db.save_predictions("weekly_load", rows, model="numpy:linear")
    print(f"② 週次負荷予測: 過去{len(vals)}週から先8週を外挿 → アプリ反映 "
          f"(傾き {slope:+.2f}/週)")
    return len(rows)


# ════════════════════════════════════════════════════════
# EXTEND HERE — 深層学習（PyTorch）に差し替える場合の雛形
# ════════════════════════════════════════════════════════
def train_completion_time_torch(data):
    """PyTorch版の例（任意）。上の sklearn 版を置き換え可能。
    特徴量を増やす/系列を扱う場合はここを拡張してください。"""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("PyTorch未インストールのためスキップ")
        return
    # 例: 単純なMLP。実データの前処理・学習ループはsklearn版を参考に実装。
    # model = nn.Sequential(nn.Linear(IN, 32), nn.ReLU(), nn.Linear(32, 1))
    # ... 学習後 db.save_predictions("completion_hours", rows, model="torch:MLP")
    print("（PyTorch拡張点: train_completion_time_torch を実装してください）")


def main():
    print("=" * 50)
    print("  Ike App — ローカル学習")
    print("=" * 50)
    db.init_db()
    data = load_export()
    c = data.get("counts", {})
    print(f"入力: ToDo {c.get('todos',0)} / 完了ログ {c.get('completions',0)} / "
          f"カレンダー {c.get('calendar_events',0)}件\n")

    n1 = train_completion_time(data)
    n2 = train_weekly_load(data)

    db.log_activity("ml_trained", payload={"completion_preds": n1, "load_preds": n2})
    print(f"\n✅ 学習完了。予測 {n1 + n2} 件をアプリに反映しました。")
    print("   アプリのダッシュボード/ToDo/設定 に表示されます。")


if __name__ == "__main__":
    main()
