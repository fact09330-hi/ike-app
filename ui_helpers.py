"""ビュー間で共有する小さなUIヘルパー"""
from datetime import datetime
import pytz

JST = pytz.timezone("Asia/Tokyo")

PRIORITY_LABELS = {1: "高", 2: "中", 3: "低"}
# ステータス色（未着手=黄/進行中=緑/保留=紫/完了=青）
STATUS_COLORS = {
    "not_started": "#FACC15", "active": "#16A34A",
    "onhold": "#7C3AED", "completed": "#2563EB",
}
STATUS_TINT = {  # 一覧の背景うっすら色
    "not_started": "rgba(250,204,21,0.14)", "active": "rgba(22,163,74,0.13)",
    "onhold": "rgba(124,58,237,0.13)", "completed": "rgba(37,99,235,0.12)",
}
KIND_ICON = {"task": "📝", "shopping": "🛒", "request": "🙏"}
KIND_LABEL = {"task": "タスク", "shopping": "買い物", "request": "頼まれごと"}
STATUS_LABELS = {"not_started": "未着手", "active": "進行中", "onhold": "保留", "completed": "完了"}
STATUS_ORDER = ["not_started", "active", "onhold", "completed"]


def iso_week_label(year: int, week: int) -> str:
    """ISO年-週 を「6月1W」形式に変換（その週の月曜が属する月＋月内の週番号）"""
    try:
        monday = datetime.fromisocalendar(year, week, 1)
    except Exception:
        return f"{week}W"
    wom = (monday.day - 1) // 7 + 1
    return f"{monday.month}月{wom}W"


def parse_dt(s: str):
    """ISO文字列を datetime(JST) に。日付のみ/日時両対応"""
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST)
        return datetime.fromisoformat(s[:10]).replace(tzinfo=JST)
    except Exception:
        return None


def load_to_tint(load: float, max_load: float) -> str:
    """負荷スコアを背景色(rgba)に変換。0→透明, max→赤み"""
    if max_load <= 0 or load <= 0:
        return "transparent"
    ratio = min(load / max_load, 1.0)
    # 赤系のオーバーレイ。最大でも0.32程度に抑える
    alpha = round(0.05 + ratio * 0.27, 3)
    return f"rgba(244, 63, 94, {alpha})"


def priority_dot(priority: int) -> str:
    return f'<span class="pri-dot pri-{priority}"></span>'


def status_badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status)
    return f'<span class="sb sb-{status}">{label}</span>'


def tag_chips(tags: str) -> str:
    if not tags:
        return ""
    return "".join(
        f'<span class="chip-gray chip">{t.strip()}</span>'
        for t in tags.split(",") if t.strip())
