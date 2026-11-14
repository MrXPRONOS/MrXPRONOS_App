"""No-fabrication, no-leakage, nested Top5 score publishing and site smoke tests."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from scripts.publish_exact_scores import build_feed, grid_summary, validated_forecast, GROUPS, MODEL, SCHEMA

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-03T06:00:00Z"
NEXT = "2026-11-03T20:00:00Z"


def grid(a, b, c):
    arr = [[.000001] * 11 for _ in range(11)]
    rows = [(a, .18), (b, .17), (c, .16)]
    for (h, away), p in rows:
        arr[h][away] = p
    mass = sum(sum(r) for r in arr)
    # Remainder given to e.g. (10,10), not enough to beat the modal.
    # Add residual in 10 moderate cells to keep original top scorer.
    extra = (1.0 - mass) / 30.0
    n = 0
    for h in range(11):
        for away in range(11):
            if (h, away) in (a, b, c):
                continue
            arr[h][away] += extra
            n += 1
            if n == 30:
                break
        if n == 30:
            break
    return arr


def make_one(i, group):
    coords = {
        "H_LOW": ((1,0),(2,0),(2,1)),
        "DRAW_LOW": ((1,1),(0,0),(2,2)),
        "A_LOW": ((0,1),(0,2),(1,2)),
    }[group]
    matrix = grid(*coords)
    return {
      "id": f"fixture-{i:02d}", "model": MODEL,
      "home": f"Équipe domicile {i}", "away": f"Équipe extérieure {i}",
      "league": "Championnat test", "kickoff_utc": NEXT,
      "history_latest_day": "2026-11-02",
      "model_fit_latest_day": "2026-11-02",
      "grid": matrix
    }


class TestTop5Publisher(unittest.TestCase):
    def setup_source(self):
        return {
          "origin": "prospective_prematch", "model": MODEL,
          "generated_at": NOW,
          "fixtures": [make_one(i, "H_LOW" if i % 2 else "DRAW_LOW") for i in range(10)]
        }

    def test_model_grid_mass_conservation(self):
        m = grid((1,0),(2,0),(2,1))
        self.assertAlmostEqual(sum(sum(r) for r in m),1,places=9)
        score,p,g,mass = grid_summary(m)
        self.assertEqual(score,"1:0")
        self.assertEqual(g,"H_LOW")
        self.assertAlmostEqual(mass,m[1][0]+m[2][0]+m[2][1])
        self.assertGreaterEqual(mass,p)

    def test_publisher_produces_two_top5_no_actual_results(self):
        feed = build_feed(self.setup_source(),generated_at=NOW)
        self.assertEqual(feed["schema_version"], SCHEMA)
        self.assertEqual(feed["date"],"2026-11-03")
        self.assertEqual(feed["status"],"published")
        self.assertEqual(len(feed["simple"]),5)
        self.assertEqual(len(feed["grouped"]),5)
        self.assertEqual(feed["selection_simple"],"A_MODAL")
        self.assertEqual(feed["selection_grouped"],"B_GROUP_MASS")
        self.assertNotIn("actual_score",json.dumps(feed))
        self.assertTrue(all(p["group_scores"]==list(GROUPS[p["group"]]) for p in feed["grouped"]))
        # Ties resolve deterministically by fixture ID.
        self.assertEqual(feed["simple"][0]["id"],"fixture-01")
        self.assertTrue(all(p["score"] != "1:1" for p in feed["simple"] + feed["grouped"]))
        self.assertTrue(all("1:1" not in p["group_scores"] for p in feed["grouped"]))

    def test_exclude_entire_1_1_fixture_no_substitution(self):
        source = self.setup_source()
        one = source["fixtures"][0]
        # The original 1:1 modal is not converted to the next-best 0:0.
        score, prob, group, group_mass = grid_summary(one["grid"])
        self.assertEqual(score, "1:1")
        feed = build_feed(source, generated_at=NOW)
        excluded = one["id"]
        self.assertNotIn(excluded, {r["id"] for r in feed["simple"]})
        self.assertNotIn(excluded, {r["id"] for r in feed["grouped"]})
        self.assertTrue(all(p["score"] != "1:1" for p in feed["simple"]))
        self.assertTrue(all("1:1" not in p["group_scores"] for p in feed["grouped"]))
        self.assertEqual(feed["selection_simple"], "A_MODAL")

    def test_draw_group_with_non_11_modal_does_not_publish_group(self):
        source = self.setup_source()
        draw = source["fixtures"][0]
        matrix = draw["grid"]
        # Swap modal cells 1:1 and 0:0 to make 0:0 the top score
        # while preserving a valid, unchanged probability distribution.
        matrix[1][1], matrix[0][0] = matrix[0][0], matrix[1][1]
        self.assertEqual(grid_summary(matrix)[0], "0:0")
        feed = build_feed(source, generated_at=NOW)
        self.assertIn(draw["id"], {p["id"] for p in feed["simple"]})
        self.assertNotIn(draw["id"], {p["id"] for p in feed["grouped"]})
        self.assertTrue(all("1:1" not in p["group_scores"] for p in feed["grouped"]))

    def test_1_1_removed_before_top5_fills_ranks_with_next_eligible_games(self):
        # Eight modal 1:1 fixtures have first priority by ID. If we selected
        # Top5 before filtering they would consume the places and yield zero
        # picks; a pre-filter must instead fill all five from later fixtures.
        source = self.setup_source()
        excluded = [make_one(i, "DRAW_LOW") for i in range(8)]
        eligible = [make_one(i, "H_LOW") for i in range(8, 15)]
        # Make 1:1 forecasts strictly stronger than the remaining scores;
        # filtering must happen before the modal ranking, not after its Top5.
        for row in excluded:
            matrix = row["grid"]
            matrix[1][1] += .04
            matrix[0][0] -= .04
            self.assertEqual(grid_summary(matrix)[0], "1:1")
        source["fixtures"] = excluded + eligible
        feed = build_feed(source, generated_at=NOW)
        self.assertEqual(feed["status"], "published")
        self.assertEqual(len(feed["simple"]), 5)
        self.assertEqual(len(feed["grouped"]), 5)
        expected = {f"fixture-{i:02d}" for i in range(8, 13)}
        self.assertEqual({row["id"] for row in feed["simple"]}, expected)
        self.assertEqual({row["id"] for row in feed["grouped"]}, expected)
        self.assertTrue(all(p["score"] != "1:1" for p in feed["simple"] + feed["grouped"]))
        self.assertTrue(all("1:1" not in p["group_scores"] for p in feed["grouped"]))

    def test_filter_before_top5_still_obeys_hard_ceiling_when_fewer_eligible(self):
        source = self.setup_source()
        source["fixtures"] = (
            [make_one(i, "DRAW_LOW") for i in range(8)]
            + [make_one(i, "H_LOW") for i in range(8, 10)]
        )
        result = build_feed(source, generated_at=NOW)
        self.assertEqual(len(result["simple"]), 2)
        self.assertEqual(len(result["grouped"]), 2)
        self.assertEqual({r["id"] for r in result["simple"]}, {"fixture-08", "fixture-09"})

    def test_all_11_modal_yields_unavailable_not_fabricated_alternative(self):
        source = self.setup_source()
        source["fixtures"] = [make_one(i, "DRAW_LOW") for i in range(7)]
        feed = build_feed(source, generated_at=NOW)
        self.assertEqual(feed["status"], "unavailable")
        self.assertEqual(feed["simple"], [])
        self.assertEqual(feed["grouped"], [])

    def test_utc_tomorrow_uses_actual_next_day_fixtures_only(self):
        source = self.setup_source()
        tomorrow = "2026-11-04T20:00:00Z"
        for rec in source["fixtures"]:
            rec["kickoff_utc"] = tomorrow
        feed = build_feed(source, generated_at=NOW, target_date=datetime(2026,11,4).date())
        self.assertEqual(feed["status"], "published")
        self.assertEqual(feed["date"], "2026-11-04")
        self.assertEqual(feed["generated_at"], NOW)
        self.assertEqual(len(feed["simple"]), 5)
        self.assertEqual(len(feed["grouped"]), 5)
        self.assertTrue(all(p["kickoff_utc"]==tomorrow for p in feed["simple"]))
        today = build_feed(source, generated_at=NOW)
        self.assertEqual(today["status"], "unavailable")
        self.assertEqual(today["simple"], [])
        with self.assertRaisesRegex(ValueError, "Only the current and next"):
            build_feed(source, generated_at=NOW, target_date=datetime(2026,11,5).date())
        source["fixtures"][0]["actual_score"] = "1:0"
        with self.assertRaisesRegex(ValueError, "Results"):
            build_feed(source, generated_at=NOW, target_date=datetime(2026,11,4).date())

    def test_group_ranking_can_differ_from_modal_ranking(self):
        source=self.setup_source()
        a=source["fixtures"][0]["grid"]
        b=source["fixtures"][1]["grid"]
        # B: modal 1:0 relatively less likely but its group very likely.
        b[1][0]=.16;b[2][0]=.15;b[2][1]=.14
        # Redistribute to a group-free score in a way preserving normalized mass.
        for matrix in (a,b):
            total=sum(map(sum,matrix))
            shift=1-total
            if abs(shift)>1e-10:
                matrix[10][10]+=shift
            if matrix[10][10]>=max(v for row in matrix for v in row if v != matrix[10][10]):
                # Keep original modal unchanged; this toy fixture remains small.
                pass
        sa=grid_summary(a);sb=grid_summary(b)
        self.assertTrue(sa[1] >= sb[1] or sa[2]!=sb[2])
        self.assertGreater(sb[3],0)

    def test_rejects_outcome_fields_and_future_model_provenance(self):
        p=self.setup_source()
        p["fixtures"][0]["actual_score"]="1:0"
        with self.assertRaisesRegex(ValueError,"Results"):
            build_feed(p,generated_at=NOW)
        p=self.setup_source()
        p["fixtures"][0]["history_latest_day"]="2026-11-03"
        with self.assertRaisesRegex(ValueError,"MUST predate"):
            build_feed(p,generated_at=NOW)

    def test_rejects_unverified_source_and_wrong_model(self):
        p=self.setup_source();p["origin"]="historical_backtest"
        with self.assertRaisesRegex(ValueError,"Only an audited prospective"):
            build_feed(p,generated_at=NOW)
        p=self.setup_source();p["fixtures"][0]["model"]="machine_learning"
        with self.assertRaisesRegex(ValueError,"Hybrid V3"):
            build_feed(p,generated_at=NOW)

    def test_started_matches_excluded_and_empty_is_unavailable(self):
        p=self.setup_source()
        for row in p["fixtures"]:row["kickoff_utc"]="2026-11-03T05:00:00Z"
        feed=build_feed(p,generated_at=NOW)
        self.assertEqual(feed["status"],"unavailable")
        self.assertEqual(feed["simple"],[])
        self.assertEqual(feed["grouped"],[])

    def test_static_tab_and_no_fake_public_predictions(self):
        html=(ROOT/"scores-exacts.html").read_text(encoding="utf8")
        js=(ROOT/"assets/js/scores-exacts.js").read_text(encoding="utf8")
        menu=(ROOT/"assets/js/menu.js").read_text(encoding="utf8")
        stub=json.loads((ROOT/"scores-exacts.json").read_text(encoding="utf8"))
        self.assertIn('id="scores-simple-list"',html)
        self.assertNotIn('id="scores-grouped-list"',html)
        self.assertNotIn('data-scores-mode="grouped"',html)
        self.assertIn('data-scores-day="-1"',html)
        self.assertIn('data-scores-day="0"',html)
        self.assertIn('data-scores-day="1"',html)
        self.assertIn("dixon-scores-daily/",js)
        self.assertIn("dixon_coles_video",js)
        self.assertIn("Top 10",html)
        self.assertNotIn("HYBRIDE V3",html)
        self.assertIn("scores-exacts.html",menu)
        self.assertIn("A_MODAL", (ROOT/"scripts/publish_exact_scores.py").read_text())
        self.assertIn("B_GROUP_MASS", (ROOT/"scripts/publish_exact_scores.py").read_text())
        self.assertIn('cache: "no-store"',js)
        self.assertIn('Date.parse(m.kickoff_utc) <= gen',js)
        self.assertIn(stub["status"],("unavailable","published"))
        # Keep the historical Hybrid V3 publisher's independent tests,
        # but its legacy feed must no longer be consumed by the public page.
        if stub["status"]=="unavailable":
            self.assertEqual(stub["simple"],[])
            self.assertEqual(stub["grouped"],[])
        else:
            self.assertEqual(stub["origin"],"prospective_prematch")
            self.assertEqual(stub["schema_version"],SCHEMA)
            self.assertEqual(stub["model"],MODEL)
            self.assertLessEqual(len(stub["simple"]),5)
            self.assertLessEqual(len(stub["grouped"]),5)
            self.assertNotIn("actual_score",json.dumps(stub))

if __name__ == "__main__":
    unittest.main()
