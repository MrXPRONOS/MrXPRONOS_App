#!/usr/bin/env python3
"""GitHub Actions delivery for extensible owner-controlled Telegram bot reactions.

Cloudflare's existing Cine Radar channel_post webhook supplies the publication IDs;
the existing 2 bots retain their low-latency Cloudflare delivery. This job sends
any configured slot from 03 onward. It does NOT create, edit, publish, or delete any Telegram post.

Runs at best every five minutes: GitHub Actions is not a realtime scheduler.
Never log API URLs that contain Telegram bot tokens.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

D1_DATABASE_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
MIN_SLOT = 3
MAX_SLOT = 9999
EXTRA_SLOTS = range(MIN_SLOT, MAX_SLOT + 1)
TOKEN_KEY_RE = re.compile(r"^TELEGRAM_REACTION_BOT_([0-9]{2,4})_TOKEN$")
SLOT_BATCH_SIZE = 25
BLOCKED_IDENTITIES = {"cineradarfr_bot", "mrxpronos_canal_bot"}
MAX_JOBS_PER_RUN = 100
MAX_NEW_JOBS_PER_RUN = 600
NETWORK_TIMEOUT = 20


class APIError(RuntimeError):
    """A sanitized error that never includes bot credentials."""


def reaction_for(post_seq: int, slot: int) -> str:
    """Odd-numbered bots heart odd posts; the roles reverse on even posts."""
    if post_seq < 1 or slot not in EXTRA_SLOTS:
        raise ValueError("Bad reaction slot or post sequence")
    return "❤️" if post_seq % 2 == slot % 2 else "👍"


def configured_tokens(env: dict[str, str]) -> dict[int, str]:
    """Read numbered GitHub secrets and an optional single JSON bundle.

    The GitHub workflow exposes slots 03..99 explicitly. For higher slots,
    TELEGRAM_REACTION_BOTS_JSON can be a map, for example
    {"100":"token-one-hundred","101":"token-one-hundred-one"}.
    No secret value is ever printed.
    """
    candidates: dict[int, str] = {}
    for name, raw_token in env.items():
        match = TOKEN_KEY_RE.fullmatch(name)
        if match is None:
            continue
        slot = int(match.group(1))
        if slot in EXTRA_SLOTS and isinstance(raw_token, str) and raw_token.strip():
            candidates[slot] = raw_token.strip()
    bundle = env.get("TELEGRAM_REACTION_BOTS_JSON", "").strip()
    if bundle:
        try:
            parsed = json.loads(bundle)
            if not isinstance(parsed, dict):
                raise ValueError("Not a mapping")
            for key, token in parsed.items():
                if (not isinstance(key, str) or not key.isdecimal()
                    or not isinstance(token, str)):
                    raise ValueError("Invalid slot or token type")
                slot = int(key)
                if slot not in EXTRA_SLOTS:
                    raise ValueError("Out-of-range slot")
                if token.strip() and slot not in candidates:
                    candidates[slot] = token.strip()
        except (ValueError, TypeError) as exc:
            raise APIError("Malformed TELEGRAM_REACTION_BOTS_JSON secret") from None

    seen = set()
    tokens: dict[int, str] = {}
    for slot in sorted(candidates):
        token = candidates[slot]
        if token not in seen:
            seen.add(token)
            tokens[slot] = token
    return tokens


def _request_json(url: str, data: dict[str, Any], headers: dict[str, str],
                  timeout: int = NETWORK_TIMEOUT) -> tuple[int, dict[str, Any]]:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=raw, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        **headers,
    }, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            payload = json.loads(error.read(4096).decode("utf-8", errors="replace"))
        except (ValueError, UnicodeError):
            payload = {}
        return error.code, payload if isinstance(payload, dict) else {}
    except (URLError, TimeoutError, OSError) as error:
        raise APIError("Network failure (" + type(error).__name__ + ")") from None


class D1:
    def __init__(self, token: str, account_id: str, transport=_request_json):
        if not token or not account_id:
            raise APIError("Cloudflare account or API token unavailable")
        self.url = (f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
                    f"/d1/database/{D1_DATABASE_ID}/query")
        self.headers = {"Authorization": "Bearer " + token}
        self.transport = transport

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        status, data = self.transport(self.url, {"sql": sql, "params": list(params)}, self.headers)
        if status != 200 or data.get("success") is not True:
            raise APIError("Cloudflare D1 query refused (HTTP " + str(status) + ")")
        results = data.get("result") or []
        if not results or results[0].get("success") is not True:
            raise APIError("Cloudflare D1 returned invalid query result")
        return results[0]

    def batch(self, updates: list[tuple[str, tuple[Any, ...]]]) -> None:
        if not updates:
            return
        batches = [{"sql": sql, "params": list(params)} for sql, params in updates]
        status, data = self.transport(self.url, {"batch": batches}, self.headers)
        if status != 200 or data.get("success") is not True:
            raise APIError("Cloudflare D1 batch update rejected (HTTP " + str(status) + ")")
        if len(data.get("result") or []) != len(batches) or any(
            r.get("success") is not True for r in data["result"]
        ):
            raise APIError("Cloudflare D1 partial/invalid batch update")


def telegram_call(token: str, method: str, data: dict[str, Any],
                  transport=_request_json) -> tuple[int, dict[str, Any]]:
    # Never log, print or raise an exception that includes this token-bearing URL.
    url = f"https://api.telegram.org/bot{token}/{method}"
    return transport(url, data, {})


def verify_bots(tokens: dict[int, str], transport=_request_json) -> dict[int, str]:
    """Check all bot IDs are unique and exclude the two existing production bots."""
    accepted = {}
    ids: dict[int,int] = {}
    for slot, token in tokens.items():
        try:
            status, answer = telegram_call(token, "getMe", {}, transport)
        except APIError:
            print(f"bot_slot={slot:02d} identity=unavailable")
            continue
        bot = answer.get("result") or {}
        bot_id = bot.get("id")
        username = str(bot.get("username") or "").casefold()
        if status != 200 or answer.get("ok") is not True:
            print(f"bot_slot={slot:02d} identity=getme_failed_http_{status}")
            continue
        if not bot.get("is_bot") or not isinstance(bot_id, int) or not username:
            print(f"bot_slot={slot:02d} identity=invalid_bot_information")
            continue
        if username in BLOCKED_IDENTITIES:
            print(f"bot_slot={slot:02d} identity=reserved_existing_bot")
            continue
        if bot_id in ids:
            print(f"bot_slot={slot:02d} identity=duplicate_of_slot_{ids[bot_id]:02d}")
            continue
        ids[bot_id] = slot
        accepted[slot] = token
    return accepted


def prepare_jobs(db: D1, slots: tuple[int, ...]) -> None:
    """Queue reactions for verified bots with their individual activation dates.

    A bot added to GitHub for the first time starts AFTER the latest already
    observed post. Existing bots retain their earlier watermarks. SQL VALUES
    avoids SQLite's compound SELECT limits, and batches bound query size.
    """
    if not slots:
        return
    if len(slots) != len(set(slots)) or any(s not in EXTRA_SLOTS for s in slots):
        raise ValueError("Invalid configured bot slots")
    for offset in range(0, len(slots), SLOT_BATCH_SIZE):
        group = slots[offset:offset + SLOT_BATCH_SIZE]
        bots = ",".join("(" + str(slot) + ")" for slot in group)
        db.query(f"""
          INSERT OR IGNORE INTO channel_reaction_extra_bot_activation(bot_slot,start_after_seq)
          SELECT b.column1, (SELECT COALESCE(MAX(seq),0) FROM channel_reaction_posts)
          FROM (VALUES{bots}) AS b
        """)
        db.query(f"""
          INSERT OR IGNORE INTO channel_reaction_extra_jobs(post_seq,bot_slot,emoji)
          SELECT p.seq,b.column1,
            CASE WHEN (p.seq % 2) = (b.column1 % 2) THEN '❤️' ELSE '👍' END
          FROM channel_reaction_posts AS p
          CROSS JOIN (VALUES{bots}) AS b
          JOIN channel_reaction_extra_bot_activation AS a ON a.bot_slot=b.column1
          WHERE p.seq > a.start_after_seq
          AND NOT EXISTS (
            SELECT 1 FROM channel_reaction_extra_jobs AS j
            WHERE j.post_seq=p.seq AND j.bot_slot=b.column1
          )
          -- Include the latest observed posts first even when history is large.
          ORDER BY p.seq DESC,b.column1
          LIMIT {MAX_NEW_JOBS_PER_RUN}
        """)


def due_jobs(db: D1, slots: tuple[int, ...]) -> list[dict[str, Any]]:
    """Select only the newest due publications, then work backwards.

    A capacity of 10 picks the 10 most recent eligible reaction jobs, not
    8 recent and 2 historical ones. Older jobs remain in D1 and are processed
    when newer jobs no longer consume the available capacity.
    """
    if not slots:
        return []
    marks = ",".join("?" for _ in slots)
    query = f"""
      SELECT j.post_seq,j.bot_slot,j.emoji,j.attempts,p.chat_id,p.message_id
      FROM channel_reaction_extra_jobs AS j
      JOIN channel_reaction_posts AS p ON p.seq=j.post_seq
      WHERE j.bot_slot IN ({marks})
        AND j.state IN ('pending','retry')
        AND datetime(j.next_try_at)<=CURRENT_TIMESTAMP
      ORDER BY j.post_seq DESC,j.bot_slot ASC LIMIT ?
    """
    return db.query(query, (*slots, MAX_JOBS_PER_RUN)).get("results") or []


def audit_primary_channel_access(db: D1, bots: dict[int, str],
                                 transport=_request_json) -> None:
    """Read-only membership test; called only on push/manual workflow runs."""
    primaries = db.query(
        "SELECT kind,chat_id FROM radar_primary_channels ORDER BY kind"
    ).get("results") or []
    for slot, token in sorted(bots.items()):
        try:
            status, info = telegram_call(token, "getMe", {}, transport)
            bot_id = (info.get("result") or {}).get("id")
            if status != 200 or not isinstance(bot_id, int):
                print(f"access_bot={slot:02d} status=identity_unavailable")
                continue
            for channel in primaries:
                kind = str(channel.get("kind") or "unknown")
                chat_id = channel.get("chat_id")
                if not chat_id:
                    print(f"access_bot={slot:02d} channel={kind} status=not_bound")
                    continue
                try:
                    code, answer = telegram_call(token, "getChatMember", {
                        "chat_id": str(chat_id), "user_id": bot_id,
                    }, transport)
                    member = (answer.get("result") or {}).get("status")
                    level = ("admin" if (code == 200 and answer.get("ok") and
                              member in ("administrator","creator")) else
                             "not_admin" if (code == 200 and answer.get("ok")) else
                             "not_accessible")
                    print(f"access_bot={slot:02d} channel={kind} status={level}")
                except APIError:
                    print(f"access_bot={slot:02d} channel={kind} status=network_unavailable")
        except APIError:
            print(f"access_bot={slot:02d} status=network_unavailable")


def retry_delay(attempts: int, retry_after: int = 0) -> int:
    return max(45, min(3600, max(retry_after, 45 * (2 ** min(attempts, 6)))))


def next_retry(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def safe_reaction_error(status: int, response: dict[str, Any]) -> str:
    """A fixed diagnostic label, never Telegram response text or credentials."""
    description = str(response.get("description") or "").casefold()
    categories = [
        ("message to react not found", "message_not_found"),
        ("chat not found", "chat_not_found"),
        ("not enough rights", "not_enough_rights"),
        ("forbidden", "forbidden"),
        ("reactions are disabled", "reactions_disabled"),
        ("reaction is not allowed", "reaction_not_allowed"),
        ("reaction_invalid", "reaction_invalid"),
        ("reaction", "reaction_rejected"),
    ]
    category = next((code for needle, code in categories if needle in description), "unknown")
    return f"telegram_http_{status}:{category}"


def make_update(row: dict[str, Any], status: int, response: dict[str, Any],
                network_error: bool = False) -> tuple[str, tuple[Any, ...]]:
    seq, slot = int(row["post_seq"]), int(row["bot_slot"])
    if not network_error and status == 200 and response.get("ok") is True:
        return ("""
          UPDATE channel_reaction_extra_jobs
          SET state='sent',sent_at=CURRENT_TIMESTAMP,last_error='',
              attempts=attempts+1,updated_at=CURRENT_TIMESTAMP
          WHERE post_seq=? AND bot_slot=? AND state IN ('pending','retry')
        """, (seq, slot))
    code = status
    error = str(response.get("description") or "network_or_api_error").lower()
    # Access can become available later after an owner adds the bot as an
    # administrator. Never abandon chat_not_found / missing-rights forever.
    # These are retried with a slow backoff, avoiding a storm of failed calls.
    recoverable_access = (not network_error and code in (400, 403) and
        any(term in error for term in (
            "chat not found", "bot is not a member", "bot is not a participant",
            "user is not a participant", "not enough rights", "bot was kicked",
        )))
    # Other 4xx failures (deleted message, disabled emoji, etc.) are final.
    permanent = (not recoverable_access and not network_error and
                 code in (400, 403, 404) and
                 not any(x in error for x in ("retry", "temporar", "flood")))
    if permanent:
        return ("""
          UPDATE channel_reaction_extra_jobs
          SET state='blocked',last_error=?,attempts=attempts+1,
              updated_at=CURRENT_TIMESTAMP
          WHERE post_seq=? AND bot_slot=?
        """, (safe_reaction_error(code, response), seq, slot))
    param = response.get("parameters") or {}
    delay = retry_delay(int(row["attempts"]), int(param.get("retry_after") or 0))
    if recoverable_access:
        delay = max(900, delay)
    return ("""
      UPDATE channel_reaction_extra_jobs
      SET state='retry',next_try_at=?,last_error=?,attempts=attempts+1,
          updated_at=CURRENT_TIMESTAMP
      WHERE post_seq=? AND bot_slot=?
    """, (next_retry(delay), safe_reaction_error(code or 0, response), seq, slot))


def run(env: dict[str, str], transport=_request_json) -> int:
    candidates = configured_tokens(env)
    if not candidates:
        print("No extra reaction tokens configured: safe no-op.")
        return 0
    bots = verify_bots(candidates, transport)
    visible = [slot for slot in sorted(candidates) if 3 <= slot <= 16]
    print("reaction_slots_03_16_configured=" + ",".join(f"{slot:02d}" for slot in visible))
    print("reaction_slots_verified=" + ",".join(f"{slot:02d}" for slot in sorted(bots)))
    if not bots:
        print("No additional bot identities verified: safe no-op.")
        return 0
    db = D1(env.get("CLOUDFLARE_API_TOKEN", "") or env.get("CF_API_TOKEN", ""),
            env.get("CLOUDFLARE_ACCOUNT_ID", ""), transport)
    if env.get("REACTION_ACCESS_AUDIT", "").lower() == "true":
        audit_primary_channel_access(db, bots, transport)
    prepare_jobs(db, tuple(sorted(bots)))
    rows = due_jobs(db, tuple(sorted(bots)))
    updates = []
    ok = 0
    blocked = 0
    for row in rows:
        slot = int(row["bot_slot"])
        emoji = reaction_for(int(row["post_seq"]), slot)
        if emoji != row["emoji"]:
            raise APIError("Reaction parity mismatch in database")
        try:
            status, answer = telegram_call(bots[slot], "setMessageReaction", {
                "chat_id": row["chat_id"],
                "message_id": int(row["message_id"]),
                "reaction": [{"type": "emoji", "emoji": emoji}],
                "is_big": False,
            }, transport)
            failed_transport = False
        except APIError:
            status, answer, failed_transport = 0, {}, True
        update = make_update(row, status, answer, failed_transport)
        if "state='sent'" in update[0]:
            ok += 1
        elif "state='blocked'" in update[0]:
            blocked += 1
        updates.append(update)
        # Small pacing protects against bursts. A 429 is postponed, not ignored.
        time.sleep(0.11)
    db.batch(updates)
    print(f"verified_bots={len(bots)} pending_examined={len(rows)} "
          f"reactions_confirmed={ok} blocked={blocked} retries={len(rows)-ok-blocked}")
    return ok


if __name__ == "__main__":
    try:
        run(dict(os.environ))
    except APIError as exc:
        print("REACTION_WORKFLOW_ERROR:", exc, file=sys.stderr)
        sys.exit(1)
