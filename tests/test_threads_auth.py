"""Offline regression tests: never contact Meta or GitHub."""
import os
import unittest
from unittest.mock import Mock, patch

from scripts import threads_auth as auth


class ThreadsAuthTests(unittest.TestCase):
    @patch.object(auth, "api_json", return_value={"id": "123456789", "username": "mr_xpronos"})
    def test_profile_valid(self, request):
        self.assertEqual(auth.check_profile("mock-token"), ("123456789", "mr_xpronos"))
        self.assertEqual(request.call_args.kwargs["token"], "mock-token")

    @patch.object(auth, "api_json", return_value={"id": "9", "username": "someone_else"})
    def test_does_not_save_wrong_threads_account(self, _request):
        with self.assertRaisesRegex(auth.ThreadsError, "Mauvais compte"):
            auth.check_profile("dummy-token")

    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": ""}):
            with self.assertRaisesRegex(auth.ThreadsError, "THREADS_ACCESS_TOKEN"):
                auth.verify()

    @patch.object(auth, "ensure_github_writer", return_value=("fake-pat", "MrXPRONOS/MrXPRONOS_App"))
    @patch.object(auth.subprocess, "run")
    def test_git_secret_write_uses_stdin_not_cli_args(self, run, _writer):
        run.return_value = Mock(returncode=0)
        auth.store_secrets({"THREADS_ACCESS_TOKEN": "secret-token-for-test"})
        args = run.call_args.args[0]
        self.assertNotIn("secret-token-for-test", args)
        self.assertEqual(run.call_args.kwargs["input"], "secret-token-for-test")
        self.assertEqual(run.call_args.kwargs["env"]["GH_TOKEN"], "fake-pat")

    @patch.object(auth, "check_profile", side_effect=[("123", "mr_xpronos"), ("123", "mr_xpronos")])
    @patch.object(auth, "store_secrets")
    @patch.object(auth, "api_json", return_value={"access_token": "rotated"})
    @patch.object(auth, "ensure_github_writer", return_value=("pat", "MrXPRONOS/MrXPRONOS_App"))
    def test_refresh_writes_validated_new_token(self, _writer, request, save, _profile):
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "original", "THREADS_USER_ID": "123"}):
            auth.refresh()
        request.assert_called_once()
        save.assert_called_once_with({"THREADS_USER_ID": "123", "THREADS_ACCESS_TOKEN": "rotated"})

    @patch.object(auth, "check_profile", return_value=("123", "mr_xpronos"))
    @patch.object(auth, "store_secrets")
    @patch.object(auth, "api_json", side_effect=auth.ThreadsError("Threads HTTP 400, code 190, subcode n/a"))
    @patch.object(auth, "ensure_github_writer", return_value=("pat", "repo/name"))
    def test_too_early_token_remains_untouched(self, _writer, _req, save, _profile):
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "stillvalid"}):
            auth.refresh()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
