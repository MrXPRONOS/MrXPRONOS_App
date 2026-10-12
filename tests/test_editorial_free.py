"""Tests hors réseau du pipeline gratuit; python -m unittest tests.test_editorial_free."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import content_studio, editorial_pages, editorial_queue, editorial_quality

class StudioTests(unittest.TestCase):
    def test_dimensions_and_text(self):
        for shape in content_studio.FORMATS.values():
            image=content_studio.draw_cover("Comment analyser un match avec prudence ?", "conseil", shape, 0, "Analyse football")
            self.assertEqual(image.size,shape)
    def test_unique_variants_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root=Path(tmp)
            (fake_root/"assets/images").mkdir(parents=True)
            with patch.object(content_studio,"ROOT",fake_root),patch.object(content_studio,"OUT",fake_root/"assets/images/editorial"):
                output=content_studio.save_cover("Série test football","conseil","slug-test")
                for key in ("image_url","social_image","story_image"):
                    self.assertTrue((fake_root/output[key]).is_file())
            self.assertEqual(output["og_image"],output["image_url"])
    def test_pages_og(self):
        page=editorial_pages.render("article",{"slug":"test-article","title":"Test & Apprendre","image_url":"assets/images/editorial/test.webp"})
        self.assertIn('og:image',page)
        self.assertIn('Test &amp; Apprendre',page)
        self.assertIn('article.html?slug=test-article',page)
    def test_queue_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/"articles.json").write_text(json.dumps([{"slug":"slug1","title":"Titre test"}]),encoding="utf-8")
            dest=root/"queue.json"
            result1=editorial_queue.build(root, dest,limit=20)
            result2=editorial_queue.build(root, dest,limit=20)
            self.assertEqual(len(result1),1)
            self.assertEqual(result1,result2)
            self.assertEqual(result2[0]["status"],"pending_review")
    def test_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"articles.json").write_text(json.dumps([{"title":"Titre unique"}]),encoding="utf-8")
            self.assertEqual(editorial_quality.validate(root,strict=True),0)

if __name__=="__main__":
    unittest.main()
