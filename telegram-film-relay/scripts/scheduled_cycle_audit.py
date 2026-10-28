"""Audit read-only des exécutions GitHub Actions CinéX : aucun appel Telegram.

Le démarrage observé ne prouve ni l'exécution à l'heure du cron, ni un post.
Ce script n'écrit pas dans le dépôt ; il produit un rapport JSON anonyme.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SLOT_HOURS = (0, 6, 12, 18)
SLOT_MINUTE = 17
LATE_TOLERANCE = timedelta(minutes=90)


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def audit_runs(runs, *, now=None, days=4):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware UTC timestamp is required")
    now = now.astimezone(timezone.utc)
    if days < 1 or days > 14:
        raise ValueError("days must be between 1 and 14")
    start = now.date() - timedelta(days=days - 1)
    observed = []
    for item in runs:
        if item.get("event") != "schedule":
            continue
        stamp = parse_utc(item["created_at"])
        if start <= stamp.date() <= now.date():
            observed.append({"id": str(item.get("id", "")),
                             "started_at": stamp,
                             "result": item.get("conclusion") or item.get("status") or "unknown"})
    days_report = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        entries = [e for e in observed if e["started_at"].date() == day]
        slots = []
        for hour in SLOT_HOURS:
            scheduled = datetime.combine(
                day, datetime.min.time(), tzinfo=timezone.utc).replace(
                    hour=hour, minute=SLOT_MINUTE)
            if scheduled > now:
                continue
            candidates = [e for e in entries
                          if scheduled <= e["started_at"] <= scheduled + LATE_TOLERANCE]
            slots.append({
                "expected_utc": scheduled.isoformat(),
                "observed_near_schedule": len(candidates),
                "successes_near_schedule": sum(e["result"] == "success" for e in candidates),
                "missing_or_late": not bool(candidates),
                "duplicate_starts_near_schedule": len(candidates) > 1,
            })
        days_report.append({
            "date_utc": str(day),
            "expected_slots_elapsed": len(slots),
            "run_count_observed": len(entries),
            "successful_runs": sum(e["result"] == "success" for e in entries),
            "failed_runs": sum(e["result"] == "failure" for e in entries),
            "slots": slots,
        })
    scheduled_count = sum(d["expected_slots_elapsed"] for d in days_report)
    observed_count = sum(d["run_count_observed"] for d in days_report)
    slot_coverage = sum(not s["missing_or_late"] for d in days_report for s in d["slots"])
    missing = scheduled_count - slot_coverage
    failed = sum(d["failed_runs"] for d in days_report)
    duplicated = sum(s["duplicate_starts_near_schedule"] for d in days_report for s in d["slots"])
    result = {
        "checked_at": now.isoformat(),
        "scope": "github_schedule_metadata_only",
        "expected_slots_elapsed": scheduled_count,
        "observed_run_count": observed_count,
        "approximate_on_time_slots": slot_coverage,
        "missing_or_late_slots": missing,
        "failed_runs": failed,
        "duplicated_nearby_slots": duplicated,
        "status": "needs_attention" if missing or failed or duplicated else "ok_metadata_only",
        "telegram_messages_checked": 0,
        "telegram_publication_verified": False,
        "cron_job_org_verified": False,
        "explanation": ("Coverage is based on GitHub run created_at within 90 minutes after "
                        "a nominal UTC slot. Late runs may be associated with other slots; "
                        "there is no proof of a delivered Telegram post or external cron."),
        "days": days_report,
    }
    return result


def list_scheduled_runs(repo, token, *, max_pages=8):
    if not repo or "/" not in repo or not token:
        raise ValueError("GitHub repository and Actions read token required")
    entries = []
    for page in range(1, max_pages + 1):
        url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
               f"telegram-film-relay.yml/runs?event=schedule&per_page=100&page={page}")
        request = Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cinex-schedule-audit",
        })
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
        batch = data.get("workflow_runs", [])
        entries.extend(batch)
        if len(batch) < 100:
            break
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--days", type=int, default=4)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        runs = list_scheduled_runs(
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GH_TOKEN", ""))
        report = audit_runs(runs, days=args.days)
    except (HTTPError, URLError, ValueError, KeyError, TimeoutError, OSError) as exc:
        report = {"status": "blocked", "error_type": type(exc).__name__,
                  "telegram_publication_verified": False,
                  "cron_job_org_verified": False,
                  "note": "Could not verify GitHub schedule metadata"}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print("CineX scheduled cycles:", report["status"],
          "(does not verify actual Telegram delivery)")


if __name__ == "__main__":
    main()
