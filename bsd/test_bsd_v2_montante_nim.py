import unittest
from datetime import datetime, timedelta, timezone

from bsd.test_bsd_v2_montante import NOW, feed, fixture
from bsd.bsd_v2_montante import POLICY
from bsd.bsd_v2_montante_nim import (
    _validate_reviews, build_nim_payload, choose_with_nim,
    history_evidence, NIM_MODEL, _candidate_id,
)


def archive():
    result = []
    for i in range(12):
        played = NOW - timedelta(days=4 + 8 * i)
        result.append({
            'id': 'home-' + str(i), 'status': 'finished',
            'event_date': played.isoformat(), 'home_team_id': 101,
            'away_team_id': 700 + i, 'home_score': 2, 'away_score': 1,
        })
        result.append({
            'id': 'away-' + str(i), 'status': 'finished',
            'event_date': played.isoformat(), 'home_team_id': 800 + i,
            'away_team_id': 202, 'home_score': 1, 'away_score': 2,
        })
    result += [
        {'id': 'h2h', 'status': 'finished',
         'event_date': (NOW - timedelta(days=130)).isoformat(),
         'home_team_id': 101, 'away_team_id': 202, 'home_score': 1, 'away_score': 1},
        {'id': 'unsettled', 'status': 'scheduled',
         'event_date': (NOW - timedelta(days=2)).isoformat(),
         'home_team_id': 101, 'away_team_id': 202,
         'home_score': 30, 'away_score': 0},
        {'id': 'future', 'status': 'finished',
         'event_date': (NOW + timedelta(days=5)).isoformat(),
         'home_team_id': 101, 'away_team_id': 202,
         'home_score': 12, 'away_score': 0},
    ]
    return result


def match(key='X2', odds=1.35, p=0.88):
    m = fixture('101', key=key, odds=odds, p=p * 100, confidence=92)
    m['home_team_id'] = 101
    m['away_team_id'] = 202
    m['model_audit'] = {'expected_goals_home': 1.65,
                        'expected_goals_away': 1.15, 'league_samples': 133}
    if key.startswith(('OVER_', 'UNDER_')):
        m['prediction']['market'] = 'over_under_15' if key.endswith('15') else 'over_under_25'
        m['prediction']['label'] = 'Total buts ' + key
    elif key.startswith('BTTS_'):
        m['prediction']['market'] = 'btts'
    elif key in ('1', 'X', '2'):
        m['prediction']['market'] = '1x2'
    return m


def reviewing(data, verdict='approve', risk='low'):
    return {'reviews': [
        {'candidate_id': r['candidate_id'], 'verdict': verdict,
         'risk_level': risk, 'risk_flags': []}
        for r in data
    ]}


class NimSelectionTests(unittest.TestCase):
    def setUp(self):
        self.empty = {'schema': POLICY, 'days': {}}
        self.history = archive()

    def test_approves_totals_and_other_bsd_markets(self):
        for key in ('OVER_15', 'UNDER_25', 'BTTS_YES', '1', '2', 'X2'):
            with self.subTest(key=key):
                m = match(key=key)
                r, ledger = choose_with_nim(
                    feed(m), self.empty, now=NOW, archive=self.history,
                    reviewer=lambda payload: reviewing(payload),
                )
                self.assertEqual(r['status'], 'selected', r)
                self.assertEqual(r['selection']['selection_key'], key)
                self.assertEqual(ledger['days'][NOW.date().isoformat()]['nim_review']['verdict'], 'approve')

    def test_veto_keeps_no_pick(self):
        r, ledger = choose_with_nim(
            feed(match()), self.empty, now=NOW, archive=self.history,
            reviewer=lambda payload: reviewing(payload, verdict='reject', risk='high'),
        )
        self.assertEqual(r['status'], 'no_pick')
        self.assertEqual(ledger['days'], {})

    def test_uncertain_is_not_approved(self):
        r, _ = choose_with_nim(
            feed(match()), self.empty, now=NOW, archive=self.history,
            reviewer=lambda payload: reviewing(payload, verdict='uncertain', risk='medium'),
        )
        self.assertEqual(r['status'], 'no_pick')

    def test_review_incomplete_fails_closed(self):
        r, _ = choose_with_nim(feed(match()), self.empty, now=NOW,
                               archive=self.history, reviewer=lambda payload: {'reviews': []})
        self.assertEqual(r['status'], 'no_pick')
        self.assertIn('nim_review_failed_', r['reason'])

    def test_api_key_missing_is_no_pick(self):
        r, _ = choose_with_nim(feed(match()), self.empty, now=NOW, archive=self.history)
        self.assertEqual(r['reason'], 'missing_nvidia_api_key')

    def test_archive_missing_is_no_pick(self):
        r, _ = choose_with_nim(feed(match()), self.empty, now=NOW,
                               reviewer=lambda payload: reviewing(payload))
        self.assertEqual(r['reason'], 'missing_private_bsd_history')

    def test_past_only_and_h2h(self):
        ev = history_evidence(match(), self.history, now=NOW)
        self.assertEqual(ev['head_to_head_last_5']['matches'], 1)
        self.assertEqual(ev['head_to_head_last_5']['scores_from_current_home_view'], ['1-1'])
        self.assertEqual(ev['home_last_8']['matches'], 8)
        self.assertEqual(ev['away_last_8']['matches'], 8)
        self.assertNotIn('future', str(ev))
        self.assertNotIn('unsettled', str(ev))
        self.assertIn('verified_starting_lineups', ev['missing_inputs'])

    def test_insufficient_history_abstains(self):
        r, _ = choose_with_nim(feed(match()), self.empty, now=NOW, archive=self.history[:2],
                               reviewer=lambda payload: reviewing(payload))
        self.assertEqual(r['reason'], 'insufficient_verified_historical_context')

    def test_reviewer_cannot_replace_market_with_fiction(self):
        def hallucination(payload):
            return {'reviews': [
                {'candidate_id': 'invented|WIN', 'verdict': 'approve',
                 'risk_level': 'low', 'risk_flags': []}
            ]}
        r, _ = choose_with_nim(feed(match()), self.empty, now=NOW,
                               archive=self.history, reviewer=hallucination)
        self.assertEqual(r['status'], 'no_pick')
        self.assertIn('nim_review_failed_', r['reason'])

    def test_single_choice_from_multiple_candidates(self):
        m = match('X2')
        n = match('OVER_15', p=.91)
        n['id'] = 'bsd:second'
        n['source_event_id'] = 'second'
        r, l = choose_with_nim(feed(m, n), self.empty, now=NOW,
                               archive=self.history, reviewer=lambda payload: reviewing(payload))
        self.assertEqual(r['status'], 'selected')
        self.assertEqual(len(l['days']), 1)
        self.assertIn(r['selection']['selection_key'], ('X2', 'OVER_15'))

    def test_no_ai_call_if_day_frozen(self):
        selected, ledger = choose_with_nim(feed(match()), self.empty, now=NOW,
                                           archive=self.history, reviewer=lambda payload: reviewing(payload))
        self.assertEqual(selected['status'], 'selected')
        called = []
        frozen, same = choose_with_nim(feed(match('BTTS_YES')), ledger,
                                       now=NOW + timedelta(minutes=10), archive=self.history,
                                       reviewer=lambda payload: called.append(payload))
        self.assertTrue(frozen['frozen'])
        self.assertFalse(called)
        self.assertEqual(same, ledger)


if __name__ == '__main__':
    unittest.main()