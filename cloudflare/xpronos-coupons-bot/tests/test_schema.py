import sqlite3
import unittest
from pathlib import Path

SQL = Path(__file__).resolve().parents[1].joinpath('migrations/0001_initial.sql').read_text(encoding='utf-8')

class D1SchemaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SQL)
        self.db.execute("INSERT INTO users(id,name,adult_confirmed,required_verified,xp) VALUES(1,'Membre',1,1,100)")
        self.db.execute("INSERT INTO users(id,name,adult_confirmed,required_verified,xp,referred_by) VALUES(2,'Parrainé',1,1,50,1)")
        self.db.execute("INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,stock) VALUES('PRO','Test','[]','4.20',30,'2099-01-01T00:00:00.000Z',1)")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def redeem(self, uid, coupon=1):
        return self.db.execute("""INSERT OR IGNORE INTO redemptions(user_id,coupon_id,snapshot,xp_spent)
            SELECT ?,c.id,json_object('title',c.title,'tier',c.tier,'total_odds',c.total_odds,'selections',json(c.selections)),
            c.xp_cost FROM coupons c JOIN users u ON u.id=?
            WHERE c.id=? AND c.active=1 AND c.expires_at>'2026-10-22T00:00:00.000Z' AND c.stock<>0
            AND u.adult_confirmed=1 AND u.required_verified=1 AND u.xp>=c.xp_cost
            RETURNING coupon_id""",(uid,uid,coupon)).fetchone()

    def test_redeem_atomic_and_stock(self):
        self.assertEqual(self.redeem(1),(1,))
        self.assertIsNone(self.redeem(1))
        self.assertIsNone(self.redeem(2))
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=1').fetchone()[0],70)
        self.assertEqual(self.db.execute('SELECT stock FROM coupons WHERE id=1').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM redemptions').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT delta FROM ledger WHERE reason='coupon:1'").fetchone()[0],-30)

    def test_task_claim_unique(self):
        self.db.execute("INSERT INTO tasks(chat_id,url,xp) VALUES('@testchannel','https://t.me/testchannel',15)")
        sql="""INSERT OR IGNORE INTO task_claims(user_id,task_id) SELECT ?,t.id
        FROM tasks t JOIN users u ON u.id=? WHERE t.id=1 AND t.active=1
        AND u.adult_confirmed=1 AND u.required_verified=1 RETURNING user_id"""
        self.assertEqual(self.db.execute(sql,(1,1)).fetchone(),(1,))
        self.assertIsNone(self.db.execute(sql,(1,1)).fetchone())
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=1').fetchone()[0],115)

    def test_referral_once(self):
        self.db.execute('UPDATE users SET referral_rewarded=1 WHERE id=2')
        self.db.execute('UPDATE users SET referral_rewarded=1 WHERE id=2')
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=1').fetchone()[0],130)
        self.assertEqual(self.db.execute("SELECT count(*) FROM ledger WHERE reason='referral:2'").fetchone()[0],1)

    def test_manual_grant_idempotent(self):
        sql='INSERT OR IGNORE INTO manual_grants(user_id,xp,update_id) SELECT 1,25,123 WHERE EXISTS(SELECT 1 FROM users WHERE id=1) RETURNING id'
        self.assertIsNotNone(self.db.execute(sql).fetchone())
        self.assertIsNone(self.db.execute(sql).fetchone())
        self.assertEqual(self.db.execute('SELECT xp FROM users WHERE id=1').fetchone()[0],125)

    def test_bonus_ledger(self):
        self.db.execute("UPDATE users SET xp=xp+5,bonus_last_at='2026-10-22T00:00:00.000Z' WHERE id=1")
        self.assertEqual(self.db.execute("SELECT count(*) FROM ledger WHERE reason='bonus'").fetchone()[0],1)

    def test_insufficient_xp(self):
        self.db.execute('UPDATE users SET xp=0 WHERE id=1')
        self.assertIsNone(self.redeem(1))
        self.assertEqual(self.db.execute('SELECT stock FROM coupons WHERE id=1').fetchone()[0],1)

    def test_locked_user(self):
        self.db.execute('UPDATE users SET required_verified=0 WHERE id=1')
        self.assertIsNone(self.redeem(1))

    def test_odds_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at) VALUES('PRO','bad','[]','3.99',30,'2099-01-01T00:00:00Z')")

if __name__ == '__main__':
    unittest.main()
