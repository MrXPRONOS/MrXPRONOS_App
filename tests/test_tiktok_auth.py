"""Non-network OAuth tests for TikTok account safety and credentials."""
import os
import unittest
from unittest.mock import Mock, patch
from scripts import tiktok_auth as auth


class TikTokAuthTests(unittest.TestCase):
    def test_missing_secret_fails(self):
        with patch.dict(os.environ, {"TIKTOK_ACCESS_TOKEN": ""}):
            with self.assertRaisesRegex(auth.TikTokError, "TIKTOK_ACCESS_TOKEN"):
                auth.verify()

    @patch.object(auth.requests, "post")
    def test_failed_token_exchange_does_not_echo_description(self, post):
        post.return_value = Mock(status_code=400)
        post.return_value.json.return_value = {
            "error": "invalid_grant", "error_description": "private-auth-code"
        }
        with self.assertRaises(auth.TikTokError) as e:
            auth.token_request({"code": "private-auth-code"})
        self.assertNotIn("private-auth-code", str(e.exception))

    @patch.object(auth.requests, "get")
    def test_get_user_info_uses_bearer_header(self, req):
        req.return_value = Mock(status_code=200)
        req.return_value.json.return_value = {
            "data": {"user": {"open_id": "123", "display_name": "Mr XPRONOS"}},
            "error": {"code": "ok"},
        }
        oid, name = auth.user_info("dummy-access-token")
        self.assertEqual((oid, name), ("123", "Mr XPRONOS"))
        self.assertEqual(req.call_args.kwargs["headers"]["Authorization"],
                         "Bearer dummy-access-token")

    @patch.object(auth, "github_writer", return_value=("mock-pat", "MrXPRONOS/MrXPRONOS_App"))
    @patch.object(auth.subprocess, "run")
    def test_token_not_in_command_args(self, run, _writer):
        run.return_value = Mock(returncode=0)
        auth.store({"TIKTOK_ACCESS_TOKEN": "private123"})
        args = run.call_args.args[0]
        self.assertNotIn("private123", args)
        self.assertEqual(run.call_args.kwargs["input"], "private123")
        self.assertEqual(run.call_args.kwargs["env"]["GH_TOKEN"], "mock-pat")

    @patch.object(auth, "token_request", return_value={
        "open_id": "correct", "access_token": "new-access",
        "refresh_token": "new-refresh", "scope": "user.info.basic",
    })
    @patch.object(auth, "github_writer", return_value=("pat", "MrXPRONOS/MrXPRONOS_App"))
    @patch.object(auth, "user_info", return_value=("correct", "Example"))
    @patch.object(auth, "store")
    def test_refresh_persists_both_rotating_tokens(self, save, _profile, _writer, token):
        with patch.dict(os.environ, {
            "TIKTOK_CLIENT_KEY": "client", "TIKTOK_CLIENT_SECRET": "secret",
            "TIKTOK_REFRESH_TOKEN": "old-refresh", "TIKTOK_OPEN_ID": "correct"
        }):
            auth.refresh()
        save.assert_called_once_with({
            "TIKTOK_OPEN_ID": "correct",
            "TIKTOK_ACCESS_TOKEN": "new-access",
            "TIKTOK_REFRESH_TOKEN": "new-refresh",
        })
        self.assertEqual(token.call_args.args[0]["grant_type"], "refresh_token")

    @patch.object(auth, "token_request", return_value={
        "open_id": "other", "access_token": "new-access",
        "refresh_token": "new-refresh",
    })
    @patch.object(auth, "github_writer", return_value=("pat", "repo/name"))
    @patch.object(auth, "user_info", return_value=("other", "Wrong"))
    @patch.object(auth, "store")
    def test_mismatch_cannot_rotate_into_different_account(self, save, _profile, _writer, _token):
        with patch.dict(os.environ, {
            "TIKTOK_CLIENT_KEY": "client", "TIKTOK_CLIENT_SECRET": "secret",
            "TIKTOK_REFRESH_TOKEN": "old-refresh", "TIKTOK_OPEN_ID": "correct"
        }):
            with self.assertRaisesRegex(auth.TikTokError, "autre utilisateur"):
                auth.refresh()
        save.assert_not_called()

    @patch.object(auth, "token_request", return_value={
        "open_id": "sample", "access_token": "access",
        "refresh_token": "refresh", "scope": "user.info.basic,video.list",
    })
    @patch.object(auth, "github_writer", return_value=("pat", "repo/name"))
    @patch.object(auth, "user_info", return_value=("sample", "MrX"))
    @patch.object(auth, "store")
    @patch.object(auth.subprocess, "run", return_value=Mock(returncode=0))
    def test_exchange_never_posts_video(self, _run, save, _profile, _writer, _token):
        with patch.dict(os.environ, {
            "TIKTOK_CLIENT_KEY": "client", "TIKTOK_CLIENT_SECRET": "secret",
            "TIKTOK_AUTH_CODE": "sample-code",
        }):
            auth.exchange()
        saved = save.call_args.args[0]
        self.assertEqual(saved["TIKTOK_ACCESS_TOKEN"], "access")
        self.assertEqual(saved["TIKTOK_REFRESH_TOKEN"], "refresh")


if __name__ == "__main__":
    unittest.main()
