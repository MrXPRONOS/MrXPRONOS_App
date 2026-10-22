import sqlite3,unittest
from pathlib import Path
DIR=Path(__file__).resolve().parents[1]/"migrations"
FILES=("0001_initial.sql","0002_free_pronos_experience.sql","0003_support_tickets.sql","0004_free_pronos_verified_media_and_delivery.sql","0005_perf_samples.sql")
class TelemetrySchema(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(":memory:")
  for file in FILES:self.db.executescript((DIR/file).read_text(encoding="utf8"))
 def tearDown(self):self.db.close()
 def test_no_personally_identifying_columns(self):
  columns={x[1] for x in self.db.execute("PRAGMA table_info(perf_samples)")}
  self.assertFalse(columns.intersection({"user_id","chat_id","message","token","ip","username"}))
  self.assertTrue({"kind","route","colo","response_ms","callback_ack_ms","first_reply_ms"}.issubset(columns))
 def test_realtime_metrics_with_nullable_telegram_values(self):
  self.db.execute("INSERT INTO perf_samples(kind,route,colo,response_ms,status) VALUES('miniapp','/coupons','LFW',187,'ok')")
  self.db.execute("INSERT INTO perf_samples(kind,route,colo,response_ms,callback_ack_ms,first_reply_ms,status) VALUES('bot_callback','/callback','LFW',271,82,251,'ok')")
  self.assertEqual(self.db.execute("SELECT COUNT(*) FROM perf_samples").fetchone()[0],2)
 def test_invalid_identifiers_not_recorded(self):
  with self.assertRaises(sqlite3.IntegrityError):
   self.db.execute("INSERT INTO perf_samples(kind,route,colo,response_ms,status) VALUES('unknown','/any','LFW',111,'ok')")
if __name__=='__main__':unittest.main()
