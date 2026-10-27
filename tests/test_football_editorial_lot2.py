"""Lot 2 regression suite: guarantees 7–17 are real and fail closed."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from football_media_v2.editorial import (
    FORMAT_NAMES, _curated_topic, choose_script, discover_topics, editorial_report,
    is_duplicate, load_storypacks, merits_video, review_draft, score_topic,
    select_topic, source_url, Fact, Topic
)
from football_media_v2.engine import main

BASE = Path(__file__).resolve().parents[1]
PACKS = BASE / 'football_media_v2' / 'editorial_packs' / 'verified_examples.json'
TODAY = date(2026,10,27)


def sample_score(a,b,match_id=500):
    return {'id':match_id, 'status':'FINISHED','utcDate':'2026-10-26T21:00:00Z',
      'homeTeam':{'name':'Test Club A'},'awayTeam':{'name':'Test Club B'},
      'score':{'fullTime':{'home':a,'away':b}},'competition':{'name':'Exemple fictif de test'}}


def sample_scorers():
    return {'competition':{'name':'Compétition fictive de test'},'season':{'id':991},
      'scorers':[{'player':{'name':name},'goals':goals,
                   'playedMatches':matches,'assists':3,
                   'team':{'name':'Equipe test '+name}}
        for name,goals,matches in [('Alpha',16,20),('Bravo',15,22),('Charlie',12,20),('Delta',11,19),('Echo',10,21)]]}


class EditorialLot2Tests(unittest.TestCase):
    def test_07_discover_multi_sources_and_scorer_formats(self):
        topics=discover_topics([sample_score(4,3)],sample_scorers(),load_storypacks(PACKS))
        self.assertTrue({'story','ranking','comparison','portrait'}.issubset({t.format for t in topics}))
        self.assertTrue(all(t.facts for t in topics))
        self.assertEqual(len(FORMAT_NAMES),6)
        self.assertEqual(set(FORMAT_NAMES),{'highlights','portrait','story','tactical','ranking','comparison'})

    def test_07_no_fake_comeback_from_result_api(self):
        topics=discover_topics([sample_score(4,3)])
        self.assertEqual(len(topics),1)
        self.assertTrue(topics[0].data['is_score_only'])
        self.assertNotIn('minute',repr(topics[0].facts))
        self.assertEqual(select_topic(topics,today=TODAY)[0],None)

    def test_08_factual_score_and_rubric(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        score_topic(t,TODAY)
        self.assertGreaterEqual(t.score,60)
        self.assertEqual(set(t.score_breakdown),{'actualite','preuves','surprise','angle','importance','medias','total'})
        self.assertEqual(t.score,sum(v for k,v in t.score_breakdown.items() if k!='total'))

    def test_09_10_gate_rejects_boring_ordinary_score(self):
        self.assertFalse(discover_topics([sample_score(3,2)]))
        t=discover_topics([sample_score(4,3)])[0]
        score_topic(t,TODAY)
        self.assertEqual(merits_video(t)[0],False)
        self.assertIn('score seul',merits_video(t)[1].lower())

    def test_11_deduplicate_event_and_angle(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        self.assertFalse(is_duplicate(t,{'seen':[]},TODAY))
        self.assertTrue(is_duplicate(t,{'seen':[t.state_key]},TODAY))
        self.assertTrue(is_duplicate(t,{'editorial_history':[{'event_id':t.event_id,'fingerprint':'else','published_at':'2026-10-24'}]},TODAY))
        self.assertFalse(is_duplicate(t,{'editorial_history':[{'event_id':t.event_id,'fingerprint':'else','published_at':'2026-09-01'}]},TODAY))

    def test_12_13_14_hook_and_evidence_based_story(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        draft,variants=choose_script(t)
        self.assertEqual(draft.variant,'paradox')
        self.assertIn('Trois buts',draft.scenes[0].voice)
        self.assertIn('titre',draft.scenes[0].voice)
        self.assertEqual(len(draft.scenes),len(draft.evidence))
        self.assertEqual(len(draft.scenes),9)
        self.assertFalse(review_draft(draft,t))
        self.assertIn('penalties',draft.evidence[0])
        self.assertNotIn('stop scroll',draft.voice.casefold())

    def test_15_every_sentence_claim_has_fact_reference(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        d,_=choose_script(t)
        referenced=set(sum(d.evidence,[]))
        self.assertTrue(referenced.issubset({f.id for f in t.facts}))
        report=editorial_report(t,d,[],[])
        self.assertIn('https://www.fifa.com/',report['sources'][0]['url'])
        self.assertTrue(all(x['fact_ids'] for x in report['timeline']))
        self.assertFalse(report['publication_allowed_by_lot2'])

    def test_16_three_variants_ranked_not_just_renamed(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        d,ranked=choose_script(t)
        self.assertEqual(len(ranked),3)
        self.assertEqual(len({v['hook'] for v in ranked}),3)
        self.assertEqual(sum(v['selected'] for v in ranked),1)
        self.assertGreaterEqual(ranked[0]['score'],ranked[1]['score'])
        self.assertEqual(d.variant,ranked[0]['variant'])

    def test_17_blank_and_duplicate_beats_rejected(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        d,_=choose_script(t)
        # Duplicate voice phrase by replacing an immutable Scene via dataclasses.replace.
        from dataclasses import replace
        d.scenes[3]=replace(d.scenes[3],voice=d.scenes[2].voice)
        self.assertTrue(any('répétée' in x for x in review_draft(d,t)))

    def test_reject_unreviewed_missing_invalid_domains(self):
        orig=load_storypacks(PACKS)[0]
        p=copy.deepcopy(orig);p['reviewed']=False
        self.assertIsNone(_curated_topic(p))
        p=copy.deepcopy(orig);p['facts'][0]['source_url']='https://fifa.com.evil.example/final'
        self.assertIsNone(_curated_topic(p))
        self.assertFalse(source_url('https://www.fifa.com.attacker.test/'))
        self.assertFalse(source_url('http://www.fifa.com/facts'))
        p=copy.deepcopy(orig);p['facts']=[f for f in p['facts'] if f['id']!='goal80']
        self.assertIsNone(_curated_topic(p))

    def test_not_claiming_stale_historical_topic_as_latest(self):
        t=discover_topics(storypacks=load_storypacks(PACKS))[0]
        score_topic(t,TODAY)
        self.assertEqual(t.score_breakdown['actualite'],1)
        self.assertEqual(t.event_date,'2022-12-18')

    def test_rankings_premier_technically_sourced_and_voice(self):
        topics=discover_topics(scorers=sample_scorers())
        for fmt in ('ranking','comparison','portrait'):
            t=next(x for x in topics if x.format==fmt)
            score_topic(t,TODAY)
            self.assertTrue(merits_video(t)[0],(fmt,t.score_breakdown))
            d,variants=choose_script(t)
            self.assertGreaterEqual(len(d.scenes),7)
            self.assertFalse(review_draft(d,t))
            self.assertGreaterEqual(len(variants),3)

    def test_no_unauthorized_highlights_from_user_json(self):
        raw=copy.deepcopy(load_storypacks(PACKS)[0]);raw['format']='highlights'
        raw['licensed_media_count']=999
        self.assertIsNone(_curated_topic(raw))

    def test_editorial_only_writes_evidence_and_no_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            code=main(['--mode','story','--storypack',str(PACKS),'--editorial-only',
                        '--out',str(out),'--state',str(out/'state.json')])
            self.assertEqual(code,0)
            report=json.loads((out/'editorial_report.json').read_text())
            self.assertEqual(report['chosen_variant'],'paradox')
            self.assertGreaterEqual(len(report['sources']),8)
            self.assertEqual(json.loads((out/'productions.json').read_text()),[])
            self.assertFalse(any(out.rglob('*.mp4')))

    def test_tactical_requires_structured_data_source(self):
        raw=copy.deepcopy(load_storypacks(PACKS)[0]);raw['format']='tactical'
        raw['script_data']={'metrics':[{'fact_id':'goal80','label':'Tirs','home':7,'away':6},
                        {'fact_id':'goal81','label':'Possession','home':'55%','away':'45%'}]}
        t=_curated_topic(raw);self.assertIsNotNone(t)
        score_topic(t,TODAY)
        d,_=choose_script(t)
        self.assertEqual(d.scenes[0].kind,'hook')
        self.assertFalse(review_draft(d,t))
        raw['script_data']['metrics'][0]['fact_id']='missing'
        self.assertIsNone(_curated_topic(raw))

if __name__=='__main__':unittest.main()

class NewsLeadTests(unittest.TestCase):
    def test_07_official_rss_keywords_are_unverified_leads(self):
        from football_media_v2.news_leads import parse_feed_xml
        raw=b'''<rss><channel><item><title>Unbelievable comeback as team claims late winner</title>
        <link>https://www.bbc.co.uk/sport/football/test-match-123</link>
        <pubDate>Mon, 26 Oct 2026 15:01:00 GMT</pubDate></item></channel></rss>'''
        leads=parse_feed_xml(raw,today=TODAY)
        self.assertEqual(len(leads),1)
        self.assertIn('comeback',leads[0]['categories'])
        self.assertFalse(leads[0]['ready_to_script'])
        self.assertFalse(leads[0]['verified'])

    def test_07_rss_excluded_forged_domains_and_stale(self):
        from football_media_v2.news_leads import parse_feed_xml
        raw=b'''<rss><channel><item><title>Record scorer historic hat-trick</title>
        <link>https://bbc.co.uk.evil.test/article</link><pubDate>Mon, 26 Oct 2026 15:01:00 GMT</pubDate>
        </item><item><title>Record scorer historic hat-trick</title>
        <link>https://www.bbc.co.uk/sport/test</link><pubDate>Thu, 01 Jan 2015 15:01:00 GMT</pubDate>
        </item></channel></rss>'''
        self.assertEqual(parse_feed_xml(raw,today=TODAY),[])

    def test_09_ranking_ties_are_not_false_ordinal_places(self):
        t=sample_scorers()
        t['scorers'][1]['goals']=t['scorers'][0]['goals']
        self.assertEqual(discover_topics(scorers=t),[])
