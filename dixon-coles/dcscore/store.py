from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .domain import Match, utc_datetime, iso_date


def default_db_path() -> str:
    return os.getenv("DCSCORE_DB") or str(Path.cwd() / "instance" / "dixon_coles.db")


class Store:
    def __init__(self, path: str | None = None):
        self.path = str(path or default_db_path())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        with self.connection() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                competition TEXT NOT NULL,
                kickoff TEXT NOT NULL,
                home_id TEXT NOT NULL,
                away_id TEXT NOT NULL,
                home_name TEXT NOT NULL,
                away_name TEXT NOT NULL,
                status TEXT NOT NULL,
                home_goals INTEGER,
                away_goals INTEGER,
                season TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_matches_league_date ON matches(competition,kickoff);
            CREATE INDEX IF NOT EXISTS ix_matches_status ON matches(status);
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY, match_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                cutoff TEXT NOT NULL,
                result_json TEXT NOT NULL,
                FOREIGN KEY(match_id) REFERENCES matches(id)
            );
            CREATE INDEX IF NOT EXISTS ix_predictions_created ON predictions(created_at DESC);
            CREATE TABLE IF NOT EXISTS xi_calibrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT NOT NULL,
                created_at TEXT NOT NULL,
                selected_xi REAL NOT NULL,
                source_signature TEXT NOT NULL,
                report_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_xi_competition_date
            ON xi_calibrations (competition, id DESC);
            """)

    def upsert_matches(self, matches: list[Match]) -> int:
        when = iso_date(datetime.now(timezone.utc))
        # Validate all before writing any rows.
        data = [(
            m.id, m.competition, iso_date(m.kickoff), m.home_id, m.away_id,
            m.home_name, m.away_name, m.status, m.home_goals, m.away_goals,
            m.season, m.source, when
        ) for m in matches]
        with self.connection() as db:
            db.executemany("""
                INSERT INTO matches
                (id,competition,kickoff,home_id,away_id,home_name,away_name,
                 status,home_goals,away_goals,season,source,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    competition=excluded.competition, kickoff=excluded.kickoff,
                    home_id=excluded.home_id, away_id=excluded.away_id,
                    home_name=excluded.home_name, away_name=excluded.away_name,
                    status=excluded.status, home_goals=excluded.home_goals,
                    away_goals=excluded.away_goals, season=excluded.season,
                    source=excluded.source, updated_at=excluded.updated_at
            """, data)
        return len(data)

    @staticmethod
    def from_row(row):
        return Match(
            id=row["id"], competition=row["competition"], kickoff=utc_datetime(row["kickoff"]),
            home_id=row["home_id"], away_id=row["away_id"],
            home_name=row["home_name"], away_name=row["away_name"],
            status=row["status"], home_goals=row["home_goals"],
            away_goals=row["away_goals"], season=row["season"], source=row["source"]
        )

    def get_match(self, match_id: str) -> Match | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        return self.from_row(row) if row else None

    def matches(self, competition: str, *, before: datetime | None = None, finished=False,
                upcoming=False, limit: int | None = None) -> list[Match]:
        query = "SELECT * FROM matches WHERE competition=?"
        args: list = [competition]
        if before is not None:
            query += " AND kickoff < ?"
            args.append(iso_date(before))
        if finished:
            query += " AND status='FINISHED' AND home_goals IS NOT NULL AND away_goals IS NOT NULL"
        if upcoming:
            query += " AND status!='FINISHED' AND kickoff > ?"
            args.append(iso_date(datetime.now(timezone.utc)))
        query += " ORDER BY kickoff " + ("DESC" if finished else "ASC")
        if limit is not None:
            query += " LIMIT ?"
            args.append(min(max(int(limit), 1), 10000))
        with self.connection() as db:
            rows = db.execute(query, args).fetchall()
        result = [self.from_row(row) for row in rows]
        return list(reversed(result)) if finished else result

    def competitions(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("""SELECT competition,
            SUM(CASE WHEN status='FINISHED' THEN 1 ELSE 0 END) AS finished,
            SUM(CASE WHEN status!='FINISHED' THEN 1 ELSE 0 END) AS scheduled,
            COUNT(*) AS total
            FROM matches GROUP BY competition ORDER BY competition""").fetchall()
        return [dict(x) for x in rows]

    def teams(self, competition: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("""
               SELECT team_id,MAX(team_name) AS team_name,COUNT(*) AS played FROM (
                   SELECT home_id AS team_id, home_name AS team_name, status FROM matches WHERE competition=?
                   UNION ALL
                   SELECT away_id AS team_id, away_name AS team_name, status FROM matches WHERE competition=?
               ) WHERE status='FINISHED' GROUP BY team_id ORDER BY team_name
            """, (competition,competition)).fetchall()
        return [dict(x) for x in rows]

    def finalize_manual(self, match_id: str, home_goals: int, away_goals: int) -> Match:
        game=self.get_match(match_id)
        if game is None:
            raise ValueError("Match introuvable.")
        if game.source!="manual" or not game.id.startswith("manual:"):
            raise ValueError("Seules les rencontres créées manuellement peuvent être clôturées ici.")
        if game.status=="FINISHED":
            raise ValueError("Un résultat final est déjà enregistré.")
        if game.kickoff>datetime.now(timezone.utc):
            raise ValueError("Impossible de saisir un résultat avant le coup d'envoi.")
        if type(home_goals) is not int or type(away_goals) is not int or min(home_goals,away_goals)<0:
            raise ValueError("Les buts doivent être des entiers non négatifs.")
        from dataclasses import replace
        final=replace(game,status="FINISHED",home_goals=home_goals,away_goals=away_goals)
        self.upsert_matches([final])
        return final

    def save_prediction(self, match_id: str, cutoff: datetime, result: dict) -> str:
        pred_id = uuid4().hex
        now = iso_date(datetime.now(timezone.utc))
        with self.connection() as db:
            db.execute("INSERT INTO predictions(id,match_id,created_at,cutoff,result_json) VALUES(?,?,?,?,?)",
                       (pred_id, match_id, now, iso_date(cutoff), json.dumps(result,ensure_ascii=False)))
        return pred_id

    def predictions(self, limit: int = 100) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("""SELECT p.id AS prediction_id,p.created_at,p.cutoff,p.result_json,
            m.status,m.home_goals,m.away_goals FROM predictions p
            INNER JOIN matches m ON m.id=p.match_id
            ORDER BY p.created_at DESC,p.rowid DESC LIMIT ?""", (min(max(int(limit),1),500),)).fetchall()
        out=[]
        for row in rows:
            data=json.loads(row["result_json"])
            best=data["top_scores"][0]
            actual = None
            correct = None
            if row["status"]=="FINISHED":
                actual=f"{row['home_goals']}-{row['away_goals']}"
                correct=(row["home_goals"]==best["home"] and row["away_goals"]==best["away"])
            out.append({"id":row["prediction_id"],"created_at":row["created_at"],
                        "cutoff":row["cutoff"],"prediction":data,"actual_score":actual,
                        "correct":correct})
        return out

    def save_xi_calibration(self, report: dict) -> int:
        """Store the exact calibration report (append-only, reproducible)."""
        if not isinstance(report,dict) or report.get("n_scored",0)<1:
            raise ValueError("Rapport de calibration incomplet.")
        competition=report["competition"]
        xi=report["selected_xi"]
        if type(xi) not in (int,float) or not 0<=xi<=0.3:
            raise ValueError("xi calibré invalide.")
        payload=json.dumps(report,ensure_ascii=False,allow_nan=False,sort_keys=True)
        with self.connection() as db:
            cursor=db.execute("""INSERT INTO xi_calibrations
                    (competition,created_at,selected_xi,source_signature,report_json)
                    VALUES(?,?,?,?,?)""",
                    (competition,iso_date(datetime.now(timezone.utc)),xi,
                     report["data_signature_sha256"],payload))
            return cursor.lastrowid

    def latest_xi_calibration(self, competition: str) -> dict | None:
        with self.connection() as db:
            row=db.execute("""SELECT id,report_json FROM xi_calibrations
                           WHERE competition=? ORDER BY id DESC LIMIT 1""",
                           (competition,)).fetchone()
        if row:
            result=json.loads(row["report_json"])
            result["calibration_id"]=row["id"]
            return result
        # A committed, audited real-data calibration is available to a fresh
        # install even before the user creates a local SQLite calibration row.
        packaged=Path(__file__).parent / "calibrations" / "eng-premier-league.json"
        if competition=="of:ENG-PL" and packaged.is_file():
            result=json.loads(packaged.read_text(encoding="utf-8"))
            if (result.get("competition")==competition
                    and result.get("data_source")==["openfootball/football.json"]
                    and result.get("n_scored",0)>=100
                    and 0<=result.get("selected_xi",-1)<=0.3):
                result["calibration_id"]="validated_packaged_report"
                return result
        return None
