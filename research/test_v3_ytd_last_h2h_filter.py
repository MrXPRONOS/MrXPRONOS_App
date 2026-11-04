"""H2H filter correctness and leakage tests; synthetic matches, no real data."""
import unittest
from datetime import date
from types import SimpleNamespace

from backtest_v3_ytd_last_h2h_filter import (
    CompletedPriorH2H, _orientation, apply_h2h_filter, summarize_h2h,
)


def game(key, day, home, away, h, a, *, league="League", hid=None, aid=None):
    return SimpleNamespace(
        key=key,day=date.fromisoformat(day),league=league,
        home=home,away=away,hg=h,ag=a,home_id=hid,away_id=aid
    )


def pick(m, score):
    return {
        "day":str(m.day), "score":score, "match_id":m.key,
        "league":m.league, "home":m.home, "away":m.away,
        "actual_score":f"{m.hg}:{m.ag}",
        "probability":.15, "modal_score":score,
        "hit":int(score==f"{m.hg}:{m.ag}"),
        "history_latest_day":"2025-12-31",
        "model_fit_latest_day":"2025-12-31",
    }


class PreviousHeadToHeadTests(unittest.TestCase):
    def test_reverse_venue_score_is_normalized(self):
        prior=game("one","2025-08-01","B","A",0,2)
        future=game("two","2026-03-01","A","B",2,0)
        state=CompletedPriorH2H()
        state.add(prior)
        status,match,result,scope=state.last(future)
        self.assertEqual(status,"verified")
        self.assertEqual(match.key,"one")
        self.assertEqual(result,(2,0))
        self.assertEqual(scope,"same_league_exact_club_names")

    def test_latest_h2h_not_an_earlier_favorable_h2h(self):
        a=game("1","2025-01-01","A","B",2,0)
        b=game("2","2025-06-01","B","A",2,0)
        m=game("3","2026-03-01","A","B",2,0)
        result=apply_h2h_filter([pick(m,"2:0")],[a,b,m])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["h2h_status"],"rejected_last_h2h_different_score")
        self.assertEqual(result[0]["last_h2h_normalized_score"],"0:2")
        self.assertEqual(result[0]["last_h2h_day"],"2025-06-01")

    def test_h2h_match_passes_and_keeps_original_probability(self):
        p=game("one","2025-04-01","A","B",1,0)
        target=game("two","2026-03-01","A","B",1,0)
        got=apply_h2h_filter([pick(target,"1:0")],[p,target])
        self.assertEqual(got[0]["h2h_status"],"kept_last_h2h_exact_win")
        self.assertEqual(got[0]["probability"],.15)
        self.assertEqual(got[0]["match_id"],"two")
        self.assertEqual(got[0]["last_h2h_day"],"2025-04-01")

    def test_same_day_h2h_cannot_leak_into_predictions(self):
        same_day=game("one","2026-03-01","B","A",0,2)
        target=game("two","2026-03-01","A","B",2,0)
        got=apply_h2h_filter([pick(target,"2:0")],[same_day,target])
        self.assertEqual(got[0]["h2h_status"],"no_prior_h2h")

    def test_future_result_does_not_qualify(self):
        target=game("one","2026-03-01","A","B",2,0)
        after=game("two","2026-06-01","B","A",0,2)
        got=apply_h2h_filter([pick(target,"2:0")],[target,after])
        self.assertEqual(got[0]["h2h_status"],"no_prior_h2h")

    def test_verified_provider_ids_can_cross_competitions(self):
        prior=game("first","2025-01-01","B","A",0,1,
                   league="Cup",hid="source_2",aid="source_1")
        target=game("second","2026-01-01","A","B",1,0,
                    league="League",hid="source_1",aid="source_2")
        result=apply_h2h_filter([pick(target,"1:0")],[prior,target])
        self.assertEqual(result[0]["h2h_status"],"kept_last_h2h_exact_win")
        self.assertEqual(result[0]["h2h_source"],"verified_provider_ids")

    def test_conflicting_provider_ids_do_not_join_by_name(self):
        prior=game("first","2025-01-01","A","B",1,0,
                   hid="src_x",aid="src_y")
        target=game("second","2026-01-01","A","B",1,0,
                    hid="src_a",aid="src_b")
        result=apply_h2h_filter([pick(target,"1:0")],[prior,target])
        self.assertEqual(result[0]["h2h_status"],"no_prior_h2h")

    def test_league_names_fallback_must_not_cross_leagues(self):
        prior=game("first","2025-01-01","A","B",1,0,league="Cup")
        target=game("second","2026-01-01","A","B",1,0,league="League")
        result=apply_h2h_filter([pick(target,"1:0")],[prior,target])
        self.assertEqual(result[0]["h2h_status"],"no_prior_h2h")

    def test_two_conflicting_recent_encounters_are_ambiguous(self):
        p=game("one","2025-08-01","A","B",1,0)
        q=game("two","2025-08-01","B","A",2,0)
        f=game("three","2026-01-01","A","B",1,0)
        result=apply_h2h_filter([pick(f,"1:0")],[p,q,f])
        self.assertEqual(result[0]["h2h_status"],"ambiguous_last_h2h")

    def test_no_reranking_after_failed_h2h(self):
        first=game("old","2025-06-01","A","B",0,0)
        selected=game("selected","2026-03-01","A","B",1,0)
        alternative=game("alternate","2026-03-01","C","D",1,0)
        out=apply_h2h_filter([pick(selected,"1:0")],[first,selected,alternative])
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["match_id"],"selected")
        self.assertEqual(out[0]["h2h_status"],"rejected_last_h2h_different_score")

    def test_reporting_never_invents_a_retained_pick(self):
        first=game("old","2025-06-01","A","B",1,0)
        selected=game("selected","2026-03-01","A","B",1,0)
        filtered=apply_h2h_filter([pick(selected,"1:0")],[first,selected])
        baseline={"days_with_at_least_one_hit":1}
        report=summarize_h2h(filtered,baseline)
        self.assertEqual(report["baseline_selections"],1)
        self.assertEqual(report["h2h_retained"],1)
        self.assertEqual(report["h2h_retained_hits"],1)
        self.assertEqual(report["h2h_winning_days"],1)
        self.assertEqual(report["by_month"]["2026-03"]["retained_selections"],1)
        self.assertEqual(report["by_score"]["1:0"]["retained"],1)


if __name__=="__main__":
    unittest.main()
