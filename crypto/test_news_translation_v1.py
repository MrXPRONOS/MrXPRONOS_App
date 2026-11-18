"""No-network safeguards for NVIDIA French translations and Telegram editorial format."""
import json
import unittest

from crypto import news_translation_v1 as tr
from crypto import news_media_v1 as media

ENGLISH = {
    "title": "Coinbase launches a new USDT crypto payment service in Ghana",
    "summary": "Coinbase says the new crypto payments service reaches 500 companies in Ghana.",
    "category": "PAIEMENTS & ADOPTION", "source": "CoinDesk",
}
FR = {
    "title_fr": "Coinbase lance un nouveau service de paiement crypto en USDT au Ghana",
    "summary_fr": "Coinbase indique que ce nouveau service de paiements crypto dessert 500 entreprises au Ghana.",
}

class FakeResponse:
    status_code = 200
    content = b"valid-translation"
    def __init__(self, payload=None, status=200):
        self.payload = payload if payload is not None else FR
        self.status_code = status
    def json(self):
        return {"choices":[{"message":{"content":self.payload if isinstance(self.payload,str) else json.dumps(self.payload,ensure_ascii=False)}}]}


class FrenchNewsTests(unittest.TestCase):
    def test_french_translation_and_per_run_cache(self):
        calls = []
        def fake_post(*args, **kwargs):
            calls.append(kwargs)
            self.assertEqual(kwargs["json"]["model"],tr.RIVA_MODEL)
            english_input = kwargs["json"]["messages"][-1]["content"]
            return FakeResponse(FR["title_fr"] if english_input==ENGLISH["title"]
                                else FR["summary_fr"])
        worker = tr.FrenchTranslator(api_key="fake-secret",post=fake_post)
        one = worker.translate(ENGLISH)
        two = worker.translate(ENGLISH)
        self.assertEqual(one,FR)
        self.assertEqual(two,FR)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]["json"]["messages"][0]["content"],"en-fr")
        self.assertNotIn("fake-secret",str(one))

    def test_only_french_already_is_not_sent_to_nvidia(self):
        a={"title":"Coinbase annonce un nouveau service de paiements crypto au Ghana",
           "summary":"Coinbase indique que ce service permet de payer en cryptomonnaies dans plusieurs entreprises au Ghana."}
        def should_not_call(*args,**kwargs):
            self.fail("French original incorrectly called external API")
        self.assertEqual(tr.FrenchTranslator(api_key="",post=should_not_call).translate(a),
                         {"title_fr":a["title"],"summary_fr":a["summary"]})

    def test_missing_key_never_posts_english(self):
        with self.assertRaisesRegex(tr.TranslationHold,"NVIDIA_API_KEY_missing"):
            tr.FrenchTranslator(api_key="").translate(ENGLISH)

    def test_english_output_refused(self):
        with self.assertRaises(tr.TranslationHold):
            tr.validate(ENGLISH["title"],ENGLISH["summary"],
                        ENGLISH["title"],ENGLISH["summary"])

    def test_source_numbers_must_survive_translation(self):
        with self.assertRaisesRegex(tr.TranslationHold,"summary_numbers_changed"):
            tr.validate(ENGLISH["title"],ENGLISH["summary"],
                        FR["title_fr"],FR["summary_fr"].replace("500","600"))

    def test_crypto_tickers_must_survive_translation(self):
        with self.assertRaisesRegex(tr.TranslationHold,"tickers_changed"):
            tr.validate(ENGLISH["title"],ENGLISH["summary"],
                        FR["title_fr"].replace("USDT","dollars"),FR["summary_fr"])

    def test_brand_names_must_survive_translation(self):
        with self.assertRaisesRegex(tr.TranslationHold,"entity_changed"):
            tr.validate(ENGLISH["title"],ENGLISH["summary"],
                        FR["title_fr"].replace("Coinbase","La société"),FR["summary_fr"])

    def test_french_caption_begins_with_actual_headline(self):
        article={"main":dict(ENGLISH),"others":[]}
        legend=media.caption(article,translated=FR,require_french=True)
        self.assertTrue(legend.startswith("<b>"+FR["title_fr"]+"</b>"))
        self.assertIn("<blockquote>"+FR["summary_fr"]+"</blockquote>",legend)
        self.assertLess(legend.index("🏷️ <i>Catégorie :"),
                        legend.index("🗞️ <i>Source : CoinDesk</i>"))
        self.assertTrue(legend.endswith("🗞️ <i>Source : CoinDesk</i>"))
        self.assertNotIn("ACTU CRYPTO</b>",legend)
        self.assertNotIn("🕒",legend)
        self.assertNotIn("https://",legend)
        self.assertNotIn(ENGLISH["title"],legend)
        self.assertLessEqual(len(legend),1024)

    def test_require_french_blocks_english_fallback(self):
        with self.assertRaises(ValueError):
            media.caption({"main":ENGLISH},require_french=True)

    def test_bad_model_json_is_held(self):
        class Bad(FakeResponse):
            def json(self):
                return {"choices":[{"message":{"content":"I cannot answer"}}]}
        def bad_post(*args,**kwargs):
            return Bad()
        with self.assertRaises(tr.TranslationHold):
            tr.FrenchTranslator(api_key="mock-key",post=bad_post).translate(ENGLISH)

    def test_unavailable_model_falls_back_to_documented_backup(self):
        seen=[]
        def fake_post(*args,**kwargs):
            seen.append(kwargs["json"]["model"])
            return FakeResponse(status=503) if len(seen)==1 else FakeResponse()
        self.assertEqual(
            tr.FrenchTranslator(api_key="mock-key",post=fake_post).translate(ENGLISH),
            FR)
        self.assertEqual(seen,[tr.RIVA_MODEL,tr.MODELS[0]])


if __name__=="__main__":
    unittest.main()
