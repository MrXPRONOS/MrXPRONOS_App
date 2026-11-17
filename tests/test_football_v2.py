import json
import tempfile
import unittest
from pathlib import Path
from football_media_v2.story import parse_match,select_match,match_scenes,parse_scorers,scorers_scenes,demo_match
from football_media_v2.rights import cleared
from football_media_v2.publish import SUPPORTED

class StoryTests(unittest.TestCase):
    def test_real_match_score_only(self):
        raw={'id':123,'status':'FINISHED','utcDate':'2026-10-25T18:00:00Z',
             'homeTeam':{'name':'Alpha'},'awayTeam':{'name':'Beta'},
             'score':{'fullTime':{'home':4,'away':3}},'competition':{'name':'Football'}}
        m=parse_match(raw);self.assertEqual((m['a'],m['b']),(4,3))
        scenes=match_scenes(m)
        self.assertGreaterEqual(len(scenes),8)
        combined=' '.join(s.voice for s in scenes)
        self.assertIn('7 but',combined.lower())
        self.assertNotIn('dernière minute',combined.lower())
    def test_no_unfinished_or_missing_results(self):
        example={'id':2,'status':'IN_PLAY','homeTeam':{'name':'A'},'awayTeam':{'name':'B'},'score':{'fullTime':{'home':2,'away':1}}}
        self.assertIsNone(parse_match(example))
        example['status']='FINISHED';example['score']['fullTime']['away']=None
        self.assertIsNone(parse_match(example))
    def test_scorers_need_three_real_rows(self):
        raw={'scorers':[{'player':{'name':'Abel'},'team':{'name':'FC'},'goals':8},
                        {'player':{'name':'Ben'},'team':{'name':'FC'},'goals':10},
                        {'player':{'name':'Clem'},'team':{'name':'FC'},'goals':9}]}
        parsed=parse_scorers(raw);self.assertEqual(parsed['scorers'][0]['name'],'Ben')
        self.assertGreaterEqual(len(scorers_scenes(parsed)),7)
    def test_demo_must_be_fake(self):
        self.assertIn('DEMO',demo_match()['id'])
    def test_reject_unapproved_video(self):
        with tempfile.TemporaryDirectory() as root:
            d=Path(root);(d/'video.mp4').write_bytes(b'not real')
            (d/'proof.txt').write_text('Made up rights assertion; absolutely not evidence!')
            (d/'manifest.json').write_text(json.dumps({'clips':[{'file':'video.mp4','proof':'proof.txt',
               'rights_holder':'Someone','source_url':'https://example.org','permission_id':'x',
               'commercial_use':True,'derivatives_allowed':True,'audio_allowed':False,
               'platforms':['telegram','youtube'],'license':'CC BY', 'reviewed_by_human':False}]}))
            self.assertEqual(cleared(d/'manifest.json',d,{'telegram','youtube'}),[])
    def test_publishing_restricted(self):
        self.assertEqual(SUPPORTED,{'telegram','youtube'})

if __name__=='__main__':unittest.main()
