import unittest
from types import SimpleNamespace
from relay import clean_text, clean_message

class CleanupTests(unittest.TestCase):
    def test_links_and_mentions(self):
        self.assertEqual(clean_text("Cours Python\nhttps://t.me/test\n@autre_canal\nwww.example.com"),"Cours Python")
    def test_bare_links(self):
        self.assertEqual(clean_text("Supports PDF\nexample.com/cours\nt.me/+abcdef\ntg://resolve?domain=foo"),"Supports PDF")
    def test_markdown(self):
        self.assertEqual(clean_text("Voir [le cours](https://example.com)"),"Voir le cours")
    def test_keep_course_content(self):
        self.assertEqual(clean_text("Formation Finance\nAuteur : Jean Dupont\nModule 1.mkv"),"Formation Finance\nAuteur : Jean Dupont\nModule 1.mkv")
    def test_utf16_entity(self):
        entity=type("MessageEntityUrl",(),{})()
        entity.offset=3; entity.length=12
        m=SimpleNamespace(raw_text="🎓 x.example.xx",entities=[entity])
        self.assertEqual(clean_message(m),"🎓")
    def test_hidden_link_label(self):
        entity=type("MessageEntityTextUrl",(),{})()
        entity.offset=0; entity.length=5; entity.url="https://example.com"
        self.assertEqual(clean_message(SimpleNamespace(raw_text="Cours",entities=[entity])),"Cours")
    def test_empty(self):
        self.assertEqual(clean_text("Telegram : @foo\nLien : https://example.com"),"")
