#!/usr/bin/env python3
"""Fil rouge Actu Foot : suivi persistant de rencontres effectivement annoncées.

Une grande affiche devient suivie après admission du ranking ou succès Telegram de son AVANT-MATCH.
La sélection est partagée entre cron complet (30 min) et cycle live (10 min)
via le même historique, mais isolée par destination (test/production). Le plafond volontairement bas concentre le fil rouge sur les 4 affiches les plus importantes.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

MAX_FOLLOWED = 4
MAX_AFTER_KICKOFF = timedelta(hours=10)

LIVE_AFTER_KICKOFF = {
    "goal", "carton_rouge", "carton_jaune", "remplacement", "score_update",
    "mi_temps", "debut_2e_mi_temps", "temps_additionnel", "prolongation",
    "mi_temps_prolongation", "tirs_au_but", "tir_au_but_marque",
    "tir_au_but_manque", "fin_tirs_au_but", "resultat",
}
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


def locked_pending(tracked: dict, now: datetime) -> dict:
    """Suivis qui ont effectivement été admis par le ranking actuel."""
    return {
        k: v for k, v in pending(tracked, now).items()
        if bool(v.get("ranking_locked"))
    }


def selection_allowed(tracked: dict, now: datetime) -> bool:
    # Les anciens suivis créés avant le ranking sticky ne doivent pas bloquer
    # les nouvelles admissions tant qu'ils n'ont pas été revalidés.
    return len(locked_pending(tracked, now)) < MAX_FOLLOWED


def lock(tracked: dict, ref: str, now: datetime, *, reason: str | None = None) -> None:
    if ref not in tracked or not isinstance(tracked[ref], dict):
        return
    tracked[ref]["ranking_locked"] = True
    tracked[ref]["ranking_locked_at"] = now.astimezone(timezone.utc).isoformat()
    if reason and not tracked[ref].get("tracking_reason"):
        tracked[ref]["tracking_reason"] = reason


def lock_selected(tracked: dict, events: list[dict], now: datetime) -> None:
    for event in events:
        ref = str(event.get("follow_ref") or "")
        if ref:
            lock(tracked, ref, now, reason="ranking")


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
        lock(tracked, identifier, now, reason=reason)
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
        # Une fois admis par le ranking, le match reste dans le lifecycle
        # jusqu'au résultat final / abandon. Le ranking décide de l'admission,
        # pas de l'éjection d'un match déjà suivi.
        "ranking_locked": True,
        "planned": bool(event.get("planned", False)),
        "plan_rank": int(event.get("plan_rank") or 99),
        "plan_role": str(event.get("plan_role") or ""),
        "prematch_sent": bool(event.get("prematch_sent", False)),
        "composition_sent": bool(event.get("composition_sent", False)),
        "kickoff_sent": bool(event.get("kickoff_sent", False)),
        "halftime_sent": bool(event.get("halftime_sent", False)),
        "second_half_sent": bool(event.get("second_half_sent", False)),
        "final_sent": False,
    }
    return identifier


def follow(tracked: dict, event: dict, now: datetime) -> str:
    """Valide un AVANT-MATCH effectivement publié et ouvre le récit du match."""
    identifier = key(event)
    if identifier in tracked:
        mark_publication(tracked, identifier, "avant_match", now)
        return identifier
    start = kickoff(event)
    if not start or not PREMATCH_WINDOW[0] <= start - now <= PREMATCH_WINDOW[1]:
        raise ValueError("Avant-match hors fenêtre")
    identifier = track(tracked, event, now, reason="avant_match")
    mark_publication(tracked, identifier, "avant_match", now)
    return identifier


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
            "lineup_home_hash": value.get("lineup_home_hash") or "",
            "lineup_away_hash": value.get("lineup_away_hash") or "",
            "lineup_home": list(value.get("lineup_home") or []),
            "lineup_away": list(value.get("lineup_away") or []),
            # Les états créés avant le ranking sticky n'avaient pas ce champ.
            # Seuls les anciens AVANT-MATCH sont conservés par continuité;
            # les suivis purement techniques doivent repasser le ranking.
            "ranking_locked": bool(
                value.get(
                    "ranking_locked",
                    str(value.get("tracking_reason") or "") == "avant_match",
                )
            ),
            "selected_at": value.get("selected_at") or "",
            "tracking_reason": value.get("tracking_reason") or "",
            "planned": bool(value.get("planned")),
            "plan_rank": int(value.get("plan_rank") or 99),
            "plan_role": value.get("plan_role") or "",
            "prematch_sent": bool(value.get("prematch_sent")),
            "composition_sent": bool(value.get("composition_sent")),
            "kickoff_sent": bool(value.get("kickoff_sent")),
            "halftime_sent": bool(value.get("halftime_sent")),
            "second_half_sent": bool(value.get("second_half_sent")),
        })
    return result


def apply_plan_metadata(tracked: dict, ref: str, plan: dict | None) -> None:
    if ref not in tracked or not isinstance(tracked[ref], dict) or not isinstance(plan, dict):
        return
    tracked[ref]["planned"] = True
    tracked[ref]["plan_rank"] = int(plan.get("rank") or plan.get("plan_rank") or 99)
    tracked[ref]["plan_role"] = str(plan.get("role") or plan.get("plan_role") or "")


def publication_allowed(tracked: dict, ref: str, category: str) -> bool:
    """Machine d'état éditoriale d'un fil rouge.

    Le canal ne doit jamais raconter la fin d'un match qu'il n'a pas commencé.
    L'avant-match ouvre le récit; le coup d'envoi ouvre la phase LIVE.
    """
    item = tracked.get(ref)
    if not isinstance(item, dict):
        return False

    category = str(category or "")
    if category == "avant_match":
        return bool(item.get("planned")) and not item.get("kickoff_sent") and not item.get("final_sent")
    if category == "composition":
        return bool(item.get("prematch_sent")) and not item.get("kickoff_sent") and not item.get("final_sent")
    if category == "changement_composition":
        return (
            bool(item.get("prematch_sent"))
            and bool(item.get("composition_sent"))
            and not item.get("kickoff_sent")
            and not item.get("final_sent")
        )
    if category == "kickoff":
        return bool(item.get("prematch_sent")) and not item.get("kickoff_sent") and not item.get("final_sent")
    if category == "suivi_interrompu":
        # Report/annulation après l'annonce avant-match reste une fin logique
        # même si le coup d'envoi n'a jamais eu lieu.
        return bool(item.get("prematch_sent")) and not item.get("final_sent")
    if category in LIVE_AFTER_KICKOFF:
        if not item.get("kickoff_sent") or item.get("final_sent"):
            return False
        if category == "debut_2e_mi_temps" and item.get("second_half_sent"):
            return False
        return True
    return True


def mark_publication(tracked: dict, ref: str, category: str, now: datetime) -> None:
    item = tracked.get(ref)
    if not isinstance(item, dict):
        return
    stamp = now.astimezone(timezone.utc).isoformat()
    category = str(category or "")
    item["last_publication_category"] = category
    item["last_publication_at"] = stamp
    if category == "avant_match":
        item["prematch_sent"] = True
        item["prematch_sent_at"] = stamp
    elif category == "composition":
        item["composition_sent"] = True
        item["composition_sent_at"] = stamp
    elif category == "kickoff":
        item["kickoff_sent"] = True
        item["kickoff_sent_at"] = stamp
    elif category == "mi_temps":
        item["halftime_sent"] = True
        item["halftime_sent_at"] = stamp
    elif category == "debut_2e_mi_temps":
        item["second_half_sent"] = True
        item["second_half_sent_at"] = stamp


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
