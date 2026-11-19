import unittest
from types import SimpleNamespace
from film_relay.public_video_showcase import select_recent_completed
from film_relay.public_video_archive import (
    is_video_message, last_ten_video_ids, matching_poster,
    normalize_title, title_similarity, archive_buttons,
)


def msg(identifier, *, title="", photo=False, video=False, document_id=None, name=""):
    document = SimpleNamespace(id=document_id or identifier, attributes=[]) if video else None
    return SimpleNamespace(
        id=identifier, raw_text=title, photo=(object() if photo else None),
        video=(object() if video else None), document=document,
        file=SimpleNamespace(name=name), buttons=None,
    )


class PublicArchiveTests(unittest.TestCase):
    def test_video_and_nonvideo(self):
        self.assertTrue(is_video_message(msg(1, title="Film", video=True)))
        self.assertFalse(is_video_message(msg(2, title="Affiche", photo=True)))

    def test_only_latest_ten_kept(self):
        messages = [msg(i, video=True) for i in range(1, 15)]
        messages += [msg(200, photo=True)]
        self.assertEqual(last_ten_video_ids(messages), set(range(5, 15)))

    def test_movie_matching_is_not_adjacent_guess(self):
        film = msg(32, title="🎞️ Le Voyage de Jade", video=True)
        poster = msg(31, title="🎬 Le Voyage de Jade\nAnnée : 2026", photo=True)
        other = msg(30, title="🎬 Film totalement différent", photo=True)
        self.assertIs(matching_poster(film, [other, poster, film]), poster)

    def test_skip_when_title_missing(self):
        film = msg(50, video=True)
        poster = msg(49, title="La fille du roi", photo=True)
        self.assertIsNone(matching_poster(film, [poster, film]))

    def test_skip_when_poster_is_too_old(self):
        film = msg(50, title="La fille du roi", video=True)
        poster = msg(30, title="La fille du roi", photo=True)
        self.assertIsNone(matching_poster(film, [poster, film]))

    def test_normalize(self):
        self.assertEqual(normalize_title("🎬 FILM : Le Grand Voyage (VF)"), "le grand voyage")
        self.assertGreater(title_similarity("Le Grand Voyage", "Le Grand Voyage VF 2026"), 0.8)

    def test_showcase_only_recent_published_posters(self):
        records = {
            "a": {"private_message_id": 100, "public_message_id": 101},
            "b": {"private_message_id": 200, "public_message_id": 201},
            "old": {"private_message_id": 300, "public_message_id": 1},
        }
        selected = select_recent_completed(records, {101, 201, 202}, count=2)
        self.assertEqual([r["public_message_id"] for r in selected], [201, 101])

    def test_two_buttons(self):
        buttons = archive_buttons("https://t.me/c/1234/5678")
        self.assertEqual(buttons[0][0].url, "https://t.me/c/1234/5678")
        self.assertEqual(len(buttons), 2)


if __name__ == "__main__":
    unittest.main()
