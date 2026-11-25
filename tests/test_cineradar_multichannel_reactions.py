"""Offline regression tests for admin-only, all-channel reaction migration."""
from __future__ import annotations

import sqlite3
import unittest

from scripts import cineradar_reaction_core as core
from scripts.cineradar_reaction_multichannel import (
    Runtime, is_torrent9, normalized, reactions_allowed,
    install_schema,
)
from scripts.cineradar_reaction_store import LocalReactionDB


def fixture():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE channel_reaction_posts(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL, message_id INTEGER NOT NULL,
            media_group_id TEXT, UNIQUE(chat_id,message_id));
        CREATE UNIQUE INDEX idx_reaction_album ON
            channel_reaction_posts(chat_id,media_group_id)
            WHERE media_group_id IS NOT NULL;
        CREATE TABLE channel_reaction_jobs(
            post_seq INTEGER, bot_role TEXT, emoji TEXT, state TEXT,
            next_try_at TEXT, last_error TEXT, PRIMARY KEY(post_seq,bot_role));
        CREATE TABLE channel_reaction_extra_jobs(
            post_seq INTEGER, bot_slot INTEGER, emoji TEXT, state TEXT,
            next_try_at TEXT, last_error TEXT, PRIMARY KEY(post_seq,bot_slot));
        CREATE TABLE channel_reaction_extra_bot_activation(
            bot_slot INTEGER PRIMARY KEY, start_after_seq INTEGER);
        CREATE TABLE channel_reaction_terminal_posts(
            post_seq INTEGER PRIMARY KEY, reason TEXT);
    """)
    return LocalReactionDB(conn)


class CoverageTests(unittest.TestCase):
    def test_torrent9_aliases_excluded(self):
        self.assertTrue(is_torrent9({"title":"Torrent 9 films","username":"other"}))
        self.assertTrue(is_torrent9({"username":"ToRrEnT_9","title":"Autre"}))
        self.assertTrue(is_torrent9({"title":"TORRENT-9"}))
        self.assertFalse(is_torrent9({"title":"Films CinéRadar","username":"seriesvf_cinex"}))

    def test_reaction_policies_respected(self):
        self.assertFalse(reactions_allowed({"available_reactions":[]}))
        self.assertFalse(reactions_allowed({"available_reactions":[{"type":"emoji","emoji":"👍"}]}))
        self.assertTrue(reactions_allowed({"available_reactions":[
            {"type":"emoji","emoji":"👍"},{"type":"emoji","emoji":"❤️"}]}))

    def test_all_historical_channels_not_only_three(self):
        db = fixture()
        try:
            db.query("INSERT INTO channel_reaction_posts(chat_id,message_id) VALUES(?,?)",
                     ("-1001111111111",1))
            db.query("INSERT INTO channel_reaction_posts(chat_id,message_id) VALUES(?,?)",
                     ("-1002222222222",2))
            def transport(url,payload,headers):
                if url.endswith("/getChat") and str(payload["chat_id"]).startswith("@"):
                    username = str(payload["chat_id"])[1:]
                    chat_ids = {"CineXFilms_vf":-1003333333333,
                                "seriesvf_cinex":-1004444444444,
                                "CineXAnimeFR":-1005555555555}
                    return 200, {"ok":True,"result":{"id":chat_ids[username],
                        "username":username,"title":username,"type":"channel"}}
                raise AssertionError("Unexpected API")
            runner = Runtime(db,{"CINE_RADAR_BOT_TOKEN":"token"},transport)
            self.assertEqual(len(runner.known_channels()),5)
        finally:
            db.connection.close()

    def test_unverified_channel_is_not_permanently_excluded(self):
        db = fixture()
        try:
            def transport(url,payload,headers):
                return 400, {"ok":False}
            runner = Runtime(db,{},transport)
            runner.tokens={"extra_3":"test"}
            runner.bot_ids={"test":333}
            self.assertEqual(runner.classify("-1001111111111"),(None,False))
            runner.pause_ineligible({"-1001111111111":(None,False)})
            self.assertEqual(db.query("SELECT COUNT(*) AS n FROM reaction_channel_policy")["results"][0]["n"],0)
        finally:
            db.connection.close()

    def test_excluded_channel_is_never_sent_to_telegram(self):
        db = fixture()
        calls=[]
        try:
            def transport(url,payload,headers):
                method=url.rsplit("/",1)[-1]
                calls.append(method)
                if method=="getChat":
                    return 200, {"ok":True,"result":{
                        "id":-1001111111111,"type":"channel",
                        "title":"Torrent9","available_reactions":None}}
                raise AssertionError("SetMessageReaction must not be called")
            runner=Runtime(db,{},transport)
            runner.tokens={"extra_3":"test"}
            runner.bot_ids={"test":333}
            self.assertEqual(runner.classify("-1001111111111"),(False,True))
            status,_=runner.guarded_transport(
                "https://api.telegram.org/bottest/setMessageReaction",
                {"chat_id":"-1001111111111","message_id":5}, {})
            self.assertEqual(status,400)
            self.assertEqual(calls,["getChat"])
        finally:
            db.connection.close()

    def test_multiple_dedicated_observers_dedupe_and_persist_cursors(self):
        db=fixture()
        count={}
        try:
            def transport(url,payload,headers):
                token=url.split("/bot",1)[1].rsplit("/",1)[0]
                method=url.rsplit("/",1)[-1]
                count[method]=count.get(method,0)+1
                if method=="getMe":
                    return 200, {"ok":True,"result":{"is_bot":True,"id":42 if token=="slot3" else 43,
                                      "username":"reaction_three" if token=="slot3" else "reaction_four"}}
                if method=="getWebhookInfo":
                    return 200, {"ok":True,"result":{"url":""}}
                if method=="getChat":
                    return 200, {"ok":True,"result":{"id":-1001111111111,
                        "type":"channel","title":"Other channel"}}
                if method=="getChatMember":
                    return 200, {"ok":True,"result":{"status":"administrator"}}
                if method=="getUpdates":
                    if payload.get("offset"):
                        return 200, {"ok":True,"result":[]}
                    return 200, {"ok":True,"result":[
                        {"update_id":71,"channel_post":{"chat":{"type":"channel",
                             "id":-1001111111111},"message_id":99}}]}
                raise AssertionError(method)
            env={"TELEGRAM_REACTION_BOT_03_TOKEN":"slot3",
                 "TELEGRAM_REACTION_BOT_04_TOKEN":"slot4"}
            runner=Runtime(db,env,transport)
            runner.verify_bots()
            known={"-1001111111111"}
            self.assertEqual(runner.observe(known),1)
            self.assertEqual(db.query("SELECT COUNT(*) AS n FROM channel_reaction_posts")["results"][0]["n"],1)
            self.assertEqual(db.query("SELECT COUNT(*) AS n FROM reaction_observer_offsets")["results"][0]["n"],2)
            self.assertEqual(runner.observe(known),0)
            self.assertEqual(db.query("SELECT COUNT(*) AS n FROM channel_reaction_posts")["results"][0]["n"],1)
            self.assertEqual(count["getUpdates"],4)
        finally:
            db.connection.close()

    def test_general_purpose_bot_not_polled(self):
        db=fixture()
        try:
            runner=Runtime(db,{},lambda *args:self.fail("Network call"))
            runner.extras={16:"generic-news-token",8001:"anime-service-token"}
            self.assertEqual(list(runner.observers()),[])
        finally:
            db.connection.close()

    def test_all_known_named_bot_secrets_registered_without_duplicates(self):
        tokens=core.configured_tokens({
            "TELEGRAM_REACTION_BOT_03_TOKEN":"named-shared",
            "ANIME_BOT_TOKEN":"named-shared",
            "SERIES_BOT_TOKEN":"series-token",
            "ACTION_BOT_TOKEN":"action-token",
            "CINEX_PUBLISH_BOT_TOKEN":"cine-publish",
        })
        self.assertEqual(tokens[3],"named-shared")
        self.assertNotIn(8001,tokens)
        self.assertEqual(tokens[8002],"series-token")
        self.assertEqual(tokens[8003],"action-token")
        self.assertEqual(tokens[8006],"cine-publish")


if __name__=="__main__":
    unittest.main()
