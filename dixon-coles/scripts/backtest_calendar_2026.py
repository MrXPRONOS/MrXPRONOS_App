"""Reproducible Jan 1–Nov 6 2026 Premier League retrospective walk-forward.

No result in the evaluated calendar month enters its fit. The automatic
model and exact-score abstention policy are frozen using data that ended
BEFORE 2026. The strategy was designed later in 2026; these are *simulated*
historical forecasts, not claims about previously posted bets.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from typing import Any

from dcscore.domain import Match
from dcscore.openfootball import COMPETITION, _team_name_id, download_openfootball_season
from dcscore.service import backtest
from dcscore.score_signal import assess_score_signal, calibrate_score_signals
from dcscore.model_selection import select_model
from dcscore.store import Store
from backtest_october_2026 import october_matches

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
# The 6 Nov 2026 Everton-Coventry fixture was not finished at the snapshot.
AS_OF = datetime(2026, 11, 6, 21, 17, tzinfo=UTC)
CALIB_START = '2024-08-01'
CALIB_END = '2025-06-01'
SEASONS = ('2021-22', '2022-23', '2023-24', '2024-25', '2025-26', '2026-27')
NOVEMBER_URL = 'https://www.theguardian.com/football/premierleague/results/2026/Nov/02'
NOVEMBER_CROSSCHECK = 'https://fbref.com/en/comps/9/schedule/'
EXPECTED_COUNTS = {'2026-01': 49, '2026-02': 42, '2026-03': 32,
                   '2026-04': 30, '2026-05': 41, '2026-08': 20,
                   '2026-09': 30, '2026-10': 38, '2026-11': 2}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())  # 284
MIN_GAMES = 500
MIN_TEAM_GAMES = 5
XI = 0.0065


def november_matches(path: Path, valid_teams: set[str]) -> tuple[list[Match], str]:
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        rd = csv.DictReader(handle)
        if not rd.fieldnames or set(rd.fieldnames) != {'date','home','away','home_goals','away_goals'}:
            raise ValueError('Colonnes du fichier novembre invalides.')
        rows = list(rd)
    if len(rows) != 2:
        raise ValueError('Les deux matchs terminés du 1er et 2 novembre sont requis.')
    results: list[Match] = []
    expected = {
        ('2026-11-01','Liverpool FC','Arsenal FC'): (0,1),
        ('2026-11-02','Newcastle United FC','Everton FC'): (0,1),
    }
    used: set[tuple[str,str,str]] = set()
    for row in rows:
        date,home,away = row['date'],row['home'],row['away']
        key=(date,home,away)
        if key not in expected or key in used:
            raise ValueError('Identité/date des matchs de novembre incohérentes.')
        if home not in valid_teams or away not in valid_teams:
            raise ValueError('Équipe non reconnue dans la Premier League 2026–27.')
        try:
            score=(int(row['home_goals']),int(row['away_goals']))
        except (TypeError,ValueError) as exc:
            raise ValueError('Score de novembre invalide.') from exc
        if score != expected[key]:
            raise ValueError('Score différent des deux sources de novembre vérifiées.')
        match_dt = datetime.strptime(date,'%Y-%m-%d').replace(tzinfo=UTC)
        if match_dt >= AS_OF:
            raise ValueError('Résultat de novembre postérieur à la date du rapport.')
        game_id = 'nov2026:' + sha256('|'.join(key).encode()).hexdigest()[:24]
        results.append(Match(id=game_id, competition=COMPETITION,
            kickoff=match_dt, home_id=_team_name_id(home), away_id=_team_name_id(away),
            home_name=home, away_name=away, home_goals=score[0], away_goals=score[1],
            status='FINISHED', season='2026-27', source='theguardian.com/football/premierleague/results/2026/Nov/02',
            result_provenance='provider_reported', neutral_venue=False))
        used.add(key)
    if used != set(expected):
        raise ValueError('Match de novembre manquant.')
    return results,digest


def _stats_for_rows(rows: list[dict], model: str) -> dict:
    assert model in ('dixon_coles', 'poisson')
    if not rows:
        return {'n':0}
    prefix = 'dixon_coles' if model=='dixon_coles' else 'poisson'
    return {
        'n':len(rows),
        'top1_hits':sum(r[prefix]['top1_hit'] for r in rows),
        'top1_hit_rate':sum(r[prefix]['top1_hit'] for r in rows)/len(rows),
        'top3_hits':sum(r[prefix]['top3_hit'] for r in rows),
        'top3_hit_rate':sum(r[prefix]['top3_hit'] for r in rows)/len(rows),
        'mean_exact_score_log_loss':mean(r[prefix]['log_loss'] for r in rows),
        'mode_1_1_count':sum(r[prefix]['mode_score']=='1-1' for r in rows),
        'recommended_n':sum(r[prefix]['recommended_score'] is not None for r in rows),
        'recommended_1_1_count':sum(r[prefix]['recommended_score']=='1-1' for r in rows),
        'recommendation_hits':sum(r[prefix]['recommendation_hit'] is True for r in rows),
        'recommendation_hit_rate':(
            sum(r[prefix]['recommendation_hit'] is True for r in rows)/
            sum(r[prefix]['recommended_score'] is not None for r in rows)
            if any(r[prefix]['recommended_score'] is not None for r in rows) else None),
    }


def build_annual_report(backtest_result: dict, selection: dict, policy: dict,
                        target_total: int, source_manifest: list[dict],
                        csv_digests: dict) -> dict:
    if selection['validation_end_exclusive'] > START.date().isoformat():
        raise RuntimeError('Sélection du modèle contaminée par 2026.')
    if policy['validation_end_exclusive'] > START.date().isoformat():
        raise RuntimeError('Filtre de score contaminé par 2026.')
    if selection['selected_model'] not in ('dixon_coles','poisson'):
        raise RuntimeError('Modèle sélectionné inconnu.')
    if backtest_result['n_requested'] != target_total:
        raise RuntimeError('Le nombre de rencontres ciblées a changé.')
    if backtest_result['n_evaluated']+backtest_result['n_skipped'] != target_total:
        raise RuntimeError('Une partie des matchs a disparu du backtest.')
    folds = backtest_result['folds']
    if not folds or any(f['last_training_match'] >= f['start'] for f in folds):
        raise RuntimeError('Fuite temporelle détectée dans un bloc de backtest.')
    detailed = []
    for row in backtest_result['detailed']:
        if not START.isoformat()[:10] <= row['kickoff'][:10] <= AS_OF.date().isoformat():
            raise RuntimeError('Match hors année civile 2026.')
        current={'date':row['kickoff'][:10], 'month':row['kickoff'][:7],
                 'match_id':row['match_id'], 'match':row['match'],
                 'actual':row['actual'], 'provenance':row['result_provenance']}
        for model in ('dixon_coles','poisson'):
            exact_scores=row['dc_top_scores'] if model=='dixon_coles' else row['poisson_top_scores']
            confidence=assess_score_signal({'top_scores':exact_scores},policy,model=model)
            expected=row['best'] if model=='dixon_coles' else row['poisson_best_score']
            if expected != exact_scores[0]['score']:
                raise RuntimeError('Classement des scores incohérent.')
            candidate={
                'mode_score':expected,
                'mode_probability':exact_scores[0]['probability'],
                'top_three':[v['score'] for v in exact_scores[:3]],
                'gap_percentage_points':confidence['gap_percentage_points'],
                'top1_hit':expected==row['actual'],
                'top3_hit':row['actual'] in [v['score'] for v in exact_scores[:3]],
                'recommended_score':confidence['recommended_score'],
                'recommendation_hit':(confidence['recommended_score']==row['actual']
                                      if confidence['recommended_score'] else None),
                'signal_status':confidence['status'],
                'log_loss':row['dc_log_loss'] if model=='dixon_coles' else row['poisson_independent_log_loss'],
            }
            current[model]=candidate
        winner=selection['selected_model']
        current['automatic_model']=winner
        current['automatic']=current[winner]
        detailed.append(current)
    if len(detailed) != backtest_result['n_evaluated']:
        raise RuntimeError('Nombre de lignes finales incohérent.')
    monthly = []
    grouped: dict[str,list[dict]] = defaultdict(list)
    for entry in detailed: grouped[entry['month']].append(entry)
    skips: dict[str,list[dict]] = defaultdict(list)
    for skipped in backtest_result['skipped']:
        month = skipped.get('month')
        if month: skips[month].append(skipped)
    for m in EXPECTED_COUNTS:
        items=grouped.get(m,[])
        monthly.append({
            'month':m, 'total_finished':EXPECTED_COUNTS[m],
            'evaluated':len(items), 'excluded':EXPECTED_COUNTS[m]-len(items),
            'dixon_coles':_stats_for_rows(items,'dixon_coles'),
            'poisson':_stats_for_rows(items,'poisson'),
            'automatic':_stats_for_rows(items,winner),
        })
    # Confirm every evaluated score fell inside an actually observed calendar month.
    if any(m['month'] not in EXPECTED_COUNTS for m in detailed):
        raise RuntimeError('Un mois inattendu apparaît dans le backtest.')
    report={
        'report_schema_version':1,
        'date_start_inclusive':'2026-01-01',
        'date_end_inclusive':'2026-11-06',
        'snapshot':'2026-11-06T21:17:00Z',
        'scope':'English Premier League (one competition), calendar 2026 to date',
        'no_future_training':True,
        'evaluation_kind':'historical simulation / retrospective, not timestamped live predictions',
        'history_before_start_frozen_model_selection':True,
        'fixed_xi':XI,
        'regularization':0.15,
        'monthly_refit':True,
        'target_matches':target_total,
        'evaluated_matches':backtest_result['n_evaluated'],
        'excluded_matches':backtest_result['n_skipped'],
        'folds':folds,
        'selected_model_before_2026':winner,
        'model_selection_pre_2026':{
            key: selection[key] for key in ('validation_start','validation_end_exclusive',
                'n_scored','n_blocks','mean_dc_log_loss','mean_poisson_log_loss',
                'selected_model','mean_gain_for_dc','ci95_paired_gain_for_dc',
                'min_practical_gain')
        },
        'signal_filter_pre_2026':{
            key:policy[key] for key in ('validation_start','validation_end_exclusive',
                                      'n_scored','n_folds','confidence_quantile','models')
        },
        'summary':{
            'dixon_coles':_stats_for_rows(detailed,'dixon_coles'),
            'poisson':_stats_for_rows(detailed,'poisson'),
            'automatic':_stats_for_rows(detailed,winner),
            'one_x_two_brier_dixon_coles':backtest_result['mean_one_x_two_brier'],
        },
        'months':monthly,
        'matches':detailed,
        'skipped':backtest_result['skipped'],
        'sources':source_manifest,
        'csv_sha256':csv_digests,
        'methodology_notes':[
            'Chaque mois 2026 est prédit avec des modèles réentraînés uniquement sur les résultats antérieurs au premier jour du mois.',
            'Dixon-Coles et Poisson ont chacun leurs propres paramètres entraînés indépendamment.',
            'Le choix automatique et les seuils anti-1–1 sont dérivés exclusivement des matchs terminés avant juin 2025, sans aucun score 2026.',
            'Un match avec moins de cinq résultats par équipe est exclu des métriques et décompté comme exclu.',
            'Le filtre anti-1–1 ne change aucune probabilité ni le score mathématiquement le plus probable. Il s’abstient de recommander un score peu convaincant.',
            'Les règles ont été développées après les matchs évalués : ce backtest ne représente pas des prédictions réellement publiées en 2026.',
            '2026 est une année civile inachevée au 6 novembre ; aucun match futur ni résultat non terminé n’est utilisé.',
            'Le dernier match du 6 novembre n’était pas terminé à la prise d’instantané ; ne pas l’inclure.',
        ],
    }
    return report


def _markdown(report: dict) -> str:
    s=report['summary'];auto=s['automatic'];m=report['model_selection_pre_2026']
    lines=[
      '# Backtest annuel 2026 — Premier League (1 janvier – 6 novembre)',
      '',
      '**Type :** simulation rétrospective, pas de pronostics publiés à l’époque.',
      f"**Périmètre :** {report['target_matches']} résultats terminés, {report['evaluated_matches']} évalués, {report['excluded_matches']} exclus faute d'historique.",
      '**Méthode :** entraînement mensuel strictement antérieur aux matchs évalués ; aucun score du mois ne rentre dans son apprentissage.',
      f"**Coefficient de décroissance :** ξ = {report['fixed_xi']}; modèle automatique fixé avant 2026 : **{report['selected_model_before_2026']}**.",
      f"**Calibration indépendante :** {m['validation_start']} à {m['validation_end_exclusive']} sur {m['n_scored']} matchs, sans utiliser 2026.",
      '',
      '## Résultats d’ensemble',
      '',
      '| Indicateur | Dixon-Coles | Poisson indépendant | Mode automatique |',
      '|---|---:|---:|---:|',
    ]
    for label,key,fmt in [
      ('Log loss score exact','mean_exact_score_log_loss','.4f'),
      ('Scores exacts Top 1','top1_hit_rate','.2%'),
      ('Scores exacts Top 3','top3_hit_rate','.2%'),
      ('Scores 1–1 en première position','mode_1_1_count','d'),
      ('Recommandations uniques','recommended_n','d'),
      ('Scores 1–1 recommandés','recommended_1_1_count','d'),
      ('Recommandations correctes','recommendation_hits','d'),
    ]:
        values=[]
        for name in ('dixon_coles','poisson','automatic'):
            x=s[name][key]
            values.append(format(x,fmt))
        lines.append('| '+label+' | '+' | '.join(values)+' |')
    lines+=['', '## Par mois', '',
      '| Mois | Matchs | Évalués | Top 1 (auto) | Top 3 (auto) | Conseils | Conseils justes | 1–1 conseillés |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in report['months']:
        a=row['automatic'];lines.append('| '+row['month']+' | '+str(row['total_finished'])+' | '+str(row['evaluated'])+' | '+(format(a.get('top1_hit_rate',0),'.1%') if a['n'] else '—')+' | '+(format(a.get('top3_hit_rate',0),'.1%') if a['n'] else '—')+' | '+str(a.get('recommended_n',0))+' | '+str(a.get('recommendation_hits',0))+' | '+str(a.get('recommended_1_1_count',0))+' |')
    lines+=['', '## Sources et limites', '',
        '* Historique 2021–2026 : OpenFootball (CC0).',
        '* Octobre 2026 : relevé StatsNext, vérifié contre une seconde source de résultats.',
        '* Novembre 2026 : The Guardian et FBref.',
        '* Les scores de juin et juillet sont absents parce que la Premier League était entre deux saisons.',
        '* Les 1–1 en Top 1 restent des modes mathématiques, pas automatiquement des recommandations.',
        '* Ce backtest ne mesure ni les cotes, ni le rendement de paris ni la performance de championnats autres que Premier League.',
    ]
    return '\n'.join(lines)+'\n'


def _match_csv(report: dict, path: Path) -> None:
    headers=['date','month','match','actual','model_selected','dc_mode','dc_p','dc_top1_hit',
             'poisson_mode','poisson_p','poisson_top1_hit','auto_recommended','auto_recommendation_hit',
             'auto_mode_1_1','auto_log_loss']
    with path.open('w',newline='',encoding='utf-8') as handle:
        w=csv.DictWriter(handle,fieldnames=headers);w.writeheader()
        for r in report['matches']:
            w.writerow({'date':r['date'],'month':r['month'],'match':r['match'],
                'actual':r['actual'],'model_selected':r['automatic_model'],
                'dc_mode':r['dixon_coles']['mode_score'],
                'dc_p':f"{r['dixon_coles']['mode_probability']:.6f}",
                'dc_top1_hit':int(r['dixon_coles']['top1_hit']),
                'poisson_mode':r['poisson']['mode_score'],
                'poisson_p':f"{r['poisson']['mode_probability']:.6f}",
                'poisson_top1_hit':int(r['poisson']['top1_hit']),
                'auto_recommended':r['automatic']['recommended_score'] or '',
                'auto_recommendation_hit':(
                    '' if r['automatic']['recommendation_hit'] is None else int(r['automatic']['recommendation_hit'])),
                'auto_mode_1_1':int(r['automatic']['mode_score']=='1-1'),
                'auto_log_loss':f"{r['automatic']['log_loss']:.6f}"})


def main(argv: list[str] | None=None)->int:
    parser=argparse.ArgumentParser(description='Backtest annuel Premier League 2026 (année à date)')
    parser.add_argument('--db',required=True)
    parser.add_argument('--october-csv',required=True)
    parser.add_argument('--november-csv',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--csv-out',required=True)
    parser.add_argument('--markdown-out',required=True)
    args=parser.parse_args(argv)
    if Path(args.db).exists():
        raise RuntimeError('La base SQLite du backtest doit être neuve et indépendante.')
    store=Store(args.db)
    raw=[];sources=[];valid=set()
    for season in SEASONS:
        rows,meta=download_openfootball_season(season,as_of=AS_OF)
        completed=[m for m in rows if m.status=='FINISHED' and m.kickoff < AS_OF]
        raw+=completed
        sources.append({**meta,'finished_loaded':len(completed)})
        if season=='2026-27': valid={m.home_name for m in rows}|{m.away_name for m in rows}
        print('SOURCE',season,'FINISHED',len(completed),flush=True)
    if len(valid)!=20:
        raise RuntimeError('La liste des équipes 2026–2027 n’est pas complète.')
    oct_games,oct_hash=october_matches(Path(args.october_csv),valid)
    nov_games,nov_hash=november_matches(Path(args.november_csv),valid)
    raw+=oct_games+nov_games
    identities={(m.kickoff.date(),m.home_id,m.away_id) for m in raw}
    if len(identities)!=len(raw):
        raise RuntimeError('Doublons de rencontres détectés entre fournisseurs.')
    candidates=[m for m in raw if START<=m.kickoff<AS_OF]
    counts=Counter(m.kickoff.strftime('%Y-%m') for m in candidates)
    if dict(counts)!=EXPECTED_COUNTS or len(candidates)!=EXPECTED_TOTAL:
        raise RuntimeError(f'Contrôle des résultats 2026 échoué: {dict(counts)} ; attendu {EXPECTED_COUNTS}')
    store.upsert_matches(raw)
    before=[m for m in raw if m.kickoff<START]
    # Freeze the model gate and score-signal policy on matches ending before
    # June 2025. No 2026 observation, label or score enters their decisions.
    selection=select_model(before,eval_start=CALIB_START,eval_end=CALIB_END,
        xi=XI,min_games=MIN_GAMES,min_team=MIN_TEAM_GAMES,
        min_scored=300,min_folds=8,regularization=0.15,
        as_of=datetime(2025,12,31,tzinfo=UTC))
    signal=calibrate_score_signals(before,eval_start=CALIB_START,eval_end=CALIB_END,
        xi=XI,min_games=MIN_GAMES,min_team=MIN_TEAM_GAMES,
        min_scored=300,min_folds=8,regularization=0.15,
        confidence_quantile=0.80,min_gap_percentage_points=1.0,
        as_of=datetime(2025,12,31,tzinfo=UTC))
    if signal['n_scored']<300 or selection['n_scored']<300:
        raise RuntimeError('La calibration historique est trop courte.')
    print('FROZEN MODEL',selection['selected_model'], 'CALIBRATION',selection['n_scored'],flush=True)
    print('SCORE POLICY',signal['n_scored'],signal['models'],flush=True)
    result=backtest(store,COMPETITION,n_samples=len(candidates),
                    min_games=MIN_GAMES,min_team=MIN_TEAM_GAMES,xi=XI,regularization=0.15)
    if result['n_requested']!=len(candidates):
        raise RuntimeError('Le backtest n’a pas ciblé toute l’année.');
    report=build_annual_report(result,selection,signal,len(candidates),sources,{
        'october':oct_hash,'november':nov_hash})
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    md=Path(args.markdown_out);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(_markdown(report),encoding='utf-8')
    csvout=Path(args.csv_out);csvout.parent.mkdir(parents=True,exist_ok=True)
    _match_csv(report,csvout)
    print('YEAR 2026',report['target_matches'],'MATCHES',report['evaluated_matches'],'EVALUATED',report['excluded_matches'],'EXCLUDED',flush=True)
    print('MODEL PRE-2026',report['selected_model_before_2026'],flush=True)
    for k,s in report['summary'].items():
        if isinstance(s,dict):
            print('METRICS',k,'N',s['n'],'LOSS',round(s['mean_exact_score_log_loss'],6),
                  'TOP1',s['top1_hits'],'TOP3',s['top3_hits'],
                  'SIGNALS',s['recommended_n'],'SIGNAL_HITS',s['recommendation_hits'],
                  'ONE_ONE_MODE',s['mode_1_1_count'],'ONE_ONE_RECOMMENDED',s['recommended_1_1_count'],flush=True)
    for m in report['months']:
        a=m['automatic'];print('MONTH',m['month'],m['evaluated'],'/',m['total_finished'],
                         'TOP1',a.get('top1_hits'),'SIGNALS',a.get('recommended_n'),flush=True)
    print('FILES',dest,md,csvout,flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
