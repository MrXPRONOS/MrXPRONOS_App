#!/usr/bin/env python3
"""BSD private archive -> prematch team form, WITHOUT exposing private match data.

Two identity routes:
(1) Exact BSD fixture ID + BSD home/away team IDs from a private fixture list;
(2) Unique stable BSD team IDs sharing an unambiguous, explicitly named league.

This is only an OPTIONAL in-process shadow adapter. Never decrypts archives,
calls APIs, writes files, modifies BSD V2 or promotes bookmaker markets.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_match_source_router import aware_time

SOURCE = "bsd"
HISTORY_SOURCE = "bsd_history"
SETTLEMENT_HOURS = 4
RECENT = 12
MIN_MATCHES = 5
MAX_STALE_DAYS = 240


def as_positive(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        i = int(value)
        return i if i > 0 and str(i) == str(value).strip() else None
    except (ValueError, TypeError):
        return None


def team_id(event: dict, side: str) -> int | None:
    x = event.get(f"{side}_team_id")
    if x is None:
        obj = event.get(f"{side}_team")
        if isinstance(obj, dict):
            x = obj.get("id")
    return as_positive(x)


def name(event: dict, side: str) -> str:
    obj = event.get(f"{side}_team")
    if isinstance(obj, dict):
        return str(obj.get("name") or obj.get("displayName") or "")
    return str(obj or "")


def league_id(event: dict) -> int | None:
    x = event.get("league_id")
    if x is None and isinstance(event.get("league"), dict):
        x = event["league"].get("id")
    return as_positive(x)


def league_name(event: dict) -> str:
    x = event.get("league_name") or event.get("competition_name")
    if not x and isinstance(event.get("league"), dict):
        x = event["league"].get("name")
    if not x and isinstance(event.get("league"), str):
        x = event.get("league")
    return competition(str(x or ""))


def build_private_index(events: list[dict]) -> tuple[dict, dict, dict]:
    index = defaultdict(list)
    named = defaultdict(set)
    seen = set()
    health = Counter()
    for event in events:
        if not isinstance(event, dict) or event.get("id") is None:
            health["malformed"] += 1
            continue
        eid = str(event["id"])
        if eid in seen:
            health["duplicate_id"] += 1
            continue
        seen.add(eid)
        h, a = team_id(event, "home"), team_id(event, "away")
        lid = league_id(event)
        stamp = aware_time(event.get("event_date"))
        hs, aws = event.get("home_score"), event.get("away_score")
        if (not lid or not h or not a or h == a or stamp is None
                or str(event.get("status", "")).lower() != "finished"
                or type(hs) is not int or type(aws) is not int
                or not 0 <= hs <= 30 or not 0 <= aws <= 30):
            health["invalid_or_incomplete"] += 1
            continue
        settled = stamp + timedelta(hours=SETTLEMENT_HOURS)
        index[(lid, h)].append((stamp, settled, hs, aws, eid))
        index[(lid, a)].append((stamp, settled, aws, hs, eid))
        league = league_name(event)
        if league:
            for side, tid in (("home", h), ("away", a)):
                n = canonical_team(name(event, side))
                if n:
                    named[(league, n)].add((lid, tid))
        health["valid_finished"] += 1
    for rows in index.values():
        rows.sort(key=lambda m: m[0], reverse=True)
    return dict(index), dict(named), {
        "records_considered": len(events),
        "valid_finished_records": health["valid_finished"],
        "duplicate_events_skipped": health["duplicate_id"],
        "invalid_or_incomplete": health["invalid_or_incomplete"],
    }


def recent_team(index: dict, lid: int, tid: int, as_of: datetime,
                kickoff: datetime) -> dict | None:
    cutoff = min(kickoff, as_of)
    eligible = [x for x in index.get((lid, tid), ())
                if x[1] < cutoff and x[0] < kickoff]
    eligible = eligible[:RECENT]
    if len(eligible) < MIN_MATCHES:
        return None
    if (cutoff - eligible[0][0]).days > MAX_STALE_DAYS:
        return None
    n = len(eligible)
    return {
        "gf": sum(r[2] for r in eligible)/n,
        "ga": sum(r[3] for r in eligible)/n,
        "btts": sum(r[2] > 0 and r[3] > 0 for r in eligible)/n,
        "over25": sum(r[2] + r[3] >= 3 for r in eligible)/n,
        "count": n,
        "max_history_timestamp": max(r[1] for r in eligible),
    }


def attach(fixtures: list[dict], history: list[dict],
           bsd_fixtures: list[dict] | None = None, *,
           as_of: datetime | None = None,
           explicitly_authorized: bool = False) -> tuple[list[dict], dict, dict]:
    """No outputs contain plaintext BSD history. Caller must treat stats as private."""
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    output = [dict(m) for m in fixtures]
    stats = {SOURCE: {}, HISTORY_SOURCE: {}}
    counts = Counter()
    if not explicitly_authorized:
        return output, stats, {
            "status": "permission_required",
            "attached_fixtures": 0, "historic_match_count": None,
            "production_modified": False, "secret_archive_exposed": False,
        }
    index, named, archive_health = build_private_index(history)
    current_by_id = {
        str(e["id"]): e for e in (bsd_fixtures or [])
        if isinstance(e, dict) and e.get("id") is not None
    }
    for row in output:
        kickoff = aware_time(row.get("kickoff_utc"))
        if kickoff is None or kickoff <= as_of or row.get("status", "prematch") != "prematch":
            counts["not_future_prematch"] += 1
            continue
        if row.get("ambiguous_match") or row.get("scores_conflict") or row.get("league_conflict"):
            counts["unsafe_identity"] += 1
            continue
        refs = row.get("sources") or {}
        if not refs:
            counts["missing_original_fixture"] += 1
            continue
        direct = refs.get(SOURCE) if isinstance(refs, dict) else None
        current = current_by_id.get(str((direct or {}).get("id") or "")) if direct else None
        lid, hid, aid = None, None, None
        source_key = HISTORY_SOURCE
        if current is not None:
            # Native fixture ID is authoritative only if names and kickoff
            # corroborate the same fixture. No uncertain cross-source remaps.
            native_time = aware_time(current.get("event_date"))
            if native_time is None or abs((native_time-kickoff).total_seconds()) > 90*60:
                counts["bsd_fixture_time_mismatch"] += 1
                continue
            if (canonical_team(name(current, "home")) != canonical_team(str(row.get("home_team") or ""))
                    or canonical_team(name(current, "away")) != canonical_team(str(row.get("away_team") or ""))):
                counts["bsd_fixture_team_mismatch"] += 1
                continue
            lid, hid, aid = league_id(current), team_id(current, "home"), team_id(current, "away")
            source_key = SOURCE
        elif direct:
            # A claimed BSD fixture ID without a verified private fixture
            # must not be used as proof of identity.
            counts["unverified_bsd_fixture_id"] += 1
            continue
        else:
            labels = {competition(str(x)) for x in row.get("league_labels", []) if competition(str(x))}
            if len(labels) != 1 or row.get("league_verified") is False:
                counts["missing_league_verification"] += 1
                continue
            league = next(iter(labels))
            homes = named.get((league, canonical_team(str(row.get("home_team") or ""))), set())
            aways = named.get((league, canonical_team(str(row.get("away_team") or ""))), set())
            if len(homes) != 1 or len(aways) != 1:
                counts["unresolved_team_identity"] += 1
                continue
            lid, hid = next(iter(homes))
            away_league, aid = next(iter(aways))
            if lid != away_league:
                counts["league_id_conflict"] += 1
                continue
        if not lid or not hid or not aid or hid == aid:
            counts["missing_stable_ids"] += 1
            continue
        home, away = recent_team(index, lid, hid, as_of, kickoff), recent_team(index, lid, aid, as_of, kickoff)
        if not home or not away:
            counts["insufficient_or_stale_bsd_history"] += 1
            continue
        if source_key == SOURCE:
            ref_id = str(direct["id"])
        else:
            canonical = "|".join([str(row.get("fixture_key") or ""), str(lid), str(hid), str(aid), kickoff.isoformat()])
            ref_id = "hist:bsd:" + sha256(canonical.encode("utf-8")).hexdigest()[:24]
            clone = dict(refs)
            clone[HISTORY_SOURCE] = {"id": ref_id, "source_kind": "private_historical_evidence",
                                     "original_fixture_id": None, "not_a_fixture_discovery": True}
            row["sources"] = clone
        cutoff = max(home["max_history_timestamp"], away["max_history_timestamp"])
        stats[source_key][ref_id] = {
            "provider_fixture_id": ref_id,
            "phase": "prematch", "observed_at": as_of.isoformat(),
            "history_until": cutoff.isoformat(),
            "samples": {"home": home["count"], "away": away["count"]},
            "families": {
                "goals": {"home_goals_for": home["gf"], "home_goals_against": home["ga"],
                          "away_goals_for": away["gf"], "away_goals_against": away["ga"]},
                "btts": {"home_btts_rate": home["btts"], "away_btts_rate": away["btts"]},
                "totals": {"home_over_2_5_rate": home["over25"], "away_over_2_5_rate": away["over25"]},
            },
            "verified_identity": True, "license_ok": True,
            "identity_method": "native_bsd_ids" if source_key == SOURCE else "unique_name_league_to_bsd_ids",
            "historical_source": SOURCE, "private_history": True,
            "source_fixture_id_kind": "native" if source_key == SOURCE else "derived_local_not_native",
            "model_trained_and_calibrated": False,
        }
        counts["attached"] += 1
        counts[source_key+"_attached"] += 1
    return output, stats, {
        "status": "private_shadow_only",
        "attached_fixtures": counts["attached"],
        "native_fixture_count": counts["bsd_attached"],
        "cross_provider_history_count": counts["bsd_history_attached"],
        "rejection_summary": dict(sorted(counts.items())),
        "historic_match_count": archive_health["valid_finished_records"],
        "production_modified": False, "secret_archive_exposed": False,
        "plaintext_archive_uploaded": False,
    }
