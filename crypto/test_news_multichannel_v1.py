"""Offline regression tests for crypto-only, per-channel RSS distribution."""
import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from crypto import news_multichannel_v1 as net
from crypto import news_digest_v1 as digest

NOW = datetime(2026, 11, 17, 23, 35, tzinfo=timezone.utc)


def candidate(title="Nigeria approves new stablecoin payment framework for banks",
              source="CoinDesk", path="news/stablecoin-nigeria"):
    main = {
        "title":title, "source":source,
        "url":"https://www.coindesk.com/"+path,
        "published_at": NOW.isoformat(), "french": False,
    }
    main.update(digest.signature(main))
    return {"main":main, "others":[], "score":80}


def targets():
    rows = []
    for n in range(10):
        private = n >= 4
        rows.append({
            "key":("%064x" % (n+1)), "bot_id":987654,
            "chat_id": "-100123456" + str(n) if private else "@CryptoTest" + str(n),
            "expected_id":"-100123456"+str(n),
            "is_private":private,
            "profile":("fr","breaking","balanced")[n % 3],
        })
    return rows


class DistributionTests(unittest.TestCase):
    def test_private_destinations_only_numeric_and_public_only_handles(self):
        self.assertEqual(len(net.validate_targets(targets())),10)
        bad=targets()
        bad[4]["chat_id"]="@InsecurePrivateAlias"
        with self.assertRaises(RuntimeError):
            net.validate_targets(bad)
        bad=targets()
        bad[0]["chat_id"]="-1001234560"
        with self.assertRaises(RuntimeError):
            net.validate_targets(bad)

    def test_no_unverified_extra_channels(self):
        bad=targets()
        bad.append(dict(bad[0]))
        with self.assertRaises(RuntimeError):
            net.validate_targets(bad)

    def test_per_channel_same_news_is_blocked_but_other_channel_not(self):
        c=candidate()
        r=[{"key":targets()[0]["key"],"story":net.story_data(c),"status":"confirmed"}]
        self.assertTrue(net.skip_for_target(c, targets()[0]["key"],r))
        self.assertFalse(net.skip_for_target(c, targets()[1]["key"],r))

    def test_duplicate_between_rss_publishers_matches(self):
        en=candidate()
        fr=candidate("Nigeria approuve un nouveau cadre stablecoin pour les paiements bancaires",
                     "Journal du Coin","news/same-story-fr")
        rows=[{"key":targets()[0]["key"],"story":net.story_data(en)}]
        self.assertTrue(net.skip_for_target(fr, targets()[0]["key"],rows))

    def test_exclusive_assignment_stable_under_channel_rotation(self):
        c=candidate()
        one=net.exclusivity(c,targets(),[])
        two=net.exclusivity(c,list(reversed(targets())),[])
        self.assertEqual(one,two)

    def test_exclusive_article_remains_owned_by_same_channel_after_rss_mirror(self):
        orig=candidate()
        mirror=candidate("Nigeria approuve un nouveau cadre stablecoin pour les paiements bancaires",
                         "Journal du Coin","news/mirror")
        t=targets()
        old=[{"key":t[3]["key"],"story":net.story_data(orig),
              "exclusive":True,"owner":t[3]["key"]}]
        self.assertEqual(net.exclusivity(mirror,t,old),(True,t[3]["key"]))

    def test_previously_shared_story_cannot_become_exclusive(self):
        orig=candidate()
        mirror=candidate("Nigeria approuve un nouveau cadre stablecoin pour les paiements bancaires",
                         "Journal du Coin","news/mirror")
        old=[{"key":targets()[3]["key"],"story":net.story_data(orig),
              "exclusive":False,"owner":None}]
        self.assertEqual(net.exclusivity(mirror,targets(),old),(False,None))

    def test_exclusive_ratio_and_owner_valid(self):
        t=targets()
        count=0
        for i in range(100):
            c=candidate(path=f"news/new-crypto-story-{i}")
            e,owner=net.exclusivity(c,t,[])
            if e:
                count+=1
                self.assertIn(owner,{x["key"] for x in t})
            else:
                self.assertIsNone(owner)
        self.assertTrue(10 <= count <= 40)

    def test_legacy_channel_history_is_respected(self):
        c=candidate()
        fp=digest.hashes(c["main"]["url"])[0]
        legacy={"sent":{},"news_fingerprints":{fp:{"number":11}}}
        self.assertTrue(net.skip_for_target(c,targets()[0]["key"],[],
                                            -1001234560,legacy,-1001234560))
        self.assertFalse(net.skip_for_target(c,targets()[1]["key"],[],
                                             -1001234560,legacy,-1001234561))

    def test_article_keys_are_stable_and_not_secret_channel_ids(self):
        c=candidate()
        key=net.article_key(c)
        self.assertEqual(len(key),40)
        self.assertNotIn("123456",key)
        self.assertEqual(key,net.article_key(c))

    def test_slot_changes_every_half_hour(self):
        self.assertEqual(net.slot_for(NOW),"2026-11-17T23:30")
        self.assertEqual(net.slot_for(NOW.replace(minute=9)),"2026-11-17T23:00")

    def test_source_rotation_is_channel_specific(self):
        c=candidate()
        t=targets()
        a=net.ranking(c,t[0],"2026-11-17T23:00",set())
        b=net.ranking(c,t[1],"2026-11-17T23:00",set())
        self.assertNotEqual(a,b)
        self.assertLess(net.ranking(c,t[0],"2026-11-17T23:00",{"CoinDesk"}),a)

    def test_exclusive_lanes_boost_only_owned_stories(self):
        t=targets()[0]
        slot=next("2026-11-18T%02d:00" % h for h in range(24)
                  if net.wants_exclusive_slot(t,"2026-11-18T%02d:00" % h))
        c=candidate()
        shared=net.ranking(c,t,slot,set(),(False,None))
        owned=net.ranking(c,t,slot,set(),(True,t["key"]))
        other=net.ranking(c,t,slot,set(),(True,targets()[1]["key"]))
        self.assertEqual(owned-shared,160)
        self.assertEqual(other,shared)
        no_lanes=next("2026-11-18T%02d:00" % h for h in range(24)
                 if not net.wants_exclusive_slot(t,"2026-11-18T%02d:00" % h))
        self.assertEqual(net.ranking(c,t,no_lanes,set(),(True,t["key"])),
                         net.ranking(c,t,no_lanes,set(),(False,None)))

    def test_service_credentials_required(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaises(RuntimeError):
                net.Supabase()

    def test_telegram_bot_identity_is_exact(self):
        with patch.object(net.Telegram,"get",return_value={"username":"other_bot","id":987654,"is_bot":True}):
            client=net.Telegram(token="fake-token")
            with self.assertRaises(RuntimeError):
                client.assert_correct_bot(targets())


if __name__=="__main__":
    unittest.main()
