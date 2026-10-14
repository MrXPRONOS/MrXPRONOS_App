#!/usr/bin/env python3
"""Send every generic football banner publication/subtype to @predict_mrxp.

Synthetic data only. This script is fail-closed to the protected Telegram TEST
channel and never mutates production history/state.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from football_cards import render_card
from generic_football_content import banner_caption, live_keyboard
from telegram_rich import post_photo
from telegram_test_guard import validate_test_channel


MATCH_CASES = [
    ("kickoff", "COUP D’ENVOI", {}),
    ("goal", "BUT — DONNÉES COMPLÈTES", {}),
    ("but_full", "BUT — BUTEUR + PASSEUR", {}),
    ("but_scorer_only", "BUT — BUTEUR SEUL", {"assist": "", "goal": {"player": "Buteur Test", "minute_text": "67'"}}),
    ("mi_temps", "MI-TEMPS", {}),
    ("score_update", "SCORE LIVE", {}),
    ("score_live_two_logos", "SCORE LIVE — 2 LOGOS", {}),
    ("score_live_one_logo", "SCORE LIVE — 1 LOGO", {"away_logo": ""}),
    ("score_live_no_logos", "SCORE LIVE — 0 LOGO", {"home_logo": "", "away_logo": ""}),
    ("score_live_no_minute", "SCORE LIVE — SANS MINUTE", {"minute": "", "time": ""}),
    ("poteau", "POTEAU", {"player": "Attaquant Test", "info": "Le ballon frappe le poteau."}),
    ("occasion_manquee", "OCCASION MANQUÉE", {"player": "Attaquant Test", "info": "Grosse occasion non convertie."}),
    ("arret_decisif", "ARRÊT DÉCISIF", {"player": "Gardien Test", "info": "Parade importante du gardien."}),
    ("carton_jaune_full", "CARTON JAUNE — JOUEUR CONNU", {"player": "Milieu Test", "reason": "Faute tactique"}),
    ("carton_jaune_unknown", "CARTON JAUNE — JOUEUR INCONNU", {"player": "", "reason": ""}),
    ("carton_rouge_full", "CARTON ROUGE — JOUEUR CONNU", {"player": "Défenseur Test", "reason": "Faute grave"}),
    ("carton_rouge_unknown", "CARTON ROUGE — JOUEUR INCONNU", {"player": "", "reason": ""}),
    ("remplacement_full", "REMPLACEMENT — ENTRANT + SORTANT", {"entrant": "Joueur Entrant", "sortant": "Joueur Sortant"}),
    ("remplacement_entrant", "REMPLACEMENT — ENTRANT SEUL", {"entrant": "Joueur Entrant", "sortant": ""}),
    ("remplacement_sortant", "REMPLACEMENT — SORTANT SEUL", {"entrant": "", "sortant": "Joueur Sortant"}),
    ("intervention_medicale", "INTERVENTION MÉDICALE", {"player": "Joueur Test", "info": "Le staff médical intervient."}),
    ("blessure_confirmee", "BLESSURE", {"player": "Joueur Test", "reason": "Le joueur ne peut pas continuer."}),
    ("retour_au_jeu", "RETOUR AU JEU", {"player": "Joueur Test", "status": "Le joueur reprend sa place."}),
    ("match_suspendu", "MATCH SUSPENDU", {"status": "Rencontre momentanément suspendue."}),
    ("match_interrompu_full", "MATCH INTERROMPU — MOTIF CONNU", {"status": "Match interrompu", "reason": "Conditions météo difficiles."}),
    ("match_interrompu_unknown", "MATCH INTERROMPU — MOTIF INCONNU", {"status": "Match interrompu", "reason": ""}),
    ("suivi_interrompu", "SUIVI INTERROMPU", {"status": "Le suivi est suspendu jusqu’à confirmation de la reprise."}),
    ("match_reporte", "MATCH REPORTÉ", {"status": "Rencontre reportée. Nouvelle date à confirmer."}),
    ("match_annule", "MATCH ANNULÉ", {"status": "Rencontre annulée."}),
    ("reprise_match", "REPRISE DU MATCH", {"status": "Le jeu reprend."}),
    ("temps_additionnel", "TEMPS ADDITIONNEL", {"minute": "90+5", "info": "Cinq minutes minimum."}),
    ("fin_1re_mi_temps", "FIN 1RE MI-TEMPS", {"minute": "45+3"}),
    ("debut_2e_mi_temps", "DÉBUT 2E MI-TEMPS", {"minute": "46"}),
    ("fin_temps_reglementaire", "FIN TEMPS RÉGLEMENTAIRE", {"minute": "90"}),
    ("prolongation", "PROLONGATIONS", {"minute": "90", "info": "Le match se poursuit en prolongation."}),
    ("mi_temps_prolongation", "MI-TEMPS PROLONGATION", {"minute": "105"}),
    ("tirs_au_but", "TIRS AU BUT", {"shootout_scores": [3, 2], "info": "Séance en cours."}),
    ("tir_au_but_marque", "TIR AU BUT MARQUÉ", {"shootout_scores": [4, 2], "player": "Tireur Test"}),
    ("tir_au_but_manque", "TIR AU BUT MANQUÉ", {"shootout_scores": [4, 2], "player": "Tireur Test", "detail": "Tentative non convertie."}),
    ("fin_tirs_au_but", "FIN TIRS AU BUT", {"shootout_scores": [5, 4], "info": "Séance terminée."}),
    ("reaction", "RÉACTION APRÈS MATCH", {"question": "Quelle note donnez-vous à cette rencontre ?"}),
    ("community_vote", "VOTE SUR UN MATCH", {"question": "Qui va gagner cette rencontre ?"}),
    ("statistique", "STATISTIQUE LIÉE AU MATCH", {"headline": "17 tirs au total", "lines": ["9 tirs pour Équipe A", "8 tirs pour Équipe B"]}),
]

CLUB_CASES = [
    ("composition_probable_full", "COMPOSITION PROBABLE — XI COMPLET", {}),
    ("composition_probable_partial", "COMPOSITION PROBABLE — PARTIELLE", {"players": ["Joueur 1", "Joueur 2", "Joueur 3", "Joueur 4", "Joueur 5"]}),
    ("changement_composition", "CHANGEMENT DE XI", {"in_player": "Joueur Entrant", "out_player": "Joueur Sortant"}),
    ("absence_confirmee", "ABSENCE CONFIRMÉE", {"player": "Joueur Test", "reason": "Forfait confirmé pour la rencontre."}),
    ("retour_groupe", "RETOUR DANS LE GROUPE", {"player": "Joueur Test", "status": "De retour dans le groupe."}),
]

GENERAL_CASES = [
    ("statistique_avancee", "STATISTIQUE GÉNÉRALE", {"headline": "Arsenal domine les corners cette semaine", "league": "Premier League", "lines": ["31 corners sur les trois derniers matchs"], "confidence": 91}),
    ("quiz", "QUIZ FOOT", {"question": "Quel club a remporté le plus de titres européens ?", "league": "Football européen"}),
    ("debat", "DÉBAT FOOT", {"headline": "Faut-il modifier le calendrier international ?", "question": "Quel est votre avis ?", "summary": "Le calendrier fait de nouveau débat.", "source": "TEST"}),
    ("sondage", "SONDAGE GÉNÉRAL", {"question": "Quel championnat aimez-vous suivre ?", "meta": "COMMUNAUTÉ"}),
]


def dummy_logo(url: str, maximum: int):
    """Clean synthetic badge for positioning; no real club identity is implied."""
    im = Image.new("RGBA", (maximum, maximum), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    gold = (241, 193, 92, 255)
    pale = (225, 235, 247, 255)
    color = pale if "away" in str(url) else gold
    margin = max(4, maximum // 18)
    draw.ellipse((margin, margin, maximum - margin, maximum - margin), outline=color, width=max(3, maximum // 18))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(20, maximum // 3))
    except OSError:
        font = ImageFont.load_default()
    label = "B" if "away" in str(url) else "C" if "club" in str(url) else "A"
    draw.text((maximum // 2, maximum // 2), label, font=font, fill=color, anchor="mm")
    return im


def base_match() -> dict:
    return {
        "home": "Manchester United",
        "away": "Paris Saint-Germain",
        "home_logo": "mock://home",
        "away_logo": "mock://away",
        "competition": "UEFA Champions League",
        "league": "UEFA Champions League",
        "score": "2-1",
        "minute": 67,
        "source": "ESPN • TEST",
        "goal": {
            "player": "Buteur Test",
            "minute_text": "67'",
            "assists": ["Passeur Test"],
            "penalty": False,
            "own_goal": False,
        },
        "scorer": "Buteur Test",
        "assist": "Passeur Test",
        "espn_url": "https://www.espn.com/soccer/",
    }


def base_club() -> dict:
    return {
        "team": "Manchester United",
        "club": "Manchester United",
        "team_logo": "mock://club",
        "competition": "Premier League",
        "league": "Premier League",
        "source": "ESPN • TEST",
        "players": [f"Joueur {i}" for i in range(1, 12)],
        "formation": "4-3-3",
        "player": "Joueur Test",
    }


def _merge(base: dict, overrides: dict) -> dict:
    out = dict(base)
    out.update(overrides)
    if "goal" in base and "goal" not in overrides:
        out["goal"] = dict(base["goal"])
    return out


def _caption(index: int, total: int, label: str, category: str, payload: dict) -> str:
    body = banner_caption(category, payload)
    top = (
        f"<b>🧪 TEST BANNIÈRE {index:02d}/{total:02d}</b>\n"
        f"<b>{label}</b>\n"
        "<i>Données fictives • canal test uniquement</i>"
    )
    return top + (("\n\n" + body) if body else "")


def _send_poll(session, token: str, chat: str, label: str) -> int:
    choices = ["Option A", "Option B", "Option C"]
    response = session.post(
        "https://api.telegram.org/bot" + token + "/sendPoll",
        data={
            "chat_id": chat,
            "question": "🧪 TEST • " + label,
            "options": json.dumps([{"text": x} for x in choices], ensure_ascii=False),
            "is_anonymous": "true",
            "allows_multiple_answers": "false",
        },
        timeout=(12, 55),
    )
    response.raise_for_status()
    data = response.json()
    if data.get("ok") is not True:
        raise RuntimeError("Telegram n'a pas confirmé le sondage test")
    return int(data["result"]["message_id"])


def main() -> int:
    token = os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_TEST_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("TEST REFUSED: token ou canal test manquant")

    guard = validate_test_channel(chat, token)
    if guard.get("username") != "predict_mrxp":
        raise RuntimeError("TEST REFUSED: destination autre que @predict_mrxp")

    cases: list[tuple[str, str, dict, str]] = []
    cases += [(cat, label, overrides, "match") for cat, label, overrides in MATCH_CASES]
    cases += [(cat, label, overrides, "club") for cat, label, overrides in CLUB_CASES]
    cases += [(cat, label, overrides, "general") for cat, label, overrides in GENERAL_CASES]
    total = len(cases)

    session = requests.Session()
    sent: list[dict] = []
    poll_categories = {"reaction", "community_vote", "quiz", "sondage"}

    with patch("programme_styles.load_logo", side_effect=dummy_logo):
        with tempfile.TemporaryDirectory(prefix="mrx-generic-banners-") as tmp:
            for index, (category, label, overrides, family) in enumerate(cases, 1):
                if family == "match":
                    payload = _merge(base_match(), overrides)
                elif family == "club":
                    payload = _merge(base_club(), overrides)
                else:
                    payload = dict(overrides)
                    payload.setdefault("source", "TEST")
                    payload.setdefault("league", "Football")

                path = Path(tmp) / f"{index:02d}-{category}.png"
                render_card(category, payload, path)
                with Image.open(path) as check:
                    if check.size != (1280, 500):
                        raise RuntimeError(f"{category}: format {check.size}, attendu 1280x500")

                keyboard = live_keyboard(payload, include_live=(family == "match"))
                message_id = post_photo(
                    session,
                    token,
                    chat,
                    path,
                    _caption(index, total, label, category, payload),
                    keyboard or {},
                    timeout=90,
                    mime="image/png",
                )
                row = {
                    "index": index,
                    "category": category,
                    "family": family,
                    "message_id": message_id,
                }
                sent.append(row)
                print("GENERIC_BANNER_TEST_SENT", json.dumps(row, ensure_ascii=False), flush=True)

                # Poll publications are tested as Telegram actually displays them:
                # banner first, native poll immediately below.
                if category in poll_categories:
                    poll_id = _send_poll(session, token, chat, label)
                    row["poll_message_id"] = poll_id
                    print("GENERIC_BANNER_POLL_SENT", category, poll_id, flush=True)

                time.sleep(0.55)

    print("GENERIC_BANNER_TEST_REPORT", json.dumps(sent, ensure_ascii=False), flush=True)
    if len(sent) != total:
        raise RuntimeError(f"Seulement {len(sent)}/{total} previews envoyées")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
