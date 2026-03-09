import requests
import datetime
import os
from icalendar import Calendar
import recurring_ical_events
import dotenv

dotenv.load_dotenv()

ICS_URL = os.getenv("CALENDAR_ICS_URL")
EXCLUDED_MEETINGS = [
    "lunch",
]

def get_todays_meetings():
    if not ICS_URL:
        print("[Calendar] No ICS_URL set")
        return []
    try:
        resp = requests.get(ICS_URL, timeout=10)
        print(f"[Calendar] Fetched ICS, status={resp.status_code}, size={len(resp.text)} chars")
        cal = Calendar.from_ical(resp.text)
    except Exception as e:
        print(f"[Calendar] fetch error: {e}")
        return []

    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end   = week_start + datetime.timedelta(days=6)
    print(f"[Calendar] Looking for events {week_start} → {week_end}")

    try:
        events = recurring_ical_events.of(cal).between(week_start, week_end)
    except Exception as e:
        print(f"[Calendar] recurrence expansion error: {e}")
        return []

    meetings = []
    for component in events:
        try:
            start = component.get("dtstart").dt
            end   = component.get("dtend").dt
            title = str(component.get("summary", "No title"))

            if any(ex.lower() in title.lower() for ex in EXCLUDED_MEETINGS):
                print(f"[Calendar] ⊘ excluded '{title}'")
                continue

            if isinstance(start, datetime.datetime):
                start = start.astimezone().replace(tzinfo=None)
            else:
                start = datetime.datetime.combine(start, datetime.time(0, 0))
            if isinstance(end, datetime.datetime):
                end = end.astimezone().replace(tzinfo=None)
            else:
                end = datetime.datetime.combine(end, datetime.time(23, 59))

            print(f"[Calendar] ✓ {start.date()} {start.strftime('%H:%M')}→{end.strftime('%H:%M')} '{title}'")

            meetings.append({
                "title":    title,
                "start":    start,
                "end":      end,
                "location": str(component.get("location", "")),
                "date":     start.date(),
            })
        except Exception as e:
            print(f"[Calendar] ✗ skipped '{str(component.get('summary', '?'))}': {e}")
            continue

    print(f"[Calendar] Total meetings this week: {len(meetings)}")
    return sorted(meetings, key=lambda m: m["start"])