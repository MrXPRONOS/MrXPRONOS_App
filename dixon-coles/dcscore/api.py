"""HTTP API + local web interface for one selected prematch at a time."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .domain import Match, utc_datetime
from .store import Store
from .sources import parse_csv, api_enabled
from .service import predict, backtest, sync_seasons
from .demo import load_demo


class SyncRequest(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9]{2,8}$")
    seasons: list[int] = Field(min_length=1,max_length=5)


class ManualRequest(BaseModel):
    competition: str
    home_id: str
    away_id: str
    kickoff: str


class FinalScoreRequest(BaseModel):
    match_id: str
    home_goals: int = Field(ge=0,le=99)
    away_goals: int = Field(ge=0,le=99)


class PredictRequest(BaseModel):
    match_id: str
    xi: float = Field(default=0.0065,ge=0,le=0.3)
    min_games: int = Field(default=80,ge=12,le=10000)
    min_team: int = Field(default=5,ge=1,le=100)
    regularization: float = Field(default=0.15,ge=0,le=10)


class BacktestRequest(BaseModel):
    competition: str
    n_samples: int = Field(default=12,ge=1,le=30)
    min_games: int = Field(default=80,ge=12,le=10000)
    min_team: int = Field(default=5,ge=1,le=100)
    xi: float = Field(default=0.0065,ge=0,le=0.3)
    regularization: float = Field(default=0.15,ge=0,le=10)


def create_app(store: Store | None=None) -> FastAPI:
    db = store or Store()
    app=FastAPI(title="Dixon-Coles — système indépendant",version="1.0.0")
    static=Path(__file__).parent / "static"

    @app.get("/")
    def homepage():
        return FileResponse(static/"index.html")

    @app.get("/assets/style.css")
    def css():
        return FileResponse(static/"style.css")

    @app.get("/assets/app.js")
    def javascript():
        return FileResponse(static/"app.js")

    @app.get("/api/health")
    def health():
        return {"ok":True,"version":"1.0.0","api_key_configured":api_enabled(),
                "competitions":len(db.competitions()),
                "note":"Aucun code ni modèle hérité des autres systèmes."}

    @app.get("/api/competitions")
    def competitions():
        return db.competitions()

    @app.get("/api/teams")
    def teams(competition: str):
        return db.teams(competition)

    @app.get("/api/matches")
    def matches(competition: str, upcoming: bool=True,limit: int=200):
        if not 1<=limit<=1000:
            raise HTTPException(400,"Limite hors bornes")
        return [m.as_json() for m in db.matches(competition,upcoming=upcoming,limit=limit)]

    @app.get("/api/predictions")
    def predictions():
        return db.predictions(100)

    @app.post("/api/import-csv")
    async def import_csv(file: UploadFile=File(...), default_competition: str="CUSTOM"):
        try:
            if not file.filename or not file.filename.lower().endswith(".csv"):
                raise ValueError("Fichier .csv attendu.")
            raw=await file.read(15_000_001)
            rows=parse_csv(raw,default_competition=default_competition)
            count=db.upsert_matches(rows)
            return {"imported_or_updated":count,"competitions":sorted({m.competition for m in rows})}
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc
        finally:
            await file.close()

    @app.post("/api/sync")
    def sync(request: SyncRequest):
        result=sync_seasons(db,request.code.upper(),request.seasons)
        if not result["rows_imported_or_updated"]:
            raise HTTPException(400,detail=result)
        return result

    @app.post("/api/fixtures/manual")
    def manual(request: ManualRequest):
        try:
            possible={r["team_id"]:r["team_name"] for r in db.teams(request.competition)}
            if request.home_id==request.away_id or request.home_id not in possible or request.away_id not in possible:
                raise ValueError("Choisir deux équipes différentes et présentes dans l'historique.")
            dt=utc_datetime(request.kickoff)
            if dt<=datetime.now(timezone.utc):
                raise ValueError("La rencontre doit être dans le futur.")
            source="demo" if request.competition.startswith("demo:") else "manual"
            fixture=Match(id="manual:"+uuid4().hex,competition=request.competition,
                          kickoff=dt,home_id=request.home_id,away_id=request.away_id,
                          home_name=possible[request.home_id],away_name=possible[request.away_id],
                          source=source)
            db.upsert_matches([fixture])
            return fixture.as_json()
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post("/api/fixtures/manual/result")
    def finalize(request: FinalScoreRequest):
        try:
            return db.finalize_manual(request.match_id,request.home_goals,request.away_goals).as_json()
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post("/api/predict")
    def prediction(request: PredictRequest):
        try:
            return predict(db,request.match_id,xi=request.xi,min_games=request.min_games,
                           min_team=request.min_team,regularization=request.regularization)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post("/api/backtest")
    def evaluation(request: BacktestRequest):
        try:
            return backtest(db,request.competition,n_samples=request.n_samples,
                            min_games=request.min_games,min_team=request.min_team,
                            xi=request.xi,regularization=request.regularization)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post("/api/demo")
    def demo():
        return load_demo(db)

    return app


app=create_app()
