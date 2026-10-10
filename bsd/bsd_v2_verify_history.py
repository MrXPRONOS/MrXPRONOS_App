"""Recover already-sent Telegram selections from older committed BSD feeds.

The public website intentionally drops some old/rejected matches. Their sent
Telegram ledger entries must still settle against the ORIGINAL published
market. Historical matches are loaded in memory for verification only; they
are never reintroduced into the public site feed.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path


def reference(row):
    """(match id, kickoff UTC date, optional second-market key) or None."""
    raw = str(row.get("ref_id") or "")
    chat, separator, suffix = raw.rpartition(":bsd:")
    ident, variant, market = suffix.partition(":")
    date = str(row.get("ref_date") or "")
    if not separator or not chat or not ident.isdigit() or len(date) != 10:
        return None
    return ("bsd:" + ident, date, market if variant else "")


def _market_present(match, market):
    if not market:
        return True
    primary=match.get("prediction")
    if isinstance(primary,dict) and primary.get("selection_key")==market:
        return True
    return any(
        isinstance(pick, dict) and pick.get("selection_key") == market
        for pick in match.get("predictions", [])
    )


def _has_match(data, match_id, match_date, market):
    return any(
        isinstance(m, dict) and m.get("source") == "bsd"
        and str(m.get("id")) == match_id and str(m.get("date")) == match_date
        and _market_present(m, market)
        for m in data.get("matches", [])
    )


def restore_published_matches(data, rows, *, repository=None, max_versions=350):
    """Recover absent match IDs / secondary selections from Git history.

    Only the 10-day range already read by the Telegram ledger is needed,
    plus a little margin for an early prediction. The source is the original
    committed data.json, so neither the bookmaker price nor market choice is
    recalculated. Never fabricate any match that is not present in Git.
    """
    pending = defaultdict(set)
    for row in rows:
        parsed = reference(row)
        if parsed is None:
            continue
        match_id, match_date, market = parsed
        if not _has_match(data, match_id, match_date, market):
            pending[(match_id, match_date)].add(market)
    if not pending:
        return data, 0

    root = Path(repository or Path(__file__).resolve().parent.parent)
    try:
        listing = subprocess.run(
            ["git", "log", "--since=14 days ago",
             f"--max-count={max_versions}", "--format=%H", "--", "data.json"],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print("BSD_VERIFY_HISTORY_UNAVAILABLE", type(exc).__name__)
        return data, 0

    recovered = {}
    # First consult the most recent historical versions, and stop immediately
    # once all missing ledger entries have been found.
    for commit in listing.stdout.splitlines():
        if not pending:
            break
        if len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit.lower()):
            continue
        try:
            snapshot = subprocess.run(
                ["git", "show", f"{commit}:data.json"],
                cwd=root, capture_output=True, text=True, check=True, timeout=15,
            )
            historical = json.loads(snapshot.stdout)
        except (OSError, ValueError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired):
            continue
        for candidate in historical.get("matches", []):
            if not isinstance(candidate, dict) or candidate.get("source") != "bsd":
                continue
            match_id = str(candidate.get("id"))
            match_date = str(candidate.get("date"))
            key = (match_id, match_date)
            if key not in pending:
                continue
            # A second selection must be present in the historical record.
            requested = pending[key]
            if key not in recovered:
                recovered[key] = dict(candidate)
            else:
                original = recovered[key]
                picks = list(original.get("predictions") or [original.get("prediction")])
                for pick in candidate.get("predictions", []):
                    if (isinstance(pick, dict) and pick.get("selection_key")
                            and not any(isinstance(p, dict) and
                                p.get("selection_key") == pick["selection_key"] for p in picks)):
                        picks.append(pick)
                original["predictions"] = picks
            requested.difference_update({
                m for m in requested if _market_present(recovered[key], m)
            })
            if not requested:
                del pending[key]

    if not recovered:
        return data, 0
    updated = dict(data)
    existing = list(data.get("matches", []))
    existing_index = {
        (str(m.get("id")), str(m.get("date"))): i
        for i, m in enumerate(existing) if isinstance(m, dict)
    }
    for key, historical in recovered.items():
        if key in existing_index:
            current = dict(existing[existing_index[key]])
            picks = list(current.get("predictions") or [current.get("prediction")])
            for pick in historical.get("predictions", []):
                if isinstance(pick, dict) and not any(
                    isinstance(p, dict) and p.get("selection_key") == pick.get("selection_key")
                    for p in picks
                ):
                    picks.append(pick)
            current["predictions"] = picks
            existing[existing_index[key]] = current
        else:
            existing.append(historical)
    updated["matches"] = existing
    count = sum(
        1 for row in rows if (parsed := reference(row)) is not None
        and not _has_match(data, *parsed) and _has_match(updated, *parsed)
    )
    print("BSD_VERIFY_HISTORY_RECOVERED", count, "pending_unresolved", sum(map(len, pending.values())))
    return updated, count
