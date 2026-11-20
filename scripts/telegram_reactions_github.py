#!/usr/bin/env python3
"""GitHub Actions delivery for 10 optional, owner-controlled Telegram bot reactions.

Cloudflare's existing Cine Radar channel_post webhook supplies the publication IDs;
the existing 2 bots retain their low-latency Cloudflare delivery. This job sends
only slots 03..12. It does NOT create, edit, publish, or delete any Telegram post.

Runs at best every five minutes: GitHub Actions is not a realtime scheduler.
Never log API URLs that contain Telegram bot tokens.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

D1_DATABASE_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
EXTRA_SLOTS = tuple(range(3, 13))
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
    tokens = {}
    seen = set()
    for slot in EXTRA_SLOTS:
        name = f"TELEGRAM_REACTION_BOT_{slot:02d}_TOKEN"
        token = env.get(name, "").strip()
        if token and token not in seen:
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
    ids = set()
    for slot, token in tokens.items():
        try:
            status, answer = telegram_call(token, "getMe", {}, transport)
        except APIError:
            print(f"bot_slot={slot:02d} identity=unavailable")
            continue
        bot = answer.get("result") or {}
        bot_id = bot.get("id")
        username = str(bot.get("username") or "").casefold()
        if (status != 200 or answer.get("ok") is not True or
            not bot.get("is_bot") or not isinstance(bot_id, int) or
            not username or username in BLOCKED_IDENTITIES or bot_id in ids):
            print(f"bot_slot={slot:02d} identity=invalid_or_duplicate")
            continue
        ids.add(bot_id)
        accepted[slot] = token
    return accepted


def prepare_jobs(db: D1) -> None:
    # This operation inserts only rows for posts AFTER the migration watermark.
    # Without the watermark, previously delivered posts would be reacted to again.
    bots = " UNION ALL ".join("SELECT " + str(i) + " AS slot" for i in EXTRA_SLOTS)
    query = f"""
      INSERT OR IGNORE INTO channel_reaction_extra_jobs(post_seq,bot_slot,emoji)
      SELECT p.seq,b.slot,
        CASE WHEN (p.seq % 2) = (b.slot % 2) THEN '❤️' ELSE '👍' END
      FROM channel_reaction_posts AS p
      CROSS JOIN ({bots}) AS b
      WHERE p.seq > (
        SELECT start_after_seq FROM channel_reaction_extra_config WHERE id=1
      )
      AND NOT EXISTS (
        SELECT 1 FROM channel_reaction_extra_jobs AS j
        WHERE j.post_seq=p.seq AND j.bot_slot=b.slot
      )
      ORDER BY p.seq,b.slot
      LIMIT {MAX_NEW_JOBS_PER_RUN}
    """
    db.query(query)


def due_jobs(db: D1, slots: tuple[int, ...]) -> list[dict[str, Any]]:
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
      ORDER BY j.post_seq,j.bot_slot LIMIT {MAX_JOBS_PER_RUN}
    """
    return db.query(query, slots).get("results") or []


def retry_delay(attempts: int, retry_after: int = 0) -> int:
    return max(45, min(3600, max(retry_after, 45 * (2 ** min(attempts, 6)))))


def next_retry(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


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
    # Permanent rejection means a bot is missing from a channel, an emoji is
    # disabled or the post was deleted. Avoid repetitive Telegram API traffic.
    permanent = (not network_error and code in (400, 403, 404) and
                 not any(x in error for x in ("retry", "temporar", "flood")))
    if permanent:
        return ("""
          UPDATE channel_reaction_extra_jobs
          SET state='blocked',last_error=?,attempts=attempts+1,
              updated_at=CURRENT_TIMESTAMP
          WHERE post_seq=? AND bot_slot=?
        """, (f"telegram_http_{code}", seq, slot))
    param = response.get("parameters") or {}
    delay = retry_delay(int(row["attempts"]), int(param.get("retry_after") or 0))
    return ("""
      UPDATE channel_reaction_extra_jobs
      SET state='retry',next_try_at=?,last_error=?,attempts=attempts+1,
          updated_at=CURRENT_TIMESTAMP
      WHERE post_seq=? AND bot_slot=?
    """, (next_retry(delay), f"telegram_http_{code or 0}", seq, slot))


def run(env: dict[str, str], transport=_request_json) -> int:
    candidates = configured_tokens(env)
    if not candidates:
        print("No extra reaction tokens configured: safe no-op.")
        return 0
    bots = verify_bots(candidates, transport)
    if not bots:
        print("No additional bot identities verified: safe no-op.")
        return 0
    db = D1(env.get("CLOUDFLARE_API_TOKEN", "") or env.get("CF_API_TOKEN", ""),
            env.get("CLOUDFLARE_ACCOUNT_ID", ""), transport)
    prepare_jobs(db)
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
