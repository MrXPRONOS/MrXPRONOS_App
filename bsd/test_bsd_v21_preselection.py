"""V2.1 intraday selection safety: pre-price quality floor, quote-independent ranking."""
import unittest
from dataclasses import replace
from bsd_markets import candidates_from_goals
from bsd_v2_core import choose_market
from bsd_v2_guardrails import V21_MIN_OVER15_CONSERVATIVE


class V21PreselectionTests(unittest.TestCase):
    def options(self, over15_probability):
        candidates=candidates_from_goals(1.4, 1.0)
        over15=next(c for c in candidates if c.key=="OVER_15")
        under35=next(c for c in candidates if c.key=="UNDER_35")
        return [replace(over15,probability=over15_probability),
                replace(under35,probability=.79)]

    def choose(self, candidates, *, protected, market_audit=None):
        kw={"min_probability":.7,"league_samples":600,"form_samples":12,
            "market_audit":market_audit}
        if protected:
            kw["selection_conservative_minimums"]={
                "OVER_15":V21_MIN_OVER15_CONSERVATIVE}
        return choose_market(candidates,**kw)

    def test_v21_disqualifies_over15_before_quotes_and_uses_next_football_rank(self):
        candidates=self.options(.84) # conservative .826: less than .85
        original,_=self.choose(candidates,protected=False)
        self.assertEqual(original["candidate"].key,"OVER_15")
        audit=[]
        selected,ranked=self.choose(candidates,protected=True,market_audit=audit)
        self.assertEqual(selected["candidate"].key,"UNDER_35")
        self.assertTrue(all(x["candidate"].key!="OVER_15" for x in ranked))
        self.assertTrue(any(x["key"]=="OVER_15" and
                            x["result"]=="below_publication_conservative_floor"
                            for x in audit))

    def test_high_confidence_over15_stays_available(self):
        selected,_=self.choose(self.options(.90),protected=True)
        self.assertEqual(selected["candidate"].key,"OVER_15")

    def test_quote_does_not_change_market_preselection(self):
        candidates=self.options(.84)
        quotes={"OU_1.5_OVER_FT":10.0,"OU_3.5_UNDER_FT":1.28}
        selected,_=choose_market(candidates,league_samples=600,form_samples=12,
            odds_by_market=quotes,require_odds=False,
            selection_conservative_minimums={"OVER_15":V21_MIN_OVER15_CONSERVATIVE})
        self.assertEqual(selected["candidate"].key,"UNDER_35")


if __name__=="__main__":
    unittest.main()
