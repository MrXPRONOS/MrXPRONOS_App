"""Rich Messages: inline buttons, media and safe explicit-error fallback."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from telegram_rich import rich_buttons,rich_markup,post_photo,post_text

class Reply:
    def __init__(self,status=200):
        self.status_code=status
    def raise_for_status(self):
        if self.status_code>=400:
            raise RuntimeError(self.status_code)
    def json(self):
        return {"ok":True,"result":{"message_id":123}}

class Stub:
    def __init__(self,*statuses):
        self.statuses=list(statuses)
        self.calls=[]
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Reply(self.statuses.pop(0))

class RichTests(unittest.TestCase):
    def setUp(self):
        self.k={"inline_keyboard":[
            [{"text":"PARIEZ SUR 1XBET","style":"primary","url":"https://a.example/path?a=1&b=2"},
             {"text":"PARIEZ SUR MELBET","style":"success","url":"https://b.example"}],
            [{"text":"Voir plus de coupons 🔥","url":"https://mrx.example"}]]}
    def test_buttons_embedded_inside_message_not_keyboard(self):
        html=rich_markup("<b>Coupon jour</b>",self.k)
        self.assertIn('<img src="tg://photo?id=coupon"/>',html)
        self.assertIn("<tg-button-row",html)
        self.assertIn('style="primary"',html)
        self.assertIn('style="success"',html)
        self.assertIn("a=1&amp;b=2",html)
        self.assertNotIn("inline_keyboard",html)
    def test_all_buttons_preserved(self):
        html=rich_buttons({"inline_keyboard":[
          [{"text":str(i),"url":"https://site.example/"+str(i)} for i in range(6)]
        ]})
        self.assertEqual(html.count("<tg-button "),6)
    def test_rich_photo_only_one_send(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"photo.png"
            Image.new("RGB",(40,40),"white").save(p)
            session=Stub(200)
            n=post_photo(session,"secret","-100",p,"<b>coupons</b>",self.k)
            self.assertEqual(n,123)
            self.assertEqual(len(session.calls),1)
            url,args=session.calls[0]
            self.assertTrue(url.endswith("/sendRichMessage"))
            rich=json.loads(args["data"]["rich_message"])
            self.assertEqual(rich["media"][0]["media"]["media"],"attach://coupon_photo")
    def test_explicit_rejection_retries_legacy_once(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"photo.png"
            Image.new("RGB",(40,40),"white").save(p)
            s=Stub(400,200)
            self.assertEqual(post_photo(s,"secret","-100",p,"Hi",self.k),123)
            self.assertEqual(len(s.calls),2)
            self.assertTrue(s.calls[1][0].endswith("/sendPhoto"))
    def test_no_retry_for_uncertain_network_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"photo.png"
            Image.new("RGB",(40,40),"white").save(p)
            class ErrorStub:
                def __init__(self):self.count=0
                def post(self,*a,**k):
                    self.count+=1
                    raise TimeoutError("ambiguous")
            stub=ErrorStub()
            with self.assertRaises(TimeoutError):
                post_photo(stub,"secret","-100",p,"text",self.k)
            self.assertEqual(stub.count,1)
    def test_rich_text(self):
        s=Stub(200)
        post_text(s,"secret","-100","Hello <you>",self.k)
        rm=json.loads(s.calls[0][1]["data"]["rich_message"])
        self.assertIn("Hello &lt;you&gt;",rm["html"])
        self.assertNotIn('<img',rm["html"])

if __name__=="__main__":
    unittest.main()
