#!/usr/bin/env python3
"""One-time, narrowly scoped cleanup of Mr XPRONOS photo coupon posts on Bluesky.

Default is a read-only audit. Explicit --delete removes ONLY own image posts
with exact text AND image alt fingerprints of the legacy photo publishers.
Never delete videos, links, ordinary images, reposts, or third-party posts.
"""
import argparse
import json
import os
import sys


def attr(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def classify(post, did):
    if attr(attr(post, "author"), "did") != did:
        return None
    uri = str(attr(post, "uri", ""))
    if not uri.startswith("at://" + did + "/app.bsky.feed.post/"):
        return None

    record = attr(post, "record")
    text = str(attr(record, "text", ""))
    embed = attr(record, "embed")
    images = attr(embed, "images")
    if not isinstance(images, list) or not images:
        return None
    if attr(embed, "video") is not None:
        return None

    alts = [str(attr(img, "alt", "")) for img in images]
    if (text.startswith("⚽ Combiné Mr XPRONOS · ")
            and "Mise simulée : 50 000 F CFA." in text
            and alts == ["Aperçu du combiné Mr XPRONOS"]):
        return "accumulator-photo"

    if ("Mr XPRONOS" in text
            and (text.startswith("⚽ Pronostic football | Mr XPRONOS")
                 or text.startswith("🌙 Sélection de nuit | Mr XPRONOS")
                 or text.startswith("🌙 Sélection de nuit · Combiné | Mr XPRONOS")
                 or text.startswith("⚽ Pronostic football · Combiné | Mr XPRONOS"))
            and all(alt.startswith(("Carte de pronostic Mr XPRONOS :", "Carte de pronostic combiné Mr XPRONOS :")) for alt in alts)):
        return "bsd-v2-photo"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--max-delete", type=int, default=100)
    args = parser.parse_args()
    handle = os.getenv("BLUESKY_HANDLE", "").strip().lstrip("@")
    password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise SystemExit("BLUESKY_HANDLE et BLUESKY_APP_PASSWORD requis")

    from atproto import Client
    client = Client()
    profile = client.login(handle, password)
    did = str(attr(profile, "did") or attr(client.me, "did"))
    cursor = None
    identified = {}
    pages = 0
    for _ in range(max(1, min(args.max_pages, 40))):
        response = client.get_author_feed(actor=did, cursor=cursor, limit=100, filter="posts_with_media")
        pages += 1
        for item in response.feed:
            post = attr(item, "post")
            category = classify(post, did)
            if category:
                identified[str(attr(post, "uri"))] = category
        next_cursor = attr(response, "cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    print("PHOTO_COUPON_AUDIT", json.dumps({"pages": pages, "candidates": len(identified),
          "kinds": {k: sum(v == k for v in identified.values())
                    for k in ("accumulator-photo", "bsd-v2-photo")}, "dry_run": not args.delete}))
    for uri, kind in identified.items():
        print("PHOTO_COUPON_CANDIDATE", kind, uri.split("/")[-1])
    if not args.delete:
        return 0
    if len(identified) > args.max_delete:
        raise RuntimeError("Trop de candidats, suppression bloquée; examiner le rapport")
    done = 0
    for uri, kind in identified.items():
        if not client.delete_post(uri):
            raise RuntimeError("Suppression non confirmée pour " + uri.split("/")[-1])
        done += 1
        print("PHOTO_COUPON_DELETED", kind, uri.split("/")[-1])
    print("PHOTO_COUPON_CLEANUP_DONE", json.dumps({"deleted": done, "candidates": len(identified)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
