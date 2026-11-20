#!/usr/bin/env python3
"""Real SQLite concurrency checks for the D1-style SQL used by Mr XPRONOS Play.
Offline only: never reads or changes production Cloudflare D1.
"""
import concurrent.futures
import pathlib
import sqlite3
import tempfile
import time
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKER = (ROOT / "worker.js").read_text(encoding="utf-8")
MIGRATION = (ROOT / "migrations/007_server_reward_intents.sql").read_text(encoding="utf-8")
BUY = (
    "INSERT OR IGNORE INTO mrxp_boost_inventory(user_id,purchase_id,sku,kind,cost,state,bought_ms,activated_ms,expires_ms,carry_milli) "
    "SELECT ?,?,?,?,?, 'owned',?,0,0,0 WHERE "
    "(SELECT COALESCE(SUM(amount),0) FROM mrxp_credit_events WHERE user_id=?)>=? AND "
    "(SELECT COUNT(*) FROM mrxp_boost_inventory WHERE user_id=? AND bought_ms>=?)<? "
    "AND NOT EXISTS(SELECT 1 FROM mrxp_boost_inventory WHERE user_id=? AND purchase_id=?)"
)
DEBIT = (
    "INSERT INTO mrxp_credit_events(user_id,event_key,event_type,amount,label,created_ms) "
    "SELECT ?,?,'purchase',?,?,? WHERE changes()=1"
)
BOOST = (
    "UPDATE mrxp_boost_inventory SET state='queued' WHERE user_id=? AND purchase_id=? "
    "AND state='owned' AND NOT EXISTS(SELECT 1 FROM mrxp_boost_inventory WHERE user_id=? "
    "AND kind='tap' AND state IN ('queued','active') AND purchase_id<>?)"
)
RATE = (
    "INSERT INTO mrxp_api_limits(user_id,action,window_start_ms,count) VALUES(?,?,?,1) "
    "ON CONFLICT(user_id,action) DO UPDATE SET "
    "count=CASE WHEN ?-window_start_ms>=? THEN 1 ELSE count+1 END,"
    "window_start_ms=CASE WHEN ?-window_start_ms>=? THEN ? ELSE window_start_ms END "
    "WHERE ?-window_start_ms>=? OR count<?"
)
SYNC_UPDATE = (
    "UPDATE players SET confirmed_xp=confirmed_xp+?,confirmed_taps=confirmed_taps+?,"
    "last_sync_ms=?,next_sync_ms=?,updated_ms=? WHERE user_id=? AND next_sync_ms<=? "
    "AND NOT EXISTS(SELECT 1 FROM sync_receipts WHERE user_id=? AND batch_id=?)"
)
SYNC_RECEIPT = (
    "INSERT OR IGNORE INTO sync_receipts(user_id,batch_id,taps,xp_awarded,wheel_count,created_ms) "
    "SELECT ?,?,?,?,?,? WHERE changes()=1 AND "
    "(SELECT last_sync_ms FROM players WHERE user_id=?)=?"
)

class AuditConcurrency(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(pathlib.Path(self.temp.name) / "audit.sqlite")
        conn = self.connect()
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE players (
          user_id TEXT PRIMARY KEY, confirmed_xp INTEGER DEFAULT 0,
          confirmed_taps INTEGER DEFAULT 0, last_sync_ms INTEGER DEFAULT 0,
          next_sync_ms INTEGER DEFAULT 0, updated_ms INTEGER DEFAULT 0
        );
        CREATE TABLE sync_receipts (
          user_id TEXT NOT NULL, batch_id TEXT NOT NULL, taps INTEGER,
          xp_awarded INTEGER, wheel_count INTEGER, created_ms INTEGER,
          PRIMARY KEY(user_id,batch_id)
        );
        CREATE TABLE mrxp_credit_events (
          user_id TEXT NOT NULL, event_key TEXT NOT NULL,
          event_type TEXT NOT NULL, amount INTEGER NOT NULL,
          label TEXT NOT NULL, created_ms INTEGER NOT NULL,
          PRIMARY KEY(user_id,event_key)
        );
        CREATE TABLE mrxp_boost_inventory (
          user_id TEXT NOT NULL, purchase_id TEXT NOT NULL,
          sku TEXT NOT NULL, kind TEXT NOT NULL, cost INTEGER NOT NULL,
          state TEXT NOT NULL, bought_ms INTEGER NOT NULL,
          activated_ms INTEGER NOT NULL DEFAULT 0,
          expires_ms INTEGER NOT NULL DEFAULT 0,
          carry_milli INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(user_id,purchase_id)
        );
        """)
        conn.executescript(MIGRATION)
        for uid in ("one", "two"):
            conn.execute("INSERT INTO players(user_id) VALUES(?)", (uid,))
            conn.execute(
                "INSERT INTO mrxp_credit_events VALUES(?,?,?,?,?,?)",
                (uid, "initial", "award", 100, "fixture", 1000),
            )
        conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db, timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @staticmethod
    def parallel(fn, jobs, workers=10):
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, jobs))

    def test_production_sql_contracts_are_not_simulated_rewrites(self):
        for label, sql in [
            ("buy", BUY), ("debit", DEBIT), ("boost", BOOST),
            ("rate limit", RATE), ("sync update", SYNC_UPDATE),
            ("sync receipt", SYNC_RECEIPT),
        ]:
            self.assertIn(sql, WORKER, "Source SQL drift: " + label)

    def test_concurrent_purchases_do_not_overdraw_or_cross_accounts(self):
        stamp = int(time.time() * 1000)
        day_start = stamp - stamp % 86400000
        jobs = [(uid, str(uuid.uuid4())) for uid in ("one", "two") for _ in range(30)]

        def purchase(task):
            uid, purchase_id = task
            con = self.connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute(
                    BUY, (uid, purchase_id, "tap-110", "tap", 25, stamp,
                          uid, 25, uid, day_start, 3, uid, purchase_id)
                )
                changed = row.rowcount
                con.execute(DEBIT, (uid, "buy:" + purchase_id, -25, "test", stamp))
                con.commit()
                return changed
            except:
                con.rollback()
                raise
            finally:
                con.close()

        changes = self.parallel(purchase, jobs)
        self.assertEqual(sum(changes), 6)
        con = self.connect()
        for uid in ("one", "two"):
            balance = con.execute(
                "SELECT SUM(amount) FROM mrxp_credit_events WHERE user_id=?", (uid,)
            ).fetchone()[0]
            owned = con.execute(
                "SELECT COUNT(*) FROM mrxp_boost_inventory WHERE user_id=?", (uid,)
            ).fetchone()[0]
            debits = con.execute(
                "SELECT COUNT(*) FROM mrxp_credit_events WHERE user_id=? AND event_type='purchase'",
                (uid,),
            ).fetchone()[0]
            self.assertEqual((balance, owned, debits), (25, 3, 3))
        con.close()

    def test_replayed_purchase_uuid_charges_once(self):
        purchase_id = str(uuid.uuid4())
        stamp = int(time.time() * 1000)
        day_start = stamp - stamp % 86400000

        def buy(_):
            con = self.connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                ok = con.execute(
                    BUY, ("one", purchase_id, "tap-110", "tap", 25, stamp,
                          "one", 25, "one", day_start, 30, "one", purchase_id)
                ).rowcount
                con.execute(DEBIT, ("one", "buy:" + purchase_id, -25, "test", stamp))
                con.commit()
                return ok
            finally:
                con.close()

        self.assertEqual(sum(self.parallel(buy, range(12))), 1)
        con = self.connect()
        self.assertEqual(con.execute(
            "SELECT COUNT(*) FROM mrxp_credit_events WHERE user_id='one' AND event_type='purchase'"
        ).fetchone()[0], 1)
        con.close()

    def test_two_simultaneous_boost_activations_cannot_stack(self):
        con = self.connect()
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for purchase_id in ids:
            con.execute(
                "INSERT INTO mrxp_boost_inventory VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("one", purchase_id, "tap-110", "tap", 25, "owned", 100, 0, 0, 0),
            )
        con.close()

        def activate(purchase_id):
            con = self.connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                changed = con.execute(
                    BOOST, ("one", purchase_id, "one", purchase_id)
                ).rowcount
                con.commit()
                return changed
            finally:
                con.close()

        self.assertEqual(sum(self.parallel(activate, ids, workers=2)), 1)

    def test_atomic_sync_one_winner_for_two_concurrent_batches(self):
        now = 2000000000000

        def synchronize(batch):
            con = self.connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                updated = con.execute(
                    SYNC_UPDATE, (12, 12, now, now + 43200000, now, "one", now, "one", batch)
                ).rowcount
                receipt = con.execute(
                    SYNC_RECEIPT, ("one", batch, 12, 12, 0, now, "one", now)
                ).rowcount
                con.commit()
                return updated, receipt
            finally:
                con.close()

        results = self.parallel(synchronize, ["batch-id-one-abcdefgh", "batch-id-two-abcdefgh"], 2)
        self.assertEqual(sum(r[0] for r in results), 1)
        self.assertEqual(sum(r[1] for r in results), 1)
        con = self.connect()
        self.assertEqual(con.execute(
            "SELECT confirmed_xp, confirmed_taps FROM players WHERE user_id='one'"
        ).fetchone(), (12, 12))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM sync_receipts").fetchone()[0], 1)
        con.close()

    def test_parallel_daily_claims_one_per_day_per_account(self):
        day = "2026-11-20"
        def claim(uid):
            con = self.connect()
            try:
                return con.execute(
                    "INSERT OR IGNORE INTO mrxp_reward_intents VALUES(?,?,?,?,?,?)",
                    (uid, "daily", day, "daily", 100, 12345),
                ).rowcount
            finally:
                con.close()

        jobs = ["one"] * 35 + ["two"] * 15
        self.assertEqual(sum(self.parallel(claim, jobs)), 2)
        con = self.connect()
        self.assertEqual(con.execute(
            "SELECT COUNT(*) FROM mrxp_reward_intents WHERE kind='daily'"
        ).fetchone()[0], 2)
        self.assertEqual(con.execute(
            "SELECT SUM(xp_awarded) FROM mrxp_reward_intents"
        ).fetchone()[0], 200)
        con.close()

    def test_rate_limiter_is_atomic_per_account(self):
        now = int(time.time() * 1000)
        def hit(uid):
            con = self.connect()
            try:
                return con.execute(
                    RATE, (uid, "/api/rewards/claim", now,
                           now, 60000, now, 60000, now, now, 60000, 25)
                ).rowcount
            finally:
                con.close()

        jobs = ["one"] * 50 + ["two"] * 50
        results = self.parallel(hit, jobs)
        self.assertEqual(sum(results), 50)
        con = self.connect()
        counts = dict(con.execute("SELECT user_id,count FROM mrxp_api_limits").fetchall())
        self.assertEqual(counts, {"one": 25, "two": 25})
        con.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
