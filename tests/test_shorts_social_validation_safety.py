"""Offline safety regression: per-validation D1 identity, public media OIDC and no duplicates."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import post_shorts_video as social


class ValidationSocialSafetyTests(unittest.TestCase):
    def test_no_empty_validation_ref_silently_falls_back_to_unprotected_send(self):
        with patch.object(sys, "argv", ["post_shorts_video.py", "--validation-ref", "",
                                         "--video", "/tmp/unused.mp4"]):
            with self.assertRaises(SystemExit) as err:
                social.main()
        self.assertEqual(err.exception.code,2)

    def test_missing_cloudflare_public_url_never_claims_or_posts_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            movie=folder/"test.mp4"
            movie.write_bytes(b"x"*150000)
            with patch.object(social,"ROOT_DIR",folder), \
                 patch.object(social,"resolve_public_url",return_value=None), \
                 patch.object(social,"post_instagram_reel") as insta, \
                 patch.object(social,"post_threads") as threads, \
                 patch.object(sys,"argv",[
                     "post_shorts_video.py","--validation-ref","morning:2026-11-14",
                     "--platforms","instagram,threads","--require-all",
                     "--video",str(movie)]):
                result=social.main()
            self.assertEqual(result,1)
            insta.assert_not_called()
            threads.assert_not_called()
            report=json.loads((folder/"social_post_results.json").read_text())
            self.assertEqual({p["platform"] for p in report},{"instagram","threads"})
            self.assertTrue(all("no provider upload" in p["message"] for p in report))
            self.assertTrue(all(p["ok"] is False for p in report))

    def test_workflow_includes_strict_oidc_and_unique_per_batch_refs(self):
        text=(ROOT/".github/workflows/shorts-coupons-production-validation.yml").read_text()
        self.assertIn("id-token: write",text)
        self.assertIn('--validation-ref "$SLOT:$TARGET"',text)
        self.assertNotIn('--validation-ref "$VALIDATION_REF"',text)
        self.assertIn('date(2026,11,13)',text)
        self.assertIn("SHORTS_LEGACY_SOCIAL_RECONCILIATION_REQUIRED",text)

    def test_worker_allowlist_is_scoped_to_production_validation_workflow(self):
        text=(ROOT/"cloudflare/public_social_media/worker.mjs").read_text()
        self.assertIn('".github/workflows/shorts-coupons-production-validation.yml"',text)
        self.assertIn('claims.ref !== "refs/heads/main"',text)
        self.assertIn('claims.aud !== AUDIENCE',text)
        self.assertIn("crypto.subtle.verify",text)


if __name__=="__main__":
    unittest.main()
