#!/usr/bin/env python3
"""Simulation visuelle d'un match live pour le canal Telegram de test.

Aucun événement n'est présenté comme réel. Tous les messages portent un bandeau
SIMULATION et utilisent le moteur de rendu production du cycle du match.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

from football_channel import Publication, Sender, lifecycle_publication, post_label  # noqa: E402


HOME = "Arsenal"
AWAY = "Chelsea"
LEAGUE = "Premier League • SIMULATION"
SOURCE = "SIMULATION DE RENDU MR XPRONOS"


def banner(item: Publication, step: str) -> Publication:
    item.key = "simulation-live:" + step + ":" + item.key
    item.text = (
        "<b>🧪 SIMULATION MATCH LIVE — TEST UNIQUEMENT</b>\n"
        "<i>Ce message n'est pas un événement sportif réel.</i>\n\n"
        + item.text
    )
    return item


def make(kind: str, key: str, **extra) -> Publication:
    signal = {
        "kind": kind,
        "key": key,
        "home": HOME,
        "away": AWAY,
        "league": LEAGUE,
        "source": SOURCE,
        **extra,
    }
    post = lifecycle_publication(signal)
    if post is None:
        raise RuntimeError("Impossible de générer " + kind)
    return banner(post, key)


def main() -> int:
    chat = (os.getenv("FOOTBALL_NEWS_CHAT_ID") or "").strip()
    prod = (os.getenv("PROD_FOOTBALL_NEWS_CHAT_ID") or "").strip()
    if not chat:
        raise RuntimeError("Canal Telegram de test manquant")
    if prod and chat == prod:
        raise RuntimeError("Sécurité: destination de test identique à la production")

    sender = Sender(dry_run=False)

    sequence = [
        make("kickoff", "kickoff", minute=1, score="0-0"),
        make(
            "goal", "goal-23", minute=23, score="1-0",
            goal={"player": "Joueur test n°9", "minute": 23, "minute_text": "23'"},
        ),
        make("mi_temps", "halftime", minute=45, score="1-0"),
        make(
            "goal", "goal-68", minute=68, score="1-1",
            goal={"player": "Joueur test n°11", "minute": 68, "minute_text": "68'"},
        ),
        make(
            "goal", "goal-82", minute=82, score="2-1",
            goal={"player": "Joueur test n°7", "minute": 82, "minute_text": "82'"},
        ),
    ]

    sent = []
    for index, post in enumerate(sequence, start=1):
        message_id = sender.send(post)
        sent.append((index, post.category, message_id))
        print("SIMULATION_SENT", index, post.category, message_id)

    final = Publication(
        "kickoff",
        "simulation-live:end",
        (
            "<b>🧪 FIN DE LA SIMULATION LIVE</b>\n\n"
            "<blockquote><b>Arsenal 2-1 Chelsea</b></blockquote>\n"
            "<i>Résultat fictif utilisé uniquement pour visualiser le fonctionnement "
            "du système live Mr XPRONOS.</i>"
        ),
        keyboard={"inline_keyboard": [[{
            "text": "Voir la page LIVE ↗",
            "url": "https://mrxpronos.github.io/MrXPRONOS_App/live.html",
            "style": "primary",
        }]]},
    )
    final_id = sender.send(final)
    print("SIMULATION_SENT_END", final_id)
    print("SIMULATION_COMPLETE", sent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
