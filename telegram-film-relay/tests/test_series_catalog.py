"""Tests sans Telegram : séries TV dans les canaux Films existants."""
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch

from film_relay.series_catalog import (series_config, classify, episode_numbers,
                                       public_buttons, series_title, season_text)
from film_relay.series_matching import looks_like_tv_episode
from scripts.partnership_cycle import posts_after_intro


def photo(i, caption):
    return NS(id=i, photo=object(), noforwards=False, raw_text=caption)


def video(i, name, caption=""):
    return NS(id=i, document=NS(id=1000+i, mime_type="video/mp4"),
              photo=None, noforwards=False, raw_text=caption,
              file=NS(name=name, duration=3600), date=datetime(2026,10,17,tzinfo=timezone.utc))


class TVSeriesTests(unittest.TestCase):
    def test_series_source_uses_existing_authorized_sources(self):
        with patch.dict(os.environ, {"TG_PRIVATE_CHANNEL":"-1001111111111",
                                     "TG_PUBLIC_CHANNEL":"@CineXFilmsDemo",
                                     "SERIES_SOURCE_CHANNELS":"@series_source1,@series_source2"},clear=False):
            cfg=series_config()
        self.assertEqual(cfg["sources"], ["@series_source1","@series_source2"])
        self.assertEqual(cfg["private"],"-1001111111111")
        self.assertEqual(cfg["public"],"@CineXFilmsDemo")
        self.assertEqual(cfg["mirror"],"@Torrent9SeriesFilms")

    def test_s02_poster_is_not_s01(self):
        messages=[photo(200,"The Last of Us - S02"),video(201,"Episode_01.mkv"),
                  video(202,"Episode_02.mkv")]
        result=classify(messages,-100987)
        self.assertEqual(len(result),2)
        self.assertEqual([r["season"] for r in result],[2,2])
        self.assertEqual([r["episode"] for r in result],[1,2])
        self.assertEqual({r["series"] for r in result},{"the-last-of-us"})

    def test_explicit_episode_season_overrides_poster(self):
        result=classify([photo(10,"Severance S02"),video(11,"Severance.S01E03.mp4")],-100555)
        self.assertEqual([(r["season"],r["episode"]) for r in result],[(1,3)])

    def test_season_headers_and_episode_numbers(self):
        header=NS(id=14,photo=None,document=None,noforwards=False,
                  raw_text="Saison 3",date=datetime(2026,10,17,tzinfo=timezone.utc))
        messages=[photo(10,"Succession"),video(11,"EP01.mkv"),header,video(15,"Episode_01.mkv")]
        result=classify(messages,-100111)
        self.assertEqual([(r["season"],r["episode"]) for r in result],[(1,1),(3,1)])

    def test_title_drops_source_signature(self):
        self.assertEqual(series_title("Little House on the Prairie 2026 @serie et film"),
                         "Little House on the Prairie 2026")

    def test_not_classify_movie_as_episode(self):
        self.assertFalse(looks_like_tv_episode("Le Film - 2026", "Le_Film.mp4"))
        self.assertTrue(looks_like_tv_episode("House of the Dragon", "S02E05.mkv"))
        self.assertTrue(looks_like_tv_episode("Episode 03", "file.mp4"))
        self.assertFalse(looks_like_tv_episode("Saison 2 disponible", "Film.mp4"))

    def test_series_buttons_are_same_as_anime(self):
        rows=public_buttons(-1001234567,{
            "main_index_id":10,"season_indices":{"1":11,"2":12},
        })
        self.assertEqual(rows[1][0].text, "📺 Saison 2")
        self.assertEqual(rows[1][0].url, "https://t.me/c/1234567/12")

    def test_post_cycle_includes_series_card_and_ad_in_source_order(self):
        import json
        import scripts.partnership_cycle as cycle
        data = {"processed": {"movie:one": {"public_message_id": 19}},
                "promotions": {"-100123": {"sent": {"0": 20}}}}
        with TemporaryDirectory() as td, patch.object(cycle, "ROOT", Path(td)), \
             patch.dict(os.environ, {"CINEX_SERIES_CATALOG_ENABLED": "true"}):
            state_path = Path(td)/"state"/"series_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({
                "completed": {"tv-series:some-series": {
                    "public_id": 21, "video_id": 123
                }},
                "mirrors": {}, "promotions": {}, "staged": {}
            }))
            items = cycle.posts_after_intro("films", data, "-100123", 10)
        self.assertEqual([(i,kind) for i,kind,_ in items],
                         [(10,"intro"),(19,"film"),(20,"promo"),(21,"series")])

    def test_post_cycle_mirrors_one_series_card_not_episodes(self):
        films={"processed":{},"promotions":{"-100123":{"sent":{"0":20}}}}
        with TemporaryDirectory() as td, patch.dict(os.environ,{"CINEX_SERIES_CATALOG_ENABLED":"false"}):
            result=posts_after_intro("films",films,"-100123",10)
        self.assertEqual([(i,kind) for i,kind,_ in result],[(10,"intro"),(20,"promo")])


if __name__ == "__main__":
    unittest.main()
