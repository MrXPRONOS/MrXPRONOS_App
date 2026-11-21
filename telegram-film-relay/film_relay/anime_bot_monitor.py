"""Privacy-safe, read-only health diagnostics for the CinéX Anime bot queue."""
from __future__ import annotations

from datetime import datetime, timezone
from collections import Counter


def health_snapshot(state: dict, *, now: int | None = None, overdue_days=14) -> dict:
    now = int(datetime.now(timezone.utc).timestamp()) if now is None else int(now)
    rows = state.get("messages", {}) or {}
    statuses = Counter(str(record.get("status", "pending")) for record in rows.values())
    series = state.get("series", {}) or {}
    weekly_overdue = 0
    fortnight_overdue = 0
    for entry in series.values():
        hint = entry.get("cadence_hint")
        if hint not in ("weekly", "fortnightly"):
            continue
        published = [
            item for item in rows.values()
            if item.get("status") == "published"
            and item.get("kind") == "video"
            and item.get("date")
        ]
        last = max((int(item["date"]) for item in published), default=0)
        if not last:
            continue
        threshold_days = 14 if hint == "weekly" else 28
        if (now - last) > threshold_days * 86400:
            if hint == "weekly":
                weekly_overdue += 1
            else:
                fortnight_overdue += 1

    ops = state.get("operation_receipts", {}) or {}
    in_flight = sum(x.get("status") in ("inflight", "uncertain")
                    for x in ops.values())
    return {
        "queue_messages": len(rows),
        "queue_pending": statuses["pending"],
        "queue_published": statuses["published"],
        "queue_quarantined": statuses["review"],
        "published_anime": len(series),
        "ambiguous_operations": in_flight,
        "weekly_overdue_estimate": weekly_overdue,
        "fortnightly_overdue_estimate": fortnight_overdue,
        "status": ("action_required" if in_flight or statuses["review"]
                   else "monitor"),
        "note": ("Estimated schedule health only; external sources may pause "
                 "releases without notice."),
    }


def evaluate_alerts(state: dict, *, now: int | None = None) -> list[dict]:
    result = health_snapshot(state, now=now)
    alerts = []
    for field, message in [
        ("ambiguous_operations", "Uncertain Telegram publication receipts"),
        ("queue_quarantined", "Source items require manual review"),
        ("weekly_overdue_estimate", "Weekly series may be delayed"),
        ("fortnightly_overdue_estimate", "Fortnightly series may be delayed"),
    ]:
        if result[field]:
            alerts.append({"code": field, "count": int(result[field]),
                           "message": message})
    return alerts
