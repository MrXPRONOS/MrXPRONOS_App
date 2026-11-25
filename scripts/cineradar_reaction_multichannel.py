#!/usr/bin/env python3
"""GitHub-only, multi-channel CineRadar reaction processing.

State is held exclusively in the existing encrypted GitHub reaction snapshot.
No Cloudflare, D1, Supabase, or personal Telegram session is accessed.
Only existing bots with verified channel administrator rights may react.
Torrent9 is always excluded by verified Telegram username/title.

Dedicated reaction bots without webhooks can observe new channel publications.
Bots using other services' webhooks remain reaction senders ONLY; their
webhooks are never deleted or overwritten.
"""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit

from scripts import cineradar_reaction_core as core
from scripts.cineradar_reaction_store import ReactionVault, load, save
from scripts.cineradar_reactions_github_only import PRIMARY_PUBLIC_CHANNELS

POLICY_TTL = 6 * 3600
MEMBERSHIP_TTL = 6 * 3600
PAUSE_DISABLED_SECONDS = 6 * 3600
MAX_OBSERVER_BOTS = 35
MAX_OBSERVED_PER_RUN = 100


def normalized(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(c for c in value if c.isascii() and c.isalnum())


def is_torrent9(chat):
    """Fail closed for the named excluded destination, including title variants."""
    return any("torrent9" in normalized(chat.get(key))
               for key in ("username", "title"))


def reactions_allowed(chat):
    available = chat.get("available_reactions")
    if available is None:
        return True
    if not isinstance(available, list) or not available:
        return False
    emojis = {x.get("emoji") for x in available if isinstance(x, dict)
              and x.get("type") == "emoji"}
    return {"❤️", "👍"}.issubset(emojis)


def install_schema(db):
    db.query("""CREATE TABLE IF NOT EXISTS reaction_observer_offsets (
        bot_id INTEGER PRIMARY KEY, next_offset INTEGER NOT NULL
    )""")
    db.query("""CREATE TABLE IF NOT EXISTS reaction_channel_policy (
        chat_id TEXT PRIMARY KEY, excluded INTEGER NOT NULL,
        usable INTEGER NOT NULL, checked_at INTEGER NOT NULL
    )""")
    db.query("""CREATE TABLE IF NOT EXISTS reaction_bot_channel_admin (
        bot_id INTEGER NOT NULL, chat_id TEXT NOT NULL, is_admin INTEGER NOT NULL,
        checked_at INTEGER NOT NULL, PRIMARY KEY(bot_id,chat_id)
    )""")


def get_bot_identity(token, transport):
    try:
        status, result = core.telegram_call(token, "getMe", {}, transport)
    except core.APIError:
        return None
    who = result.get("result") or {}
    if status != 200 or result.get("ok") is not True or not who.get("is_bot"):
        return None
    return who.get("id") if isinstance(who.get("id"), int) else None


class Runtime:
    def __init__(self, db, env, transport=core._request_json):
        self.db, self.env, self.transport = db, env, transport
        self.now = int(time.time())
        self.policy = {}
        self.members = {}
        self.tokens = {}
        self.bot_ids = {}
        self.extras = {}
        self.primaries = {}
        install_schema(db)

    def call(self, token, method, data):
        return core.telegram_call(token, method, data, self.transport)

    def verify_bots(self):
        # The known secret names + numbered slots + optional JSON bundle are
        # all discovered by configured_tokens, then independently verified.
        self.extras = core.verify_bots(core.configured_tokens(self.env), self.transport)
        self.primaries = core.verify_primary_bots(self.env, self.transport) if (
            str(self.env.get("REACTIONS_GITHUB_PRIMARY") or "").lower() == "true"
        ) else {}
        for name, token in [
            *[("extra_"+str(s),t) for s,t in self.extras.items()],
            *[("primary_"+role,t) for role,t in self.primaries.items()],
        ]:
            bot_id = get_bot_identity(token, self.transport)
            if bot_id is not None and bot_id not in self.bot_ids.values():
                self.tokens[name] = token
                self.bot_ids[token] = bot_id
        if not self.tokens:
            raise RuntimeError("No valid configured Telegram reaction bot")
        print(f"reaction_verified_distinct_bots={len(self.tokens)}")

    def known_channels(self):
        historical = {str(r["chat_id"]) for r in self.db.query(
            "SELECT DISTINCT chat_id FROM channel_reaction_posts"
        )["results"]}
        extras = str(self.env.get("CINERADAR_REACTION_CHANNEL_IDS") or "").strip()
        if extras:
            for raw in extras.split(","):
                value = raw.strip()
                if value and re.fullmatch(r"-100[0-9]{5,20}", value):
                    historical.add(value)
        # Verify the three official names; their numeric IDs are never guessed.
        lookup = (self.primaries.get("radar")
                  or self.env.get("CINE_RADAR_BOT_TOKEN")
                  or self.env.get("TELEGRAM_BOT_TOKEN")
                  or next(iter(self.tokens.values())))
        for username in PRIMARY_PUBLIC_CHANNELS:
            try:
                status, response = self.call(lookup, "getChat", {"chat_id":"@"+username})
                chat = response.get("result") or {}
                if (status == 200 and response.get("ok")
                    and chat.get("type") == "channel"
                    and str(chat.get("username") or "").casefold() == username.casefold()
                    and isinstance(chat.get("id"), int)):
                    historical.add(str(chat["id"]))
            except core.APIError:
                pass
        return historical

    def classify(self, chat_id, *, force=False):
        cid = str(chat_id)
        if cid in self.policy and not force:
            return self.policy[cid]
        if not force:
            rows = self.db.query(
                "SELECT excluded,usable,checked_at FROM reaction_channel_policy WHERE chat_id=?",
                (cid,),
            )["results"]
            if rows and self.now - int(rows[0]["checked_at"]) < POLICY_TTL:
                item = (not bool(rows[0]["excluded"]), bool(rows[0]["usable"]))
                self.policy[cid] = item
                return item
        for token in self.tokens.values():
            try:
                status, result = self.call(token, "getChat", {"chat_id": cid})
            except core.APIError:
                continue
            chat = result.get("result") or {}
            if (status != 200 or result.get("ok") is not True
                or chat.get("type") != "channel"
                or str(chat.get("id")) != cid):
                continue
            # A chat with no verifiable name must not be auto-enrolled.
            if not str(chat.get("username") or chat.get("title") or "").strip():
                return (False, False)
            item = (not is_torrent9(chat), reactions_allowed(chat))
            self.db.query(
                """INSERT INTO reaction_channel_policy(chat_id,excluded,usable,checked_at)
                VALUES(?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET
                excluded=excluded.excluded,usable=excluded.usable,checked_at=excluded.checked_at""",
                (cid, int(not item[0]), int(item[1]), self.now),
            )
            self.policy[cid] = item
            return item
        return (False, False)

    def is_admin(self, token, chat_id):
        cid = str(chat_id)
        bot_id = self.bot_ids.get(token)
        if bot_id is None:
            return False
        key = (bot_id, cid)
        if key in self.members:
            return self.members[key]
        rows = self.db.query(
            "SELECT is_admin,checked_at FROM reaction_bot_channel_admin WHERE bot_id=? AND chat_id=?",
            (bot_id,cid),
        )["results"]
        if rows and self.now - int(rows[0]["checked_at"]) < MEMBERSHIP_TTL:
            result = bool(rows[0]["is_admin"])
            self.members[key] = result
            return result
        try:
            status, result = self.call(token, "getChatMember",
                                       {"chat_id":cid,"user_id":bot_id})
        except core.APIError:
            return False
        if status != 200 or result.get("ok") is not True:
            return False
        admin = (result.get("result") or {}).get("status") in ("administrator","creator")
        self.db.query(
            """INSERT INTO reaction_bot_channel_admin(bot_id,chat_id,is_admin,checked_at)
            VALUES(?,?,?,?) ON CONFLICT(bot_id,chat_id) DO UPDATE SET
            is_admin=excluded.is_admin,checked_at=excluded.checked_at""",
            (bot_id,cid,int(admin),self.now),
        )
        self.members[key] = admin
        return admin

    def observers(self):
        # Never poll general-purpose bots: getUpdates would consume their
        # private messages or compete with existing webhook/chat handling.
        raw = [str(self.env.get("CINERADAR_REACTION_OBSERVER_TOKEN") or "").strip()]
        raw.extend(token for slot, token in sorted(self.extras.items())
                   if slot < 8000 and re.search(
                       r"^TELEGRAM_REACTION_BOT_[0-9]{2,4}_TOKEN$",
                       "TELEGRAM_REACTION_BOT_%02d_TOKEN" % slot,
                   ))
        used = set()
        for token in raw:
            if not token or token in used:
                continue
            used.add(token)
            if len(used) > MAX_OBSERVER_BOTS:
                break
            ident = self.bot_ids.get(token) or get_bot_identity(token,self.transport)
            if ident is None:
                continue
            try:
                status, response = self.call(token, "getWebhookInfo", {})
            except core.APIError:
                continue
            if status != 200 or response.get("ok") is not True:
                continue
            if (response.get("result") or {}).get("url"):
                # Never clear an active webhook belonging to another feature.
                continue
            yield token, ident

    def observe(self, eligible):
        observed, duplicates, pollers, errors = 0, 0, 0, 0
        for token, bot_id in self.observers():
            pollers += 1
            rows = self.db.query(
                "SELECT next_offset FROM reaction_observer_offsets WHERE bot_id=?",
                (bot_id,),
            )["results"]
            old = int(rows[0]["next_offset"]) if rows else None
            payload = {"limit":MAX_OBSERVED_PER_RUN,"timeout":0}
            if old is not None:
                payload["offset"] = old
            try:
                status, response = self.call(token,"getUpdates",payload)
            except core.APIError:
                errors += 1
                continue
            if status != 200 or response.get("ok") is not True:
                errors += 1
                continue
            cursor = old
            for update in response.get("result") or []:
                update_id = update.get("update_id")
                if type(update_id) is not int:
                    continue
                post = update.get("channel_post") or {}
                chat = post.get("chat") or {}
                cid = str(chat.get("id") or "")
                mid = post.get("message_id")
                if (chat.get("type") == "channel" and cid.startswith("-100")
                    and type(mid) is int and mid>0 and not post.get("is_automatic_forward")):
                    # New channels can enter the ledger only after we verify
                    # their metadata and this observer's administrator rights.
                    visible, usable = self.classify(cid, force=cid not in eligible)
                    if visible and self.is_admin(token,cid):
                        eligible.add(cid)
                        album = str(post.get("media_group_id")) if post.get("media_group_id") else None
                        before = self.db.connection.total_changes
                        self.db.query(
                            "INSERT OR IGNORE INTO channel_reaction_posts(chat_id,message_id,media_group_id) "
                            "VALUES(?,?,?)", (cid,mid,album)
                        )
                        if self.db.connection.total_changes > before:
                            observed += 1
                        else:
                            duplicates += 1
                cursor = max(cursor or 0,update_id+1)
            if cursor is not None and cursor != old:
                self.db.query(
                    """INSERT INTO reaction_observer_offsets(bot_id,next_offset) VALUES(?,?)
                    ON CONFLICT(bot_id) DO UPDATE SET next_offset=excluded.next_offset""",
                    (bot_id,cursor),
                )
        print(f"reaction_observers_pollable={pollers} observed_new={observed} "
              f"deduplicated={duplicates} poll_errors={errors}")
        return observed

    def pause_ineligible(self, policy):
        # Do not delete the imported historical ledger. Permanently suppress
        # Torrent9; pause temporarily disabled reaction destinations.
        excluded = [cid for cid, flags in policy.items() if not flags[0]]
        disabled = [cid for cid, flags in policy.items() if flags[0] and not flags[1]]
        for cid in excluded:
            self.db.query(
                """UPDATE channel_reaction_extra_jobs SET state='blocked',
                last_error='policy:torrent9_or_unverified' WHERE state IN ('pending','retry')
                AND post_seq IN (SELECT seq FROM channel_reaction_posts WHERE chat_id=?)""",
                (cid,),
            )
            self.db.query(
                """UPDATE channel_reaction_jobs SET next_try_at='9999-12-31 23:59:59',
                last_error='policy:torrent9_or_unverified'
                WHERE state IN ('pending','retry') AND next_try_at < '9999-12-31 23:59:59'
                AND post_seq IN (SELECT seq FROM channel_reaction_posts WHERE chat_id=?)""",
                (cid,),
            )
        for cid in disabled:
            self.db.query(
                """UPDATE channel_reaction_extra_jobs SET state='retry',
                next_try_at=datetime('now','+6 hours'),last_error='policy:reactions_disabled'
                WHERE state IN ('pending','retry') AND next_try_at<=CURRENT_TIMESTAMP
                AND post_seq IN (SELECT seq FROM channel_reaction_posts WHERE chat_id=?)""",
                (cid,),
            )
            self.db.query(
                """UPDATE channel_reaction_jobs SET state='retry',
                next_try_at=datetime('now','+6 hours'),last_error='policy:reactions_disabled'
                WHERE state IN ('pending','retry') AND next_try_at<=CURRENT_TIMESTAMP
                AND post_seq IN (SELECT seq FROM channel_reaction_posts WHERE chat_id=?)""",
                (cid,),
            )
        print(f"reaction_channel_policy_verified={len(policy)} "
              f"excluded_or_unverified={len(excluded)} reactions_disabled={len(disabled)}")

    def guarded_transport(self,url,data,headers):
        if url.endswith("/setMessageReaction"):
            # Parse locally only: bot secrets are never written to logs.
            try:
                token = url.split("/bot",1)[1].rsplit("/",1)[0]
            except (IndexError,ValueError):
                return 403, {"description":"Forbidden"}
            cid = str(data.get("chat_id") or "")
            allowed, usable = self.classify(cid)
            if not allowed or not usable:
                return 400, {"description":"Bad Request: reaction is not allowed"}
            if not self.is_admin(token,cid):
                return 400, {"description":"Bad Request: not enough rights"}
        return self.transport(url,data,headers)

    def dispatch(self,known):
        # Recheck any newly observed channel; Telegram's reaction settings may
        # differ across destinations and can change independently.
        policy = {cid:self.classify(cid) for cid in known}
        self.pause_ineligible(policy)
        # Existing bot activation watermarks prevent backfilling historic
        # messages when an additional bot is first configured.
        if self.primaries:
            core.prepare_primary_jobs(self.db)
        if self.extras:
            core.prepare_jobs(self.db, tuple(sorted(self.extras)))
        self.pause_ineligible(policy)
        delivered = 0
        if self.primaries:
            sent, _, _ = core.process_primary_jobs(
                self.db,self.primaries,self.guarded_transport,
            )
            delivered += sent
        if self.extras:
            rows = core.due_jobs(self.db,tuple(sorted(self.extras)))
            updates = []
            for row in rows:
                slot = int(row["bot_slot"])
                if str(row["chat_id"]) not in policy or not all(policy[str(row["chat_id"])]):
                    continue
                token = self.extras.get(slot)
                if token is None:
                    continue
                if not self.is_admin(token,str(row["chat_id"])):
                    # Preserve the job; Telegram privileges can change later.
                    updates.append(core.make_update(
                        row,400,{"description":"Bad Request: not enough rights"},
                    ))
                    continue
                try:
                    status, response = self.call(token, "setMessageReaction", {
                        "chat_id":row["chat_id"],"message_id":int(row["message_id"]),
                        "reaction":[{"type":"emoji","emoji":row["emoji"]}],"is_big":False,
                    })
                    failed = False
                except core.APIError:
                    status, response, failed = 0, {}, True
                updates.append(core.make_update(row,status,response,failed))
            if updates:
                self.db.batch(updates)
                delivered += sum("state='sent'" in sql for sql,_ in updates)
        print(f"reaction_delivery_confirmed={delivered} "
              f"configured_named_or_slot_bots={len(self.extras)} "
              f"verified_primary_bots={len(self.primaries)}")
        return delivered


def main(env=None, transport=core._request_json):
    env = dict(os.environ if env is None else env)
    vault = ReactionVault(branch="main")
    try:
        db,cursor,sha = load(vault)
    except Exception as exc:
        print("REACTIONS_STATE_NOT_READY:", type(exc).__name__,file=sys.stderr)
        return 2
    try:
        runner = Runtime(db,env,transport)
        runner.verify_bots()
        known = runner.known_channels()
        if not known:
            raise RuntimeError("No verified or historical Telegram channels")
        # The policy is cached in the same encrypted SQLite snapshot; no other
        # persistent database is read/written by this code.
        observed = runner.observe(known)
        if db.connection.total_changes:
            sha = save(vault,db,cursor,sha)
        before = db.connection.total_changes
        delivered = runner.dispatch(known)
        if db.connection.total_changes != before:
            save(vault,db,cursor,sha)
        print(f"reaction_multichannel_history_channels={len(known)} "
              f"observed={observed} confirmed={delivered} "
              f"torrent9_excluded=true cloudflare_calls=0")
        return 0
    except Exception as exc:
        print("REACTION_MULTICHANNEL_FAILED:",type(exc).__name__,str(exc)[:150]
              if isinstance(exc, RuntimeError) else "",file=sys.stderr)
        return 1
    finally:
        db.connection.close()


if __name__=="__main__":
    sys.exit(main())
