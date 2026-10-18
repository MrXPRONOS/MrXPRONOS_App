"""Fear & Greed #05 : essais isolés sans API ni Telegram."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from crypto.export_fear_v2 import classification, demo_data, parse_history
from crypto.send_crypto_fear_v2_test import validate_publication

UTC = timezone.utc


def mock_data(now, values=None):
    values = values or [19, 24, 35, 49, 52, 64, 76]
    latest = datetime(now.year, now.month, now.day, tzinfo=UTC)
    history = [{"value": str(v), "timestamp": str(int((latest - timedelta(days=6-i)).timestamp()))}
               for i, v in enumerate(values)]
    return {"metadata": {"error": None}, "data": list(reversed(history))}


class FearV2Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)

    def test_moods_exact_boundaries(self):
        expect = [(0,"PEUR EXTRÊME"),(24,"PEUR EXTRÊME"),
                  (25,"PEUR"),(44,"PEUR"),(45,"NEUTRE"),
                  (54,"NEUTRE"),(55,"AVIDITÉ"),(74,"AVIDITÉ"),
                  (75,"AVIDITÉ EXTRÊME"),(100,"AVIDITÉ EXTRÊME")]
        for score, label in expect:
            self.assertEqual(classification(score),label)

    def test_real_seven_days_and_deltas(self):
        out = parse_history(mock_data(self.now), self.now)
        self.assertEqual(out["score"],76)
        self.assertEqual(out["delta_1d"],12)
        self.assertEqual(out["delta_6d"],57)
        self.assertEqual(len(out["history"]),7)
        self.assertEqual(out["status"],"real_data")
        validate_publication(out)

    def test_bad_score_no_fake_fallback(self):
        for bad in ("101", "-1", "2.5", None, True):
            with self.subTest(bad=bad):
                data=mock_data(self.now)
                data["data"][0]["value"]=bad
                with self.assertRaises(ValueError): parse_history(data,self.now)

    def test_missing_days_rejected(self):
        data=mock_data(self.now)
        data["data"].pop(3)
        with self.assertRaises(ValueError): parse_history(data,self.now)

    def test_expired_or_future_rejected(self):
        with self.assertRaises(ValueError):
            parse_history(mock_data(self.now-timedelta(days=5)),self.now)
        with self.assertRaises(ValueError):
            parse_history(mock_data(self.now+timedelta(days=3)),self.now)

    def test_malformed_payload_rejected(self):
        for payload in ({}, {"data": []}, {"metadata":{"error":"fail"},"data": []}):
            with self.assertRaises(ValueError): parse_history(payload,self.now)

    def test_demo_forbidden_for_publication(self):
        with self.assertRaises(ValueError): validate_publication(demo_data())

    def test_tampered_labels_or_history_rejected(self):
        real=parse_history(mock_data(self.now),self.now)
        bad=copy.deepcopy(real)
        bad["classification"]="AVIDITÉ"
        with self.assertRaises(ValueError): validate_publication(bad)
        bad=copy.deepcopy(real)
        bad["history"][-1]["value"]=41
        with self.assertRaises(ValueError): validate_publication(bad)


if __name__ == "__main__":
    unittest.main()