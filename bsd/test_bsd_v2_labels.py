"""Libellés des paris : code BSD invariant, libellés publics normalisés."""
import json
import unittest
from pathlib import Path
from dataclasses import replace

from bsd_markets import candidates_from_goals
from bsd_v2_labels import market_label,normalize_selection,normalize_match
from bsd_v2_captions import single_caption

class BookmakerLabelsTests(unittest.TestCase):
    def test_every_supported_market_has_public_name(self):
        expected={"1":"1","X":"X","2":"2","1X":"1X","X2":"X2","12":"12",
                  "BTTS_YES":"Les deux équipes marquent : Oui",
                  "BTTS_NO":"Les deux équipes marquent : Non",
                  "OVER_15":"Total buts : Over 1,5",
                  "UNDER_15":"Total buts : Under 1,5",
                  "OVER_25":"Total buts : Over 2,5",
                  "UNDER_25":"Total buts : Under 2,5",
                  "OVER_35":"Total buts : Over 3,5",
                  "UNDER_35":"Total buts : Under 3,5",
                  "OVER_45":"Total buts : Over 4,5",
                  "UNDER_45":"Total buts : Under 4,5"}
        self.assertEqual(set(expected),{c.key for c in candidates_from_goals(1.4,1.2)})
        for key,label in expected.items():
            with self.subTest(key=key):
                self.assertEqual(market_label(key,"Ancien libellé"),label)
        self.assertEqual(market_label("UNSUPPORTED","Ne pas inventer"),"Ne pas inventer")

    def test_labels_change_but_selection_math_and_quote_are_immutable(self):
        old={"selection_key":"1X","type":"Domicile ou nul","label":"Domicile ou nul",
             "odds":1.78,"market_code":"DC_1X_FT","odds_source":"bsd_consensus",
             "confidence":78.5}
        new=normalize_selection(old)
        self.assertEqual(old["type"],"Domicile ou nul")
        self.assertEqual(new["type"],"1X")
        for field in ("selection_key","odds","market_code","odds_source","confidence"):
            self.assertEqual(new[field],old[field])

    def test_secondary_and_combo_preserve_independent_keys(self):
        match={"prediction":{"selection_key":"1X","type":"Domicile ou nul"},
               "predictions":[{"selection_key":"1X","type":"Domicile ou nul"},
                              {"selection_key":"BTTS_NO","type":"Les deux marquent : Non"}],
               "combo_prediction":{"selection_key":"UNDER_25","type":"Moins de 2.5 buts"}}
        normalized=normalize_match(match)
        self.assertEqual(normalized["prediction"]["type"],"1X")
        self.assertEqual(normalized["predictions"][1]["type"],
                         "Les deux équipes marquent : Non")
        self.assertEqual(normalized["combo_prediction"]["type"],"Total buts : Under 2,5")

    def test_old_caption_uses_canonical_name(self):
        m={"home_team":"A","away_team":"B","event_date":"2026-10-09T18:00:00+00:00",
           "prediction":{"selection_key":"X2","type":"Extérieur ou nul",
                         "odds":1.62,"odds_source":"bsd_consensus"}}
        caption=single_caption(m)
        self.assertIn("🎯 X2",caption)
        self.assertNotIn("Extérieur ou nul",caption)

    def test_current_data_json_fully_normalized(self):
        path=Path(__file__).resolve().parent.parent/"data.json"
        if not path.is_file():self.skipTest("Site data absent")
        doc=json.loads(path.read_text(encoding="utf-8"))
        for match in doc.get("matches",[]):
            selections=[match.get("prediction"),match.get("combo_prediction"),
                        *(match.get("predictions") or [])]
            for selection in selections:
                if not isinstance(selection,dict):continue
                canonical=market_label(selection.get("selection_key"),
                                      selection.get("type") or selection.get("label"))
                self.assertEqual(selection.get("type"),canonical)

if __name__=="__main__":
    unittest.main()
