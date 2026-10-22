import sqlite3
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"migrations"
class NewFeatures(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("PRAGMA foreign_keys=ON")
  for name in ("0001_initial.sql","0002_free_pronos_experience.sql","0003_support_tickets.sql","0004_free_pronos_verified_media_and_delivery.sql"):
   self.c.executescript((ROOT/name).read_text(encoding="utf-8"))
  self.c.execute("INSERT INTO users(id,name) VALUES(1,'Test')")
 def tearDown(self):self.c.close()
 def test_upgraded_coupon_can_hold_media(self):
  self.c.execute("""INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,competition,media_json,auto_settlement,provider)
   VALUES('VIP','Match','[]','4.20',50,'2099-01-01T00:00:00Z','Premier League','{"games":[]}',1,'espn')""")
  row=self.c.execute("SELECT competition,auto_settlement,provider FROM coupons").fetchone()
  self.assertEqual(row,('Premier League',1,'espn'))
 def test_invalid_media_is_rejected(self):
  with self.assertRaises(sqlite3.IntegrityError):
   self.c.execute("INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,media_json) VALUES('PRO','Test','[]','4.20',50,'2099-01-01','{oops}')")
 def test_alert_delivery_receipt_is_audited(self):
  self.c.execute("INSERT INTO delivery_audit(user_id,delivery_type,status,telegram_message_id) VALUES(1,'selftest','sent',555)")
  self.assertEqual(self.c.execute("SELECT count(*) FROM delivery_audit WHERE status='sent'").fetchone()[0],1)
if __name__=="__main__":unittest.main()
