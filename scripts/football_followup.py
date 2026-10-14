#!/usr/bin/env python3
"""Fil rouge Actu Foot : suivi persistant de rencontres effectivement annoncées.

Un match ne devient suivi qu'après succès Telegram de son AVANT-MATCH.
La sélection est partagée entre cron complet (30 min) et cycle live (10 min)
via le même historique, mais isolée par destination (test/production).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

MAX_FOLLOWED = 8
MAX_AFTER_KICKOFF = timedelta(hours=10)
PREMATCH_WINDOW = (timedelta(minutes=60), timedelta(minutes=120))
TRACK_WINDOW_BEFORE = timedelta(hours=4)
TRACK_WINDOW_AFTER = timedelta(hours=6)


def moment(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def name(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    if isinstance(value, dict):
        value = value.get("name") or value.get("displayName")
    return str(value or "").strip()


def norm(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    ascii_text = re.sub(r"\b(fc|cf|sc|afc|club|the|de|da|do|football)\b", " ", ascii_text)
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def kickoff(event: dict) -> datetime | None:
    return moment(event.get("event_date") or event.get("date") or event.get("start_time"))


def key(event: dict) -> str:
    when = kickoff(event)
    home, away = norm(name(event, "home")), norm(name(event, "away"))
    if not when or not home or not away:
        return ""
    return f"{when:%Y%m%d}:{home}:{away}"


def active(tracked: dict, now: datetime) -> dict:
    """Conserve aussi les matchs terminés quelques heures pour la réaction."""
    now = now.astimezone(timezone.utc)
    result = {}
    for identifier, item in tracked.items():
        if not isinstance(item, dict):
            continue
        start = moment(item.get("event_date"))
        if not start or start > now + timedelta(days=2) or start < now - MAX_AFTER_KICKOFF:
            continue
        result[identifier] = item
    return result


def pending(tracked: dict, now: datetime) -> dict:
    return {k: v for k, v in active(tracked, now).items()
            if not v.get("final_sent") and not v.get("cancelled")}


def selection_allowed(tracked: dict, now: datetime) -> bool:
    return len(pending(tracked, now)) < MAX_FOLLOWED


def track(tracked: dict, event: dict, now: datetime, *, reason: str = "auto") -> str:
    """Ajoute une rencontre au suivi technique sans exiger une publication AVANT-MATCH.

    Le suivi interne et la sélection éditoriale sont volontairement découplés :
    un gros match peut donc produire un but/carton/résultat même si aucun
    avant-match Telegram n'a été publié.
    """
    identifier = key(event)
    if not identifier:
        raise ValueError("Rencontre sans date ou équipes : suivi impossible")
    if identifier in tracked:
        return identifier
    if not selection_allowed(tracked, now):
        raise ValueError("Capacité de suivi atteinte")
    start = kickoff(event)
    if not start:
        raise ValueError("Suivi impossible sans heure de coup d'envoi")
    delta = start - now.astimezone(timezone.utc)
    if delta > TRACK_WINDOW_BEFORE or delta < -TRACK_WINDOW_AFTER:
        raise ValueError("Rencontre hors fenêtre de suivi technique")
    tracked[identifier] = {
        "home_team": name(event, "home"),
        "away_team": name(event, "away"),
        "event_date": start.isoformat(),
        "league_name": str(event.get("league_name") or event.get("competition_name") or "Football"),
        "home_logo": _logo(event, "home"),
        "away_logo": _logo(event, "away"),
        "bsd_id": str(event.get("id") or ""),
        "selected_at": now.astimezone(timezone.utc).isoformat(),
        "tracking_reason": reason,
        "final_sent": False,
    }
    return identifier


def follow(tracked: dict, event: dict, now: datetime) -> str:
    """Compatibilité AVANT-MATCH : valide sa fenêtre puis utilise le suivi technique."""
    identifier = key(event)
    if identifier in tracked:
        return identifier
    start = kickoff(event)
    if not start or not PREMATCH_WINDOW[0] <= start - now <= PREMATCH_WINDOW[1]:
        raise ValueError("Avant-match hors fenêtre")
    return track(tracked, event, now, reason="avant_match")


def _logo(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    if isinstance(value, dict):
        return str(value.get("logo") or value.get("logo_url") or "")
    return str(event.get(side + "_logo") or "")


def base_events(tracked: dict, now: datetime) -> list[dict]:
    """Crée les fixtures de référence pour ESPN / cache Supabase, sans BSD."""
    result = []
    for identifier, value in pending(tracked, now).items():
        result.append({
            "id": value.get("bsd_id") or identifier,
            "follow_ref": identifier,
            "home_team": {"name": value["home_team"], "logo": value.get("home_logo") or ""},
            "away_team": {"name": value["away_team"], "logo": value.get("away_logo") or ""},
            "event_date": value["event_date"],
            "league_name": value.get("league_name") or "Football",
        })
    return result


def completed(tracked: dict, ref: str, now: datetime) -> None:
    if ref in tracked:
        tracked[ref]["final_sent"] = True
        tracked[ref]["finished_at"] = now.astimezone(timezone.utc).isoformat()


def same_fixture(event: dict, follow: dict) -> bool:
    """Compare deux équipes ET la date : évite un autre match portant un nom semblable."""
    from football_match_lifecycle import _tokens_similarity
    start, reference = kickoff(event), moment(follow.get("event_date"))
    if not start or not reference or abs((start-reference).total_seconds()) > 3 * 3600:
        return False
    return (_tokens_similarity(name(event, "home"), follow.get("home_team") or "") >= 0.45
            and _tokens_similarity(name(event, "away"), follow.get("away_team") or "") >= 0.45)


def tracked_fixture(event: dict, tracked: dict, now: datetime) -> str | None:
    for identifier, item in pending(tracked, now).items():
        if same_fixture(event, item):
            return identifier
    return None
