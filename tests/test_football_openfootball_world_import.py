import unittest
from scripts.football_openfootball_world_import import parse_txt, safe_source_url, import_history
from scripts.football_public_domain_prematch import historical_index

NIGERIA="""= Nigeria Professional League 2025/2026

▪ Matchday 1
  Fri Aug 22 2025
           Remo Stars FC              v Rivers United FC           1-1
  Sun Aug 24 2025
           Kano Pillars FC            v Enyimba FC                 0-0
  Sun Aug 31
           Rivers United FC           v Enyimba FC                 2-1
           Abia Warriors FC           v Bayelsa United FC          - -
"""
MOROCCO="""= Morocco | Botola Pro 1 2024/25
▪ Matchday 1
  Fri Aug 30 2024
    17:00  Difaâ d'el Jadida       v JS Soualem               1-1 (0-1)
    21:00  Maghrib de Fès          v Wydad AC                 1-0 (0-0)
  Sat Aug 31
    17:00  Raja Casablanca         v RS Berkane               0-1
  Wed Jan 15
    18:00  Ittihad Tanger          v Wydad AC                 1-1
"""
BRAZIL="""= Brasileiro Série A 2026
▪ Matchday 1
  Wed Jan 28 2026
    19:00  CA Mineiro              v SE Palmeiras             2-2 (1-1)
           Coritiba FBC            v RB Bragantino            0-1 (0-0)
  Thu Jan 29
    20:00  São Paulo FC            v CR Flamengo              2-1 (0-0)
  Fri Oct 15
           Santos FC               v Fluminense FC            4-1
"""

class OpenfootballTXTTests(unittest.TestCase):
    def test_nigeria_completed_and_year(self):
        rows,health=parse_txt(NIGERIA,league="Nigeria Professional Football League",
                              path="world/africa/nigeria/2025-26_ng1.txt")
        self.assertEqual(len(rows),3,health)
        self.assertEqual([r["match_date"] for r in rows],["2025-08-22","2025-08-24","2025-08-31"])
        self.assertEqual(rows[1]["home_score"],0)
        self.assertEqual(rows[1]["away_score"],0)
        self.assertEqual(len(rows[0]["source_id"]),64)
        self.assertTrue(all(len(r["source_id"])==64 for r in rows))
        self.assertNotIn("kickoff_utc",rows[0])
        self.assertEqual(rows[0]["time_precision"],"day")

    def test_morocco_accents_and_new_year(self):
        rows,health=parse_txt(MOROCCO,league="Botola Pro 1",
                              path="world/africa/morocco/2024-25_ma1.txt")
        self.assertEqual(len(rows),4,health)
        self.assertEqual(rows[-1]["match_date"],"2025-01-15")
        self.assertEqual(rows[1]["home_team"],"Maghrib de Fès")

    def test_brazil_single_calendar_year(self):
        rows,health=parse_txt(BRAZIL,league="Brasileiro Série A",
                              path="south-america/brazil/2026_br1.txt")
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[-1]["match_date"],"2026-10-15")
        self.assertEqual(rows[0]["home_score"],2)
        self.assertEqual(rows[0]["away_score"],2)

    def test_world_results_accepted_by_prematch_historical_index(self):
        records,_=parse_txt(NIGERIA,league="Nigeria Professional Football League",
                            path="world/africa/nigeria/2025-26_ng1.txt")
        teams,report=historical_index(records)
        self.assertEqual(report["valid_unique_matches"],3)
        self.assertEqual(report["source_warnings"].get("invalid_score_or_identity",0),0)
        self.assertIn(("nigeria professional football league","remo stars"),teams)

    def test_root_level_south_america_is_approved_not_path_traversal(self):
        self.assertIn("/south-america/master/brazil/2026_br1.txt",
                      safe_source_url("south-america","brazil","2026_br1.txt"))

    def test_allowlist_and_no_dynamic_host(self):
        self.assertIn("raw.githubusercontent.com/openfootball/world/master/africa/nigeria",safe_source_url("world","africa/nigeria","2025-26_ng1.txt"))
        for repo,folder,name in (("private","africa/nigeria","2025-26_ng1.txt"),("world","../secrets","2025-26_ng1.txt"),("world","africa/nigeria","evil.json")):
            with self.assertRaises(ValueError):
                safe_source_url(repo,folder,name)

    def test_download_budget_fake(self):
        class FakeResponse:
            text=NIGERIA
            def raise_for_status(self):pass
        class Fake:
            def __init__(self):self.urls=[]
            def get(self,url,**kwargs):self.urls.append(url);return FakeResponse()
        fake=Fake()
        rows,report=import_history(max_files=2,session=fake)
        self.assertEqual(report["files_attempted"],2)
        self.assertEqual(report["download_or_parse_failures"],0)
        self.assertEqual(len(rows),6)
        self.assertEqual(len(fake.urls),2)
        self.assertEqual(report["api_calls_to_limited_football_providers"],0)

if __name__=="__main__":
    unittest.main()
