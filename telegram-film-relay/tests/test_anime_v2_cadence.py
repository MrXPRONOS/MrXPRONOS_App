"""Safely record channel claims of episode periodicity, including GIF labels."""
from __future__ import annotations
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from film_relay.anime_cadence import cadence_hint, cadence_from_message
from film_relay.anime_catalog import classify


class CadenceTests(unittest.TestCase):
    def test_weekly_and_fortnightly_text(self):
        self.assertEqual(cadence_hint("Diffusion hebdomadaire"), "weekly")
        self.assertEqual(cadence_hint("Chaque semaine"), "weekly")
        self.assertEqual(cadence_hint("Toutes les deux semaines"), "fortnightly")
        self.assertEqual(cadence_hint("Bi-hebdomadaire"), "fortnightly")
        self.assertEqual(cadence_hint("Nouveaux épisodes"), "unknown")

    def test_animated_label_filename_is_understood(self):
        gif = NS(raw_text="", file=NS(name="Hebdomadaire.gif"))
        self.assertEqual(cadence_from_message(gif), "weekly")

    def test_banner_applies_to_current_title_and_resets_on_new_poster(self):
        when = datetime(2026, 11, 21, tzinfo=timezone.utc)
        def poster(i, title):
            return NS(id=i, photo=True, noforwards=False, raw_text=title, date=when)
        def episode(i):
            return NS(id=i, photo=None, noforwards=False, date=when,
                      raw_text=f"Episode {i}", document=NS(
                          mime_type="video/mp4", id=i + 200),
                      file=NS(name=f"Episode_{i}.mp4"))
        tag = NS(id=2, photo=None, noforwards=False,
                 document=None, raw_text="", file=NS(name="HEBDOMADAIRE.gif"),
                 date=when)
        found = classify([
            poster(1, "Naruto"), tag, episode(3),
            poster(4, "Bleach"), episode(5),
        ], -100123)
        self.assertEqual([item["series"] for item in found], ["naruto", "bleach"])
        self.assertEqual([item["cadence_hint"] for item in found],
                         ["weekly", "unknown"])


if __name__ == "__main__":
    unittest.main()
