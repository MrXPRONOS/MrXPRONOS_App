"""BSD official team/league image endpoints and source-to-card integration."""
import unittest
from datetime import datetime,timezone
from io import BytesIO
from PIL import Image
from bsd_v2_assets import bsd_logo_url,valid_id,image_fields
from bsd_v2_card import _public_https, _team_image,paste_remote_logo
from bsd_v2_publish import to_site,resolve_league_names


class AssetEndpointTests(unittest.TestCase):
    def test_official_ids_and_urls(self):
        self.assertEqual(bsd_logo_url("team",165),
            "https://sports.bzzoiro.com/img/team/165/?bg=transparent")
        self.assertEqual(bsd_logo_url("league","9"),
            "https://sports.bzzoiro.com/img/league/9/?bg=transparent")
        for bad in (0,-1,None,True,1.5,"../1","1/other","0"):
            self.assertIsNone(valid_id(bad))
            self.assertEqual(bsd_logo_url("team",bad),"")
        with self.assertRaises(ValueError):
            bsd_logo_url("bad",12)

    def test_expected_team_and_competition_image_fields(self):
        m={"home_team_id":165,"away_team_id":160,"league_id":9}
        src=image_fields(m)
        self.assertEqual(src["home_logo"],
            "https://sports.bzzoiro.com/img/team/165/?bg=transparent")
        self.assertEqual(src["away_logo"],
            "https://sports.bzzoiro.com/img/team/160/?bg=transparent")
        self.assertEqual(src["league_logo"],
            "https://sports.bzzoiro.com/img/league/9/?bg=transparent")
        self.assertTrue(_public_https(src["league_logo"]))
        self.assertFalse(_public_https("http://127.0.0.1:3000/secret"))

    def test_team_endpoint_is_first_image_attempt(self):
        img=Image.new("RGB",(22,22),"blue")
        output=BytesIO()
        img.save(output,"PNG")
        calls=[]
        class Response:
            status_code=200
            content=output.getvalue()
            def raise_for_status(self):pass
        class Session:
            def get(self,url,**kwargs):
                calls.append((url,kwargs))
                return Response()
        match={"home_team_id":165,"home_team":"Santos","home_logo":""}
        result=_team_image(match,"home",session=Session())
        self.assertIsNotNone(result)
        self.assertEqual(calls[0][0],
            "https://sports.bzzoiro.com/img/team/165/?bg=transparent")
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0][1]["allow_redirects"])

    def test_invalid_image_fails_without_corrupting_card(self):
        class Response:
            status_code=404
            content=b"<html>not image</html>"
            def raise_for_status(self):
                raise RuntimeError("notfound")
        # Explicit invalid URLs are rejected without network.
        canvas=Image.new("RGB",(100,100),"white")
        self.assertFalse(paste_remote_logo(canvas,"http://localhost/image.png",0,0,40,40))

    def test_fallback_league_name_api(self):
        class Client:
            calls=[]
            def get_json(self,path,params=None,ttl=0):
                self.calls.append(path)
                if path=="/leagues/":
                    return {"results":[]}
                if path=="/leagues/9/":
                    return {"id":9,"name":"Brasileirão Série A"}
                raise AssertionError(path)
        fixture={"league_id":9}
        output={"matches":[{"league_id":9,"league":None}]}
        client=Client()
        changed=resolve_league_names(client,[fixture],output,{})
        self.assertEqual(changed,1)
        self.assertEqual(output["matches"][0]["league"],"Brasileirão Série A")
        self.assertEqual(client.calls,["/leagues/","/leagues/9/"])


if __name__=="__main__":
    unittest.main()
