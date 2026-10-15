#!/usr/bin/env python3
"""Point-in-time historical evidence for *discovered* football fixtures.

OpenFootball's public-domain season scores are adapted into per-team form
evidence. Crucially, OpenFootball DOES NOT publish today's fixture here: the
source fixture reference is a locally derived research-only key and is never
misrepresented as a native OpenFootball event ID.

No publication, no production-model changes, no user-supplied rights override.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_match_source_router import aware_time

SOURCE = "openfootball"
MAX_AGE_DAYS = 150
HISTORY_WINDOW_DAYS = 1095
MIN_GAMES = 5
LAST_GAMES = 12
FAMILIES = ("goals", "btts", "totals")


def historical_index(raw: list[dict]) -> tuple[dict, dict]:
    """Validate source, remove duplicates, quarantine contradictory scores."""
    by_fixture: dict[tuple, dict | None] = {}
    counts = Counter()
    for row in raw:
        if not isinstance(row, dict) or row.get("source") != SOURCE or row.get("status") != "finished":
            counts["unrecognized_source_or_status"] += 1
            continue
        try:
            day = date.fromisoformat(row["match_date"])
            league = competition(str(row["league"]))
            home, away = canonical_team(row["home_team"]), canonical_team(row["away_team"])
            hg, ag = row["home_score"], row["away_score"]
            ident = row["source_id"]
        except (KeyError, TypeError, ValueError):
            counts["malformed_record"] += 1
            continue
        if (not league or not home or not away or home == away
                or type(hg) is not int or type(ag) is not int
                or not (0 <= hg <= 30 and 0 <= ag <= 30)
                or not isinstance(ident, str) or len(ident) != 64):
            counts["invalid_score_or_identity"] += 1
            continue
        key = (league, day, home, away)
        item = {"league": league, "date": day, "home": home, "away": away,
                "home_score": hg, "away_score": ag, "source_id": ident}
        if key not in by_fixture:
            by_fixture[key] = item
            continue
        saved = by_fixture[key]
        if saved is None:
            continue
        if (saved["home_score"], saved["away_score"]) != (hg, ag):
            by_fixture[key] = None
            counts["conflicting_duplicate"] += 1
        else:
            counts["duplicate_dropped"] += 1
    matches = [item for item in by_fixture.values() if item is not None]
    teams = defaultdict(list)
    for item in matches:
        teams[(item["league"], item["home"])].append(
            (item["date"], item["home_score"], item["away_score"], "home", item["source_id"]))
        teams[(item["league"], item["away"])].append(
            (item["date"], item["away_score"], item["home_score"], "away", item["source_id"]))
    for rows in teams.values():
        rows.sort(key=lambda x: (x[0], x[4]), reverse=True)
    return dict(teams), {"raw_rows": len(raw), "valid_unique_matches": len(matches),
                         "source_warnings": dict(sorted(counts.items())),
                         "independently_confirmed_scores": False}


def team_form(teams: dict, league: str, name: str, target: date, *,
              max_age_days: int = MAX_AGE_DAYS, min_games: int = MIN_GAMES,
              last_games: int = LAST_GAMES) -> dict | None:
    rows = teams.get((league, canonical_team(name)), ())
    eligible = [r for r in rows if timedelta(0) < target - r[0] <= timedelta(days=HISTORY_WINDOW_DAYS)]
    latest = eligible[0][0] if eligible else None
    if latest is None or (target - latest).days > max_age_days:
        return None
    recent = eligible[:last_games]
    if len(recent) < min_games:
        return None
    n = len(recent)
    return {
        "sample_matches": n,
        "gf": sum(r[1] for r in recent) / n,
        "ga": sum(r[2] for r in recent) / n,
        "btts": sum(r[1] > 0 and r[2] > 0 for r in recent) / n,
        "over25": sum(r[1] + r[2] >= 3 for r in recent) / n,
        "latest_result_date": latest.isoformat(),
        "oldest_result_date": recent[-1][0].isoformat(),
        "historical_ids": [r[4] for r in recent],
    }


def generate(fixtures: list[dict], raw: list[dict], *,
             as_of: datetime | None = None, min_games: int = MIN_GAMES,
             max_age_days: int = MAX_AGE_DAYS) -> tuple[list[dict], dict, dict]:
    """Return new fixture copies, provider keyed stats, research coverage report."""
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    teams, quality = historical_index(raw)
    output, stats = [], {SOURCE: {}}
    skipped = Counter()
    by_league = defaultdict(Counter)
    for fixture in fixtures:
        match = dict(fixture)
        output.append(match)
        if not isinstance(fixture.get("sources"), dict) or not fixture["sources"]:
            skipped["no_daily_sources"] += 1
            continue
        kickoff = aware_time(fixture.get("kickoff_utc"))
        if kickoff is None or kickoff <= as_of:
            skipped["not_future_prematch"] += 1
            continue
        if fixture.get("ambiguous_match") or fixture.get("scores_conflict") or fixture.get("league_conflict"):
            skipped["unsafe_identity"] += 1
            continue
        if fixture.get("status", "prematch") != "prematch":
            skipped["match_started"] += 1
            continue
        # An absent league cannot be inferred only from team names.
        names = fixture.get("league_labels") or []
        leagues = {competition(str(l)) for l in names if competition(str(l))}
        if len(leagues) != 1 or fixture.get("league_verified") is False:
            skipped["missing_or_conflicting_competition"] += 1
            continue
        league = next(iter(leagues))
        by_league[league]["fixtures"] += 1
        # Use dates PRIOR to both analysis and fixture; no same-day scores.
        # Day-based public results cannot prove exact intra-day availability.
        cutoff = min(as_of.date(), kickoff.date())
        home = team_form(teams, league, fixture.get("home_team", ""), cutoff,
                         max_age_days=max_age_days, min_games=min_games)
        away = team_form(teams, league, fixture.get("away_team", ""), cutoff,
                         max_age_days=max_age_days, min_games=min_games)
        if not home or not away:
            skipped["insufficient_or_stale_team_history"] += 1
            by_league[league]["insufficient_or_stale"] += 1
            continue
        # Locally assigned key refers to historical *evidence attached to*
        # the existing daily fixture; it is NOT an upstream fixture ID.
        fixture_key = str(fixture.get("fixture_key") or "")
        local = sha256((fixture_key + "|" + kickoff.isoformat() + "|" +
                        league + "|" + canonical_team(fixture["home_team"]) + "|" +
                        canonical_team(fixture["away_team"])).encode("utf-8")).hexdigest()[:24]
        ref_id = "hist:" + SOURCE + ":" + local
        end_day = max(date.fromisoformat(home["latest_result_date"]),
                      date.fromisoformat(away["latest_result_date"]))
        history_until = datetime.combine(end_day, time.max, tzinfo=timezone.utc)
        if history_until >= as_of or history_until >= kickoff:
            skipped["time_boundary_violation"] += 1
            continue
        f = {
            "goals": {
                "home_goals_for": home["gf"], "home_goals_against": home["ga"],
                "away_goals_for": away["gf"], "away_goals_against": away["ga"],
            },
            "btts": {"home_btts_rate": home["btts"], "away_btts_rate": away["btts"]},
            "totals": {"home_over_2_5_rate": home["over25"], "away_over_2_5_rate": away["over25"]},
        }
        src = dict(match["sources"])
        src[SOURCE] = {"id": ref_id,
                       "source_kind": "historical_evidence",
                       "original_fixture_id": None, "not_a_fixture_discovery": True}
        match["sources"] = src
        stats[SOURCE][ref_id] = {
            "provider_fixture_id": ref_id, "phase": "prematch",
            "observed_at": as_of.isoformat(), "history_until": history_until.isoformat(),
            "samples": {"home": home["sample_matches"], "away": away["sample_matches"]},
            "families": f,
            "verified_identity": True,  # exact normalized team and league match only
            "identity_method": "normalized_exact_competition_and_team",
            "license_ok": True,  # OpenFootball football.json is in the public domain
            "evidence_grade": "single_source_unconfirmed_scores",
            "historical_source": SOURCE,
            "historical_event_ids": {"home": home["historical_ids"], "away": away["historical_ids"]},
            "source_fixture_id_kind": "derived_local_not_native",
        }
        by_league[league]["enriched"] += 1
        skipped["enriched_goals_btts_totals"] += 1
    report = {
        "fixtures": len(fixtures),
        "with_public_domain_goal_features": skipped["enriched_goals_btts_totals"],
        "no_corners_or_cards_fabricated": True,
        "training_approved": False, "production_publishing_allowed": False,
        "skipped": dict(sorted(skipped.items())),
        "by_league": {k: dict(v) for k, v in sorted(by_league.items())},
        "history_quality": quality,
        "as_of_utc": as_of.isoformat(),
        "statistical_source_not_fixture_discovery": SOURCE,
    }
    return output, stats, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fixtures", required=True, help="Daily union JSON")
    p.add_argument("--history-jsonl", required=True, help="Authorized OpenFootball JSONL")
    p.add_argument("--out-fixtures", required=True)
    p.add_argument("--out-statistics", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--as-of", help="Override strictly for historical backtesting (ISO UTC)")
    p.add_argument("--min-games", type=int, default=MIN_GAMES)
    p.add_argument("--max-history-age-days", type=int, default=MAX_AGE_DAYS)
    args = p.parse_args()
    if not 5 <= args.min_games <= 30 or not 30 <= args.max_history_age_days <= 365:
        p.error("Invalid sample or history-age parameters")
    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    raw = []
    for line in Path(args.history_jsonl).read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw.append(json.loads(line))
    when = aware_time(args.as_of) if args.as_of else None
    if args.as_of and when is None:
        p.error("as-of must be offset-aware ISO timestamp")
    if not isinstance(fixtures, list):
        p.error("fixtures must be a JSON list")
    adapted, snapshots, report = generate(fixtures, raw, as_of=when,
                                          min_games=args.min_games,
                                          max_age_days=args.max_history_age_days)
    for name, payload in ((args.out_fixtures, adapted), (args.out_statistics, snapshots),
                          (args.report, report)):
        out = Path(name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "history_quality"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
