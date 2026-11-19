"""Offline tests for profile synchronization of Ciné X rescue and trending channels."""
from __future__ import annotations

import asyncio
import io
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace as NS

from PIL import Image

from film_relay.channel_profiles import (
    about_text, trend_description, digest, sync_description,
    sync_photo_bytes, sync_rescue_profile, sync_trend_profile,
)


class ProfileTextTests(unittest.TestCase):
    def test_synopsis_is_used_without_hallucinating(self):
        summary=trend_description({"title":"Un film", "summary":"Une enquête dans une ville."})
        self.assertEqual(summary, "Une enquête dans une ville.")

    def test_synopsis_falls_back_to_source_cover_description(self):
        summary=trend_description({"title":"Un film","summary":""}, {
            "poster_caption":"🎬 Un film\nAnnée : 2026\nSynopsis: Deux amis se retrouvent."
        })
        self.assertEqual(summary,"Deux amis se retrouvent.")

    def test_long_description_is_bounded(self):
        self.assertLessEqual(len(about_text("A"*400)),255)
        self.assertEqual(digest("bonjour"),digest("bonjour"))

    def test_rescue_description_keeps_newlines_and_emoji(self):
        self.assertEqual("Bienvenue 🎬\nFilms et séries !","Bienvenue 🎬\nFilms et séries !")


class ProfileTelegramTests(unittest.IsolatedAsyncioTestCase):
    def fake_telethon(self):
        functions=NS(channels=NS(
            GetFullChannelRequest=lambda **kw:("get",kw),
            EditAboutRequest=lambda **kw:("edit_about",kw),
            EditPhotoRequest=lambda **kw:("edit_photo",kw),
        ))
        fake=types.ModuleType("telethon")
        fake.functions=functions
        fake.types=NS(InputChatUploadedPhoto=lambda **kw:("uploaded",kw))
        return fake

    async def test_exact_description_is_not_changed_when_matching(self):
        client=AsyncMock()
        client.side_effect=lambda req: NS(full_chat=NS(about="A\nB"))
        record={}
        with patch.dict(sys.modules,{"telethon":self.fake_telethon()}):
            changed=await sync_description(client,"rescue","A\nB",record,
                                           preserve_format=True,pause=0)
        self.assertFalse(changed)
        self.assertEqual(record["description_digest"],digest("A\nB"))
        self.assertEqual(client.await_count,1)

    async def test_description_is_verified_after_edit(self):
        client=AsyncMock()
        current={"about":"Old"}
        async def reply(req):
            if req[0]=="get":return NS(full_chat=NS(about=current["about"]))
            if req[0]=="edit_about":
                current["about"]=req[1]["about"]
                return True
        client.side_effect=reply
        record={}
        with patch.dict(sys.modules,{"telethon":self.fake_telethon()}):
            changed=await sync_description(client,"rescue","Nouveau\n🎬",record,
                                           preserve_format=True,pause=0)
        self.assertTrue(changed)
        self.assertEqual(current["about"],"Nouveau\n🎬")
        self.assertEqual(record["description_digest"],digest("Nouveau\n🎬"))

    async def test_avatar_upload_is_idempotent(self):
        image=Image.new("RGB",(640,400),"white")
        out=io.BytesIO()
        image.save(out,format="JPEG")
        record={}
        target=NS(photo=None)
        client=AsyncMock()
        client.upload_file.return_value="image-binary"
        client.get_entity.return_value=NS(photo=NS(photo_id=44))
        client.return_value=True
        with patch.dict(sys.modules,{"telethon":self.fake_telethon()}):
            changed=await sync_photo_bytes(client,target,out.getvalue(),123,record,pause=0)
        self.assertTrue(changed)
        self.assertEqual(record["profile_photo_source_id"],123)
        self.assertEqual(client.upload_file.await_count,1)
        with patch.dict(sys.modules,{"telethon":self.fake_telethon()}):
            unchanged=await sync_photo_bytes(client,NS(photo=NS(photo_id=44)),
                                             out.getvalue(),123,record,pause=0)
        self.assertFalse(unchanged)
        self.assertEqual(client.upload_file.await_count,1)

    async def test_rescue_reads_actual_channel_about_and_avatar(self):
        client=AsyncMock()
        public=NS(photo=NS(photo_id=789))
        rescue=NS(photo=None)
        record={}
        image=Image.new("RGB",(400,400),"white")
        out=io.BytesIO();image.save(out,format="JPEG")
        client.download_profile_photo.return_value=out.getvalue()
        async def mock_about(channel):
            return "Texte original\nLigne 2"
        async def mock_description(*a,**kw):
            self.assertEqual(kw["preserve_format"],True)
            self.assertEqual(a[2],"Texte original\nLigne 2")
            return True
        async def mock_photo(*args,**kwargs):
            self.assertEqual(args[3],789)
            return True
        with patch("film_relay.channel_profiles.get_channel_about",mock_about), \
             patch("film_relay.channel_profiles.sync_description",mock_description), \
             patch("film_relay.channel_profiles.sync_photo_bytes",mock_photo):
            changed=await sync_rescue_profile(client,public,rescue,record,pause=0)
        self.assertEqual(changed,(True,True))

    async def test_trend_uses_verified_telegram_poster(self):
        source_photo=NS(id=404)
        poster=NS(photo=source_photo,media=source_photo,raw_text="Film\nSynopsis: Départ.")
        client=AsyncMock()
        client.download_media.return_value=b"valid-image"
        with patch("film_relay.channel_profiles.sync_description",AsyncMock(return_value=True)) as sd, \
             patch("film_relay.channel_profiles.sync_photo_bytes",AsyncMock(return_value=True)) as sp:
            result=await sync_trend_profile(client,NS(),{"title":"Film","summary":"Synopsis officiel"},poster,{},pause=0)
        self.assertEqual(result,(True,True))
        self.assertEqual(sd.await_args.args[2],"Synopsis officiel")
        self.assertEqual(sp.await_args.args[3],404)


if __name__=="__main__":
    unittest.main()
