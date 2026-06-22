"""IKE TASK Volume スコアリングエンジン

- 休み/振休/有給は負荷0（全体負荷から除外）。同日に勉強会や外勤があればそちらは加算される。
- 飲み会/バンド/結婚式/定例会などは「遊び」カテゴリに自動分類。
- カテゴリは CATEGORY_RULES で自動判定（その他を最小化）。
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "ike_scores.json"

# 負荷0（休み系）— これらは全体負荷に含めない
OFF_KEYWORDS = ["振休", "代休", "有給", "有休", "有給休暇", "休暇", "休日", "休み", "やすみ", "off", "休"]

DEFAULT_CONFIG = {
    "scores": {
        "論文": 5.0, "論文執筆": 5.0, "manuscript": 5.0, "paper": 5.0, "投稿": 4.5, "revision": 4.5,
        "講演": 4.0, "keynote": 4.0, "invited talk": 4.0, "特別講演": 4.0, "招待講演": 4.0,
        "学会発表": 3.0, "口演": 3.0, "発表": 3.0, "conference": 3.0,
        "学会": 2.5, "当直": 2.5, "日直": 2.5,
        "web meeting": 2.0, "zoom": 2.0, "teams": 2.0, "オンライン会議": 2.0, "会議": 1.8, "打ち合わせ": 1.8,
        "勉強会": 1.5, "seminar": 1.5, "セミナー": 1.5, "workshop": 1.5,
        "外勤": 1.0, "手術": 0.8, "外来": 0.6, "仕事": 0.5, "病院": 0.5,
        "美容室": 0.3, "美容院": 0.3, "通院": 0.3,
        "飲み会": 0.5, "歓迎会": 0.5, "送別会": 0.5, "懇親会": 0.5, "会食": 0.5,
        "バンド": 0.5, "ライブ": 0.5, "結婚式": 0.5, "披露宴": 0.5, "二次会": 0.5,
        "定例会": 0.5, "定例": 0.5, "誕生日": 0.3, "旅行": 0.3,
    },
    "default_score": 0.3
}

# カテゴリ自動判定（上から優先）。(キーワード, カテゴリ)
CATEGORY_RULES = [
    (["当直"], "当直"),
    (["日直"], "日直"),
    (["外勤"], "外勤"),
    (["論文", "manuscript", "paper", "投稿", "revision"], "論文"),
    (["講演", "keynote", "招待", "特別講演"], "講演"),
    (["学会", "発表", "口演", "ポスター", "conference"], "学会発表"),
    (["勉強会", "seminar", "セミナー", "workshop", "ワークショップ"], "勉強会"),
    (["飲み会", "歓迎会", "送別会", "懇親会", "会食", "バンド", "ライブ",
      "結婚式", "披露宴", "二次会", "定例会", "定例", "誕生日", "旅行", "遊び"], "遊び"),
    (["web meeting", "zoom", "teams", "meet", "会議", "打ち合わせ", "打合せ", "面談", "ミーティング"], "会議"),
    (["美容室", "美容院", "ネイル", "通院", "受診", "歯医者"], "私用"),
    (["手術", "外来", "病院", "仕事", "勤務"], "仕事"),
]


class IKETaskVolume:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        return DEFAULT_CONFIG

    def _is_off(self, text: str) -> bool:
        return any(k.lower() in text for k in OFF_KEYWORDS)

    def score_event(self, title: str, label: str = "", description: str = "") -> float:
        """イベントの負荷スコア。休み系は0（全体負荷から除外）。"""
        text = f"{title} {label} {description}".lower()
        # 休み系は負荷0。ただし同テキストに勉強会/外勤など労働系が含まれる場合はそちらを優先
        if self._is_off(text):
            work_hit = any(
                kw.lower() in text
                for kws, cat in CATEGORY_RULES if cat not in ("遊び", "私用")
                for kw in kws)
            if not work_hit:
                return 0.0
        scores = self.config.get("scores", {})
        best_score = self.config.get("default_score", 0.3)
        for keyword, score in scores.items():
            if keyword.lower() in text and score > best_score:
                best_score = score
        return best_score

    def get_category(self, title: str, label: str = "") -> str:
        """カテゴリを自動判定。"""
        text = f"{title} {label}".lower()
        if self._is_off(text):
            work_hit = any(
                kw.lower() in text
                for kws, cat in CATEGORY_RULES if cat not in ("遊び", "私用")
                for kw in kws)
            if not work_hit:
                return "休み"
        for keywords, category in CATEGORY_RULES:
            for kw in keywords:
                if kw.lower() in text:
                    return category
        return "その他"

    def is_unscored(self, title: str, label: str = "") -> bool:
        """登録キーワードにも休み系にも当たらず、デフォルト負荷のままになるか。
        True＝「スコア設定に拾われていない予定」＝負荷に反映されていない（追加候補）。"""
        text = f"{title} {label}".lower()
        if self._is_off(text):
            return False  # 休みは意図的に負荷0なので未登録扱いにしない
        for keyword in self.config.get("scores", {}):
            if keyword.lower() in text:
                return False
        return True

    def summarize(self, events: list[dict]) -> dict:
        if not events:
            return {"total": 0.0, "count": 0, "by_category": {}}
        by_category: dict[str, float] = {}
        total = 0.0
        for event in events:
            score = self.score_event(event.get("title", ""), event.get("label", ""),
                                     event.get("description", ""))
            category = self.get_category(event.get("title", ""), event.get("label", ""))
            if score <= 0:
                continue  # 休み等は負荷に含めない
            by_category[category] = by_category.get(category, 0.0) + score
            total += score
        return {
            "total": round(total, 1),
            "count": len(events),
            "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1]))
        }

    def load_level(self, total_score: float, days: int) -> str:
        per_day = total_score / max(days, 1)
        if per_day < 0.5:
            return "🟢 余裕あり"
        elif per_day < 1.5:
            return "🟡 標準的"
        elif per_day < 3.0:
            return "🟠 やや高負荷"
        else:
            return "🔴 高負荷注意"

    def save_config(self):
        CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
