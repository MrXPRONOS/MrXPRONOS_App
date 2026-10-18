"""Verify Threads video publishing waits for Meta's FINISHED status."""
import unittest
from unittest.mock import patch
from scripts import post_shorts_video as social


class ThreadsVideoTests(unittest.TestCase):
    @patch.object(social, "request_or_raise")
    def test_publishing_waits_for_finished(self, request):
        request.side_effect = [
            {"id": "container-123"},
            {"id": "container-123", "status": "FINISHED"},
            {"id": "post-456"},
        ]
        with patch.dict(social.os.environ, {"THREADS_USER_ID": "user-123", "THREADS_ACCESS_TOKEN": "abc"}):
            result = social.post_threads("https://example.org/video.mp4", "Example")
        self.assertTrue(result.ok)
        self.assertEqual(result.data["id"], "post-456")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[1].args[0], "GET")
        self.assertIn("/threads_publish", request.call_args_list[2].args[1])

    @patch.object(social, "request_or_raise", return_value={"status": "ERROR", "error_message": "FAILED_PROCESSING_VIDEO"})
    def test_invalid_container_aborts(self, request):
        with self.assertRaisesRegex(RuntimeError, "FAILED_PROCESSING_VIDEO"):
            social.wait_threads_container("bad", "token")
        self.assertEqual(request.call_count, 1)

    @patch.object(social, "request_or_raise", return_value={"status": "PUBLISHED"})
    def test_previously_published_container_cannot_be_republished(self, request):
        with self.assertRaisesRegex(RuntimeError, "PUBLISHED"):
            social.wait_threads_container("already", "token")
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
