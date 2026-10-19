"""Fail-closed tests for future TikTok publishing. No network access."""
import os
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from scripts import post_shorts_video as social


class TikTokPostingTests(unittest.TestCase):
    @patch.object(social.requests, "post")
    def test_no_post_by_default(self, request):
        with patch.dict(os.environ, {"TIKTOK_DIRECT_POST_ENABLED": "", "TIKTOK_ACCESS_TOKEN": "fake"}, clear=False):
            result = social.post_tiktok(Path("does-not-exist.mp4"), "Example")
        self.assertFalse(result.ok)
        self.assertIn("désactivée", result.message)
        request.assert_not_called()

    @patch.object(social.requests, "post")
    def test_no_post_without_per_video_consent(self, request):
        with patch.dict(os.environ, {
            "TIKTOK_DIRECT_POST_ENABLED": "true",
            "TIKTOK_PER_VIDEO_CONSENT": "",
            "TIKTOK_ACCESS_TOKEN": "fake"
        }):
            result = social.post_tiktok(Path("does-not-exist.mp4"), "Example")
        self.assertFalse(result.ok)
        self.assertIn("Consentement explicite", result.message)
        request.assert_not_called()

    def test_http_error_does_not_reveal_response_body(self):
        response = Mock(status_code=401)
        response.json.return_value = {"error": {"code": "access_token_invalid",
                                                  "message": "sensitive-token-abc"}}
        data, error = social.tiktok_api_response(response)
        self.assertEqual(data, {})
        self.assertIn("access_token_invalid", error)
        self.assertNotIn("sensitive-token-abc", error)

    @patch.object(social.requests, "post")
    def test_missing_manual_privacy_refuses_init(self, request):
        with patch.dict(os.environ, {
            "TIKTOK_DIRECT_POST_ENABLED": "true",
            "TIKTOK_PER_VIDEO_CONSENT": "true",
            "TIKTOK_ACCESS_TOKEN": "fake",
            "TIKTOK_PRIVACY_LEVEL": ""
        }):
            result = social.post_tiktok(Path("does-not-exist.mp4"), "Example")
        self.assertFalse(result.ok)
        self.assertIn("choisir explicitement", result.message)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
