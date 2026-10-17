"""Tests hors réseau du média football Mr XPRONOS."""
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).resolve().parents[1] / "scripts" / "football_channel.py"
spec = importlib.util.spec_from_file_location("football_channel", TARGET)
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
m = module

NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)


def event(ident, start=NOW, status="notstarted", hs=None, a_s=None):
    return {
        "id": ident, "event_date": start.isoformat(), "status": status,
        "home_team": {"id": 1, "name": "Arsenal",
                      "logo": "https://example.com/arsenal.png"},
        "away_team": {"id": 2, "name": "Chelsea",
                      "logo": "https://example.com/chelsea.png"},
        "league_name": "Premier League",
        "home_score": hs, "away_score": a_s,
    }


class FootballChannelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.history = m.History(Path(self.directory.name) / "history.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_live_popularity_filter_is_strict(self):
        def fixture(home, away, competition):
            row = event("pop-test")
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            return row

        self.assertTrue(m.popular_live_match(fixture("Liverpool", "LASK", "UEFA Champions League")))
        self.assertTrue(m.popular_live_match(fixture("Arsenal", "Chelsea", "Friendly")))
        self.assertTrue(m.popular_live_match(fixture("Togo", "Benin", "Friendly")))
        self.assertTrue(m.popular_live_match(fixture("Senegal", "Benin", "Africa Cup of Nations AFCON")))
        self.assertFalse(m.popular_live_match(fixture("Bournemouth", "Fulham", "Premier League")))
        self.assertTrue(m.popular_live_match(fixture("Feyenoord", "Como", "UEFA Champions League")))
        self.assertFalse(m.popular_live_match(fixture("Arsenal U19", "Chelsea U19", "UEFA Youth League")))

    def test_grand_club_beats_regional_final_for_live_fil_rouge(self):
        def fixture(ident, home, away, competition, **extra):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            row.update(extra)
            return row

        grand_club = fixture("real", "Real Madrid", "Getafe", "La Liga")
        regional_final = fixture(
            "regional-final", "Club Alpha", "Club Beta", "Regional Cup",
            round_name="Final",
        )
        self.assertTrue(m.popular_live_match(grand_club))
        self.assertGreater(m.importance(grand_club), m.importance(regional_final))
        selected = m.select_popular_live_matches(
            [regional_final, grand_club], max_per_competition=2, max_total=1
        )
        self.assertEqual([row["id"] for row in selected], ["real"])
        self.assertEqual(m.live_tracking_reason(grand_club), "grand_club")

    def test_two_grand_clubs_get_choc_tracking_reason(self):
        row = event("clasico")
        row["home_team"]["name"] = "Real Madrid"
        row["away_team"]["name"] = "Barcelona"
        row["league_name"] = "La Liga"
        self.assertEqual(m.live_tracking_reason(row), "choc_grands_clubs")
        self.assertTrue(m.popular_live_match(row))

    def test_live_can_follow_four_major_matches_same_competition(self):
        def fixture(ident, home, away):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = "UEFA Champions League"
            return row

        matches = [
            fixture("m1", "Real Madrid", "Liverpool"),
            fixture("m2", "PSG", "Bayern Munich"),
            fixture("m3", "Arsenal", "Chelsea"),
            fixture("m4", "Inter Milan", "Juventus"),
        ]
        selected = m.select_popular_live_matches(
            matches, max_per_competition=4, max_total=4, dominance_gap=0
        )
        self.assertEqual(len(selected), 4)
        self.assertEqual({row["id"] for row in selected}, {"m1", "m2", "m3", "m4"})

    def test_major_final_without_big_club_can_enter_live(self):
        row = event("final")
        row["home_team"]["name"] = "Club Alpha"
        row["away_team"]["name"] = "Club Beta"
        row["league_name"] = "UEFA Champions League"
        row["round_name"] = "Final"
        self.assertTrue(m.popular_live_match(row))
        self.assertGreaterEqual(m.high_stakes_bonus(row), 100)

    def test_live_ranking_keeps_top_two_per_competition(self):
        def fixture(ident, home, away, competition):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            return row

        matches = [
            fixture("ucl-1", "Real Madrid", "Liverpool", "UEFA Champions League"),
            fixture("ucl-2", "PSG", "Bayern", "UEFA Champions League"),
            fixture("ucl-3", "Feyenoord", "Como", "UEFA Champions League"),
            fixture("uel-1", "Manchester United", "Porto", "UEFA Europa League"),
            fixture("uel-2", "Ajax", "Benfica", "UEFA Europa League"),
            fixture("epl-1", "Bournemouth", "Fulham", "Premier League"),
        ]
        selected = m.select_popular_live_matches(
            matches, max_per_competition=2, max_total=6
        )
        ids = {row["id"] for row in selected}
        self.assertIn("ucl-1", ids)
        self.assertIn("ucl-2", ids)
        self.assertNotIn("ucl-3", ids)
        self.assertIn("uel-1", ids)
        self.assertIn("uel-2", ids)
        self.assertNotIn("epl-1", ids)
        ucl = [row for row in selected if m.live_competition_key(row) == "uefa-champions-league"]
        self.assertEqual(len(ucl), 2)

    def test_live_ranking_exact_ucl_four_match_scenario(self):
        def fixture(ident, home, away, competition):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            return row

        matches = [
            fixture("ucl-real-liv", "Real Madrid", "Liverpool", "UEFA Champions League"),
            fixture("ucl-psg-bayern", "PSG", "Bayern", "UEFA Champions League"),
            fixture("ucl-fey-como", "Feyenoord", "Como", "UEFA Champions League"),
            fixture("ucl-ben-ajax", "Benfica", "Ajax", "UEFA Champions League"),
        ]
        selected = m.select_popular_live_matches(
            matches, max_per_competition=2, max_total=6
        )
        self.assertEqual(
            [row["id"] for row in selected],
            ["ucl-real-liv", "ucl-psg-bayern"],
        )

    def test_uefa_and_caf_champions_league_have_separate_quotas(self):
        def fixture(ident, home, away, competition):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            return row

        uefa = fixture("uefa", "Real Madrid", "Liverpool", "UEFA Champions League")
        caf = fixture("caf", "Al Ahly", "Wydad", "CAF Champions League")
        self.assertEqual(m.live_competition_key(uefa), "uefa-champions-league")
        self.assertEqual(m.live_competition_key(caf), "caf-champions-league")
        self.assertGreater(m.live_popularity_score(uefa), m.live_popularity_score(caf))

        selected = m.select_popular_live_matches(
            [uefa, caf], max_per_competition=1, max_total=2
        )
        self.assertEqual({row["id"] for row in selected}, {"uefa", "caf"})

    def test_ambiguous_champions_league_is_not_automatically_uefa(self):
        row = event("local-champions")
        row["home_team"]["name"] = "Dalian Juxing Shengheng"
        row["away_team"]["name"] = "Wuhan Lianzhen"
        row["league_name"] = "Chinese Football Champions League"

        self.assertNotEqual(m.live_competition_key(row), "uefa-champions-league")
        self.assertEqual(m.live_competition_weight(row), 0)
        self.assertFalse(m.popular_live_match(row))

    def test_foreign_premier_league_does_not_inherit_english_prestige(self):
        row = event("libya")
        row["home_team"]["name"] = "Al Ahly Benghazi"
        row["away_team"]["name"] = "Al-Tahaddi"
        row["league_name"] = "Libyan Premier League"

        self.assertNotEqual(m.live_competition_key(row), "premier-league")
        self.assertEqual(m.live_competition_weight(row), 0)
        self.assertFalse(m.popular_live_match(row))

    def test_live_ranking_has_global_cap_and_togo_priority(self):
        def fixture(ident, home, away, competition):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = competition
            return row

        matches = [
            fixture("togo", "Togo", "Benin", "Friendly"),
            fixture("ucl", "Real Madrid", "Liverpool", "UEFA Champions League"),
            fixture("epl", "Arsenal", "Chelsea", "Premier League"),
            fixture("liga", "Barcelona", "Atletico", "La Liga"),
        ]
        selected = m.select_popular_live_matches(
            matches, max_per_competition=2, max_total=2
        )
        ids = {row["id"] for row in selected}
        self.assertEqual(len(selected), 2)
        self.assertIn("togo", ids)

    def test_atletico_alias_only_targets_atletico_madrid(self):
        nacional = event("nacional")
        nacional["home_team"]["name"] = "Atletico Nacional Medellin"
        nacional["away_team"]["name"] = "Deportivo Independiente Medellin"
        nacional["league_name"] = "Colombia Primera A"

        madrid = event("madrid")
        madrid["home_team"]["name"] = "Atletico Madrid"
        madrid["away_team"]["name"] = "Getafe"
        madrid["league_name"] = "La Liga"

        nacional_breakdown = m.live_popularity_breakdown(nacional)
        madrid_breakdown = m.live_popularity_breakdown(madrid)
        self.assertEqual(nacional_breakdown["home"], 0)
        self.assertGreater(madrid_breakdown["home"], 0)
        self.assertFalse(m.popular_live_match(nacional))
        self.assertTrue(m.popular_live_match(madrid))

    def test_live_ranking_dominance_can_keep_only_one_match(self):
        def fixture(ident, home, away):
            row = event(ident)
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = "UEFA Champions League"
            return row

        selected = m.select_popular_live_matches(
            [
                fixture("huge", "Real Madrid", "Liverpool"),
                fixture("weak", "Club Alpha", "Club Beta"),
            ],
            max_per_competition=2,
            max_total=6,
            dominance_gap=45,
        )
        self.assertEqual([row["id"] for row in selected], ["huge"])

    def test_locked_match_survives_later_ranking(self):
        weak = event("locked")
        weak["home_team"]["name"] = "Feyenoord"
        weak["away_team"]["name"] = "Como"
        weak["league_name"] = "UEFA Champions League"
        weak["ranking_locked"] = True

        huge = event("huge")
        huge["home_team"]["name"] = "Real Madrid"
        huge["away_team"]["name"] = "Liverpool"
        huge["league_name"] = "UEFA Champions League"

        selected = m.select_popular_live_matches(
            [huge, weak], max_per_competition=2, max_total=6, dominance_gap=0
        )
        self.assertEqual({row["id"] for row in selected}, {"huge", "locked"})
        self.assertTrue(next(row for row in selected if row["id"] == "locked")["ranking_locked"])

    def test_live_popularity_breakdown_matches_score(self):
        row = event("breakdown")
        row["home_team"]["name"] = "Real Madrid"
        row["away_team"]["name"] = "Liverpool"
        row["league_name"] = "UEFA Champions League"
        breakdown = m.live_popularity_breakdown(row)
        self.assertEqual(breakdown["total"], m.live_popularity_score(row))
        self.assertGreater(breakdown["competition"], 0)
        self.assertGreater(breakdown["home"], 0)
        self.assertGreater(breakdown["away"], 0)
        self.assertGreater(breakdown["clubs_bonus"], 0)

    def test_flash_utilise_news_site_et_image_reelle(self):
        old_root = m.ROOT
        try:
            m.ROOT = Path(self.directory.name)
            image = m.ROOT / "assets/images/footnews/test-news.webp"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"fake-test-image")
            articles = [{
                "slug": "test-news",
                "title": "Arsenal avance sur un dossier important",
                "telegram_summary": "Les discussions progressent et une nouvelle étape a été franchie.",
                "published": (NOW - timedelta(hours=1)).isoformat(),
                "source": "Foot Mercato",
                "source_url": "https://example.com/source",
                "site_url": "https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=test-news",
                "category": "Mercato",
                "image": "assets/images/footnews/test-news.webp",
                "image_origin": "source",
            }]
            post = m.flash(articles, self.history, NOW)
            self.assertIsNotNone(post)
            self.assertIn("<b>🚨 Arsenal avance sur un dossier important</b>", post.text)
            self.assertNotIn("<blockquote>", post.text)
            self.assertNotIn("Lire l’info complète", post.text)
            self.assertIn("(Foot Mercato)", post.text)
            self.assertEqual(post.image_path, "assets/images/footnews/test-news.webp")
            self.assertIsNone(post.keyboard)
            self.assertIsNotNone(post.card)
            self.assertEqual(post.card["image_path"], "assets/images/footnews/test-news.webp")
            self.history.mark(post.key, post.category, NOW)
            self.assertIsNone(m.flash(articles, self.history, NOW))
        finally:
            m.ROOT = old_root


    def test_flash_conserve_les_lignes_numerotees_du_resume(self):
        old_root=m.ROOT
        try:
            m.ROOT=Path(self.directory.name)
            image=m.ROOT/"assets/images/footnews/list-news.webp"
            image.parent.mkdir(parents=True,exist_ok=True)
            image.write_bytes(b"fake-test-image")
            articles=[{
                "slug":"list-news",
                "title":"Trois informations avant le match",
                "telegram_summary":"1: Premier point important\n2. Deuxième point important\n3) Troisième point important",
                "published":(NOW-timedelta(hours=1)).isoformat(),
                "source":"Foot Mercato",
                "site_url":"https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=list-news",
                "category":"Actualité",
                "image":"assets/images/footnews/list-news.webp",
                "image_origin":"source",
            }]
            post=m.flash(articles,self.history,NOW)
            self.assertIsNotNone(post)
            self.assertIn("1: Premier point important\n2. Deuxième point important\n3) Troisième point important",post.text)
        finally:
            m.ROOT=old_root

    def test_flash_ajoute_corroboration_espn_sans_remplacer_la_source(self):
        old_root = m.ROOT
        try:
            m.ROOT = Path(self.directory.name)
            image = m.ROOT / "assets/images/footnews/espn-news.webp"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"fake-test-image")
            articles = [{
                "slug": "espn-news",
                "title": "Arsenal avance sur un dossier important",
                "telegram_summary": "Le média source rapporte une nouvelle étape dans le dossier.",
                "published": (NOW - timedelta(hours=1)).isoformat(),
                "source": "Foot Mercato",
                "source_url": "https://example.com/source",
                "site_url": "https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=espn-news",
                "category": "Mercato",
                "image": "assets/images/footnews/espn-news.webp",
                "image_origin": "source",
                "espn_verification": {
                    "provider": "ESPN",
                    "url": "https://www.espn.com/soccer/story/_/id/123/test",
                    "score": 0.5,
                    "matched_terms": ["arsenal", "dossier"],
                },
            }]
            post = m.flash(articles, self.history, NOW)
            self.assertIsNotNone(post)
            self.assertEqual(post.verification["type"], "news")
            self.assertEqual(post.verification["matched_terms"], ["arsenal", "dossier"])
            self.assertIn("(Foot Mercato)", post.text)
            self.assertNotIn("repérée chez ESPN", post.text)
            self.assertIsNone(post.keyboard)
        finally:
            m.ROOT = old_root

    @patch.object(m, "verify_espn_fixtures_before_publish")
    def test_preflight_avant_match_applique_horaire_et_stade_espn(self, verify):
        verify.return_value = {
            "ok": True,
            "quality": 100,
            "reason": "confirmed",
            "covered": 1,
            "missing": 0,
            "total": 1,
            "verified": [{
                "home": "Arsenal",
                "away": "Chelsea",
                "event_date": "2026-10-10T18:30:00+00:00",
                "venue": "Emirates Stadium",
            }],
            "enrichment": {},
        }
        item = m.Publication(
            "avant_match",
            "avant_match:1",
            "<p>Avant-match</p>",
            card={"home": "Arsenal", "away": "Chelsea", "time": "18:00"},
            verification={
                "type": "fixture_list",
                "kind": "avant_match",
                "fixtures": [{
                    "home": "Arsenal",
                    "away": "Chelsea",
                    "event_date": "2026-10-10T18:00:00+00:00",
                }],
            },
        )
        sender = type("S", (), {"session": object()})()
        self.assertTrue(m.espn_preflight(sender, item))
        self.assertEqual(item.card["time"], "18h30")
        self.assertIn("Emirates Stadium", item.text)

    @patch.object(m, "verify_espn_before_publish")
    def test_preflight_mi_temps_ajoute_stats_espn_fraiches(self, verify):
        verify.return_value = {
            "ok": True,
            "quality": 100,
            "reason": "confirmed",
            "event_id": "401",
            "enrichment": {
                "stats": {
                    "home": {"shots_on_target": "5", "corners": "4", "possession": "61%"},
                    "away": {"shots_on_target": "2", "corners": "1", "possession": "39%"},
                },
                "info": {},
            },
        }
        item = m.Publication(
            "mi_temps",
            "ht:401",
            "<p>Mi-temps</p>",
            verification={"event_id": "401", "kind": "mi_temps"},
        )
        sender = type("S", (), {"session": object()})()
        self.assertTrue(m.espn_preflight(sender, item))
        self.assertIn("Données ESPN à la pause", item.text)
        self.assertIn("Tirs cadrés", item.text)
        self.assertIn("5 – 2", item.text)

    @patch.object(m, "verify_espn_before_publish")
    def test_preflight_match_bloque_si_espn_ne_confirme_pas(self, verify):
        verify.return_value = {"ok": False, "quality": 0, "reason": "score_mismatch"}
        item = m.Publication(
            "goal", "goal:401", "goal",
            verification={"event_id": "401", "kind": "goal"},
        )
        sender = type("S", (), {"session": object()})()
        self.assertFalse(m.espn_preflight(sender, item))
        verify.assert_called_once()

    @patch.object(m, "_verify_espn_news_reference")
    def test_preflight_news_reste_non_bloquant_si_espn_page_indisponible(self, verify):
        verify.return_value = {"ok": False, "quality": 75, "reason": "espn_news_page_unavailable"}
        item = m.Publication(
            "flash", "flash:abc", "news",
            verification={
                "type": "news",
                "url": "https://www.espn.com/soccer/story/_/id/123/test",
                "matched_terms": ["arsenal"],
            },
        )
        sender = type("S", (), {"session": object()})()
        self.assertTrue(m.espn_preflight(sender, item))
        verify.assert_called_once()

    def test_fenetres_editoriales_production(self):
        self.assertTrue(m.in_editorial_window(
            "programme", datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc)
        ))
        self.assertFalse(m.in_editorial_window(
            "programme", datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
        ))
        self.assertTrue(m.in_editorial_window(
            "flash_morning", datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
        ))
        self.assertTrue(m.in_editorial_window(
            "statistique", datetime(2026, 10, 10, 12, 30, tzinfo=timezone.utc)
        ))
        self.assertTrue(m.in_editorial_window(
            "sondage", datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
        ))

    def test_plage_active_production_24h(self):
        for hour in (0, 6, 7, 12, 23):
            self.assertTrue(m.production_active(
                datetime(2026, 10, 10, hour, 30, tzinfo=timezone.utc)
            ))

    def test_programme_transporte_le_controle_espn_des_affiches(self):
        match = event(77, NOW + timedelta(hours=3))
        post = m.programme([match], NOW.date(), as_of=NOW)
        self.assertIsNotNone(post)
        self.assertEqual(post.verification["type"], "fixture_list")
        self.assertEqual(post.verification["kind"], "programme")
        self.assertEqual(post.verification["fixtures"][0]["home"], "Arsenal")
        self.assertEqual(post.verification["fixtures"][0]["away"], "Chelsea")

    @patch.object(m, "has_two_team_logos", return_value=True)
    @patch.object(m, "team_visual_url", return_value="https://example.com/logo.png")
    def test_avant_match_transporte_le_controle_espn(self, _logo, _has_logos):
        match = event(78, NOW + timedelta(hours=2))
        post = m.avant_match([match], self.history, NOW, [])
        self.assertIsNotNone(post)
        self.assertEqual(post.verification["type"], "fixture_list")
        self.assertEqual(post.verification["kind"], "avant_match")
        self.assertTrue(post.verification["fixtures"][0]["event_date"].endswith("+00:00"))

    @patch.object(m, "has_two_team_logos", return_value=True)
    @patch.object(m, "team_visual_url", return_value="https://example.com/logo.png")
    def test_resultat_transporte_score_dans_le_controle_espn(self, _logo, _has_logos):
        match = event(79, NOW - timedelta(hours=2), "finished", 3, 1)
        post = m.resultat([match], self.history, NOW)
        self.assertIsNotNone(post)
        self.assertEqual(post.verification["kind"], "resultat")
        self.assertEqual(post.verification["fixtures"][0]["score"], "3-1")

    def test_programme_et_horaires_togo(self):
        post = m.programme([event(1, NOW + timedelta(hours=4))], NOW.date())
        self.assertIsNotNone(post)
        self.assertEqual(post.card["matches"][0]["time"], "19h00")
        self.assertEqual(post.card["matches"][0]["home"], "Arsenal")
        self.assertEqual(post.card["matches"][0]["role"], "match_du_jour")
        self.assertIn("Match du jour", post.text)
        self.assertIn("Arsenal", post.text)

    def test_programme_becomes_exact_daily_follow_plan(self):
        row = event("plan-1", NOW + timedelta(hours=4))
        post = m.programme([row], NOW.date(), as_of=NOW)
        self.assertIsNotNone(post)
        count = self.history.set_programme_plan(post, NOW)
        self.assertEqual(count, 1)
        planned = self.history.plan_for_event(row, NOW)
        self.assertIsNotNone(planned)
        self.assertEqual(planned["rank"], 1)
        self.assertEqual(planned["role"], "match_du_jour")

    def test_programme_caps_follow_plan_at_four_matches(self):
        rows = []
        names = [
            ("Real Madrid", "Getafe"),
            ("Barcelona", "Sevilla"),
            ("Liverpool", "Everton"),
            ("Arsenal", "West Ham"),
            ("Bayern Munich", "Mainz"),
        ]
        for index, (home, away) in enumerate(names):
            row = event("p" + str(index), NOW + timedelta(hours=3, minutes=index))
            row["home_team"]["name"] = home
            row["away_team"]["name"] = away
            row["league_name"] = "Premier League" if index in (2, 3) else "Football"
            rows.append(row)
        post = m.programme(rows, NOW.date(), as_of=NOW)
        self.assertIsNotNone(post)
        self.assertEqual(len(post.card["matches"]), 4)
        self.assertEqual(len(post.verification["fixtures"]), 4)

    def test_prune_removes_only_unopened_unplanned_tracks(self):
        planned_event = event("planned", NOW + timedelta(hours=3))
        post = m.programme([planned_event], NOW.date(), as_of=NOW)
        self.assertIsNotNone(post)
        self.history.set_programme_plan(post, NOW)

        legacy = event("legacy", NOW + timedelta(hours=2))
        legacy["home_team"]["name"] = "Everton"
        legacy["away_team"]["name"] = "Chelsea"
        legacy_ref = m.followup.track(self.history.followed, legacy, NOW, reason="legacy")

        opened = event("opened", NOW + timedelta(hours=2))
        opened["home_team"]["name"] = "PSG"
        opened["away_team"]["name"] = "Marseille"
        opened_ref = m.followup.track(self.history.followed, opened, NOW, reason="legacy")
        m.followup.mark_publication(self.history.followed, opened_ref, "avant_match", NOW)

        removed = self.history.prune_unopened_unplanned(NOW)
        self.assertEqual(removed, 1)
        self.assertNotIn(legacy_ref, self.history.followed)
        self.assertIn(opened_ref, self.history.followed)

    def test_programme_does_not_fill_with_unknown_matches(self):
        row = event("small", NOW + timedelta(hours=4))
        row["home_team"]["name"] = "Ilves"
        row["away_team"]["name"] = "SJK"
        row["league_name"] = "Veikkausliiga"
        self.assertIsNone(m.programme([row], NOW.date(), as_of=NOW))

    def test_resultat_uniquement_apres_confirmation(self):
        sample = [
            event(1, NOW - timedelta(hours=3), "notstarted", 2, 1),
            event(2, NOW - timedelta(hours=3), "finished", 2, 1),
        ]
        post = m.resultat(sample, self.history, NOW)
        self.assertEqual(post.key, "resultat:2")
        self.assertEqual(post.card["scores"], (2, 1))
        self.assertNotIn("2 – 1", post.text)
        self.history.mark(post.key, post.category, NOW)
        self.assertIsNone(m.resultat(sample, self.history, NOW))

    def test_resultat_sans_deux_logos_est_ignore(self):
        sample = event(9, NOW - timedelta(hours=3), "finished", 1, 0)
        sample["home_team"].pop("logo", None)
        sample["away_team"].pop("logo", None)
        with patch.object(m, "_remote_team_logo", return_value=""):
            self.assertIsNone(m.resultat([sample], self.history, NOW))


    def test_avant_match_masque_forme_si_aucune_donnee(self):
        post = m.avant_match([event(4, NOW + timedelta(hours=2))],
                             self.history, NOW, [])
        self.assertNotIn("indisponible", post.text.lower())
        self.assertNotIn("Forme récente", post.text)
        self.assertEqual(post.key, "avant_match:4")
        self.assertIsNotNone(post.card)
        self.assertEqual(post.card["home"], "Arsenal")
        self.assertEqual(post.card["home_form"], "")
        self.assertEqual(post.card["away_form"], "")

    def test_forme_calcule_les_cinq_derniers_matchs_et_points(self):
        before = NOW + timedelta(hours=2)
        history = [
            event(101, NOW - timedelta(days=1), "finished", 2, 0),
            event(102, NOW - timedelta(days=2), "finished", 1, 1),
            event(103, NOW - timedelta(days=3), "finished", 0, 1),
            event(104, NOW - timedelta(days=4), "finished", 3, 1),
            event(105, NOW - timedelta(days=5), "finished", 2, 2),
            event(106, NOW - timedelta(days=6), "finished", 5, 0),
        ]
        value = m.form(1, "Arsenal", history, before)
        self.assertEqual(value, "V • N • D • V • N  |  8/15 pts")

    def test_statistique_issue_de_scores_termines(self):
        old = NOW - timedelta(days=1, hours=4)
        post = m.statistique([event(1, old, "finished", 4, 3),
                              event(2, old, "notstarted", 9, 8)], old.date())
        self.assertEqual(post.card["score"], "4-3")
        self.assertIn("7 buts", post.text)
        self.assertNotIn("17 buts", post.text)
        self.assertIn("<blockquote>", post.text)

    def test_sondage_fournit_options(self):
        post = m.sondage([event(12, NOW + timedelta(hours=3))],
                         self.history, NOW)
        self.assertEqual(post.category, "sondage")
        self.assertEqual(len(post.poll[1]), 3)
        self.assertTrue(any("Match nul" in option for option in post.poll[1]))

    def test_historique_persistant(self):
        self.history.mark("flash:unique", "flash", NOW)
        self.history.save(NOW)
        second = m.History(self.history.path)
        self.assertTrue(second.seen("flash:unique"))
        self.assertEqual(second.count("flash", NOW.date()), 1)

    def test_ne_jamais_publier_sans_canal_specifique(self):
        with patch.dict("os.environ", {"FOOTBALL_NEWS_CHAT_ID": "",
                                       "FOOTBALL_NEWS_BOT_TOKEN": "fake"}, clear=True):
            with self.assertRaises(RuntimeError):
                m.Sender()
            m.Sender(dry_run=True)

    def test_photo_payload_ne_contient_pas_text(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {"message_id": 201}}
        sample = m.programme([event(17, NOW + timedelta(hours=3))], NOW.date(),
                             as_of=NOW)
        from PIL import Image
        import programme_styles as ps
        fake_logo = Image.new("RGBA", (48, 48), (255, 255, 255, 255))
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-10010000222",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "0",
        }), patch.object(ps, "load_logo", return_value=fake_logo):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            result = sender.send(sample)
        self.assertEqual(result, 201)
        calls = sender.session.post.call_args_list
        self.assertGreaterEqual(len(calls), 1)
        kwargs = calls[-1].kwargs
        self.assertIn("coupon_photo", kwargs["files"])
        self.assertIn("rich_message", kwargs["data"])
        self.assertIn("MATCHS DU JOUR", kwargs["data"]["rich_message"])
        self.assertNotIn("text", kwargs["data"])

    def test_composition_canonique_retablit_heure_depuis_iso(self):
        signal = {
            "kind": "composition",
            "key": "composition:canonical",
            "home": "Inter Miami CF",
            "away": "New York City FC",
            "league": "Football",
            "source": "ESPN",
            "kickoff": "2026-10-14T23:30:00+00:00",
            "home_logo": "https://a.espncdn.com/i/teamlogos/soccer/500/20232.png",
            "away_logo": "https://a.espncdn.com/i/teamlogos/soccer/500/17606.png",
            "lineups": {
                "home": [f"Home {i}" for i in range(1, 12)],
                "away": [f"Away {i}" for i in range(1, 12)],
            },
            "lineup_home_hash": "homehash",
            "lineup_away_hash": "awayhash",
            "espn_event_id": "761861",
            "espn_url": "https://www.espn.com/soccer/match/_/gameId/761861",
        }
        post = m.lifecycle_publication(signal)
        self.assertIsNotNone(post)
        self.assertEqual(post.card["time"], "23h30")

    def test_sender_flash_avec_card_envoie_image_preparee_sans_renderer_flash(self):
        import os
        from unittest.mock import Mock
        from PIL import Image
        old_root = m.ROOT
        try:
            m.ROOT = Path(self.directory.name)
            media = m.ROOT / "assets/images/footnews/flash-ready.webp"
            media.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (24, 24), "white").save(media, "WEBP")
            item = m.Publication(
                "flash", "flash:ready", "<b>Flash</b>",
                image_path="assets/images/footnews/flash-ready.webp",
                card={"title": "Metadata only", "source": "RSS"},
            )
            with patch.dict(os.environ, {
                "FOOTBALL_NEWS_CHAT_ID": "-1001",
                "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
                "FOOTBALL_REQUIRE_COMMENTS": "0",
            }), patch.object(m, "post_photo", return_value=444) as photo, \
                 patch("football_cards.render_card") as renderer:
                sender = m.Sender()
                sender.verify_discussion = Mock(return_value=None)
                result = sender.send(item)
            self.assertEqual(result, 444)
            photo.assert_called_once()
            renderer.assert_not_called()
        finally:
            m.ROOT = old_root

    def test_publication_outbox_roundtrip_conserve_toutes_les_etapes(self):
        item = m.Publication(
            "quiz", "quiz:roundtrip", "<b>Question</b>",
            poll=("Question ?", ["A", "B"]),
            card={"question": "Question ?", "score": "1-0"},
            keyboard={"inline_keyboard": [[{"text": "Lire", "url": "https://example.com"}]]},
            poll_type="quiz",
            correct_option_ids=[1],
            poll_explanation="Réponse B",
            poll_description="Description",
            poll_shuffle=True,
            poll_allows_revoting=False,
            verification={"kind": "quiz"},
        )
        restored = m.publication_from_payload(m.publication_payload(item))
        self.assertIsNotNone(restored)
        self.assertEqual(restored.category, item.category)
        self.assertEqual(restored.key, item.key)
        self.assertEqual(restored.poll, item.poll)
        self.assertEqual(restored.card, item.card)
        self.assertEqual(restored.correct_option_ids, [1])
        self.assertFalse(restored.poll_allows_revoting)

    def test_outbox_claim_refuse_un_evenement_deja_reclame(self):
        from unittest.mock import Mock
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "can_send": False,
            "status": "claimed",
            "delivery_phase": "pending",
            "attempts": 1,
        }
        session = Mock()
        session.post.return_value = response
        with patch.dict("os.environ", {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service",
        }):
            ledger = m.RemotePublicationLedger(session, enabled=True)
            claim = ledger.claim(m.Publication("goal", "goal:locked", "goal"), NOW)
        self.assertFalse(claim["can_send"])
        self.assertIn("/rpc/actu_foot_claim_publication", session.post.call_args.args[0])

    def test_outbox_hydrate_ancienne_composition_depuis_timeline_canonique(self):
        from unittest.mock import Mock
        item = m.Publication(
            "composition", "composition:legacy", "<b>Composition</b>",
            card={
                "home": "Inter Miami CF",
                "away": "New York City FC",
                "competition": "Football",
                "source": "ESPN",
                "time": "",
                "home_logo": "https://example.com/home.png",
                "away_logo": "https://example.com/away.png",
                "home_players": [f"Home {i}" for i in range(1, 12)],
                "away_players": [f"Away {i}" for i in range(1, 12)],
                "canonical_event_key": "composition:legacy",
            },
        )
        get_response = Mock()
        get_response.raise_for_status.return_value = None
        get_response.json.return_value = [{
            "payload": {"kickoff": "2026-10-14T23:30:00+00:00"}
        }]
        patch_response = Mock()
        patch_response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = get_response
        session.patch.return_value = patch_response
        with patch.dict("os.environ", {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service",
        }):
            ledger = m.RemotePublicationLedger(session, enabled=True)
            restored = ledger._hydrate_legacy_item(item)
        self.assertEqual(restored.card["time"], "23h30")
        session.get.assert_called_once()
        session.patch.assert_called_once()
        saved = session.patch.call_args.kwargs["json"]["payload"]
        self.assertEqual(saved["card"]["time"], "23h30")

    def test_sender_poll_reprend_apres_media_sans_dupliquer_image(self):
        import os
        from unittest.mock import Mock
        from PIL import Image
        graphic = Path(self.directory.name) / "poll.png"
        Image.new("RGB", (20, 20), "white").save(graphic)
        poll_response = Mock()
        poll_response.status_code = 200
        poll_response.raise_for_status.return_value = None
        poll_response.json.return_value = {"ok": True, "result": {"message_id": 222}}
        item = m.Publication(
            "sondage", "sondage:resume", "<b>Vote</b>",
            poll=("Qui gagne ?", ["Arsenal", "Chelsea"]),
            card={"question": "Qui gagne ?"},
        )
        checkpoints = []
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "0",
        }), patch("football_cards.render_card", return_value=graphic), \
             patch.object(m, "post_photo", return_value=111) as photo, \
             patch.object(m, "_post_rate_limited", return_value=poll_response) as send_poll:
            sender = m.Sender()
            sender.verify_discussion = Mock(return_value=None)
            result = sender.send(
                item,
                resume={"delivery_phase": "media_sent", "media_message_id": 111},
                progress_cb=lambda phase, mid: checkpoints.append((phase, mid)),
            )
        self.assertEqual(result, 222)
        photo.assert_not_called()
        send_poll.assert_called_once()
        self.assertEqual(checkpoints, [("poll_sent", 222)])

    def test_sender_single_sent_finalise_sans_renvoi(self):
        import os
        from unittest.mock import Mock
        item = m.Publication("flash", "flash:resume", "hello")
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "0",
        }), patch.object(m, "post_text") as post_text:
            sender = m.Sender()
            sender.verify_discussion = Mock(return_value=None)
            result = sender.send(
                item,
                resume={"delivery_phase": "single_sent", "media_message_id": 333},
            )
        self.assertEqual(result, 333)
        post_text.assert_not_called()

    def test_replay_outbox_reconstruit_evenement_canonique_absent(self):
        from unittest.mock import Mock
        item = m.Publication(
            "resultat", "resultat:legacy", "<b>Final</b>",
            card={
                "home": "Guastatoya",
                "away": "Antigua GFC",
                "league": "Liga Nacional",
                "scores": (1, 2),
                "source": "score confirmé",
                "fixture_key": "20261015:guastatoya:antigua-gfc",
                "canonical_event_key": "resultat:20261015:guastatoya:antigua-gfc",
            },
        )
        session = Mock()
        with patch.object(m, "confirm_canonical_live_event", side_effect=[False, True]) as confirm, \
             patch.object(m, "persist_canonical_live_events", return_value=[{"key": item.key}]) as persist:
            m.ensure_canonical_publication(session, item, replay=True, strict=True)
        self.assertEqual(confirm.call_count, 2)
        persist.assert_called_once()
        signal = persist.call_args.args[1][0]
        self.assertEqual(signal["kind"], "resultat_final")
        self.assertEqual(signal["score"], "1-2")

    def test_publication_fraiche_avec_canon_existant_ne_reconstruit_pas(self):
        from unittest.mock import Mock
        item = m.Publication(
            "goal", "goal:x", "goal",
            card={"home": "Arsenal", "away": "Chelsea", "canonical_event_key": "goal:x"},
        )
        session = Mock()
        with patch.object(m, "confirm_canonical_live_event", return_value=True) as confirm, \
             patch.object(m, "persist_canonical_live_events") as persist:
            m.ensure_canonical_publication(session, item, replay=False, strict=True)
        confirm.assert_called_once_with(session, "goal:x", strict=False)
        persist.assert_not_called()

    def test_resultat_fallback_valide_reconstruit_canonique_absent(self):
        from unittest.mock import Mock
        item = m.Publication(
            "resultat", "resultat:legacy", "<b>Final</b>",
            card={
                "home": "Guastatoya",
                "away": "Antigua GFC",
                "league": "Liga Nacional",
                "scores": (1, 2),
                "source": "score confirme",
                "fixture_key": "20261015:guastatoya:antigua-gfc",
                "canonical_event_key": "resultat:20261015:guastatoya:antigua-gfc",
            },
        )
        session = Mock()
        with patch.object(m, "confirm_canonical_live_event", side_effect=[False, True]) as confirm, \
             patch.object(m, "persist_canonical_live_events", return_value=[{"key": item.key}]) as persist:
            m.ensure_canonical_publication(session, item, replay=False, strict=True)
        self.assertEqual(confirm.call_count, 2)
        persist.assert_called_once()
        signal = persist.call_args.args[1][0]
        self.assertEqual(signal["kind"], "resultat_final")
        self.assertEqual(signal["score"], "1-2")

    def test_deliver_with_outbox_marque_echec_rejouable(self):
        from unittest.mock import Mock
        item = m.Publication("goal", "goal:retry", "goal")
        sender = Mock()
        sender.send.side_effect = RuntimeError("telegram 500")
        ledger = Mock()
        ledger.claim.return_value = {"can_send": True, "delivery_phase": "pending"}
        result = m.deliver_with_outbox(sender, ledger, item, NOW)
        self.assertFalse(result["sent"])
        self.assertTrue(result["error"])
        ledger.mark.assert_called()
        args, kwargs = ledger.mark.call_args
        self.assertEqual(args[1], "failed")
        self.assertEqual(kwargs["phase"], "pending")

    def test_deliver_with_outbox_quarantaine_timeout_ambigu(self):
        from unittest.mock import Mock
        import requests
        item = m.Publication("goal", "goal:uncertain", "goal")
        sender = Mock()
        sender.send.side_effect = requests.Timeout("timeout")
        ledger = Mock()
        ledger.claim.return_value = {"can_send": True, "delivery_phase": "pending"}
        result = m.deliver_with_outbox(sender, ledger, item, NOW)
        self.assertFalse(result["sent"])
        self.assertTrue(result["uncertain"])
        self.assertEqual(ledger.mark.call_args.args[1], "uncertain")

    def test_programme_exclut_un_match_deja_commence(self):
        sample = [event(1, NOW - timedelta(hours=1)),
                  event(2, NOW + timedelta(hours=2))]
        post = m.programme(sample, NOW.date(), as_of=NOW)
        self.assertEqual(len(post.card["matches"]), 1)

    def test_programme_ignore_match_sans_deux_logos(self):
        bad = event(41, NOW + timedelta(hours=2))
        bad["home_team"].pop("logo", None)
        bad["away_team"].pop("logo", None)
        good = event(42, NOW + timedelta(hours=3))
        with patch.object(m, "_remote_team_logo", return_value=""):
            post = m.programme([bad, good], NOW.date(), as_of=NOW)
        self.assertIsNotNone(post)
        self.assertEqual(len(post.card["matches"]), 1)
        self.assertEqual(post.card["matches"][0]["home"], "Arsenal")


    def test_live_test_exige_un_canal(self):
        import os
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
        }):
            with self.assertRaises(RuntimeError):
                m.run_live_test(NOW)


    def test_commentaires_exigent_linked_chat_id(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {"id": -1001, "title": "Canal"}}
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "1",
        }):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            with self.assertRaises(RuntimeError):
                sender.verify_discussion()

    def test_commentaires_detectent_le_groupe_lie(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {
            "id": -1001, "linked_chat_id": -100999
        }}
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "1",
        }):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            self.assertEqual(sender.verify_discussion(), -100999)
            self.assertEqual(sender.verify_discussion(), -100999)
            self.assertEqual(sender.session.post.call_count, 1)

    def test_appel_aux_commentaires_dans_les_posts(self):
        post = m.programme([event(31, NOW + timedelta(hours=2))], NOW.date(), as_of=NOW)
        self.assertIn("Quel match attendez-vous", post.text)
        self.assertNotIn("<blockquote>", post.text)
        poll = m.sondage([event(32, NOW + timedelta(hours=3))], self.history, NOW)
        self.assertIn("LE DÉBAT DU JOUR", poll.poll[0])


    def test_rotation_programme_lundi_dimanche(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        self.assertEqual(mod.style_for_day("12/10/2026"), 1)  # lundi
        self.assertEqual(mod.style_for_day("18/10/2026"), 7)  # dimanche

    def test_les_sept_styles_programme_se_generent(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        payload = {"day": "10/10/2026", "matches": [
            {"home": "Club Sportif International de Test", "away": "Olympique Exemple", "time": "17h30",
             "home_logo": "https://test/logo1.png", "away_logo": "https://test/logo2.png"},
            {"home": "Real Madrid", "away": "FC Barcelona", "time": "20h00",
             "home_logo": "https://test/logo1.png", "away_logo": "https://test/logo2.png"},
            {"home": "PSG", "away": "Marseille", "time": "21h00",
             "home_logo": "https://test/logo1.png", "away_logo": "https://test/logo2.png"},
            {"home": "Bayern Munich", "away": "Borussia Dortmund", "time": "15h30",
             "home_logo": "https://test/logo1.png", "away_logo": "https://test/logo2.png"},
            {"home": "Inter Milan", "away": "AC Milan", "time": "19h45",
             "home_logo": "https://test/logo1.png", "away_logo": "https://test/logo2.png"},
        ]}
        from PIL import Image
        fake_logo = Image.new("RGBA", (52, 52), (255, 255, 255, 255))
        with patch.object(mod, "load_logo", return_value=fake_logo):
            for style in range(1, 8):
                image = mod.render_programme(payload, style=style)
                self.assertEqual(image.size, (1080, 1080))
                self.assertEqual(image.mode, "RGB")

    def test_style_programme_invalide_refuse(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        with self.assertRaises(ValueError):
            mod.render_programme({"day": "10/10/2026", "matches": [
                {"home": "A", "away": "B", "time": "12h00"}
            ]}, style=8)


if __name__ == "__main__":
    unittest.main()
