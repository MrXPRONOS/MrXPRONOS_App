"""No-network fail-closed guards for one-shot Bluesky-only recovered validation."""
import tempfile
import unittest
from pathlib import Path
from scripts.bluesky_20261114_recovery_guard import guard, assert_manifest, REF, DAY
import json


class Ledger:
    def __init__(self,rows,inner=None):
        self.rows=rows
        self.inner=inner or []
        self.calls=[]
    def query(self,sql,params):
        self.calls.append((sql,params))
        return {"results": self.inner if "kind=? AND ref_id=? LIMIT 2" in sql else self.rows}


def fixtures():
    kinds=["facebook","youtube","instagram","threads"]
    rows=[{"kind":"shorts_video_validation","delivery_status":"sent","telegram_message_id":7042}]
    rows.extend({"kind":"shorts_validation_social_"+k,"delivery_status":"sent",
                 "validation_details":json.dumps({"id":"provider-"+k})} for k in kinds)
    return rows


class RecoveryGuardTests(unittest.TestCase):
    def test_exact_source_and_provider_evidence_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=Path(tmp)/"video.mp4"
            v.write_bytes(b"a"*160_000)
            self.assertEqual(guard(Ledger(fixtures()),v,"mrxpronos.bsky.social"),"ready")
            rows=fixtures()[:-1]
            with self.assertRaisesRegex(RuntimeError,"lacks evidence"):
                guard(Ledger(rows),v,"mrxpronos.bsky.social")

    def test_prior_bluesky_hash_claim_blocks_even_on_different_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=Path(tmp)/"video.mp4"
            v.write_bytes(b"x"*160_000)
            with self.assertRaisesRegex(RuntimeError,"prior Bluesky reservation"):
                guard(Ledger(fixtures(),inner=[{"ref_date":"2026-11-13",
                                              "delivery_status":"uncertain"}]),v,
                      "mrxpronos.bsky.social")

    def test_sent_receipt_skips_and_ambiguous_receipt_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=Path(tmp)/"video.mp4"
            v.write_bytes(b"x"*160_000)
            sent=fixtures()+[{"kind":"shorts_validation_social_bluesky",
                              "delivery_status":"sent",
                              "validation_details":json.dumps({"id":"at://did:plc:example/app.bsky.feed.post/a"})}]
            self.assertEqual(guard(Ledger(sent),v,"mrxpronos.bsky.social"),"already_sent")
            sent[-1]["delivery_status"]="reserved"
            with self.assertRaisesRegex(RuntimeError,"reserved or uncertain"):
                guard(Ledger(sent),v,"mrxpronos.bsky.social")

    def test_manifest_must_prove_four_20261114_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            v=folder/"validation-2026-11-14-morning.mp4"
            v.write_bytes(b"x"*160_000)
            data={"published":[{"slot":"morning","target":DAY,
                  "summary":"4/4 VALIDÉS · AUCUN PERDU",
                  "video":str(v),"wins":4,"losses":0,"total":4}]}
            (folder/"manifest.json").write_text(json.dumps(data),encoding="utf-8")
            self.assertEqual(assert_manifest(folder),v)
            data["published"][0]["wins"]=3
            (folder/"manifest.json").write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"does not prove"):
                assert_manifest(folder)


if __name__=="__main__":
    unittest.main()
