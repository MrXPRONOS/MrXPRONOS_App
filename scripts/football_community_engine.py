#!/usr/bin/env python3
"""Moteur Communauté Actu Foot.

Transforme les données vérifiées des autres systèmes en interactions Telegram :
- vote avant-match ;
- quiz statistique à réponse correcte ;
- débat basé sur une actualité réelle ;
- réaction post-match.

Aucune IA externe et aucune API payante. Les faits de quiz viennent du moteur
statistique Mr XPRONOS. TheSportsDB est disponible comme source gratuite de
métadonnées de secours, mais n'est jamais nécessaire au fonctionnement.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import requests

from football_stats_engine import collect_snapshot, choose_league

TSDB_SEARCH_TEAM = "https://www.thesportsdb.com/api/v1/json/123/searchteams.php"
TSDB_USER_AGENT = "MrXPRONOS-Community/1.0"


def plain(value: Any, limit: int = 200) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()[:limit].rstrip()


def moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def team_name(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    if isinstance(value, dict):
        value = value.get("name") or value.get("displayName")
    return plain(value, 55)


def league_name(event: dict) -> str:
    for key in ("league_name", "competition_name", "tournament_name", "league"):
        value = event.get(key)
        if isinstance(value, dict):
            value = value.get("name")
        text = plain(value, 70)
        if text and text.casefold() not in {"football", "soccer"}:
            return text
    return "Football"


def final_score(event: dict) -> tuple[int, int] | None:
    status = plain(event.get("status"), 30).casefold()
    if status not in {"finished", "ft", "full_time"}:
        return None
    try:
        home = int(event.get("home_score"))
        away = int(event.get("away_score"))
    except (TypeError, ValueError):
        return None
    return (home, away) if min(home, away) >= 0 else None


def build_match_vote(
    events: list[dict],
    now: datetime,
    importance_fn: Callable[[dict], int],
) -> dict | None:
    """Choisit la meilleure affiche future pour un vote simple."""
    candidates = []
    for event in events:
        kickoff = moment(event.get("event_date") or event.get("start_time"))
        home, away = team_name(event, "home"), team_name(event, "away")
        if not kickoff or not home or not away:
            continue
        delta = kickoff - now
        if not timedelta(minutes=30) <= delta <= timedelta(hours=30):
            continue
        if final_score(event) is not None:
            continue
        score = int(importance_fn(event) or 0)
        candidates.append((score, kickoff, str(event.get("id") or ""), event))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    event = candidates[0][3]
    home, away = team_name(event, "home"), team_name(event, "away")
    kickoff = moment(event.get("event_date") or event.get("start_time"))
    return {
        "kind": "vote_match",
        "key": "community-vote:" + str(event.get("id") or kickoff.isoformat()),
        "question": f"🔥 {home} vs {away} — qui prend les 3 points ?",
        "options": [f"🏠 {home}", "🤝 Match nul", f"✈️ {away}"],
        "league": league_name(event),
        "home": home,
        "away": away,
        "kickoff": kickoff,
    }


def _valid_table(snapshot: dict) -> list[dict]:
    return [
        row for row in (snapshot.get("table") or [])
        if isinstance(row, dict) and plain(row.get("team"), 60)
    ]


def _unique_options(correct: str, candidates: list[str], limit: int = 4) -> list[str]:
    out = [correct]
    seen = {correct.casefold()}
    for value in candidates:
        clean = plain(value, 80)
        if clean and clean.casefold() not in seen:
            out.append(clean)
            seen.add(clean.casefold())
        if len(out) >= limit:
            break
    return out


def _rotate_options(options: list[str], seed: int) -> tuple[list[str], int]:
    if not options:
        return [], -1
    shift = seed % len(options)
    rotated = options[shift:] + options[:shift]
    return rotated, rotated.index(options[0])


def build_stats_quiz(session: requests.Session, day: date) -> dict | None:
    """Question entièrement dérivée d'un classement/top buteurs vérifié."""
    spec = choose_league(day)
    snapshot = collect_snapshot(session, day, spec=spec)
    table = _valid_table(snapshot)
    if len(table) < 4:
        return None

    source = " + ".join(snapshot.get("sources") or [])
    confidence = int(snapshot.get("confidence") or 0)
    if confidence < 70:
        return None

    mode = day.toordinal() % 5
    correct = ""
    question = ""
    explanation = ""
    distractors: list[str] = []

    if mode == 0:
        leader = min(
            table,
            key=lambda row: (row.get("rank") is None, row.get("rank") or 999),
        )
        correct = plain(leader["team"], 70)
        question = f"🏆 Qui est actuellement leader de {snapshot['league']} ?"
        explanation = (
            f"{correct} est classé {leader.get('rank', 1)}e"
            + (f" avec {leader['points']} points." if leader.get("points") is not None else ".")
        )
        distractors = [row["team"] for row in table[1:7]]

    elif mode == 1:
        eligible = [row for row in table if row.get("goals_for") is not None]
        if len(eligible) < 4:
            return None
        best = max(eligible, key=lambda row: int(row.get("goals_for") or 0))
        correct = plain(best["team"], 70)
        question = f"🔥 Quelle équipe a marqué le plus de buts en {snapshot['league']} ?"
        explanation = f"{correct} compte {best['goals_for']} buts marqués."
        distractors = [row["team"] for row in eligible if row is not best]

    elif mode == 2:
        eligible = [row for row in table if row.get("goals_against") is not None]
        if len(eligible) < 4:
            return None
        best = min(
            eligible,
            key=lambda row: (int(row.get("goals_against") or 0), -(row.get("points") or 0)),
        )
        correct = plain(best["team"], 70)
        question = f"🧱 Quelle équipe a encaissé le moins de buts en {snapshot['league']} ?"
        explanation = f"{correct} n'a encaissé que {best['goals_against']} buts."
        distractors = [row["team"] for row in eligible if row is not best]

    elif mode == 3:
        scorers = snapshot.get("top_scorers") or []
        if len(scorers) >= 4:
            best = max(scorers, key=lambda row: int(row.get("goals") or 0))
            correct = plain(best["player"], 70)
            question = f"🎯 Qui est le meilleur buteur actuel de {snapshot['league']} ?"
            explanation = f"{correct} compte {best['goals']} buts."
            distractors = [row["player"] for row in scorers if row is not best]
            source = plain(best.get("source"), 80) or source
        else:
            return build_stats_quiz_for_points(snapshot, day)

    else:
        return build_stats_quiz_for_points(snapshot, day)

    options = _unique_options(correct, distractors)
    if len(options) < 4:
        return None
    options, correct_index = _rotate_options(options, day.toordinal())
    return {
        "kind": "quiz",
        "key": f"community-quiz:{day.isoformat()}:{snapshot['league_key']}:{mode}",
        "question": question,
        "options": options,
        "correct_option_ids": [correct_index],
        "explanation": explanation + (f" Source : {source}." if source else ""),
        "source": source,
        "confidence": confidence,
        "league": snapshot["league"],
    }


def build_stats_quiz_for_points(snapshot: dict, day: date) -> dict | None:
    table = _valid_table(snapshot)
    eligible = [row for row in table if row.get("points") is not None]
    if len(eligible) < 4:
        return None
    selected = eligible[:4]
    best = max(selected, key=lambda row: int(row["points"]))
    correct = plain(best["team"], 70)
    options = _unique_options(correct, [row["team"] for row in selected if row is not best])
    if len(options) < 4:
        return None
    options, correct_index = _rotate_options(options, day.toordinal() + 2)
    source = " + ".join(snapshot.get("sources") or [])
    return {
        "kind": "quiz",
        "key": f"community-quiz:{day.isoformat()}:{snapshot['league_key']}:points",
        "question": f"📊 Laquelle de ces équipes a le plus de points en {snapshot['league']} ?",
        "options": options,
        "correct_option_ids": [correct_index],
        "explanation": f"{correct} compte {best['points']} points. Source : {source}.",
        "source": source,
        "confidence": int(snapshot.get("confidence") or 0),
        "league": snapshot["league"],
    }


def build_news_debate(news: list[dict], day: date) -> dict | None:
    """Débat à partir d'une vraie news déjà collectée par le système 1."""
    ranked = []
    for item in news:
        if not isinstance(item, dict):
            continue
        title = plain(item.get("title"), 220)
        summary = plain(item.get("summary_short") or item.get("summary"), 320)
        slug = plain(item.get("slug"), 80)
        published = moment(item.get("published"))
        if not title or not summary or not slug or not published:
            continue
        if datetime.now(timezone.utc) - published > timedelta(hours=36):
            continue
        ranked.append((
            int(item.get("editorial_score") or 0),
            published,
            item,
        ))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    item = ranked[day.toordinal() % min(len(ranked), 5)][2]
    title = plain(item.get("title"), 220)
    summary = plain(item.get("summary_short") or item.get("summary"), 300)
    return {
        "kind": "debate",
        "key": "community-debate:" + plain(item.get("slug"), 80),
        "title": title,
        "summary": summary,
        "source": plain(item.get("source"), 70),
        "url": plain(item.get("site_url"), 400),
        "question": "💬 Tu es d'accord, ou pas du tout ? Explique ton point de vue en commentaire.",
    }


def build_postmatch_reaction(
    events: list[dict],
    now: datetime,
    importance_fn: Callable[[dict], int],
) -> dict | None:
    """Sondage subjectif uniquement après une vraie grosse affiche terminée."""
    candidates = []
    for event in events:
        result = final_score(event)
        kickoff = moment(event.get("event_date") or event.get("start_time"))
        if result is None or kickoff is None:
            continue
        # Approximation volontairement large : un match fini dans la fenêtre de la soirée.
        if not now - timedelta(hours=5) <= kickoff <= now:
            continue
        home, away = team_name(event, "home"), team_name(event, "away")
        if not home or not away:
            continue
        imp = int(importance_fn(event) or 0)
        if imp <= 0:
            continue
        candidates.append((imp, kickoff, str(event.get("id") or ""), event, result))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -x[1].timestamp(), x[2]))
    _, _, _, event, result = candidates[0]
    home, away = team_name(event, "home"), team_name(event, "away")
    hs, aws = result
    return {
        "kind": "reaction",
        "key": "community-reaction:" + str(event.get("id") or ""),
        "question": f"⭐ {home} {hs}-{aws} {away} — ta note pour ce match ?",
        "options": ["🔥 5/5", "✅ 4/5", "🙂 3/5", "😕 2/5 ou moins"],
        "league": league_name(event),
    }



def build_tsdb_club_quiz(session: requests.Session, day: date) -> dict | None:
    """Fallback gratuit stable avec la clé publique TheSportsDB 123.

    Le compte gratuit documente explicitement Arsenal pour searchteams ; on
    limite volontairement ce fallback à ce club au lieu de supposer que toutes
    les recherches dynamiques sont accessibles avec la clé de test.
    """
    meta = fetch_tsdb_team_metadata(session, "Arsenal")
    if not meta:
        return None

    year = plain(meta.get("formed_year"), 8)
    country = plain(meta.get("country"), 50)
    if day.toordinal() % 2 == 0 and year.isdigit():
        correct = year
        value = int(year)
        distractors = [str(value - 5), str(value + 5), str(value + 10)]
        options, correct_index = _rotate_options(
            _unique_options(correct, distractors), day.toordinal()
        )
        if len(options) < 4:
            return None
        return {
            "kind": "quiz",
            "key": f"community-quiz-tsdb:{day.isoformat()}:arsenal-year",
            "question": "🏟️ En quelle année Arsenal a-t-il été fondé ?",
            "options": options,
            "correct_option_ids": [correct_index],
            "explanation": f"Arsenal a été fondé en {correct}. Source : TheSportsDB.",
            "source": "TheSportsDB",
            "confidence": 82,
            "league": "Culture foot",
        }

    if country:
        correct = country
        distractors = ["Spain", "Italy", "Germany", "France", "England"]
        options, correct_index = _rotate_options(
            _unique_options(correct, [x for x in distractors if x.casefold() != correct.casefold()]),
            day.toordinal(),
        )
        if len(options) < 4:
            return None
        return {
            "kind": "quiz",
            "key": f"community-quiz-tsdb:{day.isoformat()}:arsenal-country",
            "question": "🌍 Dans quel pays évolue Arsenal ?",
            "options": options,
            "correct_option_ids": [correct_index],
            "explanation": f"Arsenal évolue en {correct}. Source : TheSportsDB.",
            "source": "TheSportsDB",
            "confidence": 82,
            "league": "Culture foot",
        }
    return None


def fetch_tsdb_team_metadata(session: requests.Session, team: str) -> dict:
    """Source gratuite supplémentaire, uniquement comme métadonnée de secours."""
    try:
        response = session.get(
            TSDB_SEARCH_TEAM,
            params={"t": team},
            headers={"User-Agent": TSDB_USER_AGENT},
            timeout=(6, 16),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return {}
    rows = payload.get("teams") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    target = re.sub(r"[^a-z0-9]", "", team.casefold())
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = plain(row.get("strTeam"), 80)
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if not name or (target and key != target):
            continue
        return {
            "source": "TheSportsDB",
            "team": name,
            "stadium": plain(row.get("strStadium"), 100),
            "formed_year": plain(row.get("intFormedYear"), 8),
            "country": plain(row.get("strCountry"), 60),
        }
    return {}
