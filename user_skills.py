"""自作スキル（プラグイン）ローダー
skills/email_skill.py が存在すれば読み込み、その関数をメール処理で使う。
無ければアプリ標準の動作になる。
"""
import importlib.util
from pathlib import Path

SKILL_FILE = Path(__file__).parent / "skills" / "email_skill.py"

_cache = {"loaded": False, "module": None}


def _load():
    if _cache["loaded"]:
        return _cache["module"]
    _cache["loaded"] = True
    if SKILL_FILE.exists():
        try:
            spec = importlib.util.spec_from_file_location("email_skill", SKILL_FILE)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _cache["module"] = mod
        except Exception as e:
            print(f"[user_skills] email_skill.py 読み込み失敗: {e}")
            _cache["module"] = None
    return _cache["module"]


def has_email_skill() -> bool:
    return _load() is not None


def skill_is_needs_reply(email):
    mod = _load()
    if mod and hasattr(mod, "is_needs_reply"):
        try:
            return mod.is_needs_reply(email)
        except Exception:
            return None
    return None


def skill_generate_draft(email, sent_samples):
    mod = _load()
    if mod and hasattr(mod, "generate_draft"):
        try:
            return mod.generate_draft(email, sent_samples)
        except Exception:
            return None
    return None


def skill_priority_score(email):
    mod = _load()
    if mod and hasattr(mod, "priority_score"):
        try:
            return mod.priority_score(email)
        except Exception:
            return None
    return None
