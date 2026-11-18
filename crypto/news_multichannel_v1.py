"""RSS Actu Crypto #11: verified, diversified distribution to crypto channels.

All recipients are taken from a service-role-only RPC, which decodes encrypted
private channel IDs inside Supabase Vault. The bot and owner must both be admins.
An article has an independent anti-duplicate history per channel, with 25% of
fresh items reserved exclusively for one destination. A successful Telegram
photo is confirmed in Supabase; uncertain sends are never automatically retried.

Other production modes (#01-#10) are unchanged and keep their original channel.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

import requests

from crypto import news_digest_v1 as digest
from crypto import news_media_v1 as media

UTC = timezone.utc
EXPECTED_BOT = "mrxpronos_canal_bot"
MAX_TARGETS = 25
MAX_CANDIDATES = 60
MAX_PER_TARGET_PER_RUN = 1
# Database also enforces 6 reserved/confirmed deliveries per channel per 24h.
TOKEN_TIMEOUT = (8, 20)


def digest_number(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def article_key(candidate) -> str:
    return hashlib.sha256(candidate["main"]["url"].encode("utf-8")).hexdigest()[:40]


def story_data(candidate):
    m = candidate["main"]
    return {k: m[k] for k in ("title", "source", "url", "published_at",
                             "category", "tokens", "countries", "actors", "figures") if k in m}


def slot_for(now):
    minute = 0 if now.minute < 30 else 30
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:") + f"{minute:02d}"


def validate_targets(raw):
    if not isinstance(raw, list) or len(raw) > MAX_TARGETS:
        raise RuntimeError("invalid number of crypto-only authorized targets")
    clean = []
    for row in raw:
        if not isinstance(row, dict):
            raise RuntimeError("invalid secure target record")
        key = row.get("key")
        chat = row.get("chat_id")
        channel_id = str(row.get("expected_id") or "")
        private = row.get("is_private")
        profile = row.get("profile")
        if (not isinstance(key, str) or not re.fullmatch("[0-9a-f]{64}", key)
                or private is not True and private is not False
                or not re.fullmatch(r"-100[0-9]{5,16}", channel_id)
                or profile not in ("fr", "breaking", "balanced")
                or not isinstance(row.get("bot_id"), int)):
            raise RuntimeError("invalid encrypted target metadata")
        if private:
            if str(chat) != channel_id:
                raise RuntimeError("private channel must route by Telegram numeric ID")
        elif not isinstance(chat, str) or not re.fullmatch("@[A-Za-z0-9_]{5,32}", chat):
            raise RuntimeError("public channel must route by @username")
        clean.append(dict(row))
    if len({x["key"] for x in clean}) != len(clean):
        raise RuntimeError("duplicate private inventory keys")
    return sorted(clean, key=lambda a: a["key"])


def skip_for_target(candidate, target_key, receipts, legacy_id=None, legacy_state=None,
                    target_id=None):
    main = candidate["main"]
    if legacy_id is not None and target_id == legacy_id and legacy_state:
        if digest.already_sent(main, legacy_state):
            return True
    # Cross-media duplicate protection, not merely identical article URLs.
    for old in receipts:
        if old.get("key") == target_key and isinstance(old.get("story"), dict):
            try:
                if digest.same_event(main, old["story"]):
                    return True
            except (KeyError, ValueError, TypeError):
                continue
    return False


def exclusivity(candidate, targets, receipts):
    """Freeze an event's assignment after its first recorded publication.

    A previously shared story cannot become exclusive later just because a
    different publisher becomes the lead. Exclusive ownership follows the
    verified channel key, never the external article's source.
    """
    main = candidate["main"]
    past = [r for r in receipts if isinstance(r, dict)
            and isinstance(r.get("story"), dict)
            and digest.same_event(main, r["story"])]
    exclusive = [r for r in past if r.get("exclusive") is True and r.get("owner")]
    if exclusive:
        owner = exclusive[0]["owner"]
        return True, owner
    if past:
        return False, None
    key = article_key(candidate)
    is_exclusive = digest_number("exclusive:v1:" + key) % 100 < 25
    if not is_exclusive:
        return False, None
    ordered = sorted(targets, key=lambda x: x["key"])
    return True, ordered[digest_number("owner:v1:" + key) % len(ordered)]["key"]


def ranking(candidate, target, slot, used_sources):
    main = candidate["main"]
    k = article_key(candidate)
    score = candidate.get("score", 0)
    score += digest_number("mix:" + target["key"] + ":" + slot + ":" + k) % 61
    if target["profile"] == "fr" and main.get("french"):
        score += 30
    if target["profile"] == "breaking" and main.get("category") in ("SÉCURITÉ","RÉGLEMENTATION"):
        score += 20
    if main.get("source") in used_sources:
        score -= 22
    return score


class Supabase:
    def __init__(self, session=None):
        base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if (urlsplit(base).scheme != "https" or not base.endswith(".supabase.co")
                or not key):
            raise RuntimeError("Missing secure Supabase server credentials")
        self.base = base + "/rest/v1/rpc/"
        self.session = session or requests.Session()
        self.session.headers.update({
            "apikey": key, "Authorization": "Bearer " + key,
            "Content-Type": "application/json"
        })

    def rpc(self, name, data=None):
        try:
            r = self.session.post(self.base + name, json=data or {},
                                  timeout=(8, 35))
        except requests.RequestException:
            raise RuntimeError("Secure registry request failed") from None
        if r.status_code != 200:
            # Do not dump PostgREST errors or headers that may contain private IDs.
            raise RuntimeError("Secure registry RPC " + name + " HTTP " +
                               str(r.status_code))
        try:
            return r.json()
        except ValueError:
            raise RuntimeError("Secure registry returned invalid JSON") from None

    def targets(self):
        return validate_targets(self.rpc("mrx_crypto_news_targets"))

    def receipts(self):
        obj = self.rpc("mrx_crypto_news_receipts")
        if not isinstance(obj, list) or len(obj) > 5000:
            raise RuntimeError("Secure publication history unavailable")
        return obj

    def claim(self, target, candidate, exclusive, owner, slot):
        return self.rpc("mrx_crypto_news_claim", {
            "p_key": target["key"], "p_article": article_key(candidate),
            "p_story": story_data(candidate), "p_exclusive": exclusive,
            "p_owner": owner, "p_slot": slot,
        })

    def confirm(self, target, candidate, message_id):
        return self.rpc("mrx_crypto_news_confirm", {
            "p_key": target["key"], "p_article": article_key(candidate),
            "p_message_id": message_id,
        })


class Telegram:
    def __init__(self, token=None, session=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not self.token:
            raise RuntimeError("Exact target Telegram bot token is missing")
        self.session = session or requests.Session()
        self.base = "https://api.telegram.org/bot" + self.token + "/"

    def get(self, method, params=None):
        try:
            response = self.session.get(self.base + method, params=params or {},
                                        timeout=TOKEN_TIMEOUT)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("Telegram metadata request unavailable") from None
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise RuntimeError("Telegram membership verification unavailable")
        return data["result"]

    def assert_correct_bot(self, targets):
        bot = self.get("getMe")
        if (bot.get("username","").lower() != EXPECTED_BOT
                or bot.get("is_bot") is not True
                or not isinstance(bot.get("id"), int)):
            raise RuntimeError("Configured token is not @mrxpronos_canal_bot")
        if any(t["bot_id"] != bot["id"] for t in targets):
            raise RuntimeError("Registered bot ID does not match production token")
        return bot["id"]

    def verify_destination(self, target, bot_id):
        actual = self.get("getChat", {"chat_id": target["chat_id"]})
        if (actual.get("type") != "channel" or
                str(actual.get("id")) != str(target["expected_id"])):
            raise RuntimeError("Telegram channel identity changed")
        member = self.get("getChatMember", {
            "chat_id": target["chat_id"], "user_id": bot_id
        })
        if member.get("status") not in ("administrator","creator"):
            raise RuntimeError("Exact bot is no longer a channel administrator")
        if (member.get("status") != "creator" and
                member.get("can_post_messages") is not True):
            raise RuntimeError("Bot no longer has posting permission")
        return int(actual["id"])


def publish():
    """One half-hourly run: zero or one verified photo per selected channel."""
    from crypto import production_live_v1 as live
    from crypto import production_seed_v1 as seed

    now = datetime.now(UTC)
    slot = slot_for(now)
    db = Supabase()
    targets = db.targets()
    if not targets:
        print("CRYPTO_MULTICHANNEL_NO_ACTIVE_CRYPTO_TARGETS")
        return
    receipts = db.receipts()
    client = Telegram()
    bot_id = client.assert_correct_bot(targets)
    # Use only the confirmed exact bot, not an arbitrary fallback token.
    seed.TOKEN = client.token
    source_state = seed.read_state()
    original_id = None
    original = (os.environ.get("ACTU_CRYPTO_CHAT_ID") or "").strip()
    if original:
        try:
            original_id = int(client.get("getChat",{"chat_id":original})["id"])
        except (RuntimeError, ValueError, TypeError, KeyError):
            # Fail safe: without original-channel matching, don't blindly republish
            # old #11 articles in a channel whose history we cannot recognize.
            raise RuntimeError("Original legacy channel route cannot be verified") from None

    # Collect ONCE per 30 minutes. Do not globally exclude already published
    # #11 stories: they may be valid first-time news for another channel.
    candidates = digest.collect({"sent": {}}, now)[:MAX_CANDIDATES]
    if not candidates:
        print("CRYPTO_MULTICHANNEL_NO_VERIFIED_NEW_RSS_NEWS")
        return
    used_keys, used_sources = {}, set()
    photo_cache = {}
    counts = Counter()
    # Rotate the starting channel every time slot for fair exposure.
    shift = digest_number("channel-turn:" + slot) % len(targets)
    targets = targets[shift:] + targets[:shift]

    for target in targets:
        target_key = target["key"]
        try:
            destination_id = client.verify_destination(target, bot_id)
        except RuntimeError:
            counts["destination_verification_failed"] += 1
            continue
        ranked = sorted(
            candidates, key=lambda cand: ranking(cand,target,slot,used_sources),
            reverse=True
        )
        for cand in ranked[:12]:
            k = article_key(cand)
            if k in used_keys:
                continue
            if any(digest.same_event(cand["main"], old)
                   for old in used_keys.values()):
                continue
            if skip_for_target(cand, target_key, receipts, original_id,
                               source_state, destination_id):
                continue
            is_exclusive, owner = exclusivity(cand, targets, receipts)
            if is_exclusive and owner != target_key:
                continue
            # Reuse a correctly identified article photo across channel plans,
            # but never reuse a single mutable filename for different articles.
            if k not in photo_cache:
                unique_path = media.OUTPUT.parent / ("article_" + k + ".jpg")
                photo_cache[k] = media.photo_for(cand, dest=unique_path)
            photo = photo_cache[k]
            if photo is None:
                counts["no_real_source_image"] += 1
                continue
            image, photo_source = photo
            cap = media.caption(cand, image_source=photo_source)
            claim = db.claim(target, cand, is_exclusive, owner, slot)
            if claim != "claimed":
                counts["reservation_" + str(claim)[:30]] += 1
                # Reached per-channel daily cap; don't waste time checking more.
                if claim == "daily_cap":
                    break
                continue
            try:
                message_id = live.record_send(
                    {"id": destination_id, "destination": target["chat_id"]},
                    cap, image, parse_mode="HTML"
                )
            except (RuntimeError, ValueError):
                # A pre-send reservation prevents automatic duplicate retries
                # even if a transient Telegram error hides the delivery outcome.
                counts["telegram_delivery_unconfirmed"] += 1
                print("CRYPTO_MULTICHANNEL_DELIVERY_UNCONFIRMED",
                      "private="+str(target["is_private"]))
                break
            if db.confirm(target, cand, message_id) is not True:
                counts["db_confirm_failed"] += 1
                print("CRYPTO_MULTICHANNEL_CONFIRM_FAILED")
                break
            receipts.append({
                "key": target_key, "story": story_data(cand),
                "exclusive": is_exclusive, "owner": owner, "status": "confirmed",
            })
            used_keys[k] = cand["main"]
            used_sources.add(cand["main"]["source"])
            counts["published"] += 1
            counts["private_published" if target["is_private"] else "public_published"] += 1
            counts["exclusive_published" if is_exclusive else "shared_published"] += 1
            # Log no private Telegram ID, private title, invite or secret.
            print("CRYPTO_MULTICHANNEL_PUBLISHED",
                  "photo_confirmed=1",
                  "private="+str(target["is_private"]).lower(),
                  "exclusive="+str(is_exclusive).lower())
            break
    print("CRYPTO_MULTICHANNEL_BATCH",
          "checked="+str(len(targets)),
          "published="+str(counts["published"]),
          "public="+str(counts["public_published"]),
          "private="+str(counts["private_published"]),
          "exclusive="+str(counts["exclusive_published"]),
          "delivery_unconfirmed="+str(counts["telegram_delivery_unconfirmed"]),
          "confirm_failed="+str(counts["db_confirm_failed"]),
          "verification_failed="+str(counts["destination_verification_failed"]))
    if counts["db_confirm_failed"] or counts["telegram_delivery_unconfirmed"]:
        raise RuntimeError("One or more Telegram deliveries need a manual audit")


if __name__ == "__main__":
    publish()
