"""Bot API inbox accepts only allowlisted channel posts, idempotently."""
import unittest

from film_relay.anime_bot_queue import ingest_channel_updates


SOURCE = "-1001234567890"


def update(uid, mid, *, chat=SOURCE, caption="Naruto S01E07",
           kind="video", edited=False, protected=False):
    file = {"file_id": "FILE_TOKEN", "file_unique_id": "UNIQUE",
            "file_name": "Naruto_S01E07.mkv", "mime_type": "video/mp4"}
    message = {"message_id": mid, "chat": {"id": int(chat), "type": "channel"},
               "date": 1795260000, "caption": caption,
               "has_protected_content": protected}
    message[kind] = file if kind != "photo" else [file]
    return {"update_id": uid,
            "edited_channel_post" if edited else "channel_post": message}


class BotSourceQueueTests(unittest.TestCase):
    def test_channel_video_is_persisted_only_once(self):
        a = update(101, 7)
        state, report = ingest_channel_updates([a], {}, [SOURCE])
        self.assertEqual(report["accepted"], 1)
        self.assertIn(SOURCE + ":7", state["messages"])
        self.assertEqual(state["last_update_id"], 101)
        after, report = ingest_channel_updates([a], state, [SOURCE])
        self.assertEqual(report["repeated"], 1)
        self.assertEqual(after, state)

    def test_unauthorized_and_protected_sources_are_rejected(self):
        state, report = ingest_channel_updates([
            update(101, 7, chat="-1002222222222"),
            update(102, 8, protected=True),
        ], {}, [SOURCE])
        self.assertEqual(report["unauthorized"], 1)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(state["messages"], {})
        self.assertEqual(state["last_update_id"], 102)

    def test_gif_and_text_are_kept_as_context_not_episodes(self):
        gif = update(101, 10, kind="animation", caption="Hebdomadaire")
        text = {"update_id": 102, "channel_post": {
            "message_id": 11, "chat": {"id": int(SOURCE)},
            "text": "Nouvelle sortie ce soir", "date": 1795260000}}
        state, _ = ingest_channel_updates([gif, text], {}, [SOURCE])
        self.assertEqual(state["messages"][SOURCE + ":10"]["kind"], "animation")
        self.assertEqual(state["messages"][SOURCE + ":10"]["cadence_hint"], "weekly")
        self.assertEqual(state["messages"][SOURCE + ":11"]["kind"], "text")

    def test_edit_preserves_receipt_and_changes_caption(self):
        first, _ = ingest_channel_updates([update(101, 7)], {}, [SOURCE])
        first["messages"][SOURCE + ":7"]["status"] = "published"
        edited, report = ingest_channel_updates([
            update(102, 7, caption="Naruto S01E07 - corrigé", edited=True)
        ], first, [SOURCE])
        self.assertEqual(report["edited"], 1)
        self.assertEqual(edited["messages"][SOURCE + ":7"]["status"], "published")
        self.assertIn("corrigé", edited["messages"][SOURCE + ":7"]["text"])

    def test_queue_overflow_never_advances_cursor(self):
        source = {"last_update_id": 100, "messages": {}}
        with self.assertRaisesRegex(RuntimeError, "pleine"):
            ingest_channel_updates([update(101, 7)], source,
                                   [SOURCE], max_messages=0)
        self.assertEqual(source["last_update_id"], 100)

    def test_source_ids_require_real_channel_ids(self):
        with self.assertRaises(ValueError):
            ingest_channel_updates([], {}, ["@notanid"])


if __name__ == "__main__":
    unittest.main()
