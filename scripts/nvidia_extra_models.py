#!/usr/bin/env python3
"""Additional NVIDIA NIM probes for visual, image and video models.

Models not returned by /v1/models can still have standalone NVIDIA Build endpoints.
Keep this registry limited to explicitly documented invocation contracts.
"""
from __future__ import annotations

import base64
from io import BytesIO
import re
import time
import requests

API = "https://ai.api.nvidia.com/v1/genai/"
CHAT = "https://integrate.api.nvidia.com/v1/chat/completions"
POLL = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/"

# Full IDs, not guessed URLs. Only publicly documented NVIDIA Build endpoints.
SPECIAL_MODELS = {
    "black-forest-labs/flux.1-dev": "image_flux1_dev",
    "black-forest-labs/flux.1-schnell": "image_flux1_schnell",
    "black-forest-labs/flux.2-klein-4b": "image_flux2",
    "black-forest-labs/flux.3-image-klein": "image_flux3",
    "stabilityai/stable-diffusion-3-medium": "image_sd3",
    "stabilityai/stable-diffusion-xl": "image_sdxl",
    "stabilityai/stable-video-diffusion": "video_svd",
    "nvidia/nemotron-parse": "document_vision",
    "nvidia/nemotron-parse-2.0": "document_vision",
    "nvidia/cosmos-reason2-8b": "vision_chat",
    "nvidia/magpie-tts-multilingual": "audio_tts",
}

IMAGE_URLS = {
    "image_flux1_dev": API + "black-forest-labs/flux.1-dev",
    "image_flux1_schnell": API + "black-forest-labs/flux.1-schnell",
    "image_flux2": API + "black-forest-labs/flux.2-klein-4b",
    "image_flux3": API + "black-forest-labs/flux.3-image-klein",
    "image_sd3": API + "stabilityai/stable-diffusion-3-medium",
    "image_sdxl": API + "stabilityai/stable-diffusion-xl",
    "video_svd": API + "stabilityai/stable-video-diffusion",
}

# Models in the catalog that were previously (incorrectly) treated as special-only.
CHAT_OVERRIDE = {
    "nvidia/riva-translate-4b-instruct",
    "nvidia/riva-translate-4b-instruct-v2",
}


def category_for(model_id: str) -> str | None:
    kind = SPECIAL_MODELS.get(model_id)
    if kind and kind.startswith("image_"):
        return "image"
    if kind and kind.startswith("video_"):
        return "video"
    if kind == "audio_tts":
        return "audio"
    if kind == "document_vision":
        return "document"
    if kind == "vision_chat":
        return "vision"
    if model_id in CHAT_OVERRIDE:
        return "chat"
    return None


def make_document_image(width: int = 1024, height: int = 1280) -> str:
    # Synthetic test document; contains no customer data and is small enough for inline input.
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((120, 180), "NVIDIA TEST DOCUMENT", fill=(0, 0, 0))
    draw.text((120, 260), "Mr XPRONOS benchmark", fill=(0, 0, 0))
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def request_for(model_id: str) -> tuple[str, dict]:
    kind = SPECIAL_MODELS[model_id]
    prompt = "An orange ball on a blue table, clean studio photo."
    if kind.startswith("image_flux1"):
        payload = {
            "prompt": prompt, "mode": "base", "height": 1024, "width": 1024,
            "samples": 1, "seed": 1,
            "steps": 4 if kind == "image_flux1_schnell" else 8,
            "cfg_scale": 0 if kind == "image_flux1_schnell" else 5,
        }
    elif kind in ("image_flux2", "image_flux3"):
        payload = {
            "prompt": prompt, "mode": "Image Generation", "height": 1024, "width": 1024,
            "samples": 1, "seed": 1,
            "steps": 4 if kind == "image_flux2" else 10,
            "cfg_scale": 0 if kind == "image_flux2" else 3.5,
        }
    elif kind == "image_sd3":
        payload = {
            "prompt": prompt, "aspect_ratio": "1:1", "mode": "text-to-image",
            "model": "sd3", "output_format": "jpeg", "seed": 1, "steps": 5,
            "cfg_scale": 5,
        }
    elif kind == "image_sdxl":
        payload = {
            "height": 1024, "width": 1024, "text_prompts": [{"text": prompt, "weight": 1}],
            "samples": 1, "seed": 1, "steps": 5, "cfg_scale": 5,
            "sampler": "K_DPM_2_ANCESTRAL", "clip_guidance_preset": "NONE",
            "style_preset": "none",
        }
    elif kind == "video_svd":
        payload = {
            "image": make_document_image(1024, 576),
            "seed": 1, "cfg_scale": 1.8, "motion_bucket_id": 127,
        }
    elif kind == "audio_tts":
        payload = {"text": "This is an NVIDIA API test.", "language": "en-US",
                   "voice": "Magpie-Multilingual.EN-US.Aria",
                   "encoding": "LINEAR_PCM", "sample_rate_hz": "44100"}
    elif kind == "document_vision":
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "</s><output_markdown>"},
                {"type": "image_url", "image_url": {"url": make_document_image()}},
            ]}],
            "max_tokens": 256, "stream": False,
        }
    elif kind == "vision_chat":
        payload = {
            "model": model_id, "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe this image briefly."},
                {"type": "image_url", "image_url": {"url": make_document_image(256, 256)}},
            ]}],
            "max_tokens": 128, "stream": False,
        }
    else:
        raise ValueError("No documented specialized contract: " + model_id)
    if kind == "audio_tts":
        return ("https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize", payload)
    return IMAGE_URLS.get(kind, CHAT), payload


def valid_output(kind: str, response: requests.Response) -> bool:
    if not response.content:
        return False
    content_type = response.headers.get("Content-Type", "").lower()
    if any(t in content_type for t in ("image/", "video/", "audio/", "application/octet-stream")):
        return len(response.content) > 256
    if kind == "audio_tts":
        return response.content.startswith(b"RIFF") or response.content.startswith(b"OggS") or response.content.startswith(b"ID3")
    if "image/" in content_type or "video/" in content_type:
        return len(response.content) > 256
    try:
        data = response.json()
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    if kind in ("document_vision", "vision_chat"):
        choices = data.get("choices") or []
        if not choices:
            return False
        msg = (choices[0] or {}).get("message") or {}
        return bool((msg.get("content") or "").strip()) if isinstance(msg.get("content"), str) else bool(msg.get("content"))
    # Validate actual output structure rather than treating any HTTP 200 JSON as success.
    for key in ("artifacts", "images", "videos", "output", "data"):
        value = data.get(key)
        if isinstance(value, list) and value:
            entries = value[0]
            if isinstance(entries, dict) and any(entries.get(k) for k in
                ("base64", "b64_json", "image", "image_url", "url", "video", "content", "data")):
                return True
            if isinstance(entries, str) and len(entries) > 100:
                return True
    for key in ("image", "video", "b64_json", "base64", "image_url", "video_url"):
        if isinstance(data.get(key), str) and len(data[key]) > 20:
            return True
    return False


def poll_if_async(session: requests.Session, response: requests.Response,
                  deadline: float, timeout: float):
    request_id = response.headers.get("NVCF-REQID", "")
    if not request_id:
        try:
            payload = response.json()
            request_id = payload.get("requestId") or payload.get("request_id") or ""
        except (ValueError, AttributeError):
            pass
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", str(request_id)):
        return response, "accepted_async_not_verified"
    url = POLL + str(request_id)
    while time.monotonic() < deadline:
        time.sleep(min(3, max(0, deadline - time.monotonic())))
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
        response = session.get(url, timeout=min(timeout, remaining), allow_redirects=False)
        if response.status_code != 202:
            return response, ""
    return response, "async_timeout"


def probe_special(session: requests.Session, model_id: str, timeout: float, sanitize):
    kind = SPECIAL_MODELS[model_id]
    start = time.perf_counter()
    try:
        url, payload = request_for(model_id)
        request_timeout = max(timeout, 90) if kind.startswith(("image_", "video_")) else timeout
        if kind == "audio_tts":
            # NVIDIA TTS expects multipart/form-data (-F in official cURL), not urlencoded data.
            multipart = {key: (None, str(value)) for key, value in payload.items()}
            response = session.post(url, files=multipart, timeout=request_timeout, allow_redirects=False)
        else:
            response = session.post(url, json=payload, timeout=request_timeout, allow_redirects=False)
        async_status = ""
        if response.status_code == 202:
            response, async_status = poll_if_async(
                session, response, time.monotonic() + request_timeout, request_timeout)
        elapsed = round(time.perf_counter() - start, 3)
        if async_status:
            state = async_status
        elif response.status_code == 200:
            state = "ok" if valid_output(kind, response) else "reponse_vide"
        else:
            state = {
                400: "requete_refusee", 401: "cle_invalide",
                402: "paiement_requis", 403: "acces_refuse",
                404: "introuvable", 410: "retire",
                422: "requete_refusee", 429: "limite_atteinte",
            }.get(response.status_code,
                "erreur_serveur" if response.status_code >= 500 else "erreur_http")
        err = ""
        if state != "ok":
            if state == "reponse_vide":
                err = "HTTP 200 sans image/vidéo/texte vérifiable"
            elif state.startswith("async") or state == "accepted_async_not_verified":
                err = state
            else:
                try:
                    data = response.json()
                    err = sanitize(data.get("detail") or data.get("error") or data.get("message") or
                                   ("HTTP " + str(response.status_code))) if isinstance(data, dict) else state
                except ValueError:
                    err = "HTTP " + str(response.status_code)
        return {
            "status": state, "http_status": response.status_code,
            "elapsed": elapsed, "input_tokens": 0, "output_tokens": 0,
            "error": err, "preview": "sortie multimodale vérifiée" if state == "ok" else "",
        }
    except requests.Timeout:
        state = "timeout"
    except requests.RequestException:
        state = "erreur_reseau"
    except Exception as exc:
        state = "erreur_locale_" + type(exc).__name__
    return {
        "status": state, "http_status": None,
        "elapsed": round(time.perf_counter() - start, 3),
        "input_tokens": 0, "output_tokens": 0,
        "error": state, "preview": "",
    }
