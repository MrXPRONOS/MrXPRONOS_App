import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone

SCRIPT=pathlib.Path(__file__).resolve().parents[1]/"scripts"/"telegram_channel_monitor_v2.py"
spec=importlib.util.spec_from_file_location("telegram_channel_monitor_v2",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestMonitorOffline(unittest.TestCase):
    def test_metric_formatting(self):
        self.assertEqual(m.f(4835),"4 835")
        self.assertEqual(m.f(None),"—")

    def test_growth(self):
        self.assertEqual(m.change([{"subscriber_count":100}],120),20)
        self.assertIsNone(m.change([],100))
        self.assertIsNone(m.change([{"subscriber_count":None}],100))

    def test_html_is_escaped(self):
        row=dict(title="<script>alert(1)</script>",username="testpublic",public_url="https://t.me/testpublic",
          subscriber_count=120,delta=20,week=20,month=30,last_post_id=10,last_post_views=55,
          average_views_10=56,sampled_posts=10,mature_average_views=80,
          posts_7d=4,top=[{"public_url":"https://t.me/testpublic/10","views":55}])
        block=m.card(row,1)
        self.assertIn("&lt;script&gt;",block)
        self.assertNotIn("<script>",block)
        self.assertIn("<blockquote>",block)
        report=m.parts([row],datetime(2026,10,14,tzinfo=timezone.utc))
        self.assertEqual(len(report),1)
        self.assertLess(len(report[0]),3900) # Telegram payload stays within limits
        self.assertIn("SYNTHÈSE",report[0])

    def test_official_metric_extraction(self):
        class Stat:
            current = 125
            previous = 100
        self.assertEqual(m.official_value(Stat()),125.0)
        self.assertIsNone(m.official_value(None))

    def test_official_graph_parsing(self):
        class JsonData:
            data = '{"x":[1,2],"y":[3,4]}'
        class Graph:
            json = JsonData()
        self.assertEqual(m.official_graph(Graph())["x"],[1,2])
        self.assertIsNone(m.official_graph(None))

    def test_negative_alert(self):
        row=dict(title="Test",username="testpub",public_url="https://t.me/testpub",
          subscriber_count=90,delta=-10,week=-10,month=-10,last_post_id=None,
          last_post_views=None,average_views_10=None,sampled_posts=0,
          mature_average_views=None,posts_7d=0,top=[])
        self.assertIn("Baisse supérieure à 5 %",m.card(row,1))

    def test_positive_alert(self):
        row=dict(title="Test",username="testpub",public_url="https://t.me/testpub",
          subscriber_count=120,delta=20,week=20,month=20,last_post_id=None,
          last_post_views=None,average_views_10=10,sampled_posts=3,
          mature_average_views=5,posts_7d=1,top=[])
        self.assertIn("Hausse supérieure à 15 %",m.card(row,1))

if __name__=="__main__":
    unittest.main()
