"""Telegram strip regression tests; original ticket generation stays unchanged."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from unittest.mock import patch

from bsd_v2_telegram_banner import attach_banner, _build_embedded_banner

class TelegramBannerTests(unittest.TestCase):
    def test_banner_is_added_above_identical_coupon_pixels(self):
        for ticket_height in (1080,1580):
            with self.subTest(ticket_height=ticket_height), tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/"telegram.png"
                coupon=Image.new("RGB",(1080,ticket_height),"white")
                coupon.putpixel((97,42),(19,43,112))
                coupon.putpixel((900,ticket_height-11),(31,107,71))
                coupon.save(path)
                output=attach_banner(path)
                with Image.open(output) as result:
                    h=result.height-ticket_height
                    self.assertGreater(h,90)
                    self.assertLess(h,300)
                    self.assertEqual(result.width,1080)
                    self.assertEqual(result.crop((0,h,1080,result.height)).tobytes(),
                                     coupon.tobytes())
                    self.assertNotEqual(result.getpixel((900,round(h*.5))), (255,255,255))

    def test_banner_has_independent_sponsor_content(self):
        banner=_build_embedded_banner()
        self.assertEqual(banner.size,(1080,155))
        self.assertNotEqual(banner.getpixel((900,70)),(3,5,8))

    def test_missing_external_asset_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"preview.png"
            Image.new("RGB",(120,220),"white").save(path)
            with patch("bsd_v2_telegram_banner.BANNER",Path(tmp)/"missing.webp"):
                result=attach_banner(path)
            with Image.open(result) as image:
                self.assertGreater(image.height,220)

    def test_telegram_send_paths_apply_the_banner(self):
        import inspect
        from bsd_v2_telegram import send_one, send_combo
        from bsd_v2_verify_telegram import post_gain
        for send in (send_one,send_combo,post_gain):
            self.assertIn("attach_banner(",inspect.getsource(send))

if __name__=="__main__":
    unittest.main()
