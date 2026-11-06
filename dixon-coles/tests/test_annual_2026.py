"""Unit checks for the calendar-2026 backtest report, no live HTTP calls."""
from pathlib import Path
import sys
import csv
import json

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from backtest_calendar_2026 import (
    november_matches, build_annual_report, EXPECTED_COUNTS,
    EXPECTED_TOTAL, START, _stats_for_rows,
)


def test_expected_calendar_counts_are_complete():
    assert EXPECTED_TOTAL == 284
    assert sum(EXPECTED_COUNTS.values()) == 284
    assert all(x in EXPECTED_COUNTS for x in ('2026-01','2026-05','2026-08','2026-11'))
    assert '2026-06' not in EXPECTED_COUNTS


def _nov_fixture(tmp_path,score='0,1',duplicate=False):
    p=tmp_path/'nov.csv'
    rows=['date,home,away,home_goals,away_goals',
          f"2026-11-01,Liverpool FC,Arsenal FC,{score}",
          ('2026-11-01,Liverpool FC,Arsenal FC,0,1' if duplicate
           else '2026-11-02,Newcastle United FC,Everton FC,0,1')]
    p.write_text('\n'.join(rows)+'\n',encoding='utf8')
    return p


def test_november_results_provenance_and_validity(tmp_path):
    p=_nov_fixture(tmp_path)
    teams={'Liverpool FC','Arsenal FC','Newcastle United FC','Everton FC'}
    rows,digest=november_matches(p,teams)
    assert len(rows)==2 and len(digest)==64
    assert all(m.status=='FINISHED' and m.source.startswith('theguardian') for m in rows)
    assert [m.kickoff.strftime('%Y-%m-%d') for m in rows]==['2026-11-01','2026-11-02']


@pytest.mark.parametrize('bad', ['2,1','0,2'])
def test_november_tampered_result_fails(tmp_path,bad):
    p=_nov_fixture(tmp_path,bad)
    with pytest.raises(ValueError,match='Score différent'):
        november_matches(p,{'Liverpool FC','Arsenal FC','Newcastle United FC','Everton FC'})


def test_november_duplicate_fails(tmp_path):
    p=_nov_fixture(tmp_path,duplicate=True)
    with pytest.raises(ValueError,match='incohérentes'):
        november_matches(p,{'Liverpool FC','Arsenal FC','Newcastle United FC','Everton FC'})


def _fake_row():
    dc={'top1_hit':True,'top3_hit':True,'log_loss':2.2,'mode_score':'1-1',
        'recommended_score':None,'recommendation_hit':None}
    poi={'top1_hit':False,'top3_hit':True,'log_loss':2.1,'mode_score':'1-0',
         'recommended_score':'1-0','recommendation_hit':False}
    return {'date':'2026-01-08','month':'2026-01','match_id':'m1',
            'match':'A - B','actual':'1-1', 'dixon_coles':dc,'poisson':poi,'automatic':poi}


def test_stats_count_abstentions_without_faking_hit():
    d=_stats_for_rows([_fake_row()],'dixon_coles')
    p=_stats_for_rows([_fake_row()],'poisson')
    assert d['top1_hits']==1 and d['recommended_n']==0
    assert d['recommendation_hit_rate'] is None
    assert p['top1_hits']==0 and p['recommended_n']==1 and p['recommendation_hits']==0


def test_annual_report_refuses_future_model_selection():
    selection={'validation_end_exclusive':'2026-06-01','selected_model':'poisson'}
    with pytest.raises(RuntimeError,match='contaminée'):
        build_annual_report({'n_requested':1},selection,{},1,[],{})


def test_annual_report_refuses_missing_matches():
    selection={'validation_end_exclusive':'2025-06-01','selected_model':'poisson'}
    signal={'validation_end_exclusive':'2025-06-01'}
    with pytest.raises(RuntimeError,match='disparu'):
        build_annual_report({'n_requested':3,'n_evaluated':1,'n_skipped':1},selection,signal,3,[],{})


def test_annual_report_refuses_month_leakage():
    selection={'validation_end_exclusive':'2025-06-01','selected_model':'poisson'}
    signal={'validation_end_exclusive':'2025-06-01'}
    with pytest.raises(RuntimeError,match='Fuite temporelle'):
        build_annual_report({'n_requested':1,'n_evaluated':1,'n_skipped':0,
                             'folds':[{'start':'2026-01-01T00:00:00Z',
                                       'last_training_match':'2026-01-02T00:00:00Z'}]},
                            selection,signal,1,[],{})
