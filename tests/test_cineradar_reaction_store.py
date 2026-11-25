import base64
import os
import sqlite3
import unittest
from unittest.mock import patch

from scripts.cineradar_reaction_store import (
    ReactionVault, LocalReactionDB, pack, unpack,
)
from scripts.cineradar_reactions_github_only import observe


SCHEMA = """
CREATE TABLE channel_reaction_posts (
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 chat_id TEXT NOT NULL,
 message_id INTEGER NOT NULL,
 media_group_id TEXT,
 UNIQUE(chat_id,message_id)
);
CREATE UNIQUE INDEX idx_album ON channel_reaction_posts(chat_id,media_group_id)
 WHERE media_group_id IS NOT NULL;
CREATE TABLE channel_reaction_jobs (
 post_seq INTEGER REFERENCES channel_reaction_posts(seq),
 bot_role TEXT,
 state TEXT,
 PRIMARY KEY(post_seq,bot_role)
);
CREATE TABLE channel_reaction_extra_jobs (
 post_seq INTEGER REFERENCES channel_reaction_posts(seq),
 bot_slot INTEGER,
 state TEXT,
 PRIMARY KEY(post_seq,bot_slot)
);
CREATE TABLE channel_reaction_extra_bot_activation (
 bot_slot INTEGER PRIMARY KEY,
 start_after_seq INTEGER NOT NULL
);
CREATE TABLE channel_reaction_terminal_posts (
 post_seq INTEGER PRIMARY KEY REFERENCES channel_reaction_posts(seq),
 reason TEXT
);
"""


class EncryptedReactionStateTests(unittest.TestCase):
    def create_db(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO channel_reaction_posts(chat_id,message_id) VALUES(?,?)",
                     ("-1003921647496", 25))
        conn.execute("INSERT INTO channel_reaction_jobs VALUES(1,'radar','sent')")
        conn.commit()
        return conn

    def test_local_encrypted_snapshot_round_trip(self):
        db = self.create_db()
        try:
            snapshot = pack(db, observer_offset=888)
            restored, cursor = unpack(snapshot)
            try:
                self.assertEqual(cursor, 888)
                self.assertEqual(restored.execute(
                    "SELECT message_id FROM channel_reaction_posts"
                ).fetchone()[0], 25)
                self.assertEqual(restored.execute(
                    "SELECT state FROM channel_reaction_jobs"
                ).fetchone()[0], "sent")
            finally:
                restored.close()
        finally:
            db.close()

    def test_corrupt_snapshot_rejected(self):
        db = self.create_db()
        try:
            snapshot = pack(db)
            snapshot["sqlite_zlib_b64"] = "bm90LXNxbGl0ZQ=="
            with self.assertRaises(Exception):
                unpack(snapshot)
        finally:
            db.close()

    def test_vault_uses_distinct_authenticated_encryption_key(self):
        env = {"ML_V2_HISTORY_KEY_B64": base64.b64encode(b"x" * 32).decode()}
        with patch.dict(os.environ, env):
            vault = ReactionVault(repo="MrXPRONOS/MrXPRONOS_App",
                                  branch="main",token="dummy")
            payload = {"version": 1, "format": "test"}
            from scripts.actu_foot_github_vault import derive_key, seal, unseal
            sealed = seal(payload, vault.key)
            self.assertEqual(unseal(sealed, vault.key), payload)
            self.assertNotEqual(vault.key, derive_key())

    def test_observer_uses_telegram_only_and_deduplicates(self):
        db = self.create_db()
        wrapped = LocalReactionDB(db)
        messages = []
        def fake(url, data, headers):
            method = url.rsplit("/", 1)[-1]
            messages.append(method)
            if method == "getMe":
                return 200, {"ok": True, "result": {"is_bot": True, "id": 123}}
            if method == "getWebhookInfo":
                return 200, {"ok": True, "result": {"url": ""}}
            if method == "getChatMember":
                return 200, {"ok": True, "result": {"status": "administrator"}}
            if method == "getUpdates":
                return 200, {"ok": True, "result": [
                    {"update_id": 202, "channel_post": {
                        "chat": {"id": -1003921647496, "type": "channel"},
                        "message_id": 27,
                    }},
                    {"update_id": 203, "channel_post": {
                        "chat": {"id": -1003921647496, "type": "channel"},
                        "message_id": 27,
                    }},
                ]}
            raise AssertionError(method)
        try:
            cursor, n = observe(wrapped, {
                "CINERADAR_REACTION_OBSERVER_TOKEN": "fake",
            }, 200, transport=fake)
            self.assertEqual(cursor, 204)
            self.assertEqual(n, 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM channel_reaction_posts").fetchone()[0], 2)
            self.assertEqual(messages.count("getUpdates"), 1)
        finally:
            db.close()

    def test_observer_refuses_parallel_webhook(self):
        db = self.create_db()
        def fake(url, data, headers):
            method = url.rsplit("/", 1)[-1]
            if method == "getMe":
                return 200, {"ok": True, "result": {"is_bot": True, "id": 123}}
            return 200, {"ok": True, "result": {"url": "https://another.example/hook"}}
        try:
            with self.assertRaisesRegex(RuntimeError, "webhook"):
                observe(LocalReactionDB(db), {
                    "CINERADAR_REACTION_OBSERVER_TOKEN": "fake",
                }, 200, transport=fake)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
