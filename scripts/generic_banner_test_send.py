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

from PIL import Image, ImageDraw, ImageFont, ImageOps
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


def _retry_after(exc: requests.HTTPError, default: int = 4) -> int:
    response = getattr(exc, "response", None)
    if response is None:
        return default
    try:
        body = response.json()
        value = int((body.get("parameters") or {}).get("retry_after") or default)
        return max(default, min(value + 1, 45))
    except (ValueError, TypeError, AttributeError):
        header = response.headers.get("Retry-After") if getattr(response, "headers", None) else None
        try:
            return max(default, min(int(header) + 1, 45))
        except (ValueError, TypeError):
            return default


def _post_photo_with_retry(session, token: str, chat: str, path: Path, caption: str, keyboard: dict) -> int:
    for attempt in range(6):
        try:
            return post_photo(
                session, token, chat, path, caption, keyboard,
                timeout=90, mime="image/png",
            )
        except requests.HTTPError as exc:
            response = getattr(exc, "response", None)
            if response is None or response.status_code != 429 or attempt >= 5:
                raise
            wait = _retry_after(exc)
            print("TELEGRAM_RATE_LIMIT photo wait", wait, "seconds", flush=True)
            time.sleep(wait)
    raise RuntimeError("Telegram photo retry exhausted")


def _send_poll(session, token: str, chat: str, label: str) -> int:
    choices = ["Option A", "Option B", "Option C"]
    for attempt in range(6):
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
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code != 429 or attempt >= 5:
                raise
            wait = _retry_after(exc)
            print("TELEGRAM_RATE_LIMIT poll wait", wait, "seconds", flush=True)
            time.sleep(wait)
            continue
        data = response.json()
        if data.get("ok") is not True:
            raise RuntimeError("Telegram n'a pas confirmé le sondage test")
        return int(data["result"]["message_id"])
    raise RuntimeError("Telegram poll retry exhausted")


def _contact_sheets(paths: list[Path], output_dir: Path) -> None:
    if not paths:
        return
    thumb = (640, 250)
    cols = 2
    rows_per_sheet = 5
    page_size = cols * rows_per_sheet
    for page, start in enumerate(range(0, len(paths), page_size), 1):
        group = paths[start:start + page_size]
        sheet = Image.new("RGB", (thumb[0] * cols, thumb[1] * rows_per_sheet), (4, 13, 25))
        for offset, path in enumerate(group):
            with Image.open(path) as src:
                tile = ImageOps.fit(src.convert("RGB"), thumb, method=Image.Resampling.LANCZOS)
            x = (offset % cols) * thumb[0]
            y = (offset // cols) * thumb[1]
            sheet.paste(tile, (x, y))
        sheet.save(output_dir / f"contact-sheet-{page:02d}.jpg", "JPEG", quality=88, optimize=True)


def main() -> int:
    send_enabled = os.environ.get("GENERIC_TEST_SEND_TELEGRAM", "1").strip() == "1"
    token = os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_TEST_CHAT_ID", "").strip()
    if send_enabled:
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
    start_index = max(1, int(os.getenv("GENERIC_TEST_START_INDEX", "1")))
    end_index = min(total, int(os.getenv("GENERIC_TEST_END_INDEX", str(total))))
    if start_index > end_index:
        raise RuntimeError(f"Plage de test invalide: {start_index}>{end_index}")

    session = requests.Session()
    sent: list[dict] = []
    poll_categories = {"reaction", "community_vote", "quiz", "sondage"}
    requested_preview = os.environ.get("GENERIC_TEST_PREVIEW_DIR", "").strip()

    tmp_context = (
        tempfile.TemporaryDirectory(prefix="mrx-generic-banners-")
        if not requested_preview else None
    )
    output_dir = Path(requested_preview or tmp_context.name)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_paths: list[Path] = []

    try:
        with patch("programme_styles.load_logo", side_effect=dummy_logo):
            for index, (category, label, overrides, family) in enumerate(cases, 1):
                if index < start_index or index > end_index:
                    continue
                if family == "match":
                    payload = _merge(base_match(), overrides)
                elif family == "club":
                    payload = _merge(base_club(), overrides)
                else:
                    payload = dict(overrides)
                    payload.setdefault("source", "TEST")
                    payload.setdefault("league", "Football")

                path = output_dir / f"{index:02d}-{category}.png"
                render_card(category, payload, path)
                rendered_paths.append(path)
                with Image.open(path) as check:
                    if check.size != (1280, 500):
                        raise RuntimeError(f"{category}: format {check.size}, attendu 1280x500")

                row = {
                    "index": index,
                    "category": category,
                    "family": family,
                    "preview": path.name,
                }

                if send_enabled:
                    keyboard = live_keyboard(payload, include_live=(family == "match"))
                    message_id = _post_photo_with_retry(
                        session,
                        token,
                        chat,
                        path,
                        _caption(index, total, label, category, payload),
                        keyboard or {},
                    )
                    row["message_id"] = message_id
                    print("GENERIC_BANNER_TEST_SENT", json.dumps(row, ensure_ascii=False), flush=True)

                    if category in poll_categories:
                        poll_id = _send_poll(session, token, chat, label)
                        row["poll_message_id"] = poll_id
                        print("GENERIC_BANNER_POLL_SENT", category, poll_id, flush=True)
                    time.sleep(1.15)
                else:
                    print("GENERIC_BANNER_PREVIEW_OK", json.dumps(row, ensure_ascii=False), flush=True)

                sent.append(row)

        _contact_sheets(rendered_paths, output_dir)
        manifest = {
            "count": len(sent),
            "range": [start_index, end_index],
            "telegram": send_enabled,
            "items": sent,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    finally:
        if tmp_context is not None:
            tmp_context.cleanup()

    expected_count = end_index - start_index + 1
    print("GENERIC_BANNER_TEST_REPORT", json.dumps(sent, ensure_ascii=False), flush=True)
    if len(sent) != expected_count:
        raise RuntimeError(f"Seulement {len(sent)}/{expected_count} previews générées")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
