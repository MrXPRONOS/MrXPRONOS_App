"""Offline regression tests: never create a real Bluesky post or upload."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from scripts.bluesky_video_processed import (
    BlueskyVideoError, job_details, pds_host, processed_blob_from_status,
    wait_for_processed_video, publish_processed_video,
)

BLOB={"$type":"blob","ref":{"$link":"bafkreihv2vld4mqxk6xujb5h7qfsispqb2rfv2dh5chvxsq5y2a6wxt4da"},"mimeType":"video/mp4","size":130000}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code=status_code
        self.payload=payload or {}
    def json(self): return self.payload


class VideoProcessingTest(unittest.TestCase):
    def test_pds_audience_uses_DID_document(self):
        self.assertEqual(pds_host({"service":[{"id":"#atproto_pds","serviceEndpoint":"https://north.us-east.host.bsky.network"}]}),
                         "north.us-east.host.bsky.network")
        with self.assertRaises(BlueskyVideoError):
            pds_host({"service":[]})

    def test_job_envelopes(self):
        self.assertEqual(job_details({"jobStatus":{"jobId":"job1"}})["jobId"],"job1")
        self.assertEqual(job_details({"jobId":"job2"})["jobId"],"job2")

    def test_reject_failed_or_unfinished_processing(self):
        with self.assertRaises(BlueskyVideoError):
            processed_blob_from_status({"state":"JOB_STATE_FAILED","error":"encoder failure"})
        self.assertIsNone(processed_blob_from_status({"state":"JOB_STATE_ENCODING","blob":BLOB}))
        self.assertEqual(processed_blob_from_status({"state":"JOB_STATE_COMPLETED","blob":BLOB}),BLOB)

    def test_waits_for_transcoding_before_allowing_post(self):
        api=Mock()
        api.post.return_value=FakeResponse(payload={"jobStatus":{"state":"JOB_STATE_CREATED","jobId":"job1"}})
        api.get.side_effect=[
            FakeResponse(payload={"jobStatus":{"state":"JOB_STATE_ENCODING","jobId":"job1"}}),
            FakeResponse(payload={"jobStatus":{"state":"JOB_STATE_COMPLETED","jobId":"job1","blob":BLOB}}),
        ]
        with __import__("unittest.mock",fromlist=["patch"]).patch("scripts.bluesky_video_processed.time.sleep"):
            blob=wait_for_processed_video(api,"signed","did:plc:test","video.mp4",b"x"*130000,max_wait=100)
        self.assertEqual(blob,BLOB)
        self.assertEqual(api.get.call_count,2)
        args,kwargs=api.post.call_args
        self.assertIn("video.bsky.app",args[0])
        self.assertEqual(kwargs["params"]["did"],"did:plc:test")

    def test_video_failure_never_creates_post(self):
        api=Mock()
        api.post.return_value=FakeResponse(payload={"jobId":"job1","state":"JOB_STATE_CREATED"})
        api.get.return_value=FakeResponse(payload={"jobStatus":{"jobId":"job1","state":"JOB_STATE_FAILED","error":"invalid codec"}})
        pds=SimpleNamespace(get_service_auth=Mock(return_value=SimpleNamespace(token="signed")))
        client=SimpleNamespace(com=SimpleNamespace(atproto=SimpleNamespace(server=pds)),send_post=Mock())
        login=SimpleNamespace(did="did:plc:test",did_doc={"service":[{"id":"#atproto_pds","serviceEndpoint":"https://server.test"}]})
        with self.assertRaises(BlueskyVideoError):
            publish_processed_video(client,login,b"x"*130000,"file.mp4","caption","alt",session=api)
        client.send_post.assert_not_called()

    def test_sdk_embeds_processed_blob(self):
        from atproto import models
        from atproto_client.models.blob_ref import BlobRef
        parsed=BlobRef.model_validate(BLOB)
        embed=models.AppBskyEmbedVideo.Main(
            video=parsed, alt="MR XPRONOS",
            aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=1080,height=1920))
        self.assertIsNotNone(embed.video)

    def test_invalid_video_never_uploads(self):
        api=Mock()
        with self.assertRaises(BlueskyVideoError):
            wait_for_processed_video(api,"signed","did:plc:test","file.mp4",b"x"*100,max_wait=0)
        api.post.assert_not_called()


if __name__=="__main__":
    unittest.main()
