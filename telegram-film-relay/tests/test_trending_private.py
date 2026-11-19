import unittest
from types import SimpleNamespace

from film_relay.trending_private import (
    normalize, canonical_key, safe_trends, match_catalog_series,
    episode_plan, film_from_public, channel_title, buttons,
)


class TrendingTests(unittest.TestCase):
    def item(self, title="Le Voyage de Jade", kind="films", **fields):
        return dict(title=title, kind=kind, source="tmdb", rank=2,
                    authorized=True, year=2026, **fields)

    def test_only_authorized_ranked_titles(self):
        rows = [self.item(), {**self.item(), "source": "simkl"},
                {**self.item("Non autorisé"), "authorized": False},
                {**self.item("Très ancien"), "rank": 40}]
        self.assertEqual(len(safe_trends(rows)), 1)

    def test_channel_title_is_stable(self):
        self.assertEqual(channel_title(self.item()), channel_title(self.item()))
        self.assertIn("Ciné X Film", channel_title(self.item()))

    def test_deduplication_across_providers(self):
        a = self.item()
        b = {**a, "source": "simkl"}
        self.assertEqual(canonical_key(a), canonical_key(b))

    def test_normalization_accents(self):
        self.assertEqual(normalize("Série d'été VF"), "d ete")

    def test_catalogue_match_only_unique(self):
        entry = {"title":"Le Voyage de Jade", "public_id":12,
                 "private_poster_id":14,
                 "episodes":{"1":{"1":{"message_id":20}}}}
        self.assertIs(match_catalog_series(self.item(kind="series"), {"series":{"jade":entry}}), entry)
        self.assertIsNone(match_catalog_series(self.item(kind="series"),
                          {"series":{"a":entry, "b":dict(entry)}}))

    def test_missing_episodes_reject_incomplete_season(self):
        entry = {"episodes":{"1":{"1":{"message_id":50},"3":{"message_id":52}}}}
        self.assertEqual(episode_plan(entry), [])

    def test_episode_order_all_seasons(self):
        entry = {"episodes":{"2":{"1":{"message_id":70}},
                             "1":{"2":{"message_id":52},"1":{"message_id":51}}}}
        self.assertEqual(episode_plan(entry), [(1,1,51),(1,2,52),(2,1,70)])

    def test_do_not_guess_which_film_cover_is_right(self):
        item = self.item()
        posts = [SimpleNamespace(id=30, photo=object(),
                                 raw_text="🎬 Le Voyage de Jade\nAnnée: 2026")]
        state={"processed":{"x":{"public_message_id":30,"private_message_id":40}}}
        self.assertEqual(film_from_public(item, posts, state)["private_id"],40)
        posts.append(SimpleNamespace(id=50,photo=object(),raw_text=posts[0].raw_text))
        state["processed"]["y"]={"public_message_id":50,"private_message_id":60}
        self.assertIsNone(film_from_public(item,posts,state))

    def test_private_buttons(self):
        rows=buttons("https://t.me/+abcdefghijklmnop")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0][0].url,"https://t.me/+abcdefghijklmnop")


if __name__=="__main__":
    unittest.main()
