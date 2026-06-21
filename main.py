"""Ike App — Google Calendar 読み取り + IKE TASK Volume 集計
使い方: python main.py
"""
import os
import sys
from datetime import datetime, timedelta

import pytz
from dotenv import load_dotenv

load_dotenv()

from google_calendar_client import GoogleCalendarClient
from ike_task_volume import IKETaskVolume

JST = pytz.timezone("Asia/Tokyo")


def main():
    calendar_ids = [
        c.strip()
        for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",")
        if c.strip()
    ]
    days_future = int(os.getenv("SCORE_DAYS_FUTURE", "90"))
    days_past = int(os.getenv("SCORE_DAYS_PAST", "7"))

    now = datetime.now(JST)
    time_min = now - timedelta(days=days_past)
    time_max = now + timedelta(days=days_future)

    print("=" * 50)
    print("  Ike App — IKE TASK Volume")
    print("=" * 50)
    print(f"  集計期間: {time_min.strftime('%m/%d')} 〜 {time_max.strftime('%m/%d')}")
    print()

    try:
        gc = GoogleCalendarClient()
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    scorer = IKETaskVolume()
    all_events: list[dict] = []

    for cal_id in calendar_ids:
        events = gc.get_events(
            cal_id,
            time_min=time_min.astimezone(pytz.UTC),
            time_max=time_max.astimezone(pytz.UTC),
        )
        all_events.extend(events)
        print(f"  📅 {cal_id}: {len(events)} 件")

    print(f"\n  合計イベント: {len(all_events)} 件\n")

    # IKE TASK Volume 集計
    summary = scorer.summarize(all_events)
    total = summary["total"]
    level = scorer.load_level(total, days_future)

    print(f"📊 IKE TASK Volume (今後 {days_future} 日間)")
    print(f"  合計スコア: {total}  {level}")

    per_day = total / max(days_future, 1)
    bar = "█" * min(int(per_day * 5), 20) + "░" * max(20 - int(per_day * 5), 0)
    print(f"  [{bar}] {per_day:.2f} / 日")

    if summary["by_category"]:
        print("\n  カテゴリ別内訳:")
        for cat, score in list(summary["by_category"].items())[:8]:
            print(f"    {cat:12s}  {score:.1f}")

    # 直近7日のハイスコアイベントを表示
    high_events = [
        e for e in all_events
        if scorer.score_event(e["title"], "", e["description"]) >= 3.0
    ]
    if high_events:
        print(f"\n  ⚠️  高負荷イベント ({len(high_events)} 件):")
        for e in sorted(high_events, key=lambda x: x["start"])[:5]:
            score = scorer.score_event(e["title"], "", e["description"])
            date = e["start"][:10]
            print(f"    {date}  {e['title'][:30]}  (score: {score})")

    print()


if __name__ == "__main__":
    main()
