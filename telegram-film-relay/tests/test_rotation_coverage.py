"""Offline-only regression tests for exhaustive cinema rotation coverage."""
from __future__ import annotations

import unittest

from film_relay.rotation_coverage import CoverageError, evaluate_coverage


def public(handle):
    return {"channel_id": -1001000000000, "is_private": False,
            "public_username": handle}


def private():
    return {"channel_id": -1002000000000, "is_private": True,
            "public_username": None}


class CoverageTests(unittest.TestCase):
    def test_six_pairs_do_not_cover_eleven_public_cinema_channels(self):
        names = ["CineXFilms_vf", "seriesvf_cinex", "CineXDesirfr",
                 "CineXComediefr", "CineXAnimeFR", "filmsaction2026vf",
                 "bleachvffr", "fastandfuriousvffr", "fichiers_cloud",
                 "lecarnetdelapovf", "lupin4saisonsvf"]
        pairs = [
            ("films", "@CineXFilms_vf", -1003000000000),
            ("series", "@seriesvf_cinex", -1003000000001),
            ("desir", "@CineXDesirfr", -1003000000002),
            ("comedie", "@CineXComediefr", -1003000000003),
            ("anime", "@CineXAnimeFR", -1003000000004),
            ("action", "@filmsaction2026vf", -1003000000005),
        ]
        result = evaluate_coverage(
            [public(name) for name in names] + [private() for _ in range(35)],
            pairs,
        )
        self.assertEqual(result["verified_cinema_total"], 46)
        self.assertEqual(result["verified_cinema_private_not_rotated"], 35)
        self.assertEqual(result["verified_cinema_public"], 11)
        self.assertEqual(result["verified_public_covered"], 6)
        self.assertEqual(result["verified_public_uncovered"], 5)
        self.assertFalse(result["complete_public_coverage"])
        self.assertIn("@fastandfuriousvffr",
                      result["uncovered_possible_source_or_stock"])
        self.assertIn("@bleachvffr", result["uncovered_public"])
        self.assertNotIn("channel_id", str(result))

    def test_full_coverage_only_when_every_public_has_archive_pair(self):
        got = evaluate_coverage(
            [public("CineXFilms_vf"), private()],
            [("films", "@CineXFilms_vf", -1003000000000)],
        )
        self.assertTrue(got["complete_public_coverage"])
        self.assertEqual(got["verified_cinema_private_not_rotated"], 1)

    def test_refuses_invalid_private_metadata(self):
        with self.assertRaises(CoverageError):
            evaluate_coverage(
                [{"is_private": True, "public_username": "leak"}], []
            )

    def test_refuses_duplicate_target(self):
        with self.assertRaises(CoverageError):
            evaluate_coverage(
                [public("CineXFilms_vf"), public("@cinexfilms_vf")], []
            )

    def test_refuses_public_target_without_verified_backup(self):
        with self.assertRaises(CoverageError):
            evaluate_coverage(
                [public("CineXFilms_vf")],
                [("films", "@CineXFilms_vf", 123)],
            )


if __name__ == "__main__":
    unittest.main()
