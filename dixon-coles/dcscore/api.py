"""HTTP API + local web interface for one selected prematch at a time."""
from __future__ import annotations
from datetime import datetime, timezone
import os
import hmac
import time
from threading import Lock
from urllib.parse import urlsplit
from collections import defaultdict, deque
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .domain import Match, utc_datetime
from .store import Store
from .sources import parse_csv, api_enabled
from .service import predict, backtest, sync_seasons, sync_openfootball_seasons
from .demo import load_demo
from .calibration import tune_xi, DEFAULT_CANDIDATES


class SyncRequest(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9]{2,8}$")
    seasons: list[int] = Field(min_length=1,max_length=5)


class ManualRequest(BaseModel):
    competition: str
    home_id: str
    away_id: str
    kickoff: str
    neutral_venue: bool = False


class FinalScoreRequest(BaseModel):
    match_id: str
    home_goals: int = Field(ge=0,le=99)
    away_goals: int = Field(ge=0,le=99)


class PredictRequest(BaseModel):
    match_id: str
    xi: float | None = Field(default=None,ge=0,le=0.3)
    min_games: int = Field(default=80,ge=12,le=10000)
    min_team: int = Field(default=5,ge=1,le=100)
    regularization: float = Field(default=0.15,ge=0,le=10)


class BacktestRequest(BaseModel):
    competition: str
    n_samples: int = Field(default=12,ge=1,le=3000)
    min_games: int = Field(default=80,ge=12,le=10000)
    min_team: int = Field(default=5,ge=1,le=100)
    xi: float = Field(default=0.0065,ge=0,le=0.3)
    regularization: float = Field(default=0.15,ge=0,le=10)


class NeutralVenueRequest(BaseModel):
    match_id: str
    neutral_venue: bool
    reason: str = Field(min_length=12,max_length=500)


class CorrectScoreRequest(BaseModel):
    match_id: str
    home_goals: int = Field(ge=0,le=99)
    away_goals: int = Field(ge=0,le=99)
    reason: str = Field(min_length=12,max_length=500)


class OpenfootballSyncRequest(BaseModel):
    seasons: list[str] = Field(min_length=1,max_length=8)


class CalibrateXiRequest(BaseModel):
    competition: str = "of:ENG-PL"
    eval_start: str = "2024-08-01"
    eval_end: str = "2025-06-01"
    block_months: int = Field(default=2,ge=1,le=6)
    min_games: int = Field(default=400,ge=12,le=10000)
    min_team: int = Field(default=5,ge=1,le=100)
    min_scored: int = Field(default=100,ge=1,le=5000)
    min_folds: int = Field(default=3,ge=1,le=40)
    regularization: float = Field(default=0.15,ge=0,le=10)
    candidates: list[float] = Field(default_factory=lambda:list(DEFAULT_CANDIDATES),min_length=2,max_length=16)


def _public_mode() -> bool:
    return os.getenv("DCSCORE_PUBLIC_MODE", "0").strip() == "1"


def _required_public_token() -> str:
    token=os.getenv("DCSCORE_ADMIN_TOKEN", "")
    if len(token)<32:
        raise RuntimeError("Mode public : DCSCORE_ADMIN_TOKEN aléatoire de 32 caractères minimum requis.")
    return token


def _require_local_or_token(request: Request) -> None:
    """Fail closed for remote clients; in public mode even local/proxy must auth."""
    ip=request.client.host if request.client else ""
    if not _public_mode() and ip in ("127.0.0.1", "::1", "testclient"):
        return
    expected=_required_public_token() if _public_mode() else os.getenv("DCSCORE_ADMIN_TOKEN", "")
    authorization=request.headers.get("authorization", "")
    actual=(authorization[7:] if authorization.startswith("Bearer ") else
            request.headers.get("x-dcscore-admin-token", ""))
    if not expected or not hmac.compare_digest(expected,actual):
        raise HTTPException(401,"Authentification administrateur requise.",headers={"WWW-Authenticate":"Bearer"})


def _origin_guard(request: Request) -> None:
    if request.method not in ("POST","PUT","PATCH","DELETE"):
        return
    if request.headers.get("sec-fetch-site", "") == "cross-site":
        raise HTTPException(403,"Requête intersite refusée.")
    origin=request.headers.get("origin")
    if origin:
        parsed=urlsplit(origin)
        if parsed.scheme not in ("http","https") or parsed.netloc.lower()!=request.headers.get("host","").lower():
            raise HTTPException(403,"Origine différente du serveur : requête refusée.")

def create_app(store: Store | None=None) -> FastAPI:
    db = store or Store()
    if _public_mode():
        _required_public_token()
    app=FastAPI(title="Dixon-Coles — système indépendant",version="1.2.0",
                docs_url=None if _public_mode() else "/docs",
                redoc_url=None if _public_mode() else "/redoc",
                openapi_url=None if _public_mode() else "/openapi.json")
    # Simple in-process bound on expensive remote POSTs; deploy with an
    # upstream rate limiter too when multiple workers are used.
    rate_lock=Lock()
    rate_events: dict[str,deque[float]]=defaultdict(deque)

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.url.path!="/api/health":
            try:
                _origin_guard(request)
                _require_local_or_token(request)
                if request.method!="GET" and (_public_mode() or
                        (request.client and request.client.host not in ("127.0.0.1","::1","testclient"))):
                    ip=request.client.host if request.client else "unknown"
                    moment=time.monotonic()
                    with rate_lock:
                        records=rate_events[ip]
                        while records and moment-records[0]>=60:
                            records.popleft()
                        if len(records)>=40:
                            raise HTTPException(429,"Limite de 40 opérations par minute atteinte.")
                        records.append(moment)
            except HTTPException as exc:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail":exc.detail},status_code=exc.status_code,headers=exc.headers)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="same-origin"
        response.headers["X-Frame-Options"]="DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"]="no-store"
        return response
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
        return {"ok":True,"version":"1.2.0","api_key_configured":api_enabled(),
                "competitions":len(db.competitions()),
                "note":"Aucun code ni modèle hérité des autres systèmes.","public_mode":_public_mode()}

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

    @app.post("/api/sync-openfootball")
    def sync_public(request: Request, values: OpenfootballSyncRequest):
        _require_local_or_token(request)
        result=sync_openfootball_seasons(db,values.seasons)
        if not result["imported_or_updated"]:
            raise HTTPException(400,detail=result)
        return result

    @app.get("/api/xi/calibration")
    def xi_calibration(competition: str):
        saved=db.latest_xi_calibration(competition)
        return {"available":saved is not None,"calibration":saved}

    @app.post("/api/xi/calibrate")
    def xi_calibrate(request: Request, values: CalibrateXiRequest):
        _require_local_or_token(request)
        try:
            return tune_xi(db,values.competition,eval_start=values.eval_start,
                           eval_end=values.eval_end,block_months=values.block_months,
                           min_games=values.min_games,min_team=values.min_team,
                           min_scored=values.min_scored,min_folds=values.min_folds,
                           regularization=values.regularization,
                           candidates=tuple(values.candidates))
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.get("/api/results/audit")
    def audit_result(match_id: str):
        return db.result_history(match_id)

    @app.post("/api/results/correct")
    def correct_result(values: CorrectScoreRequest):
        try:
            result=db.correct_final_result(values.match_id,values.home_goals,values.away_goals,
                                           reason=values.reason)
            return {"match":result.as_json(),"audit":db.result_history(values.match_id)}
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.post("/api/fixtures/neutral")
    def update_venue(values: NeutralVenueRequest):
        try:
            result=db.set_neutral_venue(values.match_id,values.neutral_venue,reason=values.reason)
            return {"match":result.as_json(),"venue_audit":db.venue_history(values.match_id)}
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

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
                          source=source,neutral_venue=request.neutral_venue)
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
