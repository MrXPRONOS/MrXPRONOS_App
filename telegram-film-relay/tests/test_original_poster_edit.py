"""Regression tests: edit the historic CineX photo in place, never clone it."""
import asyncio
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from film_relay.original_poster_edit import (
    edit_original_cover, safe_buttons, original_caption_with_text,
    preflight_original_editability,
)
from film_relay.legacy_archive_repair import original_public_poster_verified
from film_relay.ten_video_rotation import verify_existing_pair


def message(mid, text, *, photo=None, video=None, doc=None, buttons=None):
    return NS(id=mid, raw_text=text, photo=NS(id=photo) if photo else None,
              video=object() if video else None,
              document=NS(id=doc, attributes=[]) if doc else None,
              file=NS(name="cinex.mkv"), buttons=buttons or [],
              noforwards=False, entities=[])


class FakeBot:
    def __init__(self, client):
        self.client = client
        self.calls = []

    async def edit_reply_markup(self, channel, message_id, *, buttons):
        self.calls.append(("edit_reply_markup", message_id))
        self.client.live.buttons = buttons
        return True

    async def edit_photo_caption(self, channel, message_id, *, caption, buttons,
                                 parse_mode=None):
        self.calls.append(("edit_photo_caption", message_id))
        self.client.live.raw_text = caption.replace("&amp;", "&").replace("&lt;", "<")
        self.client.live.buttons = buttons
        return True

    async def send_file(self, *args, **kwargs):
        raise AssertionError("Aucune nouvelle fiche publique autorisée")


class FakeClient:
    def __init__(self, post):
        self.live = post

    async def get_messages(self, channel, ids):
        return self.live


class OriginalCoverEditTests(unittest.TestCase):
    def test_no_op_edit_preflight_keeps_photo_text_and_buttons(self):
        original = message(99, "Film historique", photo=205, buttons=[
            [NS(text="Voir", url="https://t.me/c/4392607284/17")]])
        client, bot = FakeClient(original), FakeBot(FakeClient(original))
        bot.client = client
        result = asyncio.run(preflight_original_editability(client, bot, "public", original))
        self.assertTrue(result)
        self.assertEqual(bot.calls, [("edit_reply_markup", 99)])
        self.assertEqual(original.photo.id, 205)
        self.assertEqual(original.raw_text, "Film historique")
        self.assertEqual(original.buttons[0][0].url, "https://t.me/c/4392607284/17")

    def test_uneditable_historic_poster_fails_before_any_private_copy(self):
        original = message(101, "Ancien film", photo=333)
        client = FakeClient(original)
        class RejectBot(FakeBot):
            async def edit_reply_markup(self, channel, message_id, *, buttons):
                raise RuntimeError("message can't be edited")
        bot = RejectBot(client)
        with self.assertRaisesRegex(RuntimeError, "can't be edited"):
            asyncio.run(preflight_original_editability(client, bot, "public", original))
        self.assertEqual(original.photo.id, 333)
        self.assertEqual(original.raw_text, "Ancien film")

    def test_same_photo_same_message_same_caption_only_buttons_added(self):
        source = message(401, "🎬 Le Grand Film\nSynopsis original", photo=555,
                         buttons=[[NS(text="📢 Actualités", url="https://t.me/CineXFilms_vf")]])
        original = message(401, source.raw_text, photo=555,
                           buttons=[[NS(text="📢 Actualités", url="https://t.me/CineXFilms_vf")]])
        client, bot = FakeClient(source), None
        bot = FakeBot(client)
        required = [NS(text="🎬 VOIR LE FILM", url="https://t.me/c/4392607284/55"),
                    NS(text="⬇️ TÉLÉCHARGER", url="https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)]
        updated = asyncio.run(edit_original_cover(
            client, bot, "public", original, None, buttons=[[required[0]], [required[1]]],
            private_video_url=required[0].url))
        self.assertEqual(updated.id, 401)
        self.assertEqual(updated.photo.id, 555)
        self.assertEqual(updated.raw_text, "🎬 Le Grand Film\nSynopsis original")
        self.assertEqual(bot.calls, [("edit_reply_markup", 401)])
        urls = [b.url for row in updated.buttons for b in row]
        self.assertEqual(urls, [
            "https://t.me/CineXFilms_vf", required[0].url, required[1].url])

    def test_photo_text_video_merges_description_on_original(self):
        original = message(120, "📺 Naruto - Saison 1", photo=887)
        live = message(120, "📺 Naruto - Saison 1", photo=887)
        client, bot = FakeClient(live), None
        bot = FakeBot(client)
        edited = asyncio.run(edit_original_cover(
            client, bot, "public", original, None,
            buttons=[[NS(text="▶️ Regarder",
                          url="https://t.me/c/4455497484/100")]],
            private_video_url="https://t.me/c/4455497484/100",
            extra_text="Synopsis : Un ninja découvre sa mission"))
        self.assertEqual(edited.id, original.id)
        self.assertEqual(edited.photo.id, original.photo.id)
        self.assertIn("📺 Naruto - Saison 1", edited.raw_text)
        self.assertIn("Synopsis : Un ninja", edited.raw_text)
        self.assertEqual(bot.calls, [("edit_photo_caption", 120)])

    def test_existing_buttons_are_preserved_and_not_duplicated(self):
        source = message(1, "Film", photo=55, buttons=[
            [NS(text="Annonces", url="https://t.me/CineXFilms_vf")],
            [NS(text="Voir", url="https://t.me/c/4392607284/55")],
        ])
        result = safe_buttons(source, [
            [NS(text="Regarder", url="https://t.me/c/4392607284/55")],
            [NS(text="Télécharger", url="https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)],
        ], "https://t.me/c/4392607284/55")
        self.assertEqual(len([b for row in result for b in row]), 3)
        self.assertEqual(result[1][0].text, "Voir")

    def test_other_video_target_is_not_overwritten(self):
        source = message(1, "Film", photo=55, buttons=[
            [NS(text="Regarder", url="https://t.me/c/4392607284/999")]])
        with self.assertRaisesRegex(RuntimeError, "autre vidéo"):
            safe_buttons(source, [
                [NS(text="Regarder", url="https://t.me/c/4392607284/55")]],
                "https://t.me/c/4392607284/55")

    def test_opaque_callback_buttons_block_edit(self):
        source = message(1, "Film", photo=55, buttons=[
            [NS(text="Détails", data=b"callback")]])
        with self.assertRaisesRegex(RuntimeError, "non-URL"):
            safe_buttons(source, [[NS(text="Regarder", url="https://t.me/c/4392607284/55")]],
                         "https://t.me/c/4392607284/55")

    def test_no_caption_truncation(self):
        source = message(1, "A"*1000, photo=55)
        with self.assertRaisesRegex(RuntimeError, "trop longue"):
            original_caption_with_text(source, "B"*100)

    def test_caption_entities_preserved_by_html_path(self):
        source = message(1, "Une histoire <incroyable>", photo=55)
        source.text_html = "Une histoire <b>&lt;incroyable&gt;</b>"
        value, changed, html = original_caption_with_text(source, "Suite & fin")
        self.assertTrue(changed)
        self.assertTrue(html)
        self.assertIn("<b>&lt;incroyable&gt;</b>", value)
        self.assertIn("Suite &amp; fin", value)

    def test_denied_edit_leaves_public_video_and_no_clone(self):
        source = message(1, "Film original", photo=50)
        other = message(1, "Film original", photo=50)
        client = FakeClient(source)
        class DeniedBot(FakeBot):
            async def edit_reply_markup(self, channel, message_id, *, buttons):
                raise RuntimeError("message can't be edited")
        bot = DeniedBot(client)
        with self.assertRaisesRegex(RuntimeError, "can't be edited"):
            asyncio.run(edit_original_cover(
                client, bot, "public", other, None,
                buttons=[[NS(text="Regarder", url="https://t.me/c/4392607284/55")]],
                private_video_url="https://t.me/c/4392607284/55"))
        self.assertEqual(source.raw_text, "Film original")
        self.assertFalse(source.buttons)
        self.assertEqual(bot.calls, [])


class OriginalDeletionProofTests(unittest.TestCase):
    def test_duplicate_after_video_does_not_authorize_deletion(self):
        public_photo = message(100, "Saga Partie 2", photo=10)
        video = message(101, "Saga Partie 2", video=True, doc=777)
        # Old duplicate created after the original media, with all buttons:
        link = "https://t.me/c/4392607284/55"
        rescue, folder = "https://t.me/+ABCdefghi123456", "https://t.me/addlist/AAA"
        duplicate = message(900, "Saga Partie 2", photo=20, buttons=[
            [NS(url=link)], [NS(url=rescue)], [NS(url=folder)]])
        private_photo = message(54, "Saga Partie 2", photo=100, buttons=[
            [NS(url=rescue)], [NS(url=folder)]])
        private_video = message(55, "Saga Partie 2", video=True, doc=777)

        class Client:
            async def get_messages(self, channel, ids):
                return [private_photo] if isinstance(ids, list) else private_video

        with (patch("film_relay.ten_video_rotation.rescue_link_for", return_value=rescue),
              patch("film_relay.ten_video_rotation.film_folder_url", return_value=folder)):
            without_original = asyncio.run(verify_existing_pair(
                Client(), "public", "private", -1004392607284, video,
                [public_photo, duplicate], "films",
                messages=[public_photo, video, duplicate]))
            self.assertIsNone(without_original)
            public_photo.buttons = duplicate.buttons
            with_original = asyncio.run(verify_existing_pair(
                Client(), "public", "private", -1004392607284, video,
                [public_photo, duplicate], "films",
                messages=[public_photo, video, duplicate]))
            self.assertIs(with_original, public_photo)


if __name__ == "__main__":
    unittest.main()
