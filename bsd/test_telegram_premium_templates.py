"""Editorial/layout regressions for all five Telegram publication categories."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"scripts"))
from telegram_premium_templates import bonus,guide,partners,daily_promo,coupon,live,premium_sections,plain_text_sections
from telegram_rich import rich_markup,rich_buttons,legacy_caption

class PremiumTelegramTests(unittest.TestCase):
    def test_plain_text_formatting(self):
        rendered=plain_text_sections("**Gras** *italique* __souligné__ ~~barré~~")
        for expected in ("<b>Gras</b>", "<i>italique</i>", "<u>souligné</u>", "<s>barré</s>"):
            self.assertIn(expected,rendered)

    def test_quote_and_html_escaping(self):
        rendered=plain_text_sections("Bonjour <script>\n\n> **Citation** & exemple")
        self.assertIn("&lt;script&gt;",rendered)
        self.assertIn("<blockquote><b>Citation</b> &amp; exemple</blockquote>",rendered)
        self.assertNotIn("<script>",rendered)

    def test_promo_dynamic_fields_are_escaped(self):
        rendered=daily_promo("<script>","<img>","offre")
        self.assertIn("&lt;script&gt;",rendered)
        self.assertIn("&lt;img&gt;",rendered)
        self.assertNotIn("<script>",rendered)

    def test_bonus_has_distinct_paragraphs_heading_quote_emphasis(self):
        message=bonus("1Win","Bonus de bienvenue","100 % jusqu'à 500 $",
                      "Offre soumise à disponibilité.")
        for tag in ("<h3>","<p>","<blockquote>","<b>","<i>","<code>XPVIP</code>"):
            self.assertIn(tag,message)
        self.assertIn("18+",message)
        self.assertGreaterEqual(message.count("<p>"),5)

    def test_guide_has_steps_and_no_wall_of_text(self):
        message=guide("MelBet")
        self.assertIn("🧭 Les étapes",message)
        self.assertIn("1.",message)
        self.assertIn("<blockquote>",message)
        self.assertIn("<h3>",message)

    def test_partner_and_daily_promo_are_separate_templates(self):
        p=partners()
        d=daily_promo("✨ ROYAL MONDAY","Lundi : offre partenaire",
                      "100 % jusqu'à 100 USD")
        self.assertIn("PARTENAIRES",p)
        self.assertIn("<h3>",d)
        self.assertNotEqual(p,d)
        self.assertIn("<blockquote>",d)

    def test_coupon_original_market_prices_stay_unchanged(self):
        raw="<b>🔥 Coupon du jour · MR XPRONOS</b>\n<i>Avant-match</i>\n\n<blockquote>🎯 Under 2,5\n📊 Cote : <b>2,10</b></blockquote>\n\n<i>18+</i>"
        output=coupon(raw)
        self.assertIn("<h3>🔥 Coupon du jour · MR XPRONOS</h3>",output)
        self.assertIn("<blockquote>🎯 Under 2,5",output)
        self.assertIn("<b>2,10</b>",output)
        self.assertIn("<p><i>18+</i></p>",output)

    def test_rich_transport_does_not_wrap_existing_sections(self):
        raw=bonus("1Win","Bienvenue","100%","Conditions")
        rich=rich_markup(raw,{"inline_keyboard":[]})
        self.assertIn("<h3>",rich)
        self.assertNotIn("<p><h3>",rich)
        self.assertEqual(rich.count("<h3>"),1)

    def test_button_rows_remain_native_and_centered(self):
        keyboard={"inline_keyboard":[[{"text":"ACCÉDER À L'OFFRE SUR MELBET",
                        "url":"https://example.com","style":"success"}]]}
        markup=rich_buttons(keyboard)
        self.assertEqual(markup.count("<tg-button "),1)
        self.assertIn('align="center"',markup)
        self.assertIn('style="success"',markup)

    def test_legacy_fallback_strips_rich_only_blocks(self):
        html=bonus("1Win","Bienvenue","100%","Conditions")
        legacy=legacy_caption(html)
        self.assertNotIn("<h3>",legacy)
        self.assertNotIn("<p>",legacy)
        self.assertNotIn("<br/>",legacy)
        self.assertIn("<blockquote>",legacy)
        self.assertIn("<b>",legacy)
        self.assertIn("XPVIP",legacy)

    def test_html_escaping_for_dynamic_labels(self):
        output=bonus("<unsafe>","Bonus","100%","<script>")
        self.assertIn("&lt;unsafe&gt;",output.lower())
        self.assertNotIn("<script>",output)

if __name__=="__main__":
    unittest.main()
