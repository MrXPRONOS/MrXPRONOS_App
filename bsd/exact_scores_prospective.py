"""Mr XPRONOS: immutable prospective exact-score shadow ledger.

Snapshot every eligible PREMATCH fixture before kickoff; reconcile finished
results without touching or recalculating the original prediction.
The ledger is Fernet encrypted, never pushed as plaintext to the public repo.
No Telegram, predictions on the website, wagers or alerts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, cipher
from bsd_h2h import _team_id
from bsd_v2_core import V2History, estimate_goals, fixture_datetime, outcome_scores
from exact_scores import matrix_for, top_scores
from exact_scores_h2h import H2HIndex, h2h_signal
from exact_scores_under25 import Under25Model, reweight_scores

LEDGER = Path("bsd/exact_score_shadow_ledger.enc.json")
FORMAT = "mrx-exact-score-prospective-ledger-v1"
# Frozen from 2024/2025 tuning and historical 2026 validation.
MODEL = {
    "version": "mrx-exact-score-shadow-frozen-2026-10-20-v1",
    "rho": 0.0, "scale_home": 1.1, "scale_away": 1.0,
    "under_blend": 1.0, "under_variance_scale": 0.85,
    "under_threshold": 0.62,
    "h2h_rule": "legacy_low_stable_h2h_v1",
}
FORECAST_SETTLEMENT_FIELDS = frozenset(("status","forecast_sha256","settled_utc",
                                        "actual_score","under25_hit","top1_hit","top3_hit"))
MIN_LEAD_MINUTES = 30
SETTLEMENT_DELAY_HOURS = 4


def empty_ledger():
    return {"format": FORMAT, "model": dict(MODEL), "predictions": {}}


def read_ledger(path=LEDGER, encryption=None):
    if not path.exists():
        return empty_ledger()
    key = encryption or cipher()
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("format") != FORMAT or not isinstance(envelope.get("encrypted"), str):
        raise ValueError("Invalid encrypted prospective ledger")
    value = json.loads(key.decrypt(envelope["encrypted"].encode("ascii")))
    if (value.get("format") != FORMAT or value.get("model") != MODEL
            or not isinstance(value.get("predictions"), dict)):
        raise ValueError("Ledger schema/model mismatch: do not overwrite previous forecasts")
    # An already-recorded forecast may be settled, but its original inputs,
    # probabilities and timestamp must never be rewritten.
    for row in value["predictions"].values():
        evidence = json.dumps({k:v for k,v in row.items()
                               if k not in FORECAST_SETTLEMENT_FIELDS},
                              sort_keys=True,separators=(",",":"))
        digest = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        if row.get("forecast_sha256") != digest:
            raise ValueError("Immutable prediction was modified")
    return value


def write_ledger(ledger, path=LEDGER, encryption=None):
    if ledger.get("format") != FORMAT or ledger.get("model") != MODEL:
        raise ValueError("Refusing to write mismatched prospective model")
    key = encryption or cipher()
    data = json.dumps(ledger, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    envelope = {"format": FORMAT, "encrypted": key.encrypt(data.encode("utf-8")).decode("ascii")}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(envelope), encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def fixture_key(fixture):
    return str(fixture["id"]) + "|" + fixture_datetime(fixture).isoformat()


def make_snapshot(fixture, index, hindex, now):
    kickoff = fixture_datetime(fixture)
    if kickoff <= now + timedelta(minutes=MIN_LEAD_MINUTES):
        return None, "too_close_or_started"
    if str(fixture.get("status", "")).lower() in ("finished", "canceled", "cancelled",
                                                  "postponed", "abandoned"):
        return None, "not_upcoming"
    goals, reason = estimate_goals(fixture, index)
    if goals is None:
        return None, reason
    matrix = matrix_for(goals["home"], goals["away"],
                        rho=MODEL["rho"], scale_home=MODEL["scale_home"],
                        scale_away=MODEL["scale_away"])
    under = Under25Model(MODEL["under_blend"], MODEL["under_variance_scale"],
                         MODEL["under_threshold"]).predict(fixture, index, matrix)
    signal = h2h_signal(hindex.past_scores(fixture))
    final_matrix = reweight_scores(matrix, under["probability"])
    top3 = top_scores(final_matrix)
    selected = bool(signal["prioritized"] and under["priority"])
    record = {
        "match_id": str(fixture["id"]),
        "kickoff_utc": kickoff.isoformat(),
        "captured_utc": now.isoformat(),
        "model": MODEL["version"],
        "home_id": _team_id(fixture, "home"), "away_id": _team_id(fixture, "away"),
        "expected_goals": {"home": goals["home"], "away": goals["away"]},
        "h2h": {"meetings": signal["meetings"],
                "priority": bool(signal["prioritized"])},
        "under25": {"probability": round(under["probability"], 7),
                    "priority": bool(under["priority"])},
        "selected": selected,
        "top3": [{"score": [h, a], "probability": round(p, 7)}
                 for (h, a), p in top3],
        "status": "pending",
    }
    evidence = json.dumps({k: v for k, v in record.items() if k not in FORECAST_SETTLEMENT_FIELDS},
                          sort_keys=True, separators=(",", ":"))
    record["forecast_sha256"] = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    return record, "ok"


def record_fixtures(ledger, events, index, now, *, max_new=600):
    hindex = H2HIndex(index)
    added = 0
    skipped = Counter()
    seen = ledger["predictions"]
    for fixture in sorted(events, key=lambda e: (fixture_datetime(e), str(e["id"]))):
        if fixture_key(fixture) in seen:
            skipped["already_recorded"] += 1
            continue
        if added >= max_new:
            skipped["capture_limit_reached"] += 1
            continue
        result, why = make_snapshot(fixture, index, hindex, now)
        if result is None:
            skipped[why] += 1
            continue
        seen[fixture_key(fixture)] = result
        added += 1
    return {"added": added, "skipped": dict(skipped)}


def reconcile_results(ledger, events, now):
    known = {}
    for e in events:
        try:
            key = fixture_key(e)
        except (KeyError, TypeError, ValueError):
            continue
        known[key] = e
    counts = Counter()
    for key, row in ledger["predictions"].items():
        if row["status"] != "pending":
            continue
        kickoff = datetime.fromisoformat(row["kickoff_utc"])
        if now < kickoff + timedelta(hours=SETTLEMENT_DELAY_HOURS):
            continue
        candidate = known.get(key)
        if candidate is None:
            continue  # missing API result; never assume a loss or invent a result
        score = outcome_scores(candidate)
        if score is None:
            continue
        if (_team_id(candidate, "home") != row["home_id"]
                or _team_id(candidate, "away") != row["away_id"]):
            counts["identity_mismatch"] += 1
            continue
        top = [tuple(x["score"]) for x in row["top3"]]
        row["status"] = "settled"
        row["settled_utc"] = now.isoformat()
        row["actual_score"] = list(score)
        row["under25_hit"] = int(sum(score) <= 2)
        row["top1_hit"] = int(score == top[0])
        row["top3_hit"] = int(score in top)
        counts["settled"] += 1
    return dict(counts)


def report(ledger, now):
    forecasts = list(ledger["predictions"].values())
    settled = [r for r in forecasts if r["status"] == "settled"]
    def metrics(rows):
        n = len(rows)
        if not n:
            return {"n": 0, "top1_rate": None, "top3_rate": None,
                    "under25_rate": None, "under25_brier": None}
        return {"n": n,
                "top1_hits": sum(r["top1_hit"] for r in rows),
                "top3_hits": sum(r["top3_hit"] for r in rows),
                "under25_hits": sum(r["under25_hit"] for r in rows),
                "top1_rate": round(sum(r["top1_hit"] for r in rows) / n, 5),
                "top3_rate": round(sum(r["top3_hit"] for r in rows) / n, 5),
                "under25_rate": round(sum(r["under25_hit"] for r in rows) / n, 5),
                "under25_brier": round(
                    sum((r["under25"]["probability"] - r["under25_hit"])**2
                        for r in rows) / n, 6)}
    as_of = now - timedelta(days=4)
    overdue = sum(
        r["status"] == "pending" and datetime.fromisoformat(r["kickoff_utc"]) < as_of
        for r in forecasts
    )
    return {"format": "mrx-exact-score-prospective-report-v1",
            "created_utc": now.isoformat(), "model": MODEL["version"],
            "experimental": True, "published": False,
            "total_captured": len(forecasts),
            "pending": sum(r["status"] == "pending" for r in forecasts),
            "overdue_unsettled": overdue,
            "priority_captured": sum(bool(r["selected"]) for r in forecasts),
            "priority_pending": sum(
                r["selected"] and r["status"] == "pending" for r in forecasts),
            "all": metrics(settled),
            "priority": metrics([r for r in settled if r["selected"]]),
            "warning": "Prospective only; no guaranteed outcome or profit. Small samples are unstable."}


def fetch_fixture_window(client, now):
    # Same API for new fixtures and settlement, fetched once per UTC day.
    # Four prior days recover late updates and missing results.
    out = []
    seen = set()
    for offset in range(-4, 3):
        d = (now + timedelta(days=offset)).date()
        page = client.list_events(d, d, max_pages=8, ttl=0)
        if not page.complete:
            raise RuntimeError("Incomplete BSD calendar " + d.isoformat())
        for fixture in page.events:
            key = fixture_key(fixture)
            if key not in seen:
                seen.add(key)
                out.append(fixture)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--report", default="tmp/exact-scores/prospective-report.json")
    ap.add_argument("--max-requests", type=int, default=90)
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    ledger_path = Path(args.ledger)
    # Fail closed if credentials or history are not available.
    original = read_ledger(ledger_path)
    history = json.loads(MATCHES_FILE.read_text(encoding="utf-8"))
    if not history:
        ap.error("Private BSD history missing or empty")
    client = BSDClient(max_requests=args.max_requests)
    fixtures = fetch_fixture_window(client, now)
    index = V2History(history)
    capture = record_fixtures(original, fixtures, index, now)
    # An archive refresh may supply a delayed result after its live API
    # fixture leaves the four-day query window. API fixtures take precedence.
    pending_ids = {row["match_id"] for row in original["predictions"].values()
                   if row["status"] == "pending"}
    completed = [e for _at, e in index.global_games
                 if str(e["id"]) in pending_ids]
    settlement = reconcile_results(original, completed + fixtures, now)
    # Re-encrypt ONLY when first-seen records or settlements changed.
    # Prevent needless diffs: Fernet ciphertext is randomized every write.
    if capture['added'] or settlement.get('settled'):
        write_ledger(original, ledger_path)
    data = report(original, now)
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("EXACT_PROSPECTIVE_AUDIT",
          json.dumps({"capture": capture, "settlement": settlement,
                      "report": data, "api_requests": client.requests_made},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
