"""SQLite: points virtuels, missions vérifiées et coupons de pronostics.

Aucune donnée financière, aucun versement, aucune cote ni pronostic fabriqué.
Les coupons sont fournis explicitement par l'administrateur.
"""
from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from odds import normalize_selections, assert_minimum_odds
import time
from datetime import datetime, timezone
from pathlib import Path


def now() -> int:
    return int(time.time())


def utc_day(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d')


class Store:
    def __init__(self, path: str = './data/coupons.db'):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            existing = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'users' in existing:
                columns = {r['name'] for r in db.execute('PRAGMA table_info(users)')}
                if 'points' not in columns or 'balance' in columns:
                    raise RuntimeError(
                        'Ancienne base FCFA détectée. Elle ne peut PAS être réutilisée. '
                        'Choisis un DB_PATH distinct, par exemple ./data/coupons.db.'
                    )
            if 'coupons' in existing:
                old_columns = {r['name'] for r in db.execute('PRAGMA table_info(coupons)')}
                if 'total_odds' not in old_columns or 'selections_json' not in old_columns:
                    raise RuntimeError('Ancienne table de coupons détectée. Utilise une nouvelle DB_PATH (coupons_v4.db).')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    referred_by INTEGER,
                    adult_confirmed INTEGER NOT NULL DEFAULT 0,
                    required_verified INTEGER NOT NULL DEFAULT 0,
                    referral_rewarded INTEGER NOT NULL DEFAULT 0,
                    points INTEGER NOT NULL DEFAULT 0 CHECK(points >= 0),
                    created_at INTEGER NOT NULL,
                    last_bonus_at INTEGER NOT NULL DEFAULT 0,
                    bonus_day TEXT NOT NULL DEFAULT '',
                    bonus_today INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    points INTEGER NOT NULL CHECK(points > 0),
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS task_claims (
                    user_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    claimed_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id, task_id)
                );
                CREATE TABLE IF NOT EXISTS coupons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL CHECK(category IN ('SIMPLE','PRO','VIP')),
                    title TEXT NOT NULL,
                    selections_json TEXT NOT NULL,
                    total_odds TEXT NOT NULL,
                    cost INTEGER NOT NULL CHECK(cost >= 0),
                    expires_at INTEGER NOT NULL,
                    stock INTEGER NOT NULL DEFAULT -1 CHECK(stock = -1 OR stock >= 0),
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS redemptions (
                    user_id INTEGER NOT NULL,
                    coupon_id INTEGER NOT NULL,
                    spent INTEGER NOT NULL CHECK(spent >= 0),
                    claimed_at INTEGER NOT NULL,
                    title_snapshot TEXT NOT NULL,
                    selections_snapshot TEXT NOT NULL,
                    total_odds_snapshot TEXT NOT NULL,
                    category_snapshot TEXT NOT NULL,
                    expires_at_snapshot INTEGER NOT NULL,
                    PRIMARY KEY(user_id, coupon_id)
                );
                CREATE TABLE IF NOT EXISTS point_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_coupon_expiry ON coupons(active,expires_at);
                CREATE INDEX IF NOT EXISTS ix_referrer ON users(referred_by);
                CREATE INDEX IF NOT EXISTS ix_redemptions_user ON redemptions(user_id,claimed_at);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute('PRAGMA busy_timeout=15000')
            db.execute('PRAGMA foreign_keys=ON')
            db.row_factory = sqlite3.Row
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def ensure_user(self, uid: int, name: str, referred_by: int | None = None) -> bool:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone()
            if old:
                db.execute('UPDATE users SET name=? WHERE id=?', (name[:100], uid))
                return False
            ref = None
            if referred_by and referred_by != uid:
                if db.execute('SELECT 1 FROM users WHERE id=?', (referred_by,)).fetchone():
                    ref = referred_by
            db.execute('INSERT INTO users(id,name,referred_by,created_at) VALUES (?,?,?,?)',
                       (uid, name[:100] or 'Membre', ref, now()))
            return True

    def user(self, uid: int) -> dict | None:
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            return dict(row) if row else None

    def confirm_adult(self, uid: int):
        with self.connect() as db:
            return db.execute('UPDATE users SET adult_confirmed=1 WHERE id=?', (uid,)).rowcount == 1

    @staticmethod
    def _eligible(db, uid):
        row = db.execute('SELECT adult_confirmed,required_verified FROM users WHERE id=?',
                         (uid,)).fetchone()
        return bool(row and row['adult_confirmed'] and row['required_verified'])

    @staticmethod
    def _add_points(db, uid, value, reason):
        if value == 0:
            return
        db.execute('UPDATE users SET points=points+? WHERE id=?', (value, uid))
        db.execute('INSERT INTO point_ledger(user_id,delta,reason,created_at) VALUES (?,?,?,?)',
                   (uid, value, reason, now()))

    def verify_requirements(self, uid: int, referral_points: int, referrals_enabled: bool):
        """À appeler UNIQUEMENT après vérification des canaux par l'API Telegram."""
        if referral_points < 0:
            raise ValueError('Points négatifs')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            u = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            if not u:
                return 'missing'
            if not u['adult_confirmed']:
                return 'underage_not_confirmed'
            db.execute('UPDATE users SET required_verified=1 WHERE id=?', (uid,))
            if not referrals_enabled or not referral_points or not u['referred_by'] or u['referral_rewarded']:
                return 'verified'
            # Crédit attribué une seule fois même si Vérifier est pressé à répétition.
            if not db.execute('SELECT 1 FROM users WHERE id=?', (u['referred_by'],)).fetchone():
                return 'verified'
            self._add_points(db, u['referred_by'], referral_points, f'referral:{uid}')
            db.execute('UPDATE users SET referral_rewarded=1 WHERE id=?', (uid,))
            return 'referral_rewarded'

    def referral_count(self, uid):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM users WHERE referred_by=? AND referral_rewarded=1',
                              (uid,)).fetchone()[0]

    def add_task(self, chat_id, url, points):
        if points <= 0 or points > 100_000:
            raise ValueError('Points de mission hors limites')
        with self.connect() as db:
            cur = db.execute('INSERT INTO tasks(chat_id,url,points) VALUES(?,?,?)',
                             (str(chat_id), url, points))
            return cur.lastrowid

    def disable_task(self, task_id):
        with self.connect() as db:
            return db.execute('UPDATE tasks SET active=0 WHERE id=? AND active=1',
                              (task_id,)).rowcount == 1

    def tasks(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM tasks WHERE active=1 ORDER BY id DESC')]

    def task(self, task_id):
        with self.connect() as db:
            r = db.execute('SELECT * FROM tasks WHERE active=1 AND id=?', (task_id,)).fetchone()
            return dict(r) if r else None

    def claimed_task_ids(self, uid):
        with self.connect() as db:
            return {r[0] for r in db.execute('SELECT task_id FROM task_claims WHERE user_id=?', (uid,))}

    def claim_task(self, uid, task_id):
        """À appeler uniquement après vérification get_chat_member positive."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self._eligible(db, uid):
                return 'locked'
            task = db.execute('SELECT points FROM tasks WHERE id=? AND active=1', (task_id,)).fetchone()
            if not task:
                return 'missing'
            if db.execute('SELECT 1 FROM task_claims WHERE user_id=? AND task_id=?',
                          (uid, task_id)).fetchone():
                return 'already'
            db.execute('INSERT INTO task_claims VALUES (?,?,?)', (uid, task_id, now()))
            self._add_points(db, uid, task['points'], f'task:{task_id}')
            return 'ok'

    def claim_bonus(self, uid: int, points: int, cooldown: int, daily_cap: int):
        if points <= 0 or cooldown <= 0 or daily_cap < points:
            raise ValueError('Configuration bonus invalide')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self._eligible(db, uid):
                return ('locked', 0)
            u = db.execute('SELECT last_bonus_at,bonus_day,bonus_today FROM users WHERE id=?',
                           (uid,)).fetchone()
            ts = now()
            left = max(0, cooldown - (ts - u['last_bonus_at']))
            if left:
                return ('cooldown', left)
            today = utc_day(ts)
            total = u['bonus_today'] if u['bonus_day'] == today else 0
            if total + points > daily_cap:
                return ('daily_cap', 0)
            db.execute('UPDATE users SET last_bonus_at=?,bonus_day=?,bonus_today=? WHERE id=?',
                       (ts, today, total + points, uid))
            self._add_points(db, uid, points, 'periodic_bonus')
            return ('ok', 0)

    def grant_points(self, uid, amount, admin_id):
        if not 0 < amount <= 100_000:
            raise ValueError('Montant XP invalide')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                return False
            self._add_points(db, uid, amount, f'admin:{admin_id}')
            return True

    def add_coupon(self, category, title, selections, cost, expires_at, stock=-1):
        """L'ajout est rejeté si la cote combinée calculée est inférieure à 4.00."""
        category = category.upper()
        if category not in ('SIMPLE', 'PRO', 'VIP'):
            raise ValueError('Catégorie attendue : SIMPLE, PRO ou VIP.')
        if not isinstance(cost, int) or not 0 <= cost <= 100_000:
            raise ValueError('Coût XP invalide.')
        if not isinstance(stock, int) or (stock != -1 and not 1 <= stock <= 1_000_000):
            raise ValueError('Stock invalide (1..1000000 ou -1).')
        if not 1 <= len(title.strip()) <= 120:
            raise ValueError('Titre (1-120 caractères) requis.')
        if expires_at <= now():
            raise ValueError('Date limite dépassée.')
        selections = normalize_selections(selections)
        total = assert_minimum_odds(selections)
        with self.connect() as db:
            cur = db.execute('''INSERT INTO coupons(category,title,selections_json,total_odds,cost,expires_at,stock,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (category, title.strip(), json.dumps(selections, ensure_ascii=False),
                 str(total), cost, expires_at, stock, now()))
            return cur.lastrowid

    def set_coupon_active(self, coupon_id, active):
        with self.connect() as db:
            return db.execute('UPDATE coupons SET active=? WHERE id=?',
                              (int(active), coupon_id)).rowcount == 1

    def coupon(self, coupon_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM coupons WHERE id=?', (coupon_id,)).fetchone()
            return dict(row) if row else None

    def available_coupons(self, timestamp=None):
        ts = now() if timestamp is None else timestamp
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT * FROM coupons
                WHERE active=1 AND expires_at>? AND (stock=-1 OR stock>0)
                ORDER BY expires_at ASC, id DESC''', (ts,))]

    def all_coupons(self, limit=30):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM coupons ORDER BY id DESC LIMIT ?', (limit,))]

    def redeemed_ids(self, uid):
        with self.connect() as db:
            return {r[0] for r in db.execute('SELECT coupon_id FROM redemptions WHERE user_id=?', (uid,))}

    def owned_coupon(self, uid, coupon_id):
        with self.connect() as db:
            r = db.execute('SELECT * FROM redemptions WHERE user_id=? AND coupon_id=?',
                           (uid, coupon_id)).fetchone()
            return dict(r) if r else None

    def my_coupons(self, uid, limit=30):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT * FROM redemptions
                WHERE user_id=? ORDER BY claimed_at DESC,coupon_id DESC LIMIT ?''', (uid,limit))]

    def redeem_coupon(self, uid, coupon_id):
        """Attribution atomique, protège contre double-clic, stocks et points insuffisants."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self._eligible(db, uid):
                return ('locked', None)
            if db.execute('SELECT 1 FROM redemptions WHERE user_id=? AND coupon_id=?',
                          (uid, coupon_id)).fetchone():
                return ('already', None)
            c = db.execute('SELECT * FROM coupons WHERE id=?', (coupon_id,)).fetchone()
            if not c:
                return ('missing', None)
            if not c['active'] or c['expires_at'] <= now() or c['stock'] == 0:
                return ('unavailable', None)
            if db.execute('UPDATE users SET points=points-? WHERE id=? AND points>=?',
                          (c['cost'], uid, c['cost'])).rowcount != 1:
                return ('insufficient', None)
            if c['stock'] > 0:
                if db.execute('UPDATE coupons SET stock=stock-1 WHERE id=? AND stock>0',
                              (coupon_id,)).rowcount != 1:
                    raise RuntimeError('Stock incohérent, transaction annulée')
            ts = now()
            db.execute('''INSERT INTO redemptions
                (user_id,coupon_id,spent,claimed_at,title_snapshot,selections_snapshot,total_odds_snapshot,category_snapshot,expires_at_snapshot)
                VALUES (?,?,?,?,?,?,?,?,?)''', (uid, coupon_id, c['cost'], ts,
                    c['title'], c['selections_json'], c['total_odds'], c['category'], c['expires_at']))
            db.execute('INSERT INTO point_ledger(user_id,delta,reason,created_at) VALUES (?,?,?,?)',
                       (uid, -c['cost'], f'coupon:{coupon_id}', ts))
            return ('ok', dict(c))

    def stats(self):
        with self.connect() as db:
            get = lambda sql: db.execute(sql).fetchone()[0]
            return {
                'users': get('SELECT COUNT(*) FROM users'),
                'verified': get('SELECT COUNT(*) FROM users WHERE required_verified=1 AND adult_confirmed=1'),
                'referrals': get('SELECT COUNT(*) FROM users WHERE referral_rewarded=1'),
                'tasks': get('SELECT COUNT(*) FROM task_claims'),
                'coupons': get('SELECT COUNT(*) FROM coupons'),
                'redeemed': get('SELECT COUNT(*) FROM redemptions'),
                'points_earned': get('SELECT COALESCE(SUM(delta),0) FROM point_ledger WHERE delta>0'),
                'points_spent': get('SELECT COALESCE(SUM(-delta),0) FROM point_ledger WHERE delta<0'),
                'points_available': get('SELECT COALESCE(SUM(points),0) FROM users'),
            }
