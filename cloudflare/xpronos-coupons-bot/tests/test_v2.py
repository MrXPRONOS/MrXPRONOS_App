import sqlite3
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT/'migrations/0001_initial.sql').read_text(encoding='utf-8')
V2 = (ROOT/'migrations/0002_free_pronos_experience.sql').read_text(encoding='utf-8')

class FreePronosV2Tests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)
        self.db.executescript(V2)
        self.db.execute("INSERT INTO users(id,name,adult_confirmed,required_verified,xp) VALUES(10,'Tester',1,1,0)")
        self.db.execute("INSERT INTO users(id,name,adult_confirmed,required_verified,xp) VALUES(20,'Invité',1,0,0)")
        self.db.execute("INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at) VALUES('PRO','Test','[]','4.20',20,'2099-01-01T00:00:00Z')")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_migrations_existing_users_and_tables(self):
        names={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({'users','coupons','engagement_claims','user_preferences','processed_updates','coupon_notifications'}.issubset(names))
        self.assertEqual(self.db.execute('SELECT count(*) FROM users').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT result_status FROM coupons').fetchone()[0],'available')

    def test_daily_claim_only_once(self):
        sql='''INSERT OR IGNORE INTO engagement_claims(user_id,kind,period_key,xp)
        SELECT id,'daily','2026-10-22',3 FROM users WHERE id=10 AND adult_confirmed=1 AND required_verified=1 RETURNING user_id'''
        self.assertEqual(self.db.execute(sql).fetchone()[0],10)
        self.assertIsNone(self.db.execute(sql).fetchone())
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=10').fetchone()[0],3)
        self.assertEqual(self.db.execute("SELECT count(*) FROM ledger WHERE reason='daily:2026-10-22'").fetchone()[0],1)

    def test_weekly_claim_and_no_unverified(self):
        ok="INSERT OR IGNORE INTO engagement_claims(user_id,kind,period_key,xp) SELECT id,'weekly','2026-10-19',10 FROM users WHERE id=? AND adult_confirmed=1 AND required_verified=1 RETURNING user_id"
        self.assertIsNone(self.db.execute(ok,(20,)).fetchone())
        self.assertIsNotNone(self.db.execute(ok,(10,)).fetchone())
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=10').fetchone()[0],10)

    def test_alerts_opt_in_only(self):
        self.assertEqual(self.db.execute('SELECT count(*) FROM user_preferences').fetchone()[0],0)
        self.db.execute("INSERT INTO user_preferences(user_id,notify_coupons,notify_results) VALUES(10,1,0)")
        self.assertEqual(self.db.execute("SELECT notify_coupons,notify_results FROM user_preferences WHERE user_id=10").fetchone(),(1,0))

    def test_duplicate_updates_deduplicated(self):
        sql="INSERT OR IGNORE INTO processed_updates(update_id) VALUES(456) RETURNING update_id"
        self.assertEqual(self.db.execute(sql).fetchone(),(456,))
        self.assertIsNone(self.db.execute(sql).fetchone())

    def test_coupon_results_cannot_use_unexpected_status(self):
        self.db.execute("UPDATE coupons SET result_status='won',result_source='https://example.org/match' WHERE id=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE coupons SET result_status='unknown' WHERE id=1")

    def test_notifications_one_per_coupon_and_user(self):
        sql="INSERT OR IGNORE INTO coupon_notifications(user_id,coupon_id,kind) VALUES(10,1,'new') RETURNING user_id"
        self.assertEqual(self.db.execute(sql).fetchone(),(10,))
        self.assertIsNone(self.db.execute(sql).fetchone())

if __name__=='__main__':
    unittest.main()
