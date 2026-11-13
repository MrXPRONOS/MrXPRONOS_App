#!/usr/bin/env python3
"""Run the genuine Hybrid V3 on current SportData fixtures, publishing daily Top5.

Reads the authenticated 2024–Oct 24 2026 frozen research corpus, then extends
finished matches from independent SportData day snapshots. Daily incremental
snapshots are AES-GCM encrypted before they may be stored by Actions; never
commit plaintext history, future raw matrices, credentials or logs.

On failures this script FAILS CLOSED. It does not forge today's picks or
fallback to historical scored predictions/old production Pro/VIP data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import replace

BASE_CUTOFF = date(2026, 10, 24)
DAILY_HISTORY_SUBDIR = Path("research/score_v3_encrypted_daily")
MODEL_REF = "research/single-ml-v2-20261024"
MAX_DAYS_BACKFILL_PER_RUN = 60
MIN_CERTIFIED_MATCHES_PER_DAY = 1

def sportdata_source_identity(value):
    """Match the research model's strict, provider-scoped ID vocabulary.

    The audited archive's safe_source_identities() uses this same prefix for
    sportsapipro_v1_allscores. An invalid/missing provider identifier falls back
    to local-league identity instead of an unsafe cross-club join.
    """
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if (not raw or raw.casefold() in {"none", "null", "unknown", "0"}
            or not re.fullmatch(r"[A-Za-z0-9_-]+", raw)):
        return None
    return "src_sportsapipro_v1_allscores_" + raw

REPLAY_WARMUP_DAYS = 65


def quarantine_conflicting_provider_identities(matches, *, normalizer):
    """Use global provider IDs only when they identify exactly ONE club/league.

    The frozen 2024-Oct-24 cohort already strips unsafe IDs internally.
    Later certified daily SportData rows can reuse previously-safe IDs for
    different clubs. Validate the *combined* chronological cohort before
    the native V3 opponent-state training starts.

    Each ambiguous ID is removed from the ephemeral dataclass copies only.
    All matches, scores, dates, feature code and sealed archives remain intact.
    With no verified global ID the native model uses its competition-local
    team key, so unrelated clubs can never share a rating history.
    """
    matches = list(matches)
    names_by_id = defaultdict(set)
    leagues_by_id = defaultdict(set)
    for match in matches:
        for side in ("home", "away"):
            value = getattr(match, side + "_id", None)
            if value is not None:
                names_by_id[str(value)].add(
                    normalizer(getattr(match, side)))
        competition_id = getattr(match, "competition_id", None)
        if competition_id is not None:
            leagues_by_id[str(competition_id)].add(normalizer(match.league))
    bad_clubs = {key for key, names in names_by_id.items() if len(names) > 1}
    bad_leagues = {key for key, names in leagues_by_id.items() if len(names) > 1}
    sanitized = []
    affected = 0
    club_fields = 0
    league_fields = 0
    for match in matches:
        changes = {}
        for side in ("home", "away"):
            name = side + "_id"
            identifier = getattr(match, name, None)
            if identifier is not None and str(identifier) in bad_clubs:
                changes[name] = None
                club_fields += 1
        competition_id = getattr(match, "competition_id", None)
        if competition_id is not None and str(competition_id) in bad_leagues:
            changes["competition_id"] = None
            league_fields += 1
        if changes:
            affected += 1
            sanitized.append(replace(match, **changes))
        else:
            sanitized.append(match)
    audit = {
        "total_matches": len(matches),
        "ambiguous_club_ids": len(bad_clubs),
        "ambiguous_competition_ids": len(bad_leagues),
        "matches_using_local_fallback": affected,
        "club_id_occurrences_quarantined": club_fields,
        "competition_id_occurrences_quarantined": league_fields,
        "match_records_removed": 0,
        "source_archives_changed": False,
        "raw_provider_ids_logged": False,
    }
    print("V3_CROSS_COHORT_IDENTITY_SAFETY", json.dumps(audit, sort_keys=True), flush=True)
    return sanitized, audit


def install_research_modules(model_root: Path):
    root = model_root.resolve()
    if not (root / "research/single_ml_v2.py").is_file() or not (root / "research/encrypted_football").is_dir():
        raise RuntimeError("Missing the authentic Hybrid V3 research checkout or encrypted corpus")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "research"))
    return root


def provenance_today():
    now = datetime.now(timezone.utc)
    if now <= datetime(2026, 10, 25, tzinfo=timezone.utc):
        raise RuntimeError("Prospective daily engine cannot replay from incomplete 2026 history")
    return now, now.date() - timedelta(days=1)


def historical_daily_rows(history_dir, last_day, *, fetcher, normalizer, sealer, opener, key, verbose=True):
    """Return certified completed matches after the frozen Oct-24 archive.

    Read encrypted snapshots already tracked by GitHub (AES-GCM authenticated);
    otherwise retrieve each day from SportData and stage a new sealed checkpoint.
    Require continuous completed-day coverage; no missing dates and no results
    from the UTC day being published.
    """
    assert last_day >= BASE_CUTOFF
    days=(last_day-BASE_CUTOFF).days
    if days > MAX_DAYS_BACKFILL_PER_RUN + len(list(history_dir.glob("*.enc"))):
        raise RuntimeError("Historical catchup too large for safely bounded provider requests")
    history_dir.mkdir(parents=True,exist_ok=True)
    all_rows=[]
    daily_counts=[]
    seen=set()
    for delta in range(1,days+1):
        day=BASE_CUTOFF+timedelta(days=delta)
        target=history_dir/(day.isoformat()+".enc")
        label="mrx-v3-prospective-certified-day:"+str(day)
        if target.exists():
            doc=opener(target.read_bytes(),key,label)
            origin="encrypted_cache"
        else:
            response=fetcher(day,day,timeout=45,show_odds=False)
            if not response.ok:
                raise RuntimeError(f"Cannot verify completed football fixtures for {day}: {str(response.reason)[:90]}")
            doc=normalizer(day,response)
            origin="verified_sportdata_api"
            if not doc.get("verified") or doc.get("day")!=str(day):
                raise RuntimeError("Unverified provider day snapshot")
            if doc.get("certified_football_count",0)<MIN_CERTIFIED_MATCHES_PER_DAY:
                raise RuntimeError(f"Missing completed certified fixtures for {day}; refusing to train")
            # Commit only an authenticated encrypted checkpoint. Never the
            # provider JSON, raw goals or the 11x11 proprietary model matrices.
            blob=sealer(doc,key,label)
            stage=target.with_suffix(".tmp")
            stage.write_bytes(blob)
            stage.replace(target)
        if doc.get("day")!=str(day) or doc.get("verified") is not True:
            raise RuntimeError("Wrong day in authenticated historical checkpoint")
        rows=doc.get("matches")
        if not isinstance(rows,list) or len(rows)!=doc.get("certified_football_count") or not rows:
            raise RuntimeError("Incomplete or empty historical football snapshot")
        for raw in rows:
            if (not isinstance(raw,dict) or raw.get("sportId")!=1 or raw.get("is_finished") is not True
                    or raw.get("start_time","")[:10]!=str(day) or "home_score" not in raw or "away_score" not in raw):
                raise RuntimeError("Uncertified football match in historical snapshot")
            record=dict(raw)
            orig_id=str(record.get("id") or "")
            if not orig_id:
                raise RuntimeError("Missing historical fixture ID")
            # Latest SportData IDs are intentionally namespaced from audited
            # BSD / other 2024-26 fixture IDs; no cross-provider ID collision.
            key_id="sportsapipro-daily:"+orig_id
            if key_id in seen:
                raise RuntimeError("Repeated football fixture across completed days")
            seen.add(key_id)
            record["id"]=key_id
            record["source_home_team_id"] = sportdata_source_identity(record.get("source_home_team_id"))
            record["source_away_team_id"] = sportdata_source_identity(record.get("source_away_team_id"))
            record["source_competition_id"] = sportdata_source_identity(record.get("source_competition_id"))
            all_rows.append(record)
        daily_counts.append({"date":str(day),"rows":len(rows),"source":origin})
        if verbose:
            print("V3_DAILY_CERTIFIED_DAY",str(day),"matches",len(rows),"source",origin,flush=True)
    return all_rows,daily_counts


def future_fixtures(response,now,*,converter,include_tomorrow=False):
    """Retain only real supplier-declared UTC futures; never accept final scores."""
    if not response.ok:
        raise RuntimeError("Today's SportData fixture source is unavailable")
    fixtures=[]
    seen=set()
    excluded={}
    for raw in response.games:
        if not isinstance(raw,dict) or str(raw.get("sportId"))!="1":
            continue
        kickoff=converter(raw.get("startTime"))
        if kickoff is None or kickoff.tzinfo is None:
            continue
        if kickoff.date() not in ({now.date(), now.date()+timedelta(days=1)} if include_tomorrow else {now.date()}) or kickoff<=now+timedelta(minutes=10):
            continue
        if str(raw.get("statusGroup"))=="4":
            continue
        # Explicit start-time, exact provider team/league identities; no
        # guesses when a name / competition / source identifier is missing.
        h=raw.get("homeCompetitor")
        a=raw.get("awayCompetitor")
        league=raw.get("competitionDisplayName")
        ident=raw.get("id")
        if not isinstance(h,dict) or not isinstance(a,dict):
            continue
        home=h.get("name");away=a.get("name")
        if not all(isinstance(x,str) and x.strip() for x in (home,away,league)):
            continue
        if not ident or str(ident) in seen or home.strip()==away.strip():
            continue
        seen.add(str(ident))
        fixture={
          "id":"sportsapipro:"+str(ident),
          "league":league.strip(),"home":home.strip(),"away":away.strip(),
          "kickoff_utc":kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        fixtures.append(fixture)
    return fixtures


def save_verified_day(site_root, payload):
    """Persist only provider-derived day snapshots for yesterday/today/tomorrow UI.

    Never replace an already published day with an unavailable late-day rerun.
    The same date's latest successful, prematch-generated Top5 remains visible
    as an archive after kickoff, never as an available betting opportunity.
    """
    day = date.fromisoformat(payload["date"])
    archive = site_root / "scores-exacts-daily" / (day.isoformat()+".json")
    if archive.exists() and payload["status"] == "unavailable":
        previous = json.loads(archive.read_text(encoding="utf8"))
        if (previous.get("status") == "published" and previous.get("date") == day.isoformat()
                and previous.get("model") == "machine_learning_v3_hybrid"):
            return previous
    atomic_json(archive, payload)
    return payload


def atomic_json(path,payload):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    tmp.replace(path)


def resolve_public_target(site_root, out_path):
    """Freeze output path before changing cwd to the independent research checkout."""
    root = Path(site_root).resolve()
    return Path(out_path).resolve() if out_path else root / "scores-exacts.json"


def produce(site_root,model_root,*,out_path=None,now=None):
    site_root=Path(site_root).resolve()
    # Resolve the output against the caller CWD BEFORE switching into the model checkout.
    # Previously --out site/scores-exacts.json resolved under model/site and never reached main.
    resolved_target=resolve_public_target(site_root, out_path)
    model_root=install_research_modules(Path(model_root))
    previous=Path.cwd()
    try:
        # Research imports require their sealed cohort audit files at
        # 'research/{year}_multisource_audit.json', never the site root.
        os.chdir(model_root)
        from sportdata_api import fetch_games,get_api_keys
        from single_ml_v2_git import key_from_environment,seal,open_sealed
        from single_ml_v2_multisource import certified_rows,check_ml_loader
        from single_ml_v2_data import day_snapshot,utc_dt
        from single_ml_v2 import load_matches,backtest
        from single_ml_v2_opponents import canonical_name
        site_scripts=site_root/"scripts"
        sys.path.insert(0,str(site_scripts))
        from publish_exact_scores import build_feed
        if not get_api_keys():
            raise RuntimeError("No SportData API key configured; cannot publish real fixtures")
        key=key_from_environment()
        now=now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset().total_seconds()!=0:
            raise ValueError("Run timestamp must be explicit UTC")
        yesterday=now.date()-timedelta(days=1)
        if yesterday<BASE_CUTOFF:
            raise ValueError("Cannot run before frozen certified history cutoff")

        target=resolved_target
        daily_dir=site_root/DAILY_HISTORY_SUBDIR
        # First fetch today's true supplier fixtures. If the source is down,
        # do not overwrite with a deceptively successful or empty publication.
        future_result=fetch_games(now.date(),now.date()+timedelta(days=1),timeout=45,show_odds=False)
        if not future_result.ok:
            raise RuntimeError("Today's fixture provider failed — no publication")
        fixtures=future_fixtures(future_result,now,converter=utc_dt,include_tomorrow=True)
        print("V3_DAILY_FUTURE_FIXTURES",len(fixtures),"from",len(future_result.games),"provider observations",flush=True)
        if not fixtures:
            # No future games genuinely found, do not spend model training
            # minutes; an explicit unavailable feed is safe and honest.
            empty={
                "schema_version":"mrx-exact-top5-v1",
                "model":"machine_learning_v3_hybrid",
                "status":"unavailable","date":now.date().isoformat(),
                "generated_at":now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "simple":[],"grouped":[],
                "reason":"No verified upcoming football fixtures from SportData as of publication",
            }
            today = save_verified_day(site_root,empty)
            tomorrow_empty = dict(empty, date=(now.date()+timedelta(days=1)).isoformat())
            save_verified_day(site_root,tomorrow_empty)
            atomic_json(target,today)
            print("V3_DAILY_NO_UPCOMING_GAMES",flush=True)
            return today

        # Authentication failure for the old corpus or ANY day since its
        # cutoff blocks a future forecast. Strictly prior-day, no result leak.
        historical=certified_rows(key)
        training_matches=check_ml_loader(historical)
        fresh,daily_counts=historical_daily_rows(
            daily_dir,yesterday,fetcher=fetch_games,normalizer=day_snapshot,
            sealer=seal,opener=open_sealed,key=key)
        if fresh:
            with tempfile.TemporaryDirectory(prefix="mrx-v3-day-") as tmp:
                path=Path(tmp)/"certified_latest.json"
                path.write_text(json.dumps(fresh,ensure_ascii=False),encoding="utf8")
                extra=load_matches(str(path),yesterday)
            if len(extra)!=len(fresh):
                raise RuntimeError("New verified football rows were unexpectedly rejected by native V3 loader")
            if any(x.day>yesterday for x in extra):
                raise RuntimeError("Future result in V3 training")
            all_matches=sorted([*training_matches,*extra],key=lambda r:(r.day,r.key))
        else:
            all_matches=training_matches
        if not all_matches or all_matches[-1].day!=yesterday:
            raise RuntimeError("Latest historical football day not fully covered")
        # Cross-cohort IDs must be vetted AFTER joining the frozen audited
        # archive to the later authenticated daily snapshots.
        all_matches, _identity_audit = quarantine_conflicting_provider_identities(
            all_matches, normalizer=canonical_name)

        # The source-trained V3's own historical backtest replays all form
        # history. Last 65 days are true OOS chronological V3 forecasts, for
        # past-only 1:1 and DC blend weight calibration.
        eval_begin=max(date(2026,10,1),yesterday-timedelta(days=REPLAY_WARMUP_DAYS))
        with tempfile.TemporaryDirectory(prefix="mrx-v3-prospective-") as tmp:
            out=Path(tmp)/"model_report"
            # Existing research implementation performs training + prediction
            # in one deterministic loop and never adds today's fixture scores.
            backtest(all_matches,eval_begin,yesterday,str(out),
                     max_eval=0,auto_tune=False,retrain_days=30,
                     v3_models=True,prospective_fixtures=fixtures)
            raw=out/"v3_prospective_raw.json"
            if not raw.exists():
                raise RuntimeError("Actual Hybrid V3 did not emit a prospectively scored 11x11 grid")
            prospective=json.loads(raw.read_text(encoding="utf8"))
            # The original publisher verifies modal score and group mass from
            # these original V3 grid cells, with no 2026 backtest labels.
            feed=build_feed(prospective,generated_at=prospective["generated_at"],
                            target_date=now.date())
            next_feed=build_feed(prospective,generated_at=prospective["generated_at"],
                                 target_date=now.date()+timedelta(days=1))
        for entry in (feed,next_feed):
            if entry["status"]=="published" and not entry["simple"]:
                raise RuntimeError("Invalid empty published Top5 list")
        feed=save_verified_day(site_root,feed)
        next_feed=save_verified_day(site_root,next_feed)
        atomic_json(target,feed)
        print("V3_DAILY_NEXTDAY_TOP5",json.dumps({
            "date":next_feed["date"],"status":next_feed["status"],
            "simple":len(next_feed["simple"]),"grouped":len(next_feed["grouped"]),
            "generated_at":next_feed["generated_at"]
        },sort_keys=True),flush=True)
        print("V3_DAILY_TOP5_READY",json.dumps({
            "asof":feed["generated_at"],"status":feed["status"],
            "simple":len(feed["simple"]),"grouped":len(feed["grouped"]),
            "certified_archive_cutoff":str(BASE_CUTOFF),
            "new_certified_utc_days":len(daily_counts),
            "oos_replay_begin":str(eval_begin),
            "no_historical_result_published":True,
            "market_definition":"experimental_proxy_not_bookmaker_verified",
        },sort_keys=True),flush=True)
        return feed
    finally:
        os.chdir(previous)


def fast_produce(site_root, model_root, *, out_path=None, now=None):
    """Lightweight true inference: never load 2024-2026 corpus or train models."""
    start = time.monotonic()
    site_root = Path(site_root).resolve()
    target = resolve_public_target(site_root, out_path)
    model_root = install_research_modules(Path(model_root))
    old_cwd = Path.cwd()
    try:
        os.chdir(model_root)
        from sportdata_api import fetch_games, get_api_keys
        from single_ml_v2_git import key_from_environment
        from single_ml_v2_data import utc_dt
        from single_ml_v3_checkpoint import load_checkpoint, forecast_from_checkpoint
        sys.path.insert(0, str(site_root / "scripts"))
        from publish_exact_scores import build_feed
        if not get_api_keys():
            raise RuntimeError("No SportData API key; refusing unauthenticated picks")
        key = key_from_environment()
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("Only explicit UTC supported")
        yesterday = now.date() - timedelta(days=1)
        path = site_root / "research/score_v3_model_checkpoints" / (str(yesterday) + ".enc")
        checkpoint = load_checkpoint(path, key, expected_day=yesterday)
        print("V3_FAST_TIMING", json.dumps({
            "stage": "verify_and_load_trained_checkpoint",
            "seconds": round(time.monotonic()-start, 2)}), flush=True)
        step = time.monotonic()
        source = fetch_games(now.date(), now.date()+timedelta(days=1),
                             timeout=45, show_odds=False)
        if not source.ok:
            raise RuntimeError("Prospective SportData match source unavailable")
        fixtures = future_fixtures(source, now, converter=utc_dt,
                                  include_tomorrow=True)
        print("V3_FAST_TIMING", json.dumps({
            "stage": "fetch_verified_future_fixtures",
            "seconds": round(time.monotonic()-step, 2),
            "matches": len(fixtures)}), flush=True)
        if not fixtures:
            raise RuntimeError("No future fixtures to score; preserving previous published feed")
        step = time.monotonic()
        prospective = forecast_from_checkpoint(checkpoint, fixtures)
        feed = build_feed(prospective, generated_at=prospective["generated_at"],
                          target_date=now.date())
        next_feed = build_feed(prospective, generated_at=prospective["generated_at"],
                               target_date=now.date()+timedelta(days=1))
        for row in (feed, next_feed):
            if row["status"] == "published" and not row["simple"]:
                raise RuntimeError("Published feed is missing score selections")
        feed = save_verified_day(site_root, feed)
        next_feed = save_verified_day(site_root, next_feed)
        atomic_json(target, feed)
        print("V3_FAST_TIMING", json.dumps({
            "stage": "score_grid_rank_and_save",
            "seconds": round(time.monotonic()-step, 2)}), flush=True)
        print("V3_FAST_PUBLICATION_READY", json.dumps({
            "today": feed["date"], "status": feed["status"],
            "simple": len(feed["simple"]), "grouped": len(feed["grouped"]),
            "tomorrow": next_feed["date"], "tomorrow_status": next_feed["status"],
            "elapsed_seconds": round(time.monotonic()-start, 2),
            "trained_checkpoint_day": str(yesterday),
            "no_model_training": True}), flush=True)
        return feed
    finally:
        os.chdir(old_cwd)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--site-root",default=".")
    p.add_argument("--model-root",required=True)
    p.add_argument("--out",default=None)
    p.add_argument("--fast-inference", action="store_true",
                   help="Require authenticated pre-trained V3 checkpoint; never run a backtest")
    args=p.parse_args()
    runner = fast_produce if args.fast_inference else produce
    runner(args.site_root,args.model_root,out_path=args.out)


if __name__=="__main__":
    main()
