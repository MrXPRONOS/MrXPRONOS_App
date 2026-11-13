"""Pure no-network tests for daily SportData -> genuine V3 publication orchestration."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
from datetime import datetime,date,timedelta,timezone
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from scripts.run_exact_scores_v3_daily import (
    BASE_CUTOFF, DAILY_HISTORY_SUBDIR, future_fixtures, historical_daily_rows, sportdata_source_identity, save_verified_day, resolve_public_target, quarantine_conflicting_provider_identities
)


def response(records, *,ok=True):
    return SimpleNamespace(ok=ok,games=records,reason="test-only source")


def event(ident=123,*,now="2026-11-03T20:00:00Z",sport_id=1,status_group=1):
    return {
      "id":ident,"sportId":sport_id,"startTime":now,
      "statusGroup":status_group,
      "homeCompetitor":{"name":"Home FC","id":40,"score":0},
      "awayCompetitor":{"name":"Away FC","id":59,"score":0},
      "competitionDisplayName":"Test League","competitionId":55
    }


def utc_dt(t):
    return datetime.fromisoformat(t.replace("Z","+00:00")) if t else None


def match(day,i):
    return {
      "id":f"id-{i}","sportId":1,
      "start_time":str(day)+"T10:00:00Z",
      "home_team":"Home","away_team":"Away",
      "competition":"League","is_finished":True,
      "home_score":1,"away_score":0,
      "source_home_team_id":"1","source_away_team_id":"2",
      "source_competition_id":"3"
    }


@dataclass(frozen=True)
class TrainingMatch:
    key: str
    home: str
    away: str
    league: str
    home_id: str | None
    away_id: str | None
    competition_id: str | None


def validate_training_identities(matches):
    # Strictly the same identity guarantee as the native opponent-state
    # _preview() check: no global ID may refer to multiple club names.
    seen = {}
    for match in matches:
        for side in ("home", "away"):
            raw_id = getattr(match, side + "_id")
            if raw_id is None:
                continue
            club = getattr(match, side).casefold()
            if raw_id in seen and seen[raw_id] != club:
                raise ValueError("Conflicting provider ID associated to different club names")
            seen[raw_id] = club


class TestExactDailyPipeline(unittest.TestCase):
    def test_public_output_path_is_stable_when_model_changes_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "site"
            model = root / "model"
            site.mkdir()
            model.mkdir()
            original = Path.cwd()
            try:
                os.chdir(root)
                named = resolve_public_target(site, "site/scores-exacts.json")
                default = resolve_public_target(site, None)
                os.chdir(model)
                self.assertEqual(named, site / "scores-exacts.json")
                self.assertEqual(default, site / "scores-exacts.json")
                self.assertEqual(named.parent, site)
                self.assertNotEqual(named.parent, model)
            finally:
                os.chdir(original)

    def test_cross_cohort_provider_id_collision_uses_local_team_fallback(self):
        frozen=TrainingMatch("base","Club A","Club B","League 1",
                             "src_sportsapipro_v1_allscores_40","src_sportsapipro_v1_allscores_59",
                             "src_sportsapipro_v1_allscores_11")
        daily=TrainingMatch("daily","Club C","Club D","League 2",
                            "src_sportsapipro_v1_allscores_40","src_sportsapipro_v1_allscores_60",
                            "src_sportsapipro_v1_allscores_11")
        # Previously observed production exception reproduced offline.
        with self.assertRaisesRegex(ValueError,"Conflicting provider ID"):
            validate_training_identities([frozen,daily])
        cleaned, audit = quarantine_conflicting_provider_identities(
            [frozen,daily],normalizer=str.casefold)
        self.assertEqual(len(cleaned),2)
        self.assertEqual([m.key for m in cleaned],["base","daily"])
        self.assertEqual(audit["ambiguous_club_ids"],1)
        self.assertEqual(audit["ambiguous_competition_ids"],1)
        self.assertEqual(audit["matches_using_local_fallback"],2)
        self.assertEqual(audit["match_records_removed"],0)
        self.assertTrue(audit["source_archives_changed"] is False)
        self.assertIsNone(cleaned[0].home_id)
        self.assertIsNone(cleaned[1].home_id)
        self.assertIsNone(cleaned[0].competition_id)
        self.assertIsNone(cleaned[1].competition_id)
        self.assertEqual(cleaned[0].away_id,frozen.away_id)
        self.assertEqual(cleaned[1].away_id,daily.away_id)
        validate_training_identities(cleaned)
        # Frozen dataclass originals and user-facing team names are immutable.
        self.assertEqual(frozen.home_id,"src_sportsapipro_v1_allscores_40")
        self.assertEqual(daily.home_id,"src_sportsapipro_v1_allscores_40")
        self.assertEqual(cleaned[0].home,"Club A")
        self.assertEqual(cleaned[1].home,"Club C")

    def test_cross_cohort_identical_names_do_not_disable_verified_ids(self):
        a=TrainingMatch("a","Club A","Club B","League 1","same","b","league")
        b=TrainingMatch("b","Club A","Club C","League 1","same","c","league")
        cleaned,audit=quarantine_conflicting_provider_identities([a,b],normalizer=str.casefold)
        self.assertEqual(cleaned,[a,b])
        self.assertEqual(audit["matches_using_local_fallback"],0)
        self.assertEqual(audit["ambiguous_club_ids"],0)
        self.assertEqual(audit["ambiguous_competition_ids"],0)

    def test_upcoming_only_certified_utc_day(self):
        now=utc_dt("2026-11-03T15:00:00Z")
        records=[
          event(11,now="2026-11-03T20:00:00Z"),
          event(12,now="2026-11-03T12:00:00Z"),
          event(13,now="2026-11-04T20:00:00Z"),
          event(14,now="2026-11-03T20:00:00Z",sport_id=2),
          event(15,now="2026-11-03T20:00:00Z",status_group=4)
        ]
        choices=future_fixtures(response(records),now,converter=utc_dt)
        self.assertEqual(len(choices),1)
        self.assertEqual(choices[0]["id"],"sportsapipro:11")
        self.assertEqual(choices[0]["kickoff_utc"],"2026-11-03T20:00:00Z")
        self.assertEqual(set(choices[0]),{"id","league","home","away","kickoff_utc"})
        self.assertNotIn("home_score",json.dumps(choices))
        self.assertNotIn("actual_score",json.dumps(choices))

    def test_two_day_source_retains_only_verified_future_utc_targets(self):
        now=utc_dt("2026-11-03T15:00:00Z")
        rows=[
            event(11,now="2026-11-03T20:00:00Z"),
            event(12,now="2026-11-04T16:00:00Z"),
            event(13,now="2026-11-05T20:00:00Z"),
            event(14,now="2026-11-03T14:00:00Z")
        ]
        got=future_fixtures(response(rows),now,converter=utc_dt,include_tomorrow=True)
        self.assertEqual([p["id"] for p in got],["sportsapipro:11","sportsapipro:12"])
        self.assertTrue(all("score" not in json.dumps(p) for p in got))

    def test_late_empty_recalculation_preserves_real_prematch_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            today="2026-11-03"
            real={"schema_version":"mrx-exact-top5-v1",
                  "model":"machine_learning_v3_hybrid","status":"published",
                  "date":today,"generated_at":"2026-11-03T06:00:00Z",
                  "origin":"prospective_prematch","simple":[{"id":"verified"}],"grouped":[]}
            self.assertEqual(save_verified_day(root,real),real)
            no_games=dict(real,status="unavailable",simple=[],grouped=[])
            self.assertEqual(save_verified_day(root,no_games),real)
            stored=json.loads((root/"scores-exacts-daily"/(today+".json")).read_text())
            self.assertEqual(stored,real)

    def test_provider_error_never_turns_into_fake_fixtures(self):
        with self.assertRaisesRegex(RuntimeError,"unavailable"):
            future_fixtures(response([],ok=False),utc_dt("2026-11-03T15:00:00Z"),converter=utc_dt)
        self.assertEqual(future_fixtures(response([]),utc_dt("2026-11-03T15:00:00Z"),converter=utc_dt),[])

    def test_daily_provider_identifiers_are_research_safe_and_scoped(self):
        # The frozen 2024-2026 archive is normalized by
        # safe_source_identities() in single_ml_v2_multisource.py.
        # The incremental SportData rows must share that exact namespace.
        self.assertEqual(sportdata_source_identity(40), "src_sportsapipro_v1_allscores_40")
        self.assertEqual(sportdata_source_identity("59"), "src_sportsapipro_v1_allscores_59")
        for invalid in (None, True, "", "unknown", "0", "source:40", "  "):
            self.assertIsNone(sportdata_source_identity(invalid))
        with tempfile.TemporaryDirectory() as tmp:
            d = BASE_CUTOFF + timedelta(days=1)
            rows, _ = historical_daily_rows(
                Path(tmp), d,
                fetcher=lambda *_args, **_kw: response([match(d, 40)]),
                normalizer=lambda day, result: {
                    "day": str(day), "verified": True,
                    "certified_football_count": len(result.games),
                    "matches": result.games,
                },
                sealer=lambda obj, *_args: json.dumps(obj).encode(),
                opener=lambda *_args: None, key=b"test", verbose=False,
            )
            self.assertEqual(rows[0]["source_home_team_id"], "src_sportsapipro_v1_allscores_1")
            self.assertEqual(rows[0]["source_away_team_id"], "src_sportsapipro_v1_allscores_2")
            self.assertEqual(rows[0]["source_competition_id"], "src_sportsapipro_v1_allscores_3")

    def test_daily_authenticated_cache_before_fetching_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            counter=[]
            def fetcher(day,other,**kwargs):
                self.assertEqual(day,other);counter.append(day)
                return response([match(day,day.day)])
            def snap(day,result):
                rows=result.games
                return {"day":str(day),"verified":True,"certified_football_count":len(rows),"matches":rows}
            def seal(obj,key,label):
                return (label+"\n"+json.dumps(obj)).encode()
            def open_(data,key,label):
                txt=data.decode();self.assertTrue(txt.startswith(label+"\n"))
                return json.loads(txt[len(label)+1:])
            d1=BASE_CUTOFF+timedelta(days=1)
            d2=BASE_CUTOFF+timedelta(days=2)
            first,days=historical_daily_rows(base,d2,fetcher=fetcher,
                normalizer=snap,sealer=seal,opener=open_,key=b"fake",verbose=False)
            self.assertEqual(len(counter),2)
            self.assertEqual(len(first),2)
            self.assertEqual(first[0]["id"],"sportsapipro-daily:id-25")
            self.assertTrue((base/(str(d1)+".enc")).exists())
            self.assertEqual(days[0]["source"],"verified_sportdata_api")
            counter.clear()
            again,days2=historical_daily_rows(base,d2,fetcher=fetcher,
                normalizer=snap,sealer=seal,opener=open_,key=b"fake",verbose=False)
            self.assertEqual(counter,[])
            self.assertEqual(again,first)
            self.assertEqual(days2[0]["source"],"encrypted_cache")

    def test_no_unverified_day_can_reach_v3_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=BASE_CUTOFF+timedelta(days=1)
            def source(*args,**kwargs):return response([],ok=False)
            with self.assertRaisesRegex(RuntimeError,"Cannot verify"):
                historical_daily_rows(Path(tmp),d,fetcher=source,
                    normalizer=lambda day,result:None,
                    sealer=lambda *a:b"empty",opener=lambda *a:None,key=b"?",verbose=False)

    def test_uncertified_event_is_rejected_before_encrypted_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            day=BASE_CUTOFF+timedelta(days=1)
            with self.assertRaisesRegex(RuntimeError,"Missing completed certified"):
                historical_daily_rows(Path(tmp),day,
                    fetcher=lambda *a,**k:response([]),
                    normalizer=lambda d,r:{"day":str(d),"verified":True,"certified_football_count":0,"matches":[]},
                    sealer=lambda *a:b"none",opener=lambda *a:None,key=b"x",verbose=False)
            self.assertEqual(list(Path(tmp).glob("*.enc")),[])

    def test_tampered_encrypted_day_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            day=BASE_CUTOFF+timedelta(days=1)
            (Path(tmp)/(str(day)+".enc")).write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError,"ciphertext authentication failed"):
                historical_daily_rows(Path(tmp),day,
                    fetcher=lambda *a,**k:response([]),
                    normalizer=lambda *a:None,sealer=lambda *a:b"none",
                    opener=lambda *a:(_ for _ in ()).throw(RuntimeError("ciphertext authentication failed")),
                    key=b"x",verbose=False)

if __name__=="__main__":
    unittest.main()
