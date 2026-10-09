"""H2H BSD hybride : historique local prioritaire, API en complément.

Pour le backtesting, aucune requête API H2H : le résumé externe peut avoir
été recalculé après le coup d'envoi, ce qui causerait une fuite de données.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bsd_api import BSDClient


def _utc(value: str) -> datetime:
    if not value:
        raise ValueError("Date du match absente")
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Date UTC sans fuseau horaire")
    return parsed.astimezone(timezone.utc)


def _team_id(row: Dict[str, Any], side: str) -> Optional[int]:
    value = row.get(side + "_team_id")
    if value is None:
        team = row.get(side + "_team")
        if isinstance(team, dict):
            value = team.get("id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _valid_score(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = int(value)
        return n if n >= 0 and str(value).strip() == str(n) else None
    except (TypeError, ValueError):
        return None


def _completed(row: Dict[str, Any]) -> bool:
    # On exige le statut terminé, et jamais un résultat prévu ou interrompu.
    return str(row.get("status") or "").lower() == "finished"


def local_h2h(
    events: Iterable[Dict[str, Any]],
    home_team_id: int,
    away_team_id: int,
    kickoff: str,
    *,
    years: int = 3,
    recent_limit: int = 10,
) -> Dict[str, Any]:
    """Agrège uniquement les matchs achevés AVANT kickoff, toutes saisons incluses."""
    home_team_id, away_team_id = int(home_team_id), int(away_team_id)
    if home_team_id <= 0 or away_team_id <= 0 or home_team_id == away_team_id:
        raise ValueError("Identifiants d'équipes BSD distincts et positifs requis")
    if not 1 <= years <= 15:
        raise ValueError("Fenêtre H2H invalide")
    cutoff = _utc(kickoff)
    earliest = cutoff - timedelta(days=366 * years)
    meetings: List[Tuple[datetime, Dict[str, Any]]] = []
    seen = set()
    for row in events:
        if not isinstance(row, dict) or not _completed(row):
            continue
        hid, aid = _team_id(row, "home"), _team_id(row, "away")
        if {hid, aid} != {home_team_id, away_team_id}:
            continue
        event_id = row.get("id")
        if event_id is None or str(event_id) in seen:
            continue
        hs, aws = _valid_score(row.get("home_score")), _valid_score(row.get("away_score"))
        if hs is None or aws is None:
            continue
        try:
            played = _utc(str(row.get("event_date") or ""))
        except ValueError:
            continue
        if not earliest <= played < cutoff:
            continue
        seen.add(str(event_id))
        if hid == home_team_id:
            home_goals, away_goals = hs, aws
        else:
            home_goals, away_goals = aws, hs
        meetings.append((played, {
            "event_id": event_id,
            "date": played.isoformat(),
            "home_team_id": hid,
            "away_team_id": aid,
            "home_score": hs,
            "away_score": aws,
            "fixture_home_goals": home_goals,
            "fixture_away_goals": away_goals,
        }))
    meetings.sort(key=lambda pair: pair[0], reverse=True)
    total = len(meetings)
    home_wins = sum(m["fixture_home_goals"] > m["fixture_away_goals"] for _, m in meetings)
    away_wins = sum(m["fixture_home_goals"] < m["fixture_away_goals"] for _, m in meetings)
    draws = total - home_wins - away_wins
    home_goals = sum(m["fixture_home_goals"] for _, m in meetings)
    away_goals = sum(m["fixture_away_goals"] for _, m in meetings)
    return {
        "source": "local",
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "as_of": cutoff.isoformat(),
        "total_matches": total,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "avg_total_goals": round((home_goals + away_goals) / total, 3) if total else None,
        "home_win_rate": round(home_wins / total, 4) if total else None,
        "away_win_rate": round(away_wins / total, 4) if total else None,
        "recent_matches": [m for _, m in meetings[:recent_limit]],
    }


def hybrid_h2h(
    client: Optional[BSDClient],
    fixture: Dict[str, Any],
    local_events: Iterable[Dict[str, Any]],
    *,
    min_local_meetings: int = 3,
    allow_api: bool = True,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    hid, aid = _team_id(fixture, "home"), _team_id(fixture, "away")
    if hid is None or aid is None:
        return {"source": "unavailable", "reason": "team_ids_missing", "total_matches": 0}
    kickoff = str(fixture.get("event_date") or "")
    try:
        cutoff = _utc(kickoff)
        local = local_h2h(local_events, hid, aid, kickoff)
    except (TypeError, ValueError):
        return {"source": "unavailable", "reason": "invalid_fixture", "total_matches": 0}
    if local["total_matches"] >= min_local_meetings:
        return local

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Horloge UTC consciente du fuseau requise")
    # Interdit d'appeler le H2H courant pour une rencontre historique ou déjà commencée.
    if not allow_api or client is None or cutoff <= now.astimezone(timezone.utc):
        return {**local, "api_skipped": "historical_or_disabled"}

    event_id = fixture.get("id")
    if event_id is None:
        return {**local, "api_skipped": "fixture_id_missing"}
    remote = client.get_h2h(int(event_id), ttl=86400)
    if remote is None:
        return local
    if isinstance(remote, dict) and isinstance(remote.get("head_to_head"), dict):
        remote = remote["head_to_head"]
    if not isinstance(remote, dict):
        return {**local, "api_skipped": "unexpected_h2h_schema"}
    try:
        total = int(remote.get("total_matches", 0))
    except (TypeError, ValueError):
        return {**local, "api_skipped": "invalid_remote_total"}
    if total <= local["total_matches"]:
        return local
    if any(remote.get(k) is None for k in ("home_wins", "away_wins", "draws")):
        return {**local, "api_skipped": "missing_remote_counts"}
    try:
        hw, aw, dr = [int(remote[k]) for k in ("home_wins", "away_wins", "draws")]
    except (TypeError, ValueError):
        return {**local, "api_skipped": "invalid_remote_counts"}
    if min(hw, aw, dr) < 0 or hw + aw + dr != total:
        return {**local, "api_skipped": "inconsistent_remote_counts"}
    return {
        **remote,
        "source": "api",
        "home_team_id": hid,
        "away_team_id": aid,
        "as_of": cutoff.isoformat(),
        "local_meetings": local["total_matches"],
    }
