import unittest
from har_audit import build_report,provider_for
class HarAuditTests(unittest.TestCase):
    def test_provider(self):
        self.assertEqual(provider_for("https://www.sportybet.com/api/ng/test"),"sportybet")
        self.assertEqual(provider_for("https://1xbet.com/LineFeed/"),"1xbet")
        self.assertIsNone(provider_for("https://sportybet.com.evil.test/test"))
    def test_har(self):
        har={"log":{"entries":[{"request":{"url":"https://www.sportybet.com/api/ng/sample","headers":[{"name":"Authorization","value":"Bearer SECRET"}]},"response":{"content":{"text":'{"data":{"tournaments":[{"events":[{"markets":[{"desc":"Total Corners","outcomes":[{"desc":"Over","odds":"1.9"}]}]}]}]}}'}}}]}}
        result=build_report(har,"har")
        self.assertEqual(result["responses_examined"],1)
        self.assertEqual(result["data"][0]["counts"]["corners"],1)
        self.assertNotIn("SECRET",str(result))
if __name__=="__main__":unittest.main()
