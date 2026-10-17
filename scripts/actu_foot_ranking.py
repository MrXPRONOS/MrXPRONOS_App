#!/usr/bin/env python3
"""Moteur pur de classement LIVE Actu Foot.

Ce module ne collecte aucune donnée et n'envoie rien sur Telegram. Il encapsule
uniquement les règles déjà validées d'éligibilité, score de popularité, Top N
par compétition, dominance gap, priorité Togo, sticky lock et plafond global.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class RankingDeps:
    league: Callable[[dict], str]
    team: Callable[[dict, str], str]
    importance: Callable[[dict], int]
    kick: Callable[[dict], datetime | None]
    follow_key: Callable[[dict], str]
    excluded_level_terms: Sequence[str]
    national_team_terms: Sequence[str]
    team_weights: Any
    club_priority: Callable[[dict], tuple[int, int]] | None = None


def _weighted_term_score(value: str, weighted_terms: Any) -> int:
    score_value = 0
    for weight, terms in weighted_terms:
        if any(term in value for term in terms):
            score_value = max(score_value, int(weight))
    return score_value


class LiveRankingEngine:
    def __init__(self, deps: RankingDeps):
        self.deps = deps
        self.last_ranking: dict[str, Any] = {}

    def competition_key(self, event: dict) -> str:
        raw_name = self.deps.league(event)
        name = " ".join(raw_name.casefold().split())

        aliases = (
            ("caf-champions-league", ("caf champions league", "caf ligue des champions")),
            ("afc-champions-league", ("afc champions league",)),
            ("uefa-champions-league", ("uefa champions league",)),
            ("uefa-europa-league", ("uefa europa league",)),
            ("uefa-conference-league", ("uefa conference league", "uefa europa conference league")),
            ("caf-confederation", ("caf confederation",)),
            ("afcon", ("afcon", "africa cup of nations", "coupe d'afrique", "can 20")),
            ("world-cup", ("fifa world cup", "coupe du monde fifa")),
        )
        for key_name, terms in aliases:
            if any(term in name for term in terms):
                return key_name

        exact_aliases = {
            "champions league": "champions-league",
            "ligue des champions": "champions-league",
            "europa league": "uefa-europa-league",
            "conference league": "uefa-conference-league",
            "premier league": "premier-league",
            "english premier league": "premier-league",
            "england premier league": "premier-league",
            "la liga": "la-liga",
            "laliga": "la-liga",
            "spanish la liga": "la-liga",
            "serie a": "serie-a",
            "italian serie a": "serie-a",
            "bundesliga": "bundesliga",
            "german bundesliga": "bundesliga",
            "ligue 1": "ligue-1",
            "french ligue 1": "ligue-1",
            "world cup": "world-cup",
            "coupe du monde": "world-cup",
            "fa cup": "fa-cup",
            "carabao cup": "efl-cup",
            "efl cup": "efl-cup",
            "copa del rey": "copa-del-rey",
            "coppa italia": "coppa-italia",
            "dfb pokal": "dfb-pokal",
            "coupe de france": "coupe-de-france",
            "nations league": "nations-league",
            "uefa nations league": "nations-league",
            "copa america": "copa-america",
            "uefa euro": "uefa-euro",
        }
        if name in exact_aliases:
            return exact_aliases[name]

        normalized = re.sub(
            r"[^a-z0-9]+",
            "-",
            unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode(),
        ).strip("-")
        return normalized or "football"

    def competition_weight(self, event: dict) -> int:
        explicit = {
            "uefa-champions-league": 38,
            "champions-league": 16,
            "world-cup": 30,
            "premier-league": 26,
            "la-liga": 26,
            "serie-a": 26,
            "bundesliga": 26,
            "afcon": 24,
            "uefa-euro": 24,
            "copa-america": 24,
            "ligue-1": 21,
            "uefa-europa-league": 21,
            "caf-champions-league": 21,
            "uefa-conference-league": 16,
            "caf-confederation": 16,
            "afc-champions-league": 16,
            "fa-cup": 16,
            "efl-cup": 16,
            "copa-del-rey": 16,
            "coppa-italia": 16,
            "dfb-pokal": 16,
            "coupe-de-france": 16,
            "nations-league": 16,
        }
        return explicit.get(self.competition_key(event), 0)

    def match_identity(self, event: dict) -> str:
        ref = str(event.get("follow_ref") or "").strip()
        if ref:
            return ref
        try:
            fixture_key = self.deps.follow_key(event)
        except (TypeError, ValueError):
            fixture_key = ""
        if fixture_key:
            return fixture_key
        raw_id = str(event.get("id") or event.get("provider_event_id") or "").strip()
        if raw_id:
            return "id:" + raw_id
        return "|".join((
            self.competition_key(event),
            self.deps.team(event, "home").casefold(),
            self.deps.team(event, "away").casefold(),
            str(self.deps.kick(event) or ""),
        ))

    def club_priority(self, event: dict) -> tuple[int, int]:
        """(nombre de grands clubs, priorité maximale), avec aliases stricts si fournis."""
        if self.deps.club_priority is not None:
            try:
                count, maximum = self.deps.club_priority(event)
                return max(0, int(count)), max(0, int(maximum))
            except (TypeError, ValueError):
                pass
        home = self.deps.team(event, "home").casefold()
        away = self.deps.team(event, "away").casefold()
        home_weight = _weighted_term_score(home, self.deps.team_weights)
        away_weight = _weighted_term_score(away, self.deps.team_weights)
        weights = [value for value in (home_weight, away_weight) if value > 0]
        return len(weights), max(weights, default=0)

    def popularity_breakdown(self, event: dict) -> dict[str, int]:
        league_name = self.deps.league(event).casefold()
        home = self.deps.team(event, "home").casefold()
        away = self.deps.team(event, "away").casefold()
        combined = " ".join((league_name, home, away))
        if any(term in combined for term in self.deps.excluded_level_terms):
            return {
                "competition": 0, "home": 0, "away": 0, "clubs_bonus": 0,
                "home_national": 0, "away_national": 0, "togo": 0,
                "importance": 0, "total": -1000,
            }

        home_weight = _weighted_term_score(home, self.deps.team_weights)
        away_weight = _weighted_term_score(away, self.deps.team_weights)
        competition_weight = self.competition_weight(event)
        clubs_bonus = 28 if home_weight and away_weight else 8 if home_weight or away_weight else 0
        home_national = 16 if any(term in home for term in self.deps.national_team_terms) else 0
        away_national = 16 if any(term in away for term in self.deps.national_team_terms) else 0
        togo_bonus = 100 if ("togo" in home or "togo" in away) else 0
        importance_bonus = min(25, max(0, self.deps.importance(event) // 3))
        total = (
            competition_weight + home_weight + away_weight + clubs_bonus
            + home_national + away_national + togo_bonus + importance_bonus
        )
        return {
            "competition": competition_weight,
            "home": home_weight,
            "away": away_weight,
            "clubs_bonus": clubs_bonus,
            "home_national": home_national,
            "away_national": away_national,
            "togo": togo_bonus,
            "importance": importance_bonus,
            "total": total,
        }

    def popularity_score(self, event: dict) -> int:
        return int(self.popularity_breakdown(event)["total"])

    def popular_match(self, event: dict) -> bool:
        league_name = self.deps.league(event).casefold()
        home = self.deps.team(event, "home").casefold()
        away = self.deps.team(event, "away").casefold()
        combined = " ".join((league_name, home, away))

        if any(term in combined for term in self.deps.excluded_level_terms):
            return False
        if bool(event.get("ranking_locked")):
            return True
        if "togo" in home or "togo" in away:
            return True

        club_count, _club_max = self.club_priority(event)
        is_friendly = any(term in combined for term in ("friendly", "amical", "club friendly"))
        # Un grand club prime dans la sélection Actu Foot. Un amical avec un seul
        # grand club reste filtré; un vrai choc entre deux grands clubs passe.
        if club_count >= 2 or (club_count >= 1 and not is_friendly):
            return True

        national_match = (
            any(term in home for term in self.deps.national_team_terms)
            or any(term in away for term in self.deps.national_team_terms)
        )
        if national_match and self.competition_weight(event) >= 24:
            return True

        threshold = max(1, int(os.getenv("FOOTBALL_LIVE_POPULARITY_MIN", "60")))
        return self.popularity_score(event) >= threshold

    def rank_key(self, event: dict) -> tuple:
        club_count, club_max = self.club_priority(event)
        return (
            1 if bool(event.get("ranking_locked")) else 0,
            1 if ("togo" in self.deps.team(event, "home").casefold()
                  or "togo" in self.deps.team(event, "away").casefold()) else 0,
            1 if club_count else 0,
            club_count,
            club_max,
            self.popularity_score(event),
            self.deps.importance(event),
            self.deps.kick(event) or datetime.min.replace(tzinfo=timezone.utc),
            self.deps.team(event, "home"),
            self.deps.team(event, "away"),
        )

    def select(
        self,
        events: list[dict],
        *,
        max_per_competition: int | None = None,
        max_total: int | None = None,
        dominance_gap: int | None = None,
    ) -> list[dict]:
        per_comp = max(
            1,
            int(max_per_competition if max_per_competition is not None
                else os.getenv("FOOTBALL_LIVE_MAX_PER_COMPETITION", "2")),
        )
        global_cap = max(
            1,
            int(max_total if max_total is not None
                else os.getenv("FOOTBALL_LIVE_MAX_TOTAL", "4")),
        )
        gap = max(
            0,
            int(dominance_gap if dominance_gap is not None
                else os.getenv("FOOTBALL_LIVE_DOMINANCE_GAP", "30")),
        )

        unique: dict[str, dict] = {}
        for event in events:
            identity = self.match_identity(event)
            current = unique.get(identity)
            if current is None:
                unique[identity] = event
                continue
            if bool(event.get("ranking_locked")) and not bool(current.get("ranking_locked")):
                unique[identity] = event
            elif bool(event.get("ranking_locked")) == bool(current.get("ranking_locked")):
                if self.rank_key(event) > self.rank_key(current):
                    unique[identity] = event

        eligible = [event for event in unique.values() if self.popular_match(event)]
        by_competition: dict[str, list[dict]] = {}
        for event in eligible:
            by_competition.setdefault(self.competition_key(event), []).append(event)

        competition_selected: list[dict] = []
        for key_name, group in by_competition.items():
            ranked_group = sorted(group, key=self.rank_key, reverse=True)
            locked = [event for event in ranked_group if bool(event.get("ranking_locked"))]
            unlocked = [event for event in ranked_group if not bool(event.get("ranking_locked"))]

            chosen = list(locked)
            free_slots = max(0, per_comp - len(chosen))
            if free_slots and unlocked:
                first = unlocked[0]
                chosen.append(first)
                free_slots -= 1
                if free_slots and len(unlocked) > 1:
                    second = unlocked[1]
                    score_gap = self.popularity_score(first) - self.popularity_score(second)
                    second_is_togo = (
                        "togo" in self.deps.team(second, "home").casefold()
                        or "togo" in self.deps.team(second, "away").casefold()
                    )
                    if score_gap <= gap or second_is_togo:
                        chosen.append(second)

            if len(locked) > per_comp:
                print("LIVE_LOCK_OVERFLOW_COMPETITION", key_name, len(locked), "cap", per_comp)
                chosen = locked

            competition_selected.extend(chosen)

        locked_all = sorted(
            [event for event in competition_selected if bool(event.get("ranking_locked"))],
            key=self.rank_key,
            reverse=True,
        )
        new_all = sorted(
            [event for event in competition_selected if not bool(event.get("ranking_locked"))],
            key=self.rank_key,
            reverse=True,
        )
        if len(locked_all) > global_cap:
            print("LIVE_LOCK_OVERFLOW_GLOBAL", len(locked_all), "cap", global_cap)
            selected = locked_all
        else:
            selected = locked_all + new_all[:max(0, global_cap - len(locked_all))]

        ranking_rows = [
            {
                "competition": self.competition_key(event),
                "home": self.deps.team(event, "home"),
                "away": self.deps.team(event, "away"),
                "score": self.popularity_score(event),
                "grand_clubs": self.club_priority(event)[0],
                "grand_club_priority": self.club_priority(event)[1],
                "locked": bool(event.get("ranking_locked")),
                "breakdown": self.popularity_breakdown(event),
            }
            for event in selected
        ]
        self.last_ranking.clear()
        self.last_ranking.update({
            "eligible": len(eligible),
            "selected": len(selected),
            "per_comp": per_comp,
            "global_cap": global_cap,
            "dominance_gap": gap,
            "matches": ranking_rows,
        })
        if eligible:
            print(
                "LIVE_RANKING",
                "eligible", len(eligible),
                "selected", len(selected),
                "per_comp", per_comp,
                "global_cap", global_cap,
                "dominance_gap", gap,
                "matches", json.dumps(ranking_rows, ensure_ascii=False),
            )
        return selected
