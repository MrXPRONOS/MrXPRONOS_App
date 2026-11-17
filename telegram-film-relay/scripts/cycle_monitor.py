"""Durable CinéX cycle monitor. No Telegram writes, no secrets in output.

Counts verified successful empty cycles only. API errors and failed categories
must not masquerade as empty source queues.
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("state/cycle_monitor.json")
CATEGORIES = ("films", "series", "desir", "comedie", "anime")


def update_monitor(previous: dict, *, run_id: str, verification: str,
                   verified_posts: int, outcomes: dict, now: str) -> dict:
    if not str(run_id).isdigit():
        raise ValueError("GitHub run ID must be numeric")
    if verified_posts < 0:
        raise ValueError("verified posts must be nonnegative")
    if previous.get("last_run_id") == str(run_id):
        return previous  # idempotent retry, never increment the streak twice
    if any(outcomes.get(c) not in ("success",) for c in CATEGORIES):
        status = "category_failed"
    elif verification not in ("verified", "no_new_posts"):
        status = "verification_failed"
    elif verification == "verified" and verified_posts > 0:
        status = "published"
    elif verification == "no_new_posts" and verified_posts == 0:
        status = "empty"
    else:
        status = "verification_inconsistent"
    streak = int(previous.get("empty_streak", 0) or 0)
    if status == "published":
        streak = 0
    elif status == "empty":
        streak += 1
    # On failures, retain the prior streak but do not increment it.
    report = {
        "last_run_id": str(run_id),
        "last_checked": now,
        "status": status,
        "verification": verification,
        "verified_posts": verified_posts,
        "empty_streak": streak,
        "alert": status in ("category_failed", "verification_failed",
                            "verification_inconsistent") or streak >= 2,
        "outcomes": {c: outcomes.get(c, "missing") for c in CATEGORIES},
    }
    return report


def catalogue_health(folder: Path) -> dict:
    """Summarize catalogue backlog without exposing titles or private IDs."""
    results = {}
    for name in ("series", "anime"):
        path = folder / f"{name}_catalog.json"
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            audit = row.get("audit", {})
            results[name] = {
                "audit_date": audit.get("checked_at"),
                "history_scan_complete": bool(audit.get("source_scan_complete")),
                "observed_not_indexed": int(audit.get("not_yet_indexed_total", 0)),
                "unnumbered_videos": int(audit.get("unnumbered_videos_skipped", 0)),
                "source_gap_seasons": int(audit.get("source_numbering_gap_seasons", 0)),
                "active_batch": bool(row.get("active_batch")),
            }
        except (OSError, ValueError, TypeError, AttributeError):
            results[name] = {"status": "unavailable"}
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--verification", default="")
    parser.add_argument("--verified-posts", default="0", type=int)
    parser.add_argument("--outcomes", default="{}")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    outcomes = json.loads(args.outcomes)
    if not isinstance(outcomes, dict):
        raise ValueError("outcomes must be an object")
    previous = {}
    if args.path.exists():
        previous = json.loads(args.path.read_text(encoding="utf-8"))
    report = update_monitor(
        previous, run_id=args.run_id, verification=args.verification,
        verified_posts=args.verified_posts, outcomes=outcomes,
        now=datetime.now(timezone.utc).isoformat())
    args.path.parent.mkdir(parents=True, exist_ok=True)
    report["catalogues"] = catalogue_health(args.path.parent)
    args.path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    label = report["status"]
    print(f"CINEX_CYCLE status={label} verified={report['verified_posts']} "
          f"empty_streak={report['empty_streak']} alert={report['alert']}")
    if report["alert"]:
        print("::warning title=CinéX surveillance::Échec ou deux cycles vides consécutifs, contrôler les catégories et la confirmation Telegram.")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("\n### Surveillance CinéX (sans publication)\n")
            f.write(f"- État : {label}\n- Publications vérifiées : {report['verified_posts']}\n")
            f.write(f"- Cycles vides consécutifs : {report['empty_streak']}\n")
            f.write(f"- Alerte : {'oui' if report['alert'] else 'non'}\n")
            f.write("- Catégories : " + ", ".join(f"{c}={report['outcomes'][c]}" for c in CATEGORIES) + "\n")
            for name, row in report["catalogues"].items():
                if "observed_not_indexed" in row:
                    f.write(f"- Catalogue {name} : {row['observed_not_indexed']} occurrences sources "
                            f"non indexées, {row['unnumbered_videos']} vidéos sans numéro ; "
                            f"archive terminée={row['history_scan_complete']}\n")
    return 0  # category and verification failure already checked by workflow


if __name__ == "__main__":
    raise SystemExit(main())
