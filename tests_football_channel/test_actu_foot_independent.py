"""Régressions offline : programme, live sélectif, stockage, échec réseau."""
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import requests
from scripts import actu_foot_independent as mod

NOW = datetime(2026, 10, 29, 7, 0, tzinfo=timezone.utc)


def fixture(home="Real Madrid", away="Getafe", id=101, hour=18,
            league="Premier League"):
    return dict(id=str(id), home_team=home, away_team=away,
                league_name=league, event_date=NOW.replace(hour=hour).isoformat(),
                status="scheduled", home_logo="https://example.org/home.png",
                away_logo="https://example.org/away.png")


def row():
    return dict(id="12345", home="Arsenal", away="Chelsea",
                league="Premier League", rank=1,
                event_date=NOW.replace(hour=6).isoformat(), done=False,
                home_logo="https://example.org/h.png",
                away_logo="https://example.org/a.png")


def live_info(state="in", minute=55, hs=1, aws=0, clock=None, period=2):
    return dict(id="12345", home_team="Arsenal", away_team="Chelsea",
                state=state, minute=minute, period=period,
                home_score=hs, away_score=aws, status_detail="",
                raw={"competitions":[{"status":{"displayClock":clock or str(minute)}}]})


class TestActuFootIndependent(unittest.TestCase):
    def test_time_window(self):
        self.assertTrue(mod.within_programme_window(NOW))
        self.assertFalse(mod.within_programme_window(NOW.replace(hour=8)))

    def test_rank_clubs_before_final_without_clubs(self):
        club=fixture()
        final=fixture("Oxford United","Portsmouth",102)
        final["round_name"]="Final"
        self.assertGreater(mod.event_priority(club),mod.event_priority(final))

    def test_editorial_metadata_from_raw_espn(self):
        event=fixture("Oxford United","Portsmouth")
        event["league_name"]=""
        event["raw"]={"competitions":[{"altGameNote":"UEFA Semi-Final",
                                        "league":{"name":"Champions League"}}]}
        enriched=mod.enrich_espn_fixtures([event])[0]
        self.assertIn("Semi-Final",enriched["round_name"])
        self.assertEqual(enriched["league_name"],"Champions League")
        self.assertGreater(mod.channel.high_stakes_bonus(enriched),150)

    def test_league_and_round_from_real_espn_note(self):
        event=fixture("Oxford United","Portsmouth")
        event["league_name"]=""
        event["raw"]={"competitions":[{"altGameNote":"Carabao Cup, Fourth Round"}]}
        result=mod.enrich_espn_fixtures([event])[0]
        self.assertEqual(result["league_name"],"Carabao Cup")
        self.assertEqual(result["round_name"],"Fourth Round")

    def test_final_from_real_espn_note(self):
        event=fixture("Oxford United","Portsmouth")
        event["league_name"]=""
        event["raw"]={"competitions":[{"altGameNote":"FA Cup, Final"}]}
        result=mod.enrich_espn_fixtures([event])[0]
        self.assertEqual(result["league_name"],"FA Cup")
        self.assertGreater(mod.channel.high_stakes_bonus(result),300)

    def test_programme_verifiable_and_priority(self):
        events=[fixture("Oxford United","Portsmouth",101),
                fixture("Real Madrid","Getafe",102),
                fixture("Arsenal","Chelsea",103)]
        events[0]["round_name"]="Final"
        with patch.object(mod.channel,"has_two_team_logos",return_value=True):
            post,tracked=mod.selected_fixtures(events,NOW)
        self.assertIsNotNone(post)
        self.assertTrue(tracked)
        self.assertIn(tracked[0]["home"], {"Arsenal","Real Madrid"})
        self.assertTrue(all(str(t["id"]).isdigit() for t in tracked))
        self.assertEqual(post.category,"programme")

    def test_no_programme_for_missing_games(self):
        post, tracked=mod.selected_fixtures([], NOW)
        self.assertIsNone(post)
        self.assertEqual(tracked,[])

    def test_programme_single_atomic_reservation(self):
        ledger=MagicMock()
        ledger.query.return_value={"meta":{"changes":1}}
        self.assertTrue(mod.reserve_programme(ledger,"@channel","2026-10-29",[row()]))
        sql, params=ledger.query.call_args.args
        self.assertIn("selection_snapshot",sql)
        self.assertIn("'reserved'",sql)
        self.assertEqual(params[1],mod.PROGRAMME_KIND)
        self.assertEqual(json.loads(params[-1])[0]["id"],"12345")

    def test_programme_reservation_conflict(self):
        ledger=MagicMock()
        ledger.query.return_value={"meta":{"changes":0}}
        self.assertFalse(mod.reserve_programme(ledger,"@channel","2026-10-29",[row()]))

    def test_programme_reserved_blocks_republication(self):
        ledger=MagicMock()
        ledger.rows.return_value=[{"delivery_status":"reserved"}]
        sender=MagicMock(chat="@channel")
        with self.assertRaisesRegex(RuntimeError,"UNCERTAIN_DELIVERY"):
            mod.programme_cycle(NOW,sender,ledger,False)
        sender.send.assert_not_called()

    def test_programme_espn_unavailable_is_error(self):
        ledger=MagicMock()
        ledger.rows.return_value=[]
        with patch.object(mod,"fetch_espn_day",return_value=[]):
            with self.assertRaisesRegex(RuntimeError,"ESPN_DAY_EMPTY"):
                mod.programme_cycle(NOW,MagicMock(chat="@channel"),ledger,False)

    def test_real_programme_saves_before_sending(self):
        ledger=MagicMock()
        ledger.rows.return_value=[]
        ledger.query.return_value={"meta":{"changes":1}}
        sender=MagicMock(chat="@channel")
        sender.send.return_value=77
        with patch.object(mod,"fetch_espn_day",return_value=[fixture()]):
            with patch.object(mod.channel,"has_two_team_logos",return_value=True):
                mod.programme_cycle(NOW,sender,ledger,False)
        self.assertEqual(ledger.query.call_count,1)
        self.assertEqual(sender.send.call_count,1)
        ledger.mark.assert_called_once_with(mod.PROGRAMME_KIND,"@channel","2026-10-29",message_id=77)

    def test_real_espn_nested_details_are_normalized(self):
        goal = {"id":"1122","type":{"text":"Goal"},"scoringPlay":True,
                "clock":{"displayValue":"45+3"},"homeScore":1,"awayScore":0}
        payload = {"header":{"competitions":[{"details":[goal]}]}}
        fixed = mod.normalize_espn_summary(payload)
        self.assertEqual(fixed["details"],[goal])
        actual = mod.extract_goals(fixed)
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]["minute_total"],48)

    def test_real_soccer_goal_participants_yield_scorer(self):
        details=[{"id":"goal-1","scoringPlay":True,
                  "clock":{"displayValue":"39'"},
                  "team":{"id":"100","displayName":"Juventus"},
                  "participants":[{"athlete":{"id":"p-3","displayName":"Matilde Pavan"}}],
                  "homeScore":0,"awayScore":1}]
        raw={"header":{"competitions":[{"details":details}]}}
        result=mod.extract_goals(mod.normalize_espn_summary(raw))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["player"],"Matilde Pavan")
        self.assertEqual(result[0]["minute_total"],39)

    def test_two_distinct_goals_and_final(self):
        info=live_info(hs=2)
        goals=[dict(id="goal1",minute_total=52,home_score=1,away_score=0),
               dict(id="goal2",minute_total=54,home_score=2,away_score=0)]
        with patch.object(mod,"extract_goals",return_value=goals):
            signals=mod.live_signals(row(),info,{},NOW)
        self.assertEqual(len([s for s in signals if s["kind"]=="goal"]),2)
        self.assertEqual(len({s["key"] for s in signals}),len(signals))
        info["state"]="post"
        with patch.object(mod,"extract_match_enrichment",return_value={}):
            with patch.object(mod,"extract_goals",return_value=goals):
                final=mod.live_signals(row(),info,{},NOW)
        self.assertEqual(len([s for s in final if s["kind"]=="resultat_final"]),1)
        self.assertEqual(len([s for s in final if s["kind"]=="goal"]),2)

    def test_90_plus_3_goal_uses_extended_minute(self):
        goal=dict(id="extra-goal",minute_total=93,minute_text="90+3",home_score=2,away_score=1)
        info=live_info(minute=90,clock="90+3",hs=2,aws=1)
        with patch.object(mod,"extract_goals",return_value=[goal]):
            signals=mod.live_signals(row(),info,{},NOW)
        goals=[s for s in signals if s["kind"]=="goal"]
        self.assertEqual(goals[0]["minute"],93)
        self.assertEqual(goals[0]["minute_text"],"90+3")

    def test_half_time_catchup_goal(self):
        info=live_info(state="in",minute=45,clock="45+4",period=1)
        info["status_detail"]="Half Time"
        goal=dict(id="half-goal",minute_total=49,home_score=1,away_score=0)
        with patch.object(mod,"extract_goals",return_value=[goal]):
            signals=mod.live_signals(row(),info,{},NOW)
        self.assertTrue(any(s["kind"]=="goal" for s in signals))
        self.assertTrue(any(s["kind"]=="mi_temps" for s in signals))

    def test_no_new_score_no_publication(self):
        info=live_info(minute=60)
        with patch.object(mod,"extract_goals",return_value=[]):
            self.assertEqual(mod.live_signals(row(),info,{},NOW),[])

    def test_cards_and_substitutions(self):
        card=dict(id="red-1",type="red",player="Player A",minute=71)
        change=dict(id="sub-1",entrant="Player B",sortant="Player C",minute=73)
        with patch.object(mod,"extract_cards",return_value=[card]):
            with patch.object(mod,"extract_substitutions",return_value=[change]):
                signals=mod.live_signals(row(),live_info(minute=74),{},NOW)
        self.assertIn("carton_rouge",[s["kind"] for s in signals])
        self.assertIn("remplacement",[s["kind"] for s in signals])

    def test_lineups_and_changes(self):
        lineups={"home":["H"+str(i) for i in range(11)],
                 "away":["A"+str(i) for i in range(11)]}
        with patch.object(mod,"extract_lineups",return_value=lineups):
            initial=mod.live_signals(row(),live_info(),{},NOW)
        self.assertIn("composition",[s["kind"] for s in initial])
        r=row()
        r["lineup_home"]=lineups["home"].copy()
        r["lineup_away"]=lineups["away"].copy()
        changed={"home":lineups["home"][:-1]+["New"],"away":lineups["away"]}
        with patch.object(mod,"extract_lineups",return_value=changed):
            updates=mod.live_signals(r,live_info(),{},NOW)
        self.assertIn("changement_composition",[s["kind"] for s in updates])

    def test_shootout_and_final(self):
        info=live_info(state="post",minute=120,period=5)
        info["home_shootout_score"]=5
        info["away_shootout_score"]=4
        kick=dict(id="shot-1",outcome="made",minute=120,player="A")
        with patch.object(mod,"extract_shootout_kicks",return_value=[kick]):
            signals=mod.live_signals(row(),info,{},NOW)
        kinds={s["kind"] for s in signals}
        self.assertTrue({"tirs_au_but","tir_au_but_marque","fin_tirs_au_but","resultat_final"}.issubset(kinds))

    def test_duplicate_suppression(self):
        ledger=MagicMock()
        ledger.claim.side_effect=[True,False]
        ledger.rows.return_value=[{"delivery_status":"sent"}]
        sender=MagicMock(chat="@test")
        sender.send.return_value=99
        post=MagicMock(category="goal")
        self.assertTrue(mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",post,dry_run=False))
        self.assertTrue(mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",post,dry_run=False))
        sender.send.assert_called_once()

    def test_uncertain_delivery_never_resends(self):
        ledger=MagicMock()
        ledger.claim.return_value=False
        ledger.rows.return_value=[{"delivery_status":"reserved"}]
        sender=MagicMock(chat="@test")
        with self.assertRaisesRegex(RuntimeError,"UNCERTAIN_DELIVERY"):
            mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",MagicMock(),dry_run=False)
        sender.send.assert_not_called()

    def test_explicit_429_releases_claim(self):
        ledger=MagicMock()
        ledger.claim.return_value=True
        response=requests.Response()
        response.status_code=429
        sender=MagicMock(chat="@test")
        sender.send.side_effect=requests.HTTPError("429",response=response)
        with self.assertRaises(requests.HTTPError):
            mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",MagicMock(),dry_run=False)
        ledger.release.assert_called_once_with(mod.EVENT_KIND,"@test:goal:x","2026-10-29")

    def test_timeout_keeps_claim(self):
        ledger=MagicMock()
        ledger.claim.return_value=True
        sender=MagicMock(chat="@test")
        sender.send.side_effect=requests.Timeout()
        with self.assertRaises(requests.Timeout):
            mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",MagicMock(),dry_run=False)
        ledger.release.assert_not_called()

    def test_first_score_is_baseline_not_ghost_goal(self):
        fields, signal=mod.score_transition(row(),live_info(hs=0,aws=0),NOW,False)
        self.assertEqual(fields["confirmed_score"],"0-0")
        self.assertIsNone(signal)

    def test_one_changed_score_creates_pending_only(self):
        fixture=row()
        fixture["confirmed_score"]="0-0"
        fields,signal=mod.score_transition(fixture,live_info(hs=1,aws=0),NOW,False)
        self.assertEqual(fields["pending_score"],"1-0")
        self.assertIsNone(signal)

    def test_two_confirmed_checks_emit_goal_without_scorer(self):
        fixture=row()
        fixture.update(confirmed_score="0-0", pending_score="1-0",
                       pending_at=NOW.isoformat())
        fields,signal=mod.score_transition(
            fixture,live_info(hs=1,aws=0),NOW+timedelta(minutes=2),False)
        self.assertEqual(fields["confirmed_score"],"1-0")
        self.assertEqual(signal["kind"],"goal")
        self.assertEqual(signal["goal"],{})

    def test_score_correction_emits_score_not_false_goal(self):
        fixture=row()
        fixture.update(confirmed_score="2-1", pending_score="1-1",
                       pending_at=NOW.isoformat())
        fields,signal=mod.score_transition(
            fixture,live_info(hs=1,aws=1),NOW+timedelta(minutes=2),False)
        self.assertEqual(signal["kind"],"score_update")
        self.assertEqual(fields["confirmed_score"],"1-1")

    def test_detailed_goal_skips_score_fallback(self):
        fixture=row()
        fixture.update(confirmed_score="0-0")
        fields,signal=mod.score_transition(fixture,live_info(hs=1,aws=0),NOW,True)
        self.assertEqual(fields["confirmed_score"],"1-0")
        self.assertIsNone(signal)

    def test_unchanged_score_creates_no_d1_writes(self):
        fixture=row()
        fixture.update(confirmed_score="1-0")
        fields,signal=mod.score_transition(fixture,live_info(hs=1,aws=0),NOW,False)
        self.assertEqual(fields,{})
        self.assertIsNone(signal)

    def test_score_state_cas_write(self):
        fixture=row()
        fixture["confirmed_score"]="0-0"
        ledger=MagicMock()
        ledger.query.return_value={"meta":{"changes":1}}
        original=[fixture]
        raw=json.dumps(original)
        updated_raw, updated=mod.save_score_state(
            ledger,"@test","2026-10-29",raw,original,"12345",{"pending_score":"1-0"})
        self.assertEqual(updated[0]["pending_score"],"1-0")
        self.assertEqual(json.loads(updated_raw)[0]["pending_score"],"1-0")

    def test_all_restored_event_kinds_build_telegram_publications(self):
        from scripts import football_channel as channel
        base = {
            "home":"Arsenal","away":"Chelsea","league":"Premier League",
            "score":"1-0","minute":55,"source":"ESPN","key":"smoke:12345",
            "home_logo":"https://example.org/h.png",
            "away_logo":"https://example.org/a.png",
            "espn_event_id":"12345",
            "shootout_scores":[5,4],
            "lineups":{"home":["H"+str(i) for i in range(11)],
                       "away":["A"+str(i) for i in range(11)]},
        }
        categories=(
            "kickoff","goal","mi_temps","debut_2e_mi_temps",
            "temps_additionnel","prolongation","mi_temps_prolongation",
            "carton_rouge","carton_jaune","remplacement",
            "composition","changement_composition","tirs_au_but",
            "tir_au_but_marque","tir_au_but_manque","fin_tirs_au_but",
            "score_update"
        )
        import os
        with patch.dict(os.environ,{"FOOTBALL_ENABLE_SCORE_UPDATES":"1"}):
            for category in categories:
                signal=dict(base,kind=category)
                with self.subTest(category=category):
                    self.assertIsNotNone(channel.lifecycle_publication(signal),
                                         category)
        self.assertIsNotNone(channel.followed_final_publication(
            dict(base,kind="resultat_final")))
        self.assertIsNotNone(channel.followed_interruption_publication(
            dict(base,kind="suivi_interrompu",status="suspended")))

    def test_no_live_api_when_no_plan(self):
        ledger=MagicMock()
        ledger.query.return_value={"results":[]}
        sender=MagicMock(chat="@test")
        with patch.object(mod,"fetch_espn_summary") as fetch:
            mod.lifecycle_cycle(NOW,sender,ledger,False)
        fetch.assert_not_called()

    def test_live_summary_unavailable_reports_error(self):
        ledger=MagicMock()
        ledger.query.return_value={"results":[]}
        sender=MagicMock(chat="@test")
        with patch.object(mod,"get_plan",side_effect=[([row()],"[]"),([],None)]):
            with patch.object(mod,"fetch_espn_summary",return_value={}):
                with self.assertRaisesRegex(RuntimeError,"ESPN_SUMMARY_UNAVAILABLE"):
                    mod.lifecycle_cycle(NOW,sender,ledger,False)

    def test_finished_plan_cas(self):
        ledger=MagicMock()
        ledger.query.return_value={"meta":{"changes":1}}
        original=[row()]
        raw=json.dumps(original)
        new_raw, updated=mod.mark_finished(ledger,"@test","2026-10-29",raw,original,"12345")
        self.assertTrue(updated[0]["done"])
        self.assertIn("selection_snapshot",ledger.query.call_args.args[0])
        self.assertEqual(json.loads(new_raw)[0]["done"],True)

if __name__=="__main__":
    unittest.main()
