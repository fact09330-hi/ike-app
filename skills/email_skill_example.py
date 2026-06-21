"""【自作スキルのテンプレート】メール処理をあなたのPythonで差し替える

使い方:
  このファイルをコピーして  skills/email_skill.py  という名前で保存すると、
  アプリが自動で読み込み、下の関数があればメール処理に使います。
  （`email_skill.py` が無ければ、アプリ標準の動作になります）

  3つの関数のうち、実装したものだけが使われます（無くてもOK）。
"""


def is_needs_reply(email: dict) -> bool | None:
    """このメールは「要返信」か？を自分のロジックで判定する。
    True=要返信に含める / False=除外 / None=アプリ標準判定にまかせる

    email の主なキー:
      subject, sender, snippet, body, source(hospital/grad/personal),
      received_at, thread_id
    """
    text = (email.get("subject", "") + email.get("body", "")).lower()
    # 例: 「?」や「お願い」「ご確認」「日程」を含むものだけ要返信にする
    keywords = ["?", "？", "お願い", "ご確認", "日程", "返信", "教えて", "ご都合"]
    if any(k in text for k in keywords):
        return True
    # 宣伝っぽいものは除外
    if any(k in text for k in ["セール", "キャンペーン", "ポイント", "クーポン"]):
        return False
    return None  # それ以外はアプリ標準にまかせる


def generate_draft(email: dict, sent_samples: list[str]) -> str | None:
    """返信下書きを自分のロジック/テンプレで生成する。
    文字列を返すとそれが下書きになる。None を返すとアプリ標準（or Claude）にまかせる。

    sent_samples: あなたの過去の送信メール本文（文体の参考用）
    """
    # 例: 大学病院あてだけ、決まった定型文を使う
    if email.get("source") == "hospital":
        name = email.get("sender", "").split("<")[0].strip() or "ご担当者"
        return (f"{name} 様\n\nお世話になっております。池本です。\n"
                f"ご連絡ありがとうございます。\n[本文]\n\n"
                f"何卒よろしくお願いいたします。")
    return None  # 標準にまかせる


def priority_score(email: dict) -> float | None:
    """メールの優先度スコア（任意）。大きいほど上に表示。Noneで標準。"""
    return None
