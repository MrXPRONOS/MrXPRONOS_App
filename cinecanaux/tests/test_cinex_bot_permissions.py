import importlib.util
import json
from pathlib import Path
from unittest import TestCase, mock
import sys

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location("permission_auditor",SCRIPTS/"audit_cinex_bot_permissions.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BotPermissionsTests(TestCase):
    def test_read_only_bot_permission_audit_flags_sensitive_rights(self):
        class Stub:
            def __init__(self,token):
                self.token=token
            def call(self,method,params):
                self.assertFalse = False  # No real Bot API calls.
                if method=="getMe":return {"id":987,"is_bot":True,"username":"ExampleBot"}
                if method=="getChatMember":
                    if params["chat_id"]=="@seriesvf_cinex":
                        return {"status":"administrator","can_post_messages":True,
                                "can_promote_members":True,"can_delete_messages":True}
                    return {"status":"administrator","can_post_messages":False}
                raise AssertionError("Unexpected Telegram API write")
        with mock.patch.object(mod,"BotAPI",Stub):
            x=mod.audit_permissions([("publisher","123:token"),("duplicate","123:token")],
                                    [("series_main","@seriesvf_cinex"),
                                     ("series_source_01","-1001234567890")])
        self.assertEqual(x["bot_count"],1)
        self.assertEqual(x["manual_review_count"],1)
        self.assertEqual(x["unreachable_count"],0)
        self.assertEqual(len(x["checks"]),2)
        self.assertEqual(x["checks"][0]["dangerous"],["can_delete_messages","can_promote_members"])
        self.assertTrue(x["checks"][0]["can_publish"])
        self.assertIsNone(x["checks"][1]["can_publish"])
        self.assertNotIn("123:token",json.dumps(x))

    def test_no_live_rights_can_be_modified_by_inspection(self):
        x=mod.inspect_permission(
            {"status":"administrator","can_post_messages":False,"can_promote_members":True},
            destination=True)
        self.assertFalse(x["can_publish"])
        self.assertEqual(x["dangerous"],["can_promote_members"])
        y=mod.inspect_permission({"status":"left"},destination=True)
        self.assertFalse(y["can_publish"])
        self.assertEqual(y["dangerous"],[])

    def test_unreachable_membership_is_reported_without_channel_identifiers(self):
        class Stub:
            def __init__(self,token):pass
            def call(self,method,params):
                if method=="getMe":return {"id":987,"is_bot":True}
                if method=="getChatMember":raise RuntimeError("getChatMember HTTP 400")
                raise AssertionError(method)
        with mock.patch.object(mod,"BotAPI",Stub):
            r=mod.audit_permissions([("radar","123:test")],[("franchise_source","-1001234567890")])
        self.assertEqual(r["unreachable_count"],1)
        self.assertEqual(r["checks"][0]["access"],"unavailable")
        self.assertNotIn("-1001234567890",json.dumps(r))

    def test_dedicated_publisher_requires_verified_username_and_all_destinations(self):
        targets=[
            ("series_main","a"),("series_rescue","b"),
            ("films_main","c"),("films_rescue","d"),
            ("franchise_source","e"),("series_source_01","f"),
        ]
        class Fake:
            def __init__(self,token): self.token=token
            def call(self,method,params):
                if method=="getMe":
                    return {"is_bot":True,"id":123,"username":"CineXPublishBot"}
                if method=="getChatMember":
                    return {"status":"administrator","can_post_messages":True}
                raise AssertionError(method)
        with mock.patch.object(mod,"BotAPI",Fake):
            r=mod.audit_permissions([("publisher","123:secret")],targets,publisher_username="@CineXPublishBot",expected_series_count=1)
        self.assertTrue(r["publisher"]["ready"])
        self.assertEqual(r["publisher"]["identity"],"verified")
        self.assertTrue(r["publisher"]["destinations_verified"])
        self.assertTrue(r["publisher"]["source_access_verified"])
        self.assertNotIn("123:secret",json.dumps(r))
        with mock.patch.object(mod,"BotAPI",Fake):
            bad=mod.audit_permissions([("publisher","123:secret")],targets,publisher_username="DifferentBot",expected_series_count=1)
        self.assertEqual(bad["publisher"]["identity"],"mismatch")
        self.assertFalse(bad["publisher"]["ready"])

    def test_missing_rights_or_target_fail_closed(self):
        targets=[
            ("series_main","a"),("series_rescue","b"),
            ("films_main","c"),("films_rescue","d"),
            ("franchise_source","e"),("series_source_01","f"),
        ]
        class Fake:
            def __init__(self,token):pass
            def call(self,method,params):
                if method=="getMe": return {"is_bot":True,"id":321,"username":"SafePublisher"}
                if method=="getChatMember":
                    if params["chat_id"]=="b":
                        return {"status":"administrator","can_post_messages":False}
                    return {"status":"administrator","can_post_messages":True}
                raise AssertionError(method)
        with mock.patch.object(mod,"BotAPI",Fake):
            missing_post=mod.audit_permissions([("publisher","321:x")],targets,publisher_username="SafePublisher",expected_series_count=1)
            missing_channel=mod.audit_permissions([("publisher","321:x")],targets[:-1],publisher_username="SafePublisher",expected_series_count=1)
        self.assertFalse(missing_post["publisher"]["ready"])
        self.assertFalse(missing_post["publisher"]["destinations_verified"])
        self.assertFalse(missing_channel["publisher"]["ready"])
        self.assertIn("series_source_01",missing_channel["publisher"]["missing_categories"])

    def test_reject_nonbot_identity_and_never_expose_secret(self):
        class Fake:
            def __init__(self,token):pass
            def call(self,method,params):
                if method=="getMe":return {"id":123,"is_bot":False,"username":"person"}
                raise AssertionError(method)
        with mock.patch.object(mod,"BotAPI",Fake):
            r=mod.audit_permissions([("publisher","123:sensitive")],[],publisher_username="CineXPublishBot")
        self.assertEqual(r["publisher"]["identity"],"unavailable")
        self.assertFalse(r["publisher"]["ready"])
        self.assertNotIn("123:sensitive",json.dumps(r))

    def test_readonly_methods_are_whitelisted_by_test(self):
        class Fake:
            def __init__(self,token):pass
            def call(self,method,params):
                if method=="getMe":return {"id":987,"is_bot":True,"username":"TestPublisher"}
                if method=="getChatMember":
                    return {"status":"administrator","can_post_messages":True}
                raise AssertionError("Unexpected mutating Telegram method: "+method)
        with mock.patch.object(mod,"BotAPI",Fake):
            mod.audit_permissions([("publisher","987:test")],[("series_main","a")],
                                  publisher_username="TestPublisher",expected_series_count=1)
