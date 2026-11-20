"""No Telegram network: movie identity, colored keyboards and legacy dedup."""
import importlib.util
import pathlib
import tempfile
import unittest

from film_relay.film_identity import film_fingerprint
from film_relay.state import State

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("classic_publish",ROOT/"scripts"/"publish_cinex_classic_bot.py")
script=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(script)


class ClassicDedupTests(unittest.TestCase):
    def test_same_movie_different_release_encoding_has_same_identity(self):
        a=film_fingerprint("🎬 Les Billes", "Les.Billes.2024.720p.WEB-DL.mkv")
        b=film_fingerprint("🎬 Les Billes", "Les.Billes.2024.1080p.x265.mp4")
        self.assertIsNotNone(a)
        self.assertEqual(a,b)

    def test_remake_sequel_and_ambiguous_do_not_collide(self):
        base=film_fingerprint("Les Billes 2024", "Les.Billes.2024.mp4")
        self.assertNotEqual(base,film_fingerprint("Les Billes 2021","Les.Billes.2021.mp4"))
        self.assertNotEqual(base,film_fingerprint("Les Billes 2 2024","Les.Billes.2.2024.mkv"))
        self.assertIsNone(film_fingerprint("Film","video.mp4"))
        self.assertIsNone(film_fingerprint("Les Billes 2024","Les.Billes.2021.mp4"))

    def test_state_detects_title_duplicates_across_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            state=State(str(pathlib.Path(folder)/"state.json"))
            title=film_fingerprint("Les Billes 2024","Les.Billes.2024.mkv")
            state.add("-10011111111:4:5","doc:1",12,18,title)
            self.assertTrue(state.recorded("-10022222222:8:9","doc:2",title))
            self.assertFalse(state.recorded("-10022222222:8:9","doc:2",film_fingerprint("Les Billes 2 2024")))
            again=State(str(pathlib.Path(folder)/"state.json"))
            self.assertTrue(again.recorded("-10022222222:8:9",None,title))

    def test_source_already_published_in_legacy_state_blocks_new_post(self):
        old={"processed":{"source:1:2":{"private_message_id":238,"public_message_id":168}}}
        self.assertEqual(script.previous_classic_publication(old,238),("source:1:2",168))
        self.assertIsNone(script.previous_classic_publication(old,999))

    def test_colored_buttons_have_exact_three_actions(self):
        rows=script.poster_buttons("https://t.me/CineRadarFr_Bot?start=d_"+"A"*24,
                                   "https://t.me/+ABCDEF1234567890","https://t.me/addlist/ABCDEF123")
        self.assertEqual([x[0]["style"] for x in rows["inline_keyboard"]],
                         ["success","danger","primary"])
        self.assertEqual(len(rows["inline_keyboard"]),3)
        save=script.save_buttons(353)
        self.assertEqual(save["inline_keyboard"][0][0]["style"],"primary")
        self.assertIn("share/url?",save["inline_keyboard"][0][0]["url"])


if __name__=="__main__":
    unittest.main()
