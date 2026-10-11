"""Classification BSD Simple / Pro / VIP, without changing market selection."""
import unittest
from bsd_v2_core import classify_quality_category

def features(league=100, recent=12, venue=8):
    return {"league_samples":league,"home_recent_matches":recent,
            "away_recent_matches":recent,"home_venue_matches":venue,
            "away_venue_matches":venue}

class VIPClassificationTests(unittest.TestCase):
    def test_vip_qualified(self):
        self.assertEqual(classify_quality_category(.87,features()),"vip")
    def test_pro_but_not_vip(self):
        self.assertEqual(classify_quality_category(.80,features()),"pro")
        self.assertEqual(classify_quality_category(.809,features()),"pro")
    def test_new_vip_confidence_floor(self):
        self.assertEqual(classify_quality_category(.81,features()),"vip")
    def test_not_enough_league_data(self):
        self.assertEqual(classify_quality_category(.90,features(league=50)),"pro")
    def test_vip_at_maximum_history_depth(self):
        self.assertEqual(classify_quality_category(.90,features(recent=12)),"vip")
    def test_not_enough_recent_data(self):
        self.assertEqual(classify_quality_category(.90,features(recent=11)),"pro")
    def test_not_enough_venue_data(self):
        self.assertEqual(classify_quality_category(.90,features(venue=4)),"pro")
    def test_simple(self):
        self.assertEqual(classify_quality_category(.70,features()),"simple")
    def test_missing_features_is_safe(self):
        self.assertEqual(classify_quality_category(.99,{}),"simple")

if __name__=="__main__":
    unittest.main()
