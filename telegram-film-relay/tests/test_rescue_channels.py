"""Offline regressions: Secours backup channels and Telegram buttons."""
from __future__ import annotations

import json
import hashlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from film_relay.rescue_channels import (
    BUTTON_TEXT, exact_private_candidates, public_username,
    is_invite, targets_from_env, rescue_link_for, add_rescue_tuple_row,
    add_rescue_button_row, read_state, write_state,
)
from film_relay.publication import url_button_rows
from film_relay.series_catalog import public_buttons as series_buttons
from film_relay.anime_catalog import public_buttons as anime_buttons
from film_relay.public_video_archive import archive_buttons
from film_relay.trending_private import buttons as trend_buttons
from scripts.merge_rescue_channels import merge


class RescueChannelTests(unittest.TestCase):
    def fixture(self, directory: Path):
        path = directory / "rescue.json"
        write_state({"channels": {"@cinexfilms_vf": {
            "public_username": "@cinexfilms_vf", "public_id": -100111222333,
            "rescue_channel_id": -100444555666,
            "rescue_title": "Ciné X Films VF Secours",
            "invite_link": "https://t.me/+abcdefghijklmno1",
        }}}, path)
        runtime = directory / "runtime.json"
        runtime.write_text(json.dumps({"channels":{"@cinexfilms_vf":{
            "url":"https://t.me/+abcdefghijklmno1",
            "rescue_channel_id":-100444555666
        }}}),encoding="utf-8")
        self.addCleanup(lambda: os.environ.pop("CINEX_RESCUE_RUNTIME_FILE",None))
        os.environ["CINEX_RESCUE_RUNTIME_FILE"]=str(runtime)
        return path

    def test_targets_owner_primary_and_all_categories(self):
        env = {
            "TG_PUBLIC_CHANNEL": "@CineXFilms_vf",
            "DESIR_PUBLIC_CHANNEL": "@CineXDesirfr",
            "COMEDIE_PUBLIC_CHANNEL": "@CineXComediefr",
            "ANIME_PUBLIC_CHANNEL": "@CineXAnimeFR",
        }
        expected = {"@cinexfilms_vf", "@seriesvf_cinex",
                    "@cinexdesirfr", "@cinexcomediefr", "@cinexanimefr"}
        self.assertEqual(set(targets_from_env(env)), expected)

    def test_paused_external_mirror_is_not_provisioned(self):
        self.assertNotIn("@torrent9seriesfilms", targets_from_env({
            "TG_PUBLIC_CHANNEL":"@CineXFilms_vf",
            "CINEX_TORRENT9_PAUSED":"true",
            "TG_MIRROR_CHANNEL":"@Torrent9SeriesFilms",
        }))

    def test_url_must_be_native_private_invitation(self):
        self.assertTrue(is_invite("https://t.me/+abcdefghijklmno1"))
        self.assertFalse(is_invite("https://t.me/CineXFilms_vf"))
        self.assertFalse(is_invite("https://example.com/invite"))
        self.assertFalse(is_invite("https://t.me/c/123/40"))

    def test_existing_and_invalid_rescue_link(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            self.assertEqual(rescue_link_for("@CineXFilms_vf", path=path),
                             "https://t.me/+abcdefghijklmno1")
            self.assertIsNone(rescue_link_for("@Unknown_123", path=path))
            state = read_state(path)
            self.assertNotIn("invite_link", state["channels"]["@cinexfilms_vf"])
            self.assertIn("invite_sha256", state["channels"]["@cinexfilms_vf"])
            runtime = Path(os.environ["CINEX_RESCUE_RUNTIME_FILE"])
            runtime.write_text(json.dumps({"channels":{"@cinexfilms_vf":{
                "url":"https://malicious.invalid","rescue_channel_id":-100444555666
            }}}),encoding="utf-8")
            self.assertIsNone(rescue_link_for("@CineXFilms_vf", path=path))

    def test_do_not_append_until_link_is_verified(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            rows = [[("🎬 Voir", "https://t.me/c/123/5")]]
            self.assertEqual(add_rescue_tuple_row(rows, "@CineXFilms_vf", path=path), rows)

    def test_append_one_button_to_film_poster(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            with patch("film_relay.rescue_channels.STATE_PATH", path):
                # Explicit path is used to ensure no production state is assumed.
                rows = add_rescue_tuple_row(
                    [[("🎬 Voir", "https://t.me/c/123/5")]],
                    SimpleNamespace(username="CineXFilms_vf"), path=path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1][0][0], BUTTON_TEXT)
            self.assertEqual(rows[-1][0][1], "https://t.me/+abcdefghijklmno1")

    def test_bot_keyboards_and_catalogs_preserve_movie_links(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            public = SimpleNamespace(username="CineXFilms_vf")
            direct = add_rescue_button_row(
                [[SimpleNamespace(url="https://t.me/c/111/25")]], public, path=path)
            self.assertEqual(direct[-1][0].text, BUTTON_TEXT)
            self.assertEqual(direct[0][0].url, "https://t.me/c/111/25")
            # The catalog public buttons are unchanged with absent rescue state.
            catalog = {"season_indices":{"1": 7},"main_index_id":5}
            self.assertEqual(len(series_buttons(-100111222333, catalog)), 3)
            self.assertEqual(len(anime_buttons(-100111222333, catalog)), 3)
            self.assertEqual(len(archive_buttons("https://t.me/c/111/25")), 2)
            self.assertEqual(len(trend_buttons("https://t.me/+abcdefghijklmno1")), 2)

    def test_legacy_buttons_unchanged_without_saved_rescue(self):
        self.assertEqual(len(url_button_rows("https://t.me/c/222/15")), 2)

    def test_tracked_state_has_no_invitation_urls(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            self.assertNotIn("https://t.me/+",path.read_text())
            self.assertIn("invite_sha256",path.read_text())

    def test_no_link_if_runtime_file_missing(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            with patch.dict(os.environ,{"CINEX_RESCUE_RUNTIME_FILE":str(Path(directory)/"absent")}):
                self.assertIsNone(rescue_link_for("@CineXFilms_vf",path=path))

    def test_exact_recovery_rejects_homonymous_public(self):
        title = "Ciné X Films VF Secours"
        dialogs = [
            SimpleNamespace(entity=SimpleNamespace(broadcast=True, username=None, title=title)),
            SimpleNamespace(entity=SimpleNamespace(broadcast=True, username="fake", title=title)),
            SimpleNamespace(entity=SimpleNamespace(broadcast=False, username=None, title=title)),
        ]
        self.assertEqual(len(exact_private_candidates(dialogs, title)), 1)

    def test_checkpoint_merge_preserves_identity(self):
        old={"channels":{"@cinexfilms_vf":{"public_id":-1001,"rescue_channel_id":-1002,"invite_link":"old"}}}
        new={"channels":{"@cinexfilms_vf":{"public_id":-1001,"rescue_channel_id":-1002,"invite_link":"new"}}}
        import hashlib
        self.assertEqual(merge(old,new)["channels"]["@cinexfilms_vf"]["invite_sha256"],
                         hashlib.sha256("new".encode()).hexdigest())
        self.assertNotIn("invite_link",merge(old,new)["channels"]["@cinexfilms_vf"])
        new["channels"]["@cinexfilms_vf"]["rescue_channel_id"]=-1003
        with self.assertRaises(ValueError):
            merge(old,new)


if __name__ == "__main__":
    unittest.main()
