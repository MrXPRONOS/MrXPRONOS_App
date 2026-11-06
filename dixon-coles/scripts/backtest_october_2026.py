"""Reproducible October 2026 Premier League backtest (no look-ahead).

Inputs: CC0 OpenFootball historic PL seasons (through 2026-09-30) and a
cross-checked October 2026 results CSV. This script never trains on matches
from October 2026 or later; it is a retrospective *monthly* forecast made
at 2026-10-01T00:00Z, not match-by-match daily retraining.

October match results were transcribed from:
https://statsnext.com/premier-league/matches/2026-10
and cross-checked against:
https://bbcinsight.pages.dev/sport/football/premier-league/scores-fixtures/2026-10?filter=results

These are factual results reported by third parties, not certified records.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import sys
from pathlib import Path

from dcscore.domain import Match
from dcscore.openfootball import (
    COMPETITION, _team_name_id, download_openfootball_season,
)
from dcscore.service import backtest
from dcscore.store import Store

UTC = timezone.utc
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 11, 1, tzinfo=UTC)
SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27")
EXPECTED = 38
SCORE_SOURCE = "statsnext.com/premier-league/matches/2026-10"
VERIFY_SOURCE = "bbcinsight.pages.dev/sport/football/premier-league/scores-fixtures/2026-10?filter=results"


def october_matches(path: Path, valid_teams: set[str]) -> tuple[list[Match], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    content = raw.decode("utf-8-sig")
    out = []
    names = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"date", "home", "away", "home_goals", "away_goals"}
        if not reader.fieldnames or set(reader.fieldnames) != required:
            raise ValueError("Colonnes de résultats octobre inattendues")
        for index, row in enumerate(reader, start=2):
            try:
                if any(not row.get(k) for k in required):
                    raise ValueError("Champ obligatoire absent")
                day = datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=UTC)
                if not START <= day < END:
                    raise ValueError("Hors du mois d'octobre 2026")
                home = row["home"].strip(); away = row["away"].strip()
                if home == away or home not in valid_teams or away not in valid_teams:
                    raise ValueError("Équipes non concordantes avec OpenFootball 2026-27")
                score1, score2 = int(row["home_goals"]), int(row["away_goals"])
                if score1 < 0 or score2 < 0:
                    raise ValueError("Score négatif")
                key = (row["date"], home, away)
                if key in names:
                    raise ValueError("Résultat dupliqué")
                names.add(key)
                ident = hashlib.sha256(("|".join(key)).encode()).hexdigest()[:24]
                out.append(Match(
                    id="oct2026:" + ident, competition=COMPETITION, kickoff=day,
                    home_id=_team_name_id(home), away_id=_team_name_id(away),
                    home_name=home, away_name=away, home_goals=score1,
                    away_goals=score2, status="FINISHED", season="2026-27",
                    source=SCORE_SOURCE, result_provenance="provider_reported",
                    neutral_venue=False,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Ligne {index} invalide : {exc}") from exc
    if len(out) != EXPECTED:
        raise ValueError(f"Attendu {EXPECTED} résultats, trouvé {len(out)}")
    return out, digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backtest Dixon-Coles sur octobre 2026")
    parser.add_argument("--db", required=True, help="Base de données SQLite temporaire vierge")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--xi", type=float, default=0.0065)
    args = parser.parse_args(argv)
    if Path(args.db).exists():
        raise RuntimeError("Refus d'utiliser une base déjà existante : fournir un chemin vierge")
    store = Store(args.db)
    sources = []
    valid_teams = set()
    all_rows = []
    for season in SEASONS:
        rows, meta = download_openfootball_season(season, as_of=START)
        if season == "2026-27":
            valid_teams = {m.home_name for m in rows} | {m.away_name for m in rows}
        finished = [m for m in rows if m.status == "FINISHED" and m.kickoff < START]
        sources.append({**meta, "loaded_past_results": len(finished)})
        all_rows.extend(finished)
    if len(all_rows) < 1800 or len(valid_teams) != 20:
        raise RuntimeError("Historique de formation insuffisant ou clubs 2026-27 incomplets")
    store.upsert_matches(all_rows)
    oct_rows, csv_digest = october_matches(Path(args.csv), valid_teams)
    store.upsert_matches(oct_rows)
    # Strictly require only the October 2026 38 matches to be in the
    # validation target. Do not silently switch to another month.
    all_finished = store.matches(COMPETITION, finished=True)
    latest = [m for m in all_finished if m.kickoff >= START]
    if len(latest) != EXPECTED or any(m.kickoff >= END for m in latest):
        raise RuntimeError("Période cible contaminée : des matchs hors octobre sont présents")
    result = backtest(store, COMPETITION, n_samples=EXPECTED,
                      min_games=400, min_team=5, xi=args.xi)
    if result['n_requested'] != EXPECTED or result['n_folds'] != 1:
        raise RuntimeError("Le backtest n'évalue pas exactement un mois")
    if result['n_evaluated'] + result['n_skipped'] != EXPECTED:
        raise RuntimeError("Il manque des résultats dans l'évaluation")
    if any(not row['kickoff'].startswith('2026-10') for row in result['detailed']):
        raise RuntimeError("Des scores hors octobre sont évalués")
    if any(fold['start'] != '2026-10-01T00:00:00Z' or
           fold['last_training_match'] >= '2026-10-01T00:00:00Z'
           for fold in result['folds']):
        raise RuntimeError("Fuite temporelle : une rencontre d'octobre aurait été utilisée à l'entraînement")
    # Model choice is calibrated on August 2025 - May 2026 only, not on
    # the 38 October results. The retrospective rule was implemented after
    # October and must NOT be misrepresented as a live October forecast.
    choice=store.latest_model_selection(COMPETITION)
    if choice is None:
        raise RuntimeError("Rapport de sélection pré-octobre absent : ne pas choisir le modèle a posteriori.")
    if choice['validation_end_exclusive']>START.date().isoformat():
        raise RuntimeError("Choix de modèle contaminé par la période testée.")
    if choice['selected_model'] not in ('dixon_coles','poisson'):
        raise RuntimeError("Modèle choisi invalide.")
    method=choice['selected_model']
    loss_key='dc_log_loss' if method=='dixon_coles' else 'poisson_independent_log_loss'
    score_key='best' if method=='dixon_coles' else 'poisson_best_score'
    top3_key='top_three' if method=='dixon_coles' else 'poisson_top_three'
    auto={
        'selected_model_from_pre_october_validation':method,
        'validation_start':choice['validation_start'],
        'validation_end_exclusive':choice['validation_end_exclusive'],
        'validation_matches':choice['n_scored'],
        'mean_exact_score_log_loss':sum(x[loss_key] for x in result['detailed'])/len(result['detailed']),
        'top1_hit_rate':sum(x['actual']==x[score_key] for x in result['detailed'])/len(result['detailed']),
        'top3_hit_rate':sum(x['actual'] in x[top3_key] for x in result['detailed'])/len(result['detailed']),
        'top1_one_one_count':sum(x[score_key]=='1-1' for x in result['detailed']),
        'note':('Règle calibrée uniquement sur la saison 2025–26. '
                'La méthode a été ajoutée rétrospectivement après octobre : '
                'ce résultat ne constitue pas un essai prospectif.'),
    }
    report = {
        'automatic_model_choice':auto,
        "period_start_inclusive": START.isoformat(),
        "period_end_exclusive": END.isoformat(),
        "competition": COMPETITION,
        "model": "Dixon-Coles V1.2",
        "xi": args.xi,
        "test_method": "one monthly refit 2026-10-01; no October final scores in training",
        "data_notes": "Fixture dates only; exact kickoffs not available in CSV. Times represented as 00:00Z, but training stops at 2026-10-01.",
        "train_historic_count": len(all_rows),
        "sources": {
            "training": sources,
            "october_results": {
                "url": "https://" + SCORE_SOURCE,
                "crosscheck_url": "https://" + VERIFY_SOURCE,
                "license": "third party match facts, not certified",
                "csv_sha256": csv_digest,
                "n_matches": len(oct_rows),
            },
        },
        "metrics": result,
    }
    dest = Path(args.output)
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("BACKTEST OCTOBRE 2026 — PREMIER LEAGUE")
    print(f"Historique avant le 1er octobre: {len(all_rows)} rencontres")
    print(f"Matchs en octobre vérifiés: {len(oct_rows)}")
    print(f"Matchs évalués: {result['n_evaluated']}/{EXPECTED} ; ignorés: {result['n_skipped']}")
    print(f"Top 1: {result['top1_hit_rate']:.4%}  | Top 3: {result['top3_hit_rate']:.4%}")
    print(f"Log loss DC: {result['mean_dc_log_loss']:.6f} | Poisson indépendant: {result['mean_poisson_independent_log_loss']:.6f}")
    print(f"Log loss Poisson aux mêmes intensités DC: {result['mean_poisson_same_intensities_log_loss']:.6f}")
    print(f"Mode de repli automatique pré-octobre: {auto['selected_model_from_pre_october_validation']}")
    print(f"Log loss automatique octobre: {auto['mean_exact_score_log_loss']:.6f}")
    print(f"Top1 automatique: {auto['top1_hit_rate']:.4%} ; Top3: {auto['top3_hit_rate']:.4%} ; Mode 1-1: {auto['top1_one_one_count']}/38")
    print(f"Brier 1N2: {result['mean_one_x_two_brier']:.6f}")
    print(f"Rapport détaillé: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
