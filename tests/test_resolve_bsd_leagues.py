"""Verified only: official BSD league_id -> non-invented competition labels."""
from __future__ import annotations
import unittest

from scripts.resolve_bsd_leagues import resolve_league_labels, event_label, league_id


def future(ident, *, name=None):
    return {"id":int(ident)*100 if ident is not None else 100, "status":"notstarted",
            "league_id":ident,"league_name":name,
            "home_team":"Example FC","away_team":"Away United",
            "event_date":"2026-11-03T21:00:00Z"}


class FakeClient:
    def __init__(self, payloads):
        self.payloads=payloads
        self.calls=[]
    def get_json(self,path,params=None,ttl=900):
        self.calls.append((path,params))
        if path not in self.payloads:
            raise ValueError("Missing provider endpoint")
        return self.payloads[path]


class TestLeagues(unittest.TestCase):
    def test_original_id_lookups_use_official_detail(self):
        e=[future(47),future(84)]
        c=FakeClient({"/leagues/47/":{"id":47,"name":"UEFA Champions League"},
                      "/leagues/84/":{"id":84,"name":"Première Ligue"}})
        out,audit=resolve_league_labels(e,[],c)
        self.assertEqual([event_label(r) for r in out],["UEFA Champions League","Première Ligue"])
        self.assertEqual(audit["official_league_labels_added"],2)
        self.assertEqual(audit["still_missing"],0)
        self.assertEqual(e[0]["league_name"],None)  # never mutate source

    def test_unambiguous_archived_provider_id_without_http(self):
        history=[{"id":1,"league_id":6,"league_name":"Ligue 1"}]
        c=FakeClient({})
        out,audit=resolve_league_labels([future(6)],history,c)
        self.assertEqual(event_label(out[0]),"Ligue 1")
        self.assertEqual(c.calls,[])

    def test_conflicting_archive_names_not_guessed(self):
        history=[{"league_id":6,"league_name":"Ligue 1"},
                 {"league_id":6,"league_name":"Autre championnat"}]
        c=FakeClient({})
        out,audit=resolve_league_labels([future(6)],history,c)
        self.assertEqual(event_label(out[0]),"")
        self.assertEqual(audit["still_missing"],1)

    def test_official_catalog_fallback_when_detail_unavailable(self):
        c=FakeClient({"/leagues/":{"results":[{"id":5,"name":"Champions League"}]}})
        out,audit=resolve_league_labels([future(5)],[],c)
        self.assertEqual(event_label(out[0]),"Champions League")
        self.assertEqual(audit["official_catalog_pages"],1)

    def test_no_generic_or_invalid_id(self):
        c=FakeClient({})
        out,audit=resolve_league_labels([future(None)],[],c)
        self.assertEqual(event_label(out[0]),"")
        self.assertEqual(audit["official_league_labels_added"],0)
        self.assertIsNone(league_id("0001"))


if __name__=="__main__":
    unittest.main()
