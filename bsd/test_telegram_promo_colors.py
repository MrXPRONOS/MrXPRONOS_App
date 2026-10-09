"""Color palette regression tests, without Telegram or network access."""
import sys,unittest,tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"scripts"))
from telegram_promo_colors import dominant_button_style,colorized_button

class TelegramPosterColorTests(unittest.TestCase):
    def test_primary_green_red_and_neutral(self):
        with tempfile.TemporaryDirectory() as d:
            for name,rgb,expected in [
                ("blue",(25,100,215),"primary"),
                ("green",(23,160,83),"success"),
                ("red",(225,43,55),"danger"),
                ("orange",(240,130,30),"danger"),
                ("neutral",(230,230,230),"primary")]:
                path=Path(d)/(name+".png")
                Image.new("RGB",(80,80),rgb).save(path)
                self.assertEqual(dominant_button_style(path),expected)
    def test_ignores_small_logo_and_transparency(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"poster.png"
            image=Image.new("RGBA",(100,100),(18,152,80,255))
            for y in range(12):
                for x in range(12):
                    image.putpixel((x,y),(243,25,44,255))
            image.save(path)
            self.assertEqual(dominant_button_style(path),"success")
            self.assertEqual(colorized_button("CTA","https://example.com",path)["style"],"success")
    def test_missing_file_fallback(self):
        self.assertEqual(dominant_button_style("/missing_file.png"),"primary")

if __name__=="__main__":unittest.main()
