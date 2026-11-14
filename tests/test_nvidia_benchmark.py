"""Tests offline des requêtes multimodales NVIDIA : aucun crédit API requis."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from nvidia_extra_models import (
    SPECIAL_MODELS, category_for, request_for, valid_output, make_document_image
)
from test_nvidia_models import model_type, success_from_json


class NvidiaBenchmarkTests(unittest.TestCase):
    def test_known_image_models_have_documented_payloads(self):
        for model, kind in SPECIAL_MODELS.items():
            if kind.startswith("image_"):
                url, payload = request_for(model)
                self.assertIn("ai.api.nvidia.com/v1/genai/", url)
                self.assertTrue(payload.get("prompt") or payload.get("text_prompts"))
                self.assertEqual(category_for(model), "image")

    def test_audio_endpoint_uses_documented_contract(self):
        url, payload = request_for("nvidia/magpie-tts-multilingual")
        self.assertIn(".invocation.api.nvcf.nvidia.com/v1/audio/synthesize", url)
        self.assertEqual(payload["language"], "en-US")
        self.assertEqual(category_for("nvidia/magpie-tts-multilingual"), "audio")

    def test_video_uses_synthetic_input(self):
        url, payload = request_for("stabilityai/stable-video-diffusion")
        self.assertIn("stable-video-diffusion", url)
        self.assertTrue(payload["image"].startswith("data:image/png;base64,"))
        self.assertEqual(model_type("stabilityai/stable-video-diffusion"), "video")

    def test_document_models_receive_image_and_prompt(self):
        for model in ("nvidia/nemotron-parse", "nvidia/nemotron-parse-2.0"):
            url, payload = request_for(model)
            self.assertTrue(url.endswith("/chat/completions"))
            self.assertEqual(payload["model"], model)
            self.assertEqual(category_for(model), "document")
            self.assertEqual(len(payload["messages"][0]["content"]), 2)

    def test_translation_treated_as_chat(self):
        self.assertEqual(model_type("nvidia/riva-translate-4b-instruct-v2"), "chat")

    def test_true_image_response(self):
        r = Mock()
        r.headers = {"Content-Type": "application/json"}
        r.content = b'{"artifacts":[{"base64":"SGVsbG8="}]}'
        r.json.return_value = {"artifacts": [{"base64": "SGVsbG8="}]}
        self.assertTrue(valid_output("image_flux2", r))

    def test_http_200_without_media_is_not_success(self):
        r = Mock()
        r.headers = {"Content-Type": "application/json"}
        r.content = b'{"status":"ok"}'
        r.json.return_value = {"status": "ok"}
        self.assertFalse(valid_output("image_flux2", r))

    def test_text_chat_and_embeddings_validation(self):
        ok, _ = success_from_json("chat", {"choices": [{"message": {"content": "OK"}}]})
        self.assertTrue(ok)
        ok, _ = success_from_json("embedding", {"data": [{"embedding": [0.2, 0.4]}]})
        self.assertTrue(ok)
        ok, _ = success_from_json("chat", {"choices": [{"message": {"content": ""}}]})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
