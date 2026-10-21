import tempfile
import threading
import unittest
from pathlib import Path
from decimal import Decimal
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import Store, now
from odds import calculate_total_odds, assert_minimum_odds


VALID = [
    {'match': 'Arsenal - Chelsea', 'market': 'Plus de 1,5 but', 'odd': '1.70'},
    {'match': 'Milan - Napoli', 'market': 'Double chance 1X', 'odd': '2.40'},
]


class CouponTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(str(Path(self.tmp.name) / 'coupons.db'))
        self.store.ensure_user(12345, 'Alpha')
        self.store.confirm_adult(12345)
        self.store.verify_requirements(12345, 0, False)

    def test_combined_odds(self):
        self.assertEqual(calculate_total_odds(VALID), Decimal('4.08'))
        self.assertEqual(assert_minimum_odds(VALID), Decimal('4.08'))

    def test_exactly_four_accepted(self):
        self.assertEqual(assert_minimum_odds([{'match':'A - B','market':'Victoire domicile','odd':'4.00'}]), Decimal('4.00'))

    def test_below_four_rejected(self):
        with self.assertRaisesRegex(ValueError, 'insuffisante'):
            assert_minimum_odds([{'match':'A - B','market':'Victoire domicile','odd':'3.99'}])
        with self.assertRaisesRegex(ValueError, 'insuffisante'):
            # 2.15 x 1.86 = 3.9990, s'affiche 4.00 après arrondi,
            # mais DOIT être rejeté pour éviter des faux 4.00.
            assert_minimum_odds([
                {'match':'A - B','market':'Marché A','odd':'2.15'},
                {'match':'C - D','market':'Marché B','odd':'1.86'}
            ])

    def test_invalid_odds_rejected(self):
        for bad in ('1.00','0','nan','inf','abc','1000','1.123'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                assert_minimum_odds([{'match':'A - B','market':'Marché sportif','odd':bad}])

    def test_add_coupon_and_redeem_exactly_once(self):
        self.store.grant_points(12345, 80, 999)
        coupon_id = self.store.add_coupon('PRO', 'Le soir', VALID, 50, now()+3600, 10)
        c = self.store.coupon(coupon_id)
        self.assertEqual(c['total_odds'], '4.08')
        self.assertEqual(self.store.redeem_coupon(12345, coupon_id)[0], 'ok')
        self.assertEqual(self.store.redeem_coupon(12345, coupon_id)[0], 'already')
        self.assertEqual(self.store.user(12345)['points'], 30)
        self.assertEqual(self.store.coupon(coupon_id)['stock'], 9)
        my = self.store.my_coupons(12345)
        self.assertEqual(my[0]['total_odds_snapshot'], '4.08')
        self.assertIn('Arsenal', my[0]['selections_snapshot'])

    def test_insufficient_xp_and_stock(self):
        cid = self.store.add_coupon('VIP', 'Ticket VIP', VALID, 50, now()+3600, 1)
        self.assertEqual(self.store.redeem_coupon(12345, cid)[0], 'insufficient')
        self.store.grant_points(12345, 60, 999)
        self.assertEqual(self.store.redeem_coupon(12345, cid)[0], 'ok')
        self.store.ensure_user(456, 'Bêta')
        self.store.confirm_adult(456)
        self.store.verify_requirements(456, 0, False)
        self.store.grant_points(456, 60, 999)
        self.assertEqual(self.store.redeem_coupon(456, cid)[0], 'unavailable')
        self.assertEqual(self.store.user(456)['points'], 60)

    def test_no_coupon_below_four(self):
        with self.assertRaisesRegex(ValueError, 'insuffisante'):
            self.store.add_coupon('SIMPLE','Mauvais coupon',
                                  [{'match':'A - B','market':'Plus de 1,5 but','odd':'3.99'}],
                                  0,now()+3600)
        self.assertEqual(self.store.stats()['coupons'], 0)

    def test_no_double_bonus(self):
        self.assertEqual(self.store.claim_bonus(12345, 5, 7200, 10)[0], 'ok')
        self.assertEqual(self.store.claim_bonus(12345, 5, 7200, 10)[0], 'cooldown')
        self.assertEqual(self.store.user(12345)['points'], 5)

    def test_task_claim_once(self):
        tid = self.store.add_task('@canal','https://t.me/canal',15)
        self.assertEqual(self.store.claim_task(12345, tid), 'ok')
        self.assertEqual(self.store.claim_task(12345, tid), 'already')
        self.assertEqual(self.store.user(12345)['points'], 15)

    def test_referral_once(self):
        self.store.ensure_user(678, 'Filleul', referred_by=12345)
        self.store.confirm_adult(678)
        self.assertEqual(self.store.verify_requirements(678, 30, True), 'referral_rewarded')
        self.assertEqual(self.store.verify_requirements(678, 30, True), 'verified')
        self.assertEqual(self.store.user(12345)['points'], 30)

    def test_referral_disabled_without_required_channels(self):
        self.store.ensure_user(678, 'Filleul', referred_by=12345)
        self.store.confirm_adult(678)
        self.assertEqual(self.store.verify_requirements(678, 30, False), 'verified')
        self.assertEqual(self.store.user(12345)['points'], 0)

    def test_locked_for_unverified(self):
        self.store.ensure_user(678,'Filleul')
        self.assertEqual(self.store.claim_task(678, self.store.add_task('@test','https://t.me/test',20)),'locked')
        cid = self.store.add_coupon('SIMPLE','A',VALID,0,now()+3600)
        self.assertEqual(self.store.redeem_coupon(678,cid)[0], 'locked')

    def test_concurrent_single_stock(self):
        self.store.grant_points(12345, 100, 999)
        uid = 456
        self.store.ensure_user(uid, 'Bêta')
        self.store.confirm_adult(uid)
        self.store.verify_requirements(uid, 0, False)
        self.store.grant_points(uid, 100, 999)
        cid = self.store.add_coupon('PRO','Dernier', VALID, 50, now()+3600, stock=1)
        results = []
        lock = threading.Lock()
        def run(user):
            res = self.store.redeem_coupon(user, cid)[0]
            with lock:
                results.append(res)
        a = threading.Thread(target=run, args=(12345,))
        b = threading.Thread(target=run, args=(456,))
        a.start(); b.start(); a.join(); b.join()
        self.assertEqual(sorted(results), ['ok','unavailable'])
        self.assertEqual(self.store.coupon(cid)['stock'], 0)
        self.assertEqual(self.store.user(12345)['points'] + self.store.user(uid)['points'], 150)

    def test_expiry_and_disable(self):
        cid = self.store.add_coupon('SIMPLE', 'Le soir', VALID, 0, now()+3600)
        self.store.set_coupon_active(cid, False)
        self.assertEqual(self.store.redeem_coupon(12345, cid)[0], 'unavailable')
        self.store.set_coupon_active(cid, True)
        with self.store.connect() as db:
            db.execute('UPDATE coupons SET expires_at=? WHERE id=?', (now()-1, cid))
        self.assertEqual(self.store.redeem_coupon(12345, cid)[0], 'unavailable')

    def test_legacy_money_db_rejected(self):
        path = Path(self.tmp.name) / 'legacy.db'
        import sqlite3
        db = sqlite3.connect(path)
        try:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)')
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(RuntimeError, 'Ancienne base FCFA'):
            Store(str(path))


if __name__ == '__main__':
    unittest.main()
