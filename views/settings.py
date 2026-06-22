"""設定画面 — IKE TASK Volume スコア、AI、プリセット、カレンダー連携、ローカルML"""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

import database as db
import ai_assistant as ai
from calendar_loader import list_calendars, is_authenticated

APP_DIR = Path(__file__).resolve().parent.parent


def render(scorer, events=None):
    st.markdown("# 設定")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 IKE TASK Volume", "📋 プリセット", "🤖 AI / Claude",
         "📅 カレンダー連携", "🔮 ローカルML"])

    # ── スコア設定 ──
    with tab1:
        st.markdown("### キーワード別スコア")
        st.caption("予定名・タスクにキーワードが含まれると、そのスコアが負荷として加算されます。"
                   "論文＞講演＞学会発表… のように重み付けをカスタマイズできます。")
        scores = scorer.config.get("scores", {})
        df = pd.DataFrame([{"キーワード": k, "スコア": v} for k, v in scores.items()]
                          ).sort_values("スコア", ascending=False).reset_index(drop=True)
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic",
                                hide_index=True, key="score_ed",
                                column_config={
                                    "スコア": st.column_config.NumberColumn(
                                        min_value=0.0, max_value=10.0, step=0.1, format="%.1f")})
        if st.button("💾 保存", type="primary"):
            new_scores = {}
            for _, row in edited.iterrows():
                kw = str(row["キーワード"]).strip()
                if kw:
                    try:
                        new_scores[kw] = float(row["スコア"])
                    except (ValueError, TypeError):
                        pass
            scorer.config["scores"] = new_scores
            scorer.save_config()
            st.cache_data.clear()
            st.success("保存しました。各画面の負荷スコアに反映されます。")
        st.caption("💡 不要なキーワードは上の表で行を削除（行頭を選んで Delete）→💾保存で消せます。")

        # ── カレンダー語句の診断：負荷に拾われていない予定を見つける ──
        with st.expander("📅 カレンダー語句の診断（負荷に拾われていない予定を見つける）"):
            default_s = scorer.config.get("default_score", 0.3)
            st.caption(f"実際のGoogleカレンダーの予定で、上のスコアにも休み系にも当たらず"
                       f"デフォルト負荷（{default_s}）のままの予定を、出現回数が多い順に表示します。"
                       "重要なものは上の表にキーワードを追加すると負荷へ反映されます。")
            if not events:
                st.caption("（カレンダーの予定が読み込まれていません。同期後に開いてください）")
            else:
                from collections import Counter
                cnt = Counter()
                for e in events:
                    title = (e.get("title") or "").strip()
                    if title and scorer.is_unscored(title):
                        cnt[title] += 1
                if not cnt:
                    st.success("未登録の予定はありません。主要な予定はすべて負荷に反映されています。")
                else:
                    st.markdown(f"**未登録の予定：{len(cnt)} 種**（負荷に未反映＝追加候補）")
                    rows = [{"予定名": t, "出現回数": n} for t, n in cnt.most_common(40)]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption("👆 数えたい予定があれば、上の表に「予定名に含まれる語」とスコアを追加→💾保存。")

    # ── プリセット管理 ──
    with tab2:
        st.markdown("### ワークフロー・プリセット")
        st.caption("論文執筆・学会発表など定型フローのタスク雛形。**組み込み分も編集できます**。"
                   "工程は1行1タスク「タスク名, 開始からの日数, 優先度(1-3)」形式。")
        for p in db.get_presets():
            badge = "🔧 組込（編集可）" if p["is_builtin"] else "✏️ 自作"
            with st.expander(f"{badge}　{p['name']}　（{p['category']} · {len(p['steps'])}工程）"):
                en = st.text_input("プリセット名", value=p["name"], key=f"pn_{p['id']}")
                ec = st.text_input("カテゴリ", value=p["category"], key=f"pc_{p['id']}")
                steps_text = "\n".join(
                    f"{s['title']}, {s.get('offset_days',0)}, {s.get('priority',2)}"
                    for s in p["steps"])
                est = st.text_area("工程", value=steps_text, height=160, key=f"ps_{p['id']}")
                bc = st.columns([1, 1, 3])
                if bc[0].button("💾 保存", key=f"savepre_{p['id']}", type="primary"):
                    steps = []
                    for line in est.splitlines():
                        parts = [x.strip() for x in line.split(",")]
                        if parts and parts[0]:
                            steps.append({
                                "title": parts[0],
                                "offset_days": int(parts[1]) if len(parts) > 1 and parts[1].lstrip('-').isdigit() else 0,
                                "priority": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2})
                    db.update_preset(p["id"], name=en, category=ec, steps=steps)
                    st.success("保存しました"); st.rerun()
                if bc[1].button("🗑 削除", key=f"delpre_{p['id']}"):
                    db.delete_preset(p["id"]); st.rerun()

        st.markdown("#### ＋ 新規プリセット作成")
        with st.form("new_preset", clear_on_submit=True):
            pn = st.text_input("プリセット名")
            pc = st.text_input("カテゴリ")
            st.caption("工程は1行1タスク、「タスク名, 開始からの日数, 優先度(1-3)」形式")
            steps_text = st.text_area("工程", height=120,
                                      placeholder="構成検討, 0, 1\nスライド作成, 7, 2\n発表, 14, 1")
            if st.form_submit_button("作成", type="primary"):
                steps = []
                for line in steps_text.splitlines():
                    parts = [x.strip() for x in line.split(",")]
                    if parts and parts[0]:
                        steps.append({
                            "title": parts[0],
                            "offset_days": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                            "priority": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2})
                if pn and steps:
                    db.add_preset(pn, pc, steps, is_builtin=0)
                    st.success(f"プリセット「{pn}」を作成しました")
                    st.rerun()

    # ── AI設定 ──
    with tab3:
        st.markdown("### Claude API 連携")
        if ai.is_available():
            st.success(f"✅ AI機能 有効（モデル: {ai.DEFAULT_MODEL}）")
            st.caption("プロジェクト提案・負荷分析・メール下書きがClaudeで生成されます。")
        else:
            st.warning("⚠️ AI機能 無効（現在はルールベースで動作）")
            st.markdown("""
**有効化の手順:**
1. https://console.anthropic.com/ で API キーを取得
2. `ike_app/.env` に以下を追記:
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```
3. アプリを再起動
""")
        stats = db.get_completion_stats()
        st.markdown("### 学習データ")
        _exc = stats.get("excluded", 0)
        _exc_note = f"（即時完了 {_exc}件は除外）" if _exc else ""
        st.caption(f"完了タスク記録: {stats['count']}件{_exc_note} · "
                   f"平均完了時間 {stats['avg_hours']}h · 中央値 {stats['median_hours']}h")
        st.caption("作成から30分未満で完了したもの（プリセットで一括「実行済み」化したもの等）は、"
                   "実作業ではないため平均・学習の集計から自動で除外しています。")

    # ── カレンダー ──
    with tab4:
        st.markdown("### Google Calendar")
        if is_authenticated():
            st.success("✅ 連携済み")
            cals = list_calendars()
            for c in cals:
                star = " 🌟primary" if c["primary"] else ""
                st.code(f"{c['name']}{star}\n{c['id']}", language=None)
        else:
            st.warning("未連携。ターミナルで `python setup_google_auth.py` を実行してください。")

    # ── ローカルML ──
    with tab5:
        _local_ml_tab()


def _local_ml_tab():
    st.markdown("### 🔮 ローカルML（自前Python学習・API課金なし）")
    st.caption("データを出力 → あなたのPythonで学習 → 結果をアプリに反映する仕組みです。"
               "Claude APIを使わず、ローカルで完結します。")

    comp = db.prediction_meta("completion_hours")
    load = db.prediction_meta("weekly_load")
    c1, c2 = st.columns(2)
    c1.metric("完了時間予測", f"{comp['count']}件",
              help=f"モデル: {comp['model'] or '未学習'} / 更新: {comp['updated'] or '—'}")
    c2.metric("週次負荷予測", f"{load['count']}件",
              help=f"モデル: {load['model'] or '未学習'} / 更新: {load['updated'] or '—'}")

    if st.button("📤 エクスポート ＆ 学習を実行", type="primary"):
        with st.spinner("export_data.py → train_local.py を実行中..."):
            try:
                r1 = subprocess.run([sys.executable, "export_data.py"],
                                    cwd=APP_DIR, capture_output=True, text=True, timeout=180)
                r2 = subprocess.run([sys.executable, "train_local.py"],
                                    cwd=APP_DIR, capture_output=True, text=True, timeout=300)
                st.code((r1.stdout or "") + "\n" + (r2.stdout or "") +
                        (("\n[err]\n" + r2.stderr) if r2.returncode else ""), language=None)
                st.success("完了。予測がアプリに反映されました。")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"実行エラー: {e}")

    # 週次負荷予測の表示
    preds = db.get_predictions("weekly_load")
    if preds:
        import plotly.graph_objects as go
        from style import CHART
        st.markdown("#### 来週以降の予測負荷")
        df = pd.DataFrame([{"週": p["ref_id"], "予測負荷": p["value"]} for p in preds]
                          ).sort_values("週")
        fig = go.Figure(go.Bar(x=df["週"], y=df["予測負荷"], marker_color=CHART["accent"]))
        fig.update_layout(
            height=220, margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor=CHART["paper"], plot_bgcolor=CHART["paper"],
            font=dict(color=CHART["font"], size=11),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor=CHART["grid"]))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 記録中のデータ（実行速度など）
    st.markdown("---")
    st.markdown("#### 📝 記録中のデータ（今後の改善・学習に使用）")
    cstats = db.get_completion_stats()
    st.caption(f"ToDoの**実行速度**を記録中: 完了 {cstats['count']}件 · "
               f"平均 {cstats['avg_hours']}h / 中央値 {cstats['median_hours']}h")
    acts = db.activity_summary()
    if acts:
        adf = pd.DataFrame([{"記録項目": a["kind"], "件数": a["count"],
                             "最終記録": (a["last"] or "")[:16]} for a in acts])
        st.dataframe(adf, use_container_width=True, hide_index=True)
    st.caption("これらは `activity_log` に蓄積され、export_data.py → train_local.py で学習に使われます。")

    st.markdown("---")
    st.markdown("""
**仕組みと拡張**
- `export_data.py` … プロジェクト/ToDo/カレンダー/完了ログを `data_exports/latest.json` に出力
- `train_local.py` … ①完了時間予測（scikit-learn）②週次負荷予測（numpy）を学習し `predictions` テーブルに反映
- 深層学習に拡張する場合は `train_local.py` の **EXTEND HERE**（PyTorch雛形）を実装
- 定期実行: `bash setup_ml_schedule.sh` で毎日自動（エクスポート→学習→反映）
""")
    st.info("💡 完了時間予測はタスクを完了するほど精度が上がります（現在ログ蓄積中）。")
