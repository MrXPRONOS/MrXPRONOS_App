"""Ciné Radar channel-format discovery tests without Telegram credentials."""
import unittest
from types import SimpleNamespace as NS
from datetime import datetime,timezone
from film_relay.public_directory import public_sequences,assess_public_channel
from film_relay.discovery import evaluate_messages

NOW=datetime(2026,10,22,tzinfo=timezone.utc)
def photo(i,caption=""):
    return NS(id=i,photo=object(),document=None,video=None,raw_text=caption,noforwards=False,date=NOW,entities=None)
def text(i,value):
    return NS(id=i,photo=None,document=None,video=None,raw_text=value,noforwards=False,date=NOW,entities=None)
def movie(i,name="Un.Film.2026.mp4",size=250_000_000):
    return NS(id=i,photo=None,document=NS(mime_type="video/mp4",size=size,attributes=[NS(file_name=name)]),
              video=None,file=NS(name=name,duration=4500,size=size),raw_text="",noforwards=False,date=NOW,entities=None)
def mkv(i,name="Cinema.Film.2026.mkv"):
    return NS(id=i,photo=None,document=NS(mime_type="application/octet-stream",size=300_000_000,attributes=[NS(file_name=name)]),
              video=None,file=NS(name=name,duration=0,size=300_000_000),raw_text="",noforwards=False,date=NOW,entities=None)

class CineRadarDiscoveryFormatTests(unittest.TestCase):
    def test_photo_caption_followed_by_video(self):
        a=public_sequences([movie(2),photo(1,"Titre : Grand Film en français")])
        self.assertEqual([(x.pattern,x.poster_id,x.video_id) for x in a],[("photo_caption_video",1,2)])

    def test_photo_then_text_then_video(self):
        a=public_sequences([movie(6),text(5,"Genre : Action, aventure 2026"),photo(4)])
        self.assertEqual(len(a),1)
        self.assertEqual(a[0].pattern,"photo_text_video")
        self.assertEqual(a[0].description_id,5)

    def test_mkv_as_named_file(self):
        a=public_sequences([mkv(10,"Grand.Cinema.Film.mkv")])
        self.assertEqual(len(a),1)
        self.assertEqual(a[0].pattern,"standalone_mkv")

    def test_dedupe_mkv_already_associated_with_poster(self):
        a=public_sequences([photo(1,"Film : Cinéma en francais"),mkv(2)])
        self.assertEqual(len(a),1)
        self.assertEqual(a[0].pattern,"photo_caption_video")

    def test_reject_false_posters_or_advertisements(self):
        self.assertEqual(public_sequences([photo(1,"https://t.me/canal"),movie(2)]),[])
        self.assertEqual(public_sequences([photo(1),text(2,"Voir lien"),movie(3)]),[])
        self.assertEqual(public_sequences([photo(1,"Titre : premier film"),photo(2,"Titre : second film"),movie(3)])[0].poster_id,2)

    def test_two_examples_are_required_for_auto_eligibility(self):
        one=assess_public_channel([photo(1,"Titre: Film numéro un"),movie(2)])
        self.assertFalse(one["format_verified"])
        many=evaluate_messages([photo(1,"Film: Une super histoire"),movie(2),photo(3),
                               text(4,"Genre: Science fiction fantastique"),mkv(5)])
        self.assertTrue(many["format_verified"])
        self.assertEqual(many["matching_pairs"],2)
        self.assertIn("photo_text_video",many["patterns"])

    def test_mkv_only_channel_with_two_distinct_files(self):
        a=evaluate_messages([mkv(10),mkv(11,"Second.Super.Long.Film.mkv")])
        self.assertTrue(a["format_verified"])
        self.assertEqual(a["matching_pairs"],2)

if __name__=="__main__":
    unittest.main()
