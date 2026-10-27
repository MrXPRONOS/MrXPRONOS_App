"""Read-only per-cycle receipts and job-outcome report; never contacts Telegram.

Receipt changes are NOT proof of public publication: they describe only local JSON.
Each GitHub Actions run uploads one anonymous report as an artifact.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

FILES = {
    "films": ("state.json", "processed"),
    "series": ("series_state.json", "completed"),
    "desir": ("desir_state.json", "completed"),
    "comedie": ("comedie_state.json", "completed"),
    "anime": ("anime_state.json", "completed"),
}
STEP_KEYS = {"films": "CINEX_OUTCOME_FILMS", "series": "CINEX_OUTCOME_SERIES",
             "desir": "CINEX_OUTCOME_DESIR", "comedie": "CINEX_OUTCOME_COMEDIE",
             "anime": "CINEX_OUTCOME_ANIME"}


def receipt_counts(folder: Path) -> dict:
    counts = {}
    for name, (filename, key) in FILES.items():
        path = folder / filename
        if not path.exists():
            counts[name] = None
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data.get(key)
        counts[name] = len(records) if isinstance(records, dict) else None
    return counts


def build_report(before: dict, after: dict, outcomes: dict, *,
                 event: str, manual_publish: bool, run_id: str = "") -> dict:
    requested = event != "workflow_dispatch" or manual_publish
    rows = {}
    for name in FILES:
        first, last = before.get(name), after.get(name)
        delta = last - first if isinstance(first, int) and isinstance(last, int) else None
        result = outcomes.get(name, "unavailable")
        if not requested:
            status = "diagnostic_only"
        elif result in ("failure", "cancelled"):
            status = "failed"
        elif result != "success":
            status = "not_executed"
        elif delta is None:
            status = "receipts_unavailable"
        elif delta > 0:
            status = "new_receipts_unverified"
        elif delta == 0:
            status = "no_new_receipts"
        else:
            status = "receipts_decreased"
        rows[name] = {"step_outcome": result, "before": first,
                      "after": last, "new_receipts_net": delta, "status": status}
    statuses = {row["status"] for row in rows.values()}
    overall = ("diagnostic_only" if not requested else
               "needs_attention" if statuses & {
                   "failed", "not_executed", "receipts_unavailable",
                   "no_new_receipts", "receipts_decreased"} else
               "receipts_detected_unverified")
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "github_run_id": str(run_id),
        "event": event, "publication_requested": requested,
        "publication_verified_on_telegram": False,
        "status": overall, "categories": rows,
        "note": ("Compteurs de reçus JSON seulement. Un succès Actions ou un delta positif "
                 "ne prouve pas qu'un message est visible dans Telegram."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path("telegram-film-relay/state"))
    args = parser.parse_args()
    if bool(args.baseline) == bool(args.report):
        parser.error("Choose either --baseline or --report")
    if args.baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(
            json.dumps(receipt_counts(args.state_dir), sort_keys=True) + "\n",
            encoding="utf-8")
        return
    baseline_file = os.environ.get("CINEX_BASELINE_FILE", "")
    before = (json.loads(Path(baseline_file).read_text(encoding="utf-8"))
              if baseline_file and Path(baseline_file).exists() else {})
    try:
        after = receipt_counts(args.state_dir)
    except (OSError, ValueError, TypeError):
        after = {}
    outcomes = {name: os.environ.get(key, "unavailable").strip() or "unavailable"
                for name, key in STEP_KEYS.items()}
    result = build_report(
        before, after, outcomes,
        event=os.environ.get("GITHUB_EVENT_NAME", "unknown"),
        manual_publish=os.environ.get("CINEX_MANUAL_PUBLISH", "").lower() in
                       {"true", "1", "yes"},
        run_id=os.environ.get("GITHUB_RUN_ID", ""))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("CineX cycle: " + result["status"] +
          " (receipt changes do not certify Telegram publication)")


if __name__ == "__main__":
    main()
