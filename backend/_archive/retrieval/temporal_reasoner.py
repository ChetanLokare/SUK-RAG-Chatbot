"""
Temporal reasoning module (PRODUCTION VERSION)
"""

from typing import List, Dict
from datetime import datetime, timezone


# =========================================================
# SAFE PARSE
# =========================================================

def _parse_ts(ts):

    try:
        return datetime.fromtimestamp(int(ts), timezone.utc)
    except Exception:
        return None


# =========================================================
# EXTRACT EVENTS
# =========================================================

def extract_events(contexts: List[Dict]):

    events = []

    for ctx in contexts:

        meta = ctx.get("metadata") or {}

        ts = meta.get("deadline_ts")

        if not ts:
            continue

        dt = _parse_ts(ts)

        if not dt:
            continue

        events.append({
            "date": dt,
            "text": ctx.get("text", ""),
            "source": meta.get("source_value"),
            "metadata": meta,
        })

    return events


# =========================================================
# NEXT EVENT
# =========================================================

def find_next_event(contexts: List[Dict]):

    now = datetime.now(timezone.utc)

    events = extract_events(contexts)

    future = [e for e in events if e["date"] >= now]

    if not future:
        return None

    future.sort(key=lambda x: x["date"])

    return future[0]


# =========================================================
# SORT TIMELINE
# =========================================================

def sort_events(contexts: List[Dict]):

    events = extract_events(contexts)

    return sorted(events, key=lambda x: x["date"])