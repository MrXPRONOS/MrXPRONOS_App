#!/usr/bin/env python3
"""Read-only live BSD settlement check. Never edits the feed or sends messages."""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bsd_api import BSDClient
from bsd_h2h import _utc
from bsd_v2_publish import update_settlement

ROOT = Path(__file__).resolve().parents[1]


def inspect(feed, now, fetch_detail, max_samples=8):
    if feed.get("source") != "bsd" or feed.get("model_version") != "bsd-v2-isolated":
        raise ValueError("Unexpected production feed")
    due = []
    seen = set()
    for row in feed.get("matches") or []:
        if not isinstance(row, dict) or row.get("source") != "bsd":
            continue
        eid = str(row.get("source_event_id") or str(row.get("id") or "").removeprefix("bsd:"))
        if eid in seen:
            raise ValueError("Duplicate published native event ID: fail closed")
        seen.add(eid)
        if row.get("is_finished") is True or row.get("status") == "finished":
            continue
        try:
            age = now - _utc(str(row["event_date"]))
        except (KeyError, TypeError, ValueError):
            continue
        if age >= timedelta(hours=4):
            due.append((row, eid))
    due.sort(key=lambda item: item[0]["event_date"], reverse=True)
    sample = due[:max_samples]
    counts = {"due": len(due), "sample": len(sample), "bsd_finished_verified": 0,
              "bsd_still_unresolved": 0, "bsd_missing": 0, "bsd_identity_mismatch": 0,
              "source_errors": 0}
    for row, eid in sample:
        if not eid.isascii() or not eid.isdecimal():
            counts["bsd_identity_mismatch"] += 1
            continue
        try:
            detail = fetch_detail(eid)
        except Exception as exc:
            counts["source_errors"] += 1
            print("BSD_SETTLEMENT_SOURCE_ERROR", type(exc).__name__)
            continue
        if not isinstance(detail, dict):
            counts["bsd_missing"] += 1
            continue
        if str(detail.get("id") or "") != eid:
            counts["bsd_identity_mismatch"] += 1
            continue
        confirmed = update_settlement(row, detail)
        if confirmed is not row and confirmed.get("is_finished") is True:
            counts["bsd_finished_verified"] += 1
        else:
            counts["bsd_still_unresolved"] += 1
    return counts


def main():
    feed_path = ROOT / "data.json"
    audit_paths = [feed_path, ROOT / "bsd/publication_ledger.json",
                   ROOT / "bsd/quality_report.json"]
    original = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in audit_paths}
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    client = BSDClient(max_requests=12)
    report = inspect(feed, now, lambda eid: client.get_json("/events/%s/" % int(eid), ttl=0))
    report.update({"checked_at": now.isoformat(), "bsd_api_calls": client.requests_made,
                   "mode": "read_only", "published_predictions_changed": False})
    for path in audit_paths:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original[str(path)], (
            "Read-only settlement audit changed a production artifact")
    print("BSD_SETTLEMENT_LIVE_AUDIT", json.dumps(report, sort_keys=True))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## BSD V2 — Live settlement read-only verification\\n\\n")
            for key in ("due", "sample", "bsd_finished_verified", "bsd_still_unresolved",
                        "bsd_missing", "bsd_identity_mismatch", "source_errors", "bsd_api_calls"):
                fh.write(f"- {key}: {report[key]}\\n")
            fh.write("\\nNo data.json, ledger, Telegram or bets were modified.\\n")
    if report["source_errors"]:
        raise SystemExit("BSD settlement source unavailable for sampled events")


if __name__ == "__main__":
    main()
