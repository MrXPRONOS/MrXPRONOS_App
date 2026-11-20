"""Stages 1-2 offline checks: guard, matching and safe SQL."""
import unittest
from types import SimpleNamespace
from scripts.catalog_stage12 import configured_targets, classify, describe_result, sql_queries

def video(message_id, caption, filename):
    doc=SimpleNamespace(id=1000+message_id,attributes=[])
    return SimpleNamespace(id=message_id,document=doc,video=object(),noforwards=False,
                           raw_text=caption,
                           file=SimpleNamespace(name=filename,size=2400000))

class Stage12CatalogTests(unittest.TestCase):
    def targets(self):
        return {
            "SERIES_PRIVATE_CHANNEL":"-1004455497484",
            "SERIES_PUBLIC_CHANNEL":"@seriesvf_cinex",
            "ACTION_PRIVATE_CHANNEL":"-1004462439590",
            "ACTION_PUBLIC_CHANNEL":"@filmsaction2026vf",
            "CINEX_DOWNLOADS_ENABLED":"true",
        }

    def test_owner_recreated_ids_are_used_without_hardcoded_fallback(self):
        targets=configured_targets(self.targets())
        self.assertEqual(targets[0]["private_chat_id"],"-1004455497484")
        self.assertEqual(targets[1]["private_chat_id"],"-1004462439590")

    def test_duplicate_private_channels_rejected(self):
        values=self.targets()
        values["ACTION_PRIVATE_CHANNEL"]=values["SERIES_PRIVATE_CHANNEL"]
        with self.assertRaises(ValueError):
            configured_targets(values)

    def test_missing_rights_do_not_become_approved(self):
        values=self.targets()
        values["CINEX_DOWNLOADS_ENABLED"]="false"
        self.assertFalse(configured_targets(values)[0]["rights_attested"])
        self.assertFalse(configured_targets(values)[1]["rights_attested"])

    def test_series_episode_number_and_video_reference(self):
        row=classify(video(37,"GIGN S01E02 VF","GIGN_S01E02.mp4"),"series")
        self.assertIsNotNone(row)
        self.assertEqual((row["season_number"],row["episode_number"]),(1,2))
        self.assertEqual(row["source_message_id"],37)

    def test_explicit_season_total_prevents_early_completion(self):
        row=classify(video(37,"GIGN S01E02/10 VF","GIGN_S01E02.mp4"),"series")
        self.assertEqual(row["declared_total"],10)
        row=classify(video(38,"GIGN S01E02 VF","GIGN_S01E02.mp4"),"series")
        self.assertIsNone(row["declared_total"])
        row=classify(video(39,"GIGN S01E10 Fin de saison","GIGN_S01E10.mp4"),"series")
        self.assertEqual(row["declared_total"],10)

    def test_series_without_explicit_episode_is_quarantined(self):
        self.assertIsNone(classify(video(39,"GIGN VF","GIGN.mp4"),"series"))

    def test_action_episode_is_not_assigned_as_film(self):
        self.assertIsNone(classify(video(40,"GIGN S01E02","GIGN_S01E02.mp4"),"action"))

    def test_protected_message_is_rejected(self):
        msg=video(33,"GIGN S01E01","GIGN_S01E01.mp4")
        msg.noforwards=True
        self.assertIsNone(classify(msg,"series"))

    def test_conflicting_titles_are_quarantined(self):
        self.assertIsNone(classify(video(41,"GIGN S01E01","Another_Show_S01E01.mp4"),"series"))

    def test_all_imports_pending_and_no_telegram_side_effect(self):
        target=configured_targets(self.targets())[0]
        item=classify(video(37,"GIGN S01E02","GIGN_S01E02.mp4"),"series")
        report={"scanned_at":"2026-11-20T00:00:00Z",
                "libraries":[describe_result(target,[item],1,0)]}
        queries=list(sql_queries(report))
        self.assertEqual(len(queries),3)
        sql=" ".join(x["sql"] for x in queries).lower()
        self.assertIn("cine_delivery_media",sql)
        self.assertNotIn("update cine_delivery_media set availability='approved'",sql)
        self.assertNotIn("sendmessage",sql)
        self.assertNotIn("copymessage",sql)
        self.assertNotIn("deletemessage",sql)

if __name__=="__main__":
    unittest.main()
