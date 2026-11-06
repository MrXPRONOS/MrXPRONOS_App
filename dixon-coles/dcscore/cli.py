"""Command-line interface. Run `python -m dcscore.cli --help`."""
from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from .store import Store
from .sources import parse_csv
from .service import predict,backtest,sync_seasons,sync_openfootball_seasons
from .demo import load_demo
from .calibration import tune_xi, holdout_evaluation, DEFAULT_CANDIDATES
from .model_selection import select_model


def main(argv: list[str] | None=None):
    p=argparse.ArgumentParser(description="Dixon-Coles — nouveau moteur indépendant")
    p.add_argument("--db",default=None,help="Chemin vers la nouvelle base SQLite")
    commands=p.add_subparsers(dest="command",required=True)
    serve=commands.add_parser("serve",help="Lance l'interface web locale")
    serve.add_argument("--host",default="127.0.0.1")
    serve.add_argument("--port",type=int,default=8088)
    imp=commands.add_parser("import-csv",help="Importe le CSV UTF-8 d'un championnat")
    imp.add_argument("file")
    imp.add_argument("--competition",default="CUSTOM")
    sync=commands.add_parser("sync",help="Récupère les saisons via football-data.org v4")
    sync.add_argument("--code",required=True,help="Exemple: PL, FL1, PD, BL1, SA")
    sync.add_argument("--seasons",type=int,nargs="+",required=True)
    of=commands.add_parser("sync-openfootball", help="Importe les résultats réels CC0 Premier League (sans clé API)")
    of.add_argument("--seasons",nargs="+",required=True,help="Exemple : 2022-23 2023-24 2024-25 2025-26")
    cal=commands.add_parser("calibrate-xi",help="Optimise ξ sur des résultats réels (validation chronologique)")
    cal.add_argument("--competition",default="of:ENG-PL")
    cal.add_argument("--start",required=True,help="Début de validation AAAA-MM-01")
    cal.add_argument("--end",required=True,help="Fin exclusive de validation AAAA-MM-01")
    cal.add_argument("--block-months",type=int,default=2)
    cal.add_argument("--min-games",type=int,default=400)
    cal.add_argument("--min-team",type=int,default=5)
    cal.add_argument("--min-folds",type=int,default=3)
    cal.add_argument("--min-scored",type=int,default=100)
    cal.add_argument("--regularization",type=float,default=0.15)
    cal.add_argument("--candidates",nargs="+",type=float,default=list(DEFAULT_CANDIDATES))
    cal.add_argument("--output",help="Enregistrer le rapport JSON complet")
    cal.add_argument("--holdout-start",help="Évaluation FINALE indépendante (AAAA-MM-01)")
    cal.add_argument("--holdout-end",help="Fin exclusive du holdout (AAAA-MM-01)")
    selection=commands.add_parser('calibrate-model-choice',
        help='Compare Poisson et Dixon-Coles sans accès aux scores futurs')
    selection.add_argument('--competition',default='of:ENG-PL')
    selection.add_argument('--start',required=True)
    selection.add_argument('--end',required=True)
    selection.add_argument('--xi',type=float,default=0.0065)
    selection.add_argument('--min-games',type=int,default=400)
    selection.add_argument('--min-team',type=int,default=5)
    selection.add_argument('--min-scored',type=int,default=150)
    selection.add_argument('--min-practical-gain',type=float,default=0.005)
    selection.add_argument('--output',help='Exporter le rapport JSON')
    pred=commands.add_parser("predict",help="Analyse un match futur déjà sélectionné")
    pred.add_argument("match_id")
    pred.add_argument('--model-mode',choices=('auto','dixon_coles','poisson'),default='auto')
    pred.add_argument("--xi",type=float,default=None,help="Override manuel. Par défaut : xi calibré s’il existe.")
    pred.add_argument("--min-games",type=int,default=80)
    back=commands.add_parser("backtest",help="Backtest chronologique")
    back.add_argument("--competition",required=True)
    back.add_argument("--samples",type=int,default=100)
    back.add_argument("--xi",type=float,default=0.0065)
    back.add_argument("--min-games",type=int,default=80)
    commands.add_parser("demo",help="Génère des résultats fictifs (explicitement DEMO)")
    commands.add_parser("leagues",help="Liste les compétitions importées")
    ls=commands.add_parser("fixtures",help="Liste les rencontres futures")
    ls.add_argument("--competition",required=True)
    args=p.parse_args(argv)
    if args.db:
        import os
        os.environ["DCSCORE_DB"]=args.db
    if args.command=="serve":
        from .api import _required_public_token
        import os
        if args.host not in ("127.0.0.1", "::1", "localhost"):
            if os.getenv("DCSCORE_PUBLIC_MODE") != "1":
                print("ERREUR : DCSCORE_PUBLIC_MODE=1 est requis pour écouter hors localhost.",file=sys.stderr)
                return 1
            try:
                _required_public_token()
            except RuntimeError as exc:
                print(f"ERREUR : {exc}",file=sys.stderr)
                return 1
        uvicorn.run("dcscore.api:create_app",host=args.host,port=args.port,factory=True)
        return 0
    db=Store()
    try:
        if args.command=="import-csv":
            with open(args.file,"rb") as f:
                rows=parse_csv(f.read(),default_competition=args.competition)
            result={"imported_or_updated":db.upsert_matches(rows),
                    "competitions":sorted({m.competition for m in rows})}
        elif args.command=="sync":
            result=sync_seasons(db,args.code,args.seasons)
        elif args.command=="sync-openfootball":
            result=sync_openfootball_seasons(db,args.seasons)
        elif args.command=="calibrate-xi":
            result=tune_xi(db,args.competition,eval_start=args.start,eval_end=args.end,
                           candidates=tuple(args.candidates),block_months=args.block_months,
                           min_games=args.min_games,min_team=args.min_team,
                           min_folds=args.min_folds,min_scored=args.min_scored,
                           regularization=args.regularization)
            if args.holdout_start or args.holdout_end:
                if not args.holdout_start or not args.holdout_end:
                    raise ValueError("Les deux dates de holdout sont nécessaires.")
                if args.holdout_start < args.end:
                    raise ValueError("Le holdout doit commencer après la calibration.")
                result["holdout_not_used_for_selection"]=holdout_evaluation(
                    db.matches(args.competition,finished=True),xi=result["selected_xi"],
                    eval_start=args.holdout_start,eval_end=args.holdout_end,
                    min_games=args.min_games,min_team=args.min_team,
                    regularization=args.regularization)
            if args.output:
                from pathlib import Path
                path=Path(args.output)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
                result={"competition":result["competition"],"selected_xi":result["selected_xi"],
                        "n_scored":result["n_scored"],"n_folds":result["n_folds"],
                        "selected_mean_log_loss":result["selected_mean_log_loss"],
                        "historical_mean_log_loss":result["historical_mean_log_loss"],
                        "holdout":result.get("holdout_not_used_for_selection"),
                        "saved_report":str(path)}
        elif args.command=='calibrate-model-choice':
            result=select_model(db.matches(args.competition,finished=True),
               eval_start=args.start,eval_end=args.end,xi=args.xi,
               min_games=args.min_games,min_team=args.min_team,
               min_scored=args.min_scored,min_practical_gain=args.min_practical_gain)
            db.save_model_selection(result)
            if args.output:
                from pathlib import Path
                path=Path(args.output)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        elif args.command=="predict":
            result=predict(db,args.match_id,xi=args.xi,model_mode=args.model_mode,min_games=args.min_games)
        elif args.command=="backtest":
            result=backtest(db,args.competition,n_samples=args.samples,xi=args.xi,min_games=args.min_games)
        elif args.command=="demo":
            result=load_demo(db)
        elif args.command=="leagues":
            result=db.competitions()
        elif args.command=="fixtures":
            result=[m.as_json() for m in db.matches(args.competition,upcoming=True)]
        else:
            return 2
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as exc:
        print(f"ERREUR : {exc}",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
