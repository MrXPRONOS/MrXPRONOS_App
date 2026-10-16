import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from film_relay.promotions import CAMPAIGNS, render_poster, campaign_caption, campaign_button, due
from film_relay.state import State

class PromoTests(unittest.TestCase):
    def test_channels(self):
        self.assertEqual([x[1] for x in CAMPAIGNS],[
            "@actufoot_mrxp","@mr_xpronos_vip","@mrxpronosfr"])
        for index in range(3):
            self.assertLessEqual(len(campaign_caption(index).splitlines()),4)
            self.assertEqual(campaign_button(index)[1],
                             "https://t.me/"+CAMPAIGNS[index][1][1:])

    def test_posters(self):
        for index in range(3):
            poster=Image.open(render_poster(index))
            self.assertEqual(poster.size,(1080,1350))
            self.assertEqual(poster.format,"JPEG")

    def test_rotation(self):
        with TemporaryDirectory() as td:
            state=State(str(Path(td)/"state.json"))
            self.assertIsNone(due(state,"channel",1))
            self.assertEqual(due(state,"channel",2),0)
            cursor=state.data["promotions"]["channel"]
            cursor["last_film_total"]=2
            cursor["next_index"]=1
            self.assertIsNone(due(state,"channel",3))
            self.assertEqual(due(state,"channel",4),1)

if __name__=="__main__":
    unittest.main()
