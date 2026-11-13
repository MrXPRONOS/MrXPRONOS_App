"""Publish Bluesky video ONLY after the video service confirms transcoding.

The Python SDK's high-level send_video() uses uploadBlob and can return an
apparently successful post URI while Bluesky's video CDN has not processed the
raw MP4. This helper follows the official video.bsky.app processing workflow.
No retries after a potentially successful post; caller owns D1 dedup claims.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import requests

VIDEO_SERVICE = "https://video.bsky.app"
TIMEOUT_SECONDS = 300


class BlueskyVideoError(RuntimeError):
    pass


def pds_host(did_doc):
    """Resolve the server audience from the account's DID document."""
    if hasattr(did_doc, "model_dump"):
        did_doc = did_doc.model_dump(by_alias=True)
    if not isinstance(did_doc, dict):
        raise BlueskyVideoError("Document DID Bluesky indisponible")
    for entry in did_doc.get("service") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id", "")).endswith("#atproto_pds"):
            endpoint = entry.get("serviceEndpoint") or entry.get("service_endpoint") or ""
            parsed = urlparse(str(endpoint))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.port:
                raise BlueskyVideoError("Adresse PDS non valide dans le document DID")
            return parsed.hostname
    raise BlueskyVideoError("Service PDS introuvable dans le document DID")


def job_details(payload):
    """Upload returns either JobStatus directly or an envelope; polling wraps it."""
    if not isinstance(payload, dict):
        raise BlueskyVideoError("Reponse non JSON valide du service video")
    return payload.get("jobStatus") or payload


def processed_blob_from_status(status):
    """Never accept a video without a processed blob and a supported terminal state."""
    if not isinstance(status, dict):
        raise BlueskyVideoError("Statut video absent")
    state = str(status.get("state") or "").upper()
    if state == "JOB_STATE_FAILED":
        raise BlueskyVideoError("Traitement video Bluesky echoue : " + str(status.get("error") or "erreur de traitement")[:120])
    blob = status.get("blob")
    if blob is not None:
        if not isinstance(blob, dict) or not blob.get("ref") or not blob.get("mimeType") or not isinstance(blob.get("size"), int):
            raise BlueskyVideoError("Blob video transcode invalide")
        if state not in ("JOB_STATE_COMPLETED", "") and str(status.get("error") or "") != "already_exists":
            # Explicit blob is authoritative, but non-terminal status is not.
            return None
        return blob
    return None


def wait_for_processed_video(session, token, did, filename, video, *, max_wait=TIMEOUT_SECONDS, interval=2):
    """Upload to Bluesky video CDN and wait for a completed processed blob."""
    if not str(did).startswith("did:") or not token:
        raise BlueskyVideoError("Autorisation video Bluesky invalide")
    if not video or not filename.lower().endswith(".mp4"):
        raise BlueskyVideoError("Source MP4 absente")
    if not 100_000 <= len(video) <= 50_000_000:
        raise BlueskyVideoError("MP4 hors de la plage autorisee")

    headers = {"Authorization": "Bearer " + token, "Content-Type": "video/mp4"}
    response = session.post(
        VIDEO_SERVICE + "/xrpc/app.bsky.video.uploadVideo",
        params={"did": did, "name": Path(filename).name},
        headers=headers,
        data=video,
        timeout=180,
    )
    try:
        initial = job_details(response.json())
    except (ValueError, TypeError) as exc:
        raise BlueskyVideoError("Reponse de chargement video non interpretable") from exc
    if response.status_code not in (200, 201, 409):
        raise BlueskyVideoError("Upload video Bluesky refuse HTTP " + str(response.status_code))

    blob = processed_blob_from_status(initial)
    if blob:
        return blob
    job_id = str(initial.get("jobId") or "")
    if not job_id:
        raise BlueskyVideoError("Bluesky n'a fourni ni video traitee ni identifiant de traitement")
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        result = session.get(
            VIDEO_SERVICE + "/xrpc/app.bsky.video.getJobStatus",
            params={"jobId": job_id},
            timeout=35,
        )
        if result.status_code != 200:
            raise BlueskyVideoError("Impossible de lire le traitement video, HTTP " + str(result.status_code))
        try:
            status = job_details(result.json())
        except (ValueError, TypeError) as exc:
            raise BlueskyVideoError("Statut de traitement non interpretable") from exc
        blob = processed_blob_from_status(status)
        if blob:
            return blob
        time.sleep(interval)
    raise BlueskyVideoError("Video non traitee apres cinq minutes : publication abandonnee")


def publish_processed_video(client, login_result, video, filename, caption, alt, *, session=None):
    """Create a Bluesky post only once the transcoding service confirms playback data."""
    from atproto import models
    from atproto_client.models.blob_ref import BlobRef

    session = session or requests.Session()
    did = str(login_result.did)
    # The SDK login response does not consistently expose did_doc across
    # atproto-client versions. Never access it as a mandatory attribute.
    doc = getattr(login_result, "did_doc", None)
    if not doc:
        # describeRepo is a read-only, authenticated PDS lookup and returns
        # the DID document even when createSession omits didDoc.
        lookup = client.com.atproto.repo.describe_repo({"repo": did})
        doc = getattr(lookup, "did_doc", None)
    if not doc:
        raise BlueskyVideoError("Document DID Bluesky introuvable apres connexion et describeRepo")
    host = pds_host(doc)
    grant = client.com.atproto.server.get_service_auth({
        "aud": "did:web:" + host,
        "lxm": "com.atproto.repo.uploadBlob",
        "exp": int(time.time()) + 1800,
    })
    service_token = str(grant.token or "")
    if not service_token:
        raise BlueskyVideoError("Autorisation video inter-service non obtenue")

    blob = wait_for_processed_video(session, service_token, did, filename, video)
    processed = BlobRef.model_validate(blob)
    aspect = models.AppBskyEmbedDefs.AspectRatio(width=1080, height=1920)
    embed = models.AppBskyEmbedVideo.Main(video=processed, alt=alt[:900], aspect_ratio=aspect)
    response = client.send_post(text=caption[:280], embed=embed, langs=["fr"])
    if not str(response.uri).startswith("at://"):
        raise BlueskyVideoError("Bluesky n'a pas confirme l'URI du post")
    return response
