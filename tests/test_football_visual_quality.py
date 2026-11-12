"""Phase 1: visual design regressions.  No network needed, no real match claims."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageStat
from football_media_v2.visuals import (W,H,scene_poster,layout_for,MissingLicensedMedia,
                                        _wrap,ft,SAFE_X,demo_visual_asset)
from football_media_v2.story import match_scenes,demo_match,Scene
from football_media_v2.engine import prepare_scenes

ASSET=demo_visual_asset()

class PremiumVisualTests(unittest.TestCase):
    def test_six_distinct_layouts_in_nine_shot_match(self):
        layouts=[layout_for(s.kind) for s in match_scenes(demo_match())]
        self.assertGreaterEqual(len(set(layouts)),6)
        self.assertEqual(len(layouts),len(set(layouts)), 'Each narrative role needs its own design')
    def test_real_photo_is_mandatory(self):
        scene=match_scenes(demo_match())[0]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(MissingLicensedMedia):
                scene_poster(scene,Path(td)/'bad.jpg',0,1,photo=None)
    def test_tiny_photo_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'tiny.jpg';Image.new('RGB',(320,240),(130,80,50)).save(p)
            with self.assertRaises(MissingLicensedMedia):
                scene_poster(match_scenes(demo_match())[0],Path(td)/'out.jpg',0,1,photo=p)
    def test_nine_template_visual_outputs_exact_dimension(self):
        self.assertTrue(ASSET.exists())
        with tempfile.TemporaryDirectory() as td:
            scenes=match_scenes(demo_match())
            result=[]
            for i,scene in enumerate(scenes):
                p=Path(td)/f'{i}.jpg'
                meta=scene_poster(scene,p,i,len(scenes),watermark=True,photo=ASSET)
                self.assertEqual(meta['layout'],layout_for(scene.kind))
                with Image.open(p) as im:
                    self.assertEqual(im.size,(W,H))
                    # Photograph dominates; not a giant opaque typographic card.
                    center=im.crop((90,180,630,650)).convert('RGB')
                    self.assertGreater(sum(ImageStat.Stat(center).stddev),45)
                result.append(p.read_bytes())
            self.assertEqual(len(result),len(set(result)), 'Layouts are all visually distinct files')
    def test_long_headline_cannot_be_silently_truncated(self):
        scene=Scene('hook','A LA UNE',('INCROYABLEMENT LONG '*40),'Détails','','2.5')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                scene_poster(scene,Path(td)/'out.jpg',0,1,photo=ASSET)
    def test_no_drawn_football_figures_in_visual_module(self):
        p=Path(__file__).resolve().parents[1]/'football_media_v2/visuals.py'
        src=p.read_text('utf8')
        self.assertNotIn('def football(',src)
        self.assertNotIn('def stadium_athlete(',src)
        self.assertNotIn('def backdrop(',src)
    def test_demo_asset_never_claims_real_game(self):
        txt=(ASSET.parent/'README.md').read_text('utf8')
        self.assertIn('STRICTEMENT FICTIF',txt.upper())
        self.assertIn('NON PUBLIABLE',txt.upper())
    def test_render_no_media_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(MissingLicensedMedia):
                prepare_scenes(match_scenes(demo_match()),Path(td),None,photos=[])

if __name__=='__main__':unittest.main()
