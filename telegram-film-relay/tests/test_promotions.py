import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from film_relay.promotions import CAMPAIGNS, render_poster, campaign_caption, campaign_button, due
from film_relay.state import State

class PromoTests(unittest.TestCase):
    def test_channels(self):
        self.assertEqual([x[1] for x in CAMPAIGNS], [
            "@actufoot_mrxp", "@mr_xpronos_vip", "@mrxpronosfr"])
        for index in range(3):
            self.assertEqual(len(campaign_caption(index).splitlines()), 3)
            self.assertEqual(campaign_button(index)[1],
                             "https://t.me/" + CAMPAIGNS[index][1][1:])

    def test_original_png_bytes(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            for index, key in enumerate(("actu", "live", "jour")):
                Image.new("RGB", (480, 600), (20+index*30, 40, 60)).save(root / f"mrx_{key}.png")
            with patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": td}):
                for index, key in enumerate(("actu", "live", "jour")):
                    blob = render_poster(index)
                    self.assertEqual(blob.read(), (root / f"mrx_{key}.png").read_bytes())
                    blob.seek(0)
                    self.assertEqual(Image.open(blob).format, "PNG")

    def test_no_substitute_when_original_missing(self):
        with TemporaryDirectory() as td, patch.dict(os.environ, {"CINEX_PROMO_ASSETS_DIR": td}):
            with self.assertRaises(FileNotFoundError):
                render_poster(0)

    def test_rotation(self):
        with TemporaryDirectory() as td:
            state = State(str(Path(td) / "state.json"))
            self.assertIsNone(due(state, "channel", 1))
            self.assertEqual(due(state, "channel", 2), 0)
            cursor = state.data["promotions"]["channel"]
            cursor["last_film_total"] = 2
            cursor["next_index"] = 1
            self.assertIsNone(due(state, "channel", 3))
            self.assertEqual(due(state, "channel", 4), 1)
            cursor["last_film_total"] = 4
            cursor["next_index"] = 2
            self.assertEqual(due(state, "channel", 6), 2)

if __name__ == "__main__":
    unittest.main()
