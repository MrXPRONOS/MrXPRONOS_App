"""CLI entrypoint: python -m dcscore.daily --day tomorrow --source auto."""
from __future__ import annotations
import argparse
from datetime import datetime,date,timedelta
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from .daily_pipeline import run_daily,save_outputs
from .daily_sources import DailySourceError,FootballDataProvider,OpenFootballProvider,OpenLigaDBProvider,CompositeProvider
from .daily_espn import ESPNProvider


def resolve_day(raw:str,now:datetime)->date:
    local_today=now.astimezone(ZoneInfo('Africa/Lome')).date()
    if raw=='tomorrow':return local_today+timedelta(days=1)
    if raw=='today':return local_today
    try:return date.fromisoformat(raw)
    except ValueError as exc:raise ValueError('Date attendue: today, tomorrow ou AAAA-MM-JJ') from exc


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description='Sélection quotidienne indépendante des 10 matchs, scores exacts et JSON pour vidéos.')
    p.add_argument('--day',default='tomorrow',help='today, tomorrow ou YYYY-MM-DD ; planifié à 21h UTC pour demain')
    p.add_argument('--source',choices=['auto','football-data','openfootball','openligadb','espn'],default='auto')
    p.add_argument('--count',type=int,default=10)
    p.add_argument('--calibrate-laliga-goals',action='store_true',
                   help='Calibrage temporel conservateur de Liga, uniquement après validation historique')
    p.add_argument('--min-games',type=int,default=80)
    p.add_argument('--min-team',type=int,default=6)
    p.add_argument('--min-importance',type=int,default=105)
    p.add_argument('--max-staleness-days',type=float,default=21.)
    p.add_argument('--output-dir',default='results/daily')
    args=p.parse_args(argv)
    now=datetime.now(ZoneInfo('Africa/Lome'))
    try:
        day=resolve_day(args.day,now)
        if args.source=='football-data':
            provider=FootballDataProvider()
        elif args.source=='openfootball':
            provider=OpenFootballProvider()
        elif args.source=='openligadb':
            provider=OpenLigaDBProvider()
        elif args.source=='espn':
            provider=ESPNProvider()
        else:
            sources=[]
            if os.environ.get('FOOTBALL_DATA_TOKEN','').strip():
                sources.append(FootballDataProvider())
            sources.extend([ESPNProvider(),OpenLigaDBProvider(),OpenFootballProvider()])
            provider=CompositeProvider(sources)
        report=run_daily(provider,day=day,as_of=now,limit=args.count,
                         min_games=args.min_games,min_team=args.min_team,
                         min_importance=args.min_importance,
                         max_staleness_days=args.max_staleness_days,
                         enable_goal_calibration=args.calibrate_laliga_goals)
        if args.source=='auto' and not os.environ.get('FOOTBALL_DATA_TOKEN','').strip():
            report['warnings'].append('FOOTBALL_DATA_TOKEN absent : calendrier des grands championnats et des coupes accessible uniquement par sources communautaires gratuites.')
            report['source_access_note']='Le fournisseur football-data.org demande une clé API, et certains championnats/coupes demandent un abonnement.'
        destination=Path(args.output_dir)/day.isoformat()
        save_outputs(report,destination/'predictions.json',destination/'video_payload.json')
        print(json.dumps({'status':report['status'],'date':day.isoformat(),
                          'selected':report['selected_count'],'required':report['required_count'],
                          'provider':report['source_mode'],'ready_for_video':report['ready_for_video'],
                          'discovered_count':report['count_before_quality_checks'],
                          'source_discovery_counts':report.get('source_discovery_counts',{}),
                          'reasons_not_ready':report['reasons_not_ready'],
                          'warnings':report['warnings'][:5],
                          'path':str(destination/'predictions.json')},ensure_ascii=False,indent=2))
        return 0  # PARTIAL/NO_ELIGIBLE is an explicit business state, not fabricated success.
    except (DailySourceError,ValueError,OSError) as exc:
        print('ERREUR QUOTIDIENNE: '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
