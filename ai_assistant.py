"""AI アシスタント — Claude API でプロジェクト/負荷の提案を行う。
ANTHROPIC_API_KEY が無い場合はヒューリスティック（ルールベース）提案にフォールバック。
"""
import os
import json

# 最新の Claude モデル（2026年時点）。コストと品質のバランスで Sonnet を既定に。
DEFAULT_MODEL = os.getenv("IKE_LLM_MODEL", "claude-sonnet-4-6")


def is_available() -> bool:
    """Claude API が使えるか（キー＋パッケージ）"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _call_claude(system: str, user: str, max_tokens: int = 800) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


# ─────────────────────────── プロジェクト提案 ───────────────────────────
def suggest_for_project(project: dict, tasks: list, load_per_week: dict | None = None) -> dict:
    """プロジェクトへの追加・修正提案を返す。
    戻り値: {"available": bool, "suggestions": [str, ...], "source": "ai"|"heuristic"}
    """
    if is_available():
        try:
            return _ai_suggest_project(project, tasks, load_per_week)
        except Exception as e:
            return {"available": False, "source": "error",
                    "suggestions": [f"AI呼び出しエラー: {e}"]}
    return _heuristic_suggest_project(project, tasks, load_per_week)


def _ai_suggest_project(project, tasks, load_per_week):
    task_lines = "\n".join(
        f"- {'[完了]' if t['completed'] else '[未]'} {t['title']} "
        f"(優先度{t['priority']}, 期限{t.get('due_date') or 'なし'})"
        for t in tasks) or "（タスクなし）"
    load_str = ""
    if load_per_week:
        top = sorted(load_per_week.items(), key=lambda x: -x[1])[:3]
        load_str = "負荷の高い週: " + ", ".join(f"{w}(スコア{s:.1f})" for w, s in top)

    system = (
        "あなたは多忙な医師兼大学院生のプロジェクト管理を支援するアシスタントです。"
        "簡潔・具体的・実行可能な提案を日本語で、最大5個、箇条書きで返してください。"
        "前置きや結びの文は不要です。")
    user = (
        f"プロジェクト名: {project['name']}\n"
        f"カテゴリ: {project.get('category','')}\n"
        f"期間: {project.get('start_date')} 〜 {project.get('end_date')}\n"
        f"ステータス: {project.get('status')}\n"
        f"既存タスク:\n{task_lines}\n{load_str}\n\n"
        "このプロジェクトに対し、(1)追加すべきタスク (2)抜けている工程 "
        "(3)負荷を考慮した日程調整 の観点で提案してください。")
    text = _call_claude(system, user)
    suggestions = [line.strip(" ・-*　") for line in text.splitlines()
                   if line.strip(" ・-*　")]
    return {"available": True, "source": "ai", "suggestions": suggestions[:5]}


def _heuristic_suggest_project(project, tasks, load_per_week):
    """APIキーが無い時のルールベース提案"""
    suggestions = []
    incomplete = [t for t in tasks if not t["completed"]]
    no_due = [t for t in incomplete if not t.get("due_date")]

    if not tasks:
        suggestions.append("タスクがまだありません。プリセットから工程を一括追加すると早いです。")
    if no_due:
        suggestions.append(f"期限未設定のタスクが{len(no_due)}件あります。日程を入れるとガント/カレンダーに反映されます。")
    if project.get("status") == "not_started" and incomplete:
        suggestions.append("タスクがあるのにステータスが「未着手」です。「進行中」に変更しましょう。")
    if load_per_week:
        peak = max(load_per_week.items(), key=lambda x: x[1], default=(None, 0))
        if peak[0] and peak[1] > 8:
            suggestions.append(f"{peak[0]}は負荷が高い週です（スコア{peak[1]:.1f}）。この週の締切は避けると安全です。")
    cat = project.get("category", "")
    if "論文" in project["name"] or "論文" in cat:
        if not any("投稿" in t["title"] for t in tasks):
            suggestions.append("「投稿先選定」「カバーレター作成」のタスクが見当たりません。")
    if not suggestions:
        suggestions.append("順調です。次の締切タスクに集中しましょう。")

    suggestions.append("💡 より高度なAI提案にはANTHROPIC_API_KEYの設定が必要です（設定タブ参照）。")
    return {"available": False, "source": "heuristic", "suggestions": suggestions}


# ─────────────────────────── メール返信下書き ───────────────────────────
def generate_reply_draft(email: dict, sent_samples: list[str] | None = None) -> dict:
    """要返信メールへの返信下書きを生成。
    戻り値: {"draft": str, "source": "ai"|"heuristic"|"skill"}
    """
    # ① 自作スキルが下書きを返せばそれを優先
    try:
        import user_skills
        custom = user_skills.skill_generate_draft(email, sent_samples or [])
        if custom:
            return {"draft": custom, "source": "skill"}
    except Exception:
        pass
    if is_available():
        try:
            return _ai_draft(email, sent_samples or [])
        except Exception as e:
            d = _heuristic_draft(email)
            d["draft"] = f"（AI生成失敗: {e}）\n\n" + d["draft"]
            return d
    return _heuristic_draft(email)


def _sender_name(sender: str) -> str:
    import re
    # "山田太郎 <yamada@x.jp>" → 山田太郎 / メールのみなら@前
    name = re.sub(r'<[^>]+>', '', sender).strip().strip('"')
    if not name and "@" in sender:
        name = sender.split("@")[0]
    return name or "ご担当者"


def _ai_draft(email, sent_samples):
    style = ""
    if sent_samples:
        joined = "\n---\n".join(s[:600] for s in sent_samples[:6])
        style = f"\n\n【あなた（差出人）の過去の送信メール例。文体・言い回し・敬語の癖を再現すること】\n{joined}"
    system = (
        "あなたは多忙な医師兼大学院生本人として、受信メールへの返信下書きを作成します。"
        "過去の送信例があれば、その人の文体・敬語・署名の癖を忠実に再現してください。"
        "丁寧で簡潔な日本語。本文のみを出力し、説明や注釈は不要です。"
        "内容が不確かな部分は[ ]で空欄にして相手に補完させてください。")
    user = (
        f"差出人: {email.get('sender')}\n"
        f"件名: {email.get('subject')}\n"
        f"本文:\n{email.get('body', email.get('snippet',''))[:1500]}\n"
        f"{style}\n\nこのメールへの返信下書きを作成してください。")
    text = _call_claude(system, user, max_tokens=700)
    return {"draft": text.strip(), "source": "ai"}


def _heuristic_draft(email):
    name = _sender_name(email.get("sender", ""))
    draft = (
        f"{name} 様\n\n"
        f"お世話になっております。\n\n"
        f"ご連絡いただきありがとうございます。\n"
        f"[ご返信内容をここに記入してください]\n\n"
        f"お手数をおかけしますが、何卒よろしくお願いいたします。")
    return {"draft": draft, "source": "heuristic"}


# ─────────────────────────── 負荷分析 ───────────────────────────
def analyze_workload(weekly_load: dict, summary: dict) -> str:
    """カレンダー負荷の所見を返す（短文）"""
    if not weekly_load:
        return "データが不足しています。"
    if is_available():
        try:
            top = sorted(weekly_load.items(), key=lambda x: -x[1])[:4]
            load_str = ", ".join(f"{w}: {s:.1f}" for w, s in sorted(weekly_load.items()))
            system = ("あなたは多忙な医師兼大学院生の働き方アドバイザーです。"
                      "週次の負荷スコアを見て、いつにタスクを寄せ/避けるべきか2-3文で助言してください。")
            user = f"週次負荷スコア: {load_str}\n合計: {summary.get('total')}"
            return _call_claude(system, user, max_tokens=300)
        except Exception:
            pass
    # ヒューリスティック
    items = sorted(weekly_load.items())
    peak = max(weekly_load.items(), key=lambda x: x[1])
    low = min(weekly_load.items(), key=lambda x: x[1])
    return (f"負荷のピークは {peak[0]}（スコア{peak[1]:.1f}）。"
            f"比較的余裕があるのは {low[0]}（{low[1]:.1f}）です。"
            f"締切や新規タスクは余裕のある週に寄せるのがおすすめです。")
