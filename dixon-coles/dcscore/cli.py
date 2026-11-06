"""Command-line interface. Run `python -m dcscore.cli --help`."""
from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from .store import Store
from .sources import parse_csv
from .service import predict,backtest,sync_seasons
from .demo import load_demo


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
    pred=commands.add_parser("predict",help="Analyse un match futur déjà sélectionné")
    pred.add_argument("match_id")
    pred.add_argument("--xi",type=float,default=0.0065)
    pred.add_argument("--min-games",type=int,default=80)
    back=commands.add_parser("backtest",help="Backtest chronologique")
    back.add_argument("--competition",required=True)
    back.add_argument("--samples",type=int,default=12)
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
        elif args.command=="predict":
            result=predict(db,args.match_id,xi=args.xi,min_games=args.min_games)
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
