#!/usr/bin/env python3
"""Authenticated 2024-2026 multisource archive bridge for the existing ML V2.

Only temporary plaintext in /tmp. Source archives are never modified. No new
provider request or production dependency.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from single_ml_v2_git import key_from_environment
from single_ml_v2_2024_union import combine
from single_ml_v2 import load_matches

COUNTS = {2024: 91331, 2025: 87451, 2026: 76934}
CUTOFF = date(2026, 10, 24)


def certified_rows(key, *, root=None, audit_root=Path("research"), through=CUTOFF):
    """Authenticate each year's ciphertext and compare with its published audit."""
    if through != CUTOFF:
        raise ValueError("Frozen 2026 historical cohort must end on 2026-10-24")
    audit_root = Path(audit_root)
    all_rows = []
    previous_last = None
    for year, expected in COUNTS.items():
        options = {"year": year, "through": through if year == 2026 else None}
        if root is not None:
            options["root"] = root
        rows, report = combine(key, **options)
        stored = json.loads((audit_root / f"{year}_multisource_audit.json").read_text(encoding="utf8"))
        if any(k not in report or report[k] != v for k, v in stored.items()):
            # Published audit schemas differ by year; require EVERY stored assertion,
            # while permitting newer diagnostic-only fields in calculated reports.
            differences = sorted(k for k, v in stored.items() if report.get(k) != v)
            raise ValueError(f"{year} encrypted audit disagreement: {differences}")
        if len(rows) != expected or report["distinct_safe_matches"] != expected:
            raise ValueError(f"{year} incorrect source reconciliation total")
        if report["sportscore_failed_days_remaining"] or report["remaining_provider_failed_dates"]:
            raise ValueError(f"{year} has unresolved failed source dates")
        if year == 2026 and (report["bsd_reconciled_source_id_observations"] != 15
                             or report["conflicting_outcome_identities_quarantined"] != 9):
            raise ValueError("2026 BSD quarantine/reconciliation evidence missing")
        if any(row.get("sportId") != 1 or row.get("is_finished") is not True for row in rows):
            raise ValueError(f"{year} uncertified or unfinished match")
        if any(row.get("date", "")[:4] != str(year) for row in rows):
            raise ValueError(f"{year} row falls outside frozen source year")
        if previous_last is not None and rows[0]["date"] <= previous_last:
            raise ValueError("Overlapping annual cohorts")
        previous_last = rows[-1]["date"]
        all_rows.extend(rows)
    if len(all_rows) != sum(COUNTS.values()):
        raise ValueError("Unexpected cumulative training cohort size")
    if len({row["id"] for row in all_rows}) != len(all_rows):
        raise ValueError("Repeated source fixture ID across annual cohorts")
    return all_rows


def check_ml_loader(rows, *, loader=load_matches):
    """Use the ACTUAL ML V2 loader, not a reimplemented schema validator."""
    fd, name = tempfile.mkstemp(prefix="mlv2-source-", suffix=".json", dir="/tmp")
    os.close(fd)
    path = Path(name)
    try:
        path.chmod(0o600)
        with path.open("w", encoding="utf8") as output:
            json.dump(rows, output, ensure_ascii=False)
        matches = loader(str(path), CUTOFF)
        if len(matches) != len(rows):
            raise ValueError(f"ML V2 loader rejected {len(rows) - len(matches)} audited rows")
        if any(m.day > CUTOFF for m in matches):
            raise ValueError("ML V2 received post-cutoff match")
        return matches
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--start", default="2026-10-01")
    parser.add_argument("--end", default="2026-10-24")
    parser.add_argument("--out", default="/tmp/ml-v2-multisource-backtest")
    parser.add_argument("--max-eval", type=int, default=60)
    args = parser.parse_args()
    key = key_from_environment()
    rows = certified_rows(key)
    matches = check_ml_loader(rows)
    print("MULTISOURCE_ML_V2_COMPATIBILITY", json.dumps({
        "archive_rows": len(rows), "ml_accepted_rows": len(matches),
        "year_counts": COUNTS, "cutoff": str(CUTOFF),
        "plaintext_committed": False}, sort_keys=True), flush=True)
    if args.validate_only:
        return
    from single_ml_v2 import backtest
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if not (date(2024, 1, 1) < start <= end <= CUTOFF):
        raise ValueError("Invalid retrospective backtest interval")
    # Explicitly bounded research smoke run; long training must be planned separately.
    backtest(matches, start, end, args.out, max_eval=args.max_eval,
             retrain_days=30, auto_tune=False)


if __name__ == "__main__":
    main()
