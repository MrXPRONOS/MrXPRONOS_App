"""Telegram copy for the three generic MR XPRONOS football banners.

Rule: the banner identifies the subject (team(s) + event label). The caption
contains only useful details that are NOT already visible on the image.
"""
from __future__ import annotations

import html
import re
from typing import Any

LIVE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/live.html"


def _plain(value: Any, cap: int = 400) -> str:
    text = re.sub(r"<[^>]*>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:cap]


def _esc(value: Any, cap: int = 400) -> str:
    return html.escape(_plain(value, cap), quote=False)


def _minute(payload: dict[str, Any]) -> str:
    value = _plain(
        payload.get("minute_text")
        or payload.get("time")
        or payload.get("minute"),
        20,
    )
    if not value:
        return ""
    if value.endswith(("'", "’")):
        return value
    return value + "'" if re.fullmatch(r"\d+(?:\+\d+)?", value) else value


def _score(payload: dict[str, Any]) -> str:
    raw = _plain(payload.get("score"), 20)
    if raw:
        return raw.replace("-", "–")
    scores = payload.get("scores")
    if isinstance(scores, (list, tuple)) and len(scores) >= 2:
        return f"{scores[0]}–{scores[1]}"
    return ""


def _source_line(payload: dict[str, Any]) -> str:
    competition = _plain(payload.get("competition") or payload.get("league"), 80)
    source = _plain(payload.get("source"), 80)
    parts = []
    if competition:
        parts.append(_esc(competition))
    if source:
        parts.append("Source : " + _esc(source))
    return "<i>" + " • ".join(parts) + "</i>" if parts else ""


def _blockquote(lines: list[str]) -> str:
    clean = [line for line in lines if line]
    return "<blockquote>" + "<br/>".join(clean) + "</blockquote>" if clean else ""


def live_keyboard(payload: dict[str, Any], *, include_live: bool = True) -> dict[str, Any] | None:
    rows: list[list[dict[str, str]]] = []
    if include_live:
        rows.append([{
            "text": "⚡ Suivre le LIVE",
            "url": LIVE_URL,
            "style": "primary",
        }])
    espn = _plain(payload.get("espn_url"), 600)
    if espn.startswith("https://www.espn.com/"):
        rows.append([{
            "text": "✅ Source ESPN",
            "url": espn,
            "style": "success",
        }])
    url = _plain(payload.get("url") or payload.get("article_url"), 600)
    if url.startswith("https://"):
        rows.append([{
            "text": "📰 Lire l’article ↗",
            "url": url,
            "style": "primary",
        }])
    return {"inline_keyboard": rows} if rows else None


def banner_caption(category: str, payload: dict[str, Any]) -> str:
    """Return compact rich HTML copy for a generic banner."""
    category = str(category or "")
    minute = _minute(payload)
    score = _score(payload)
    source_line = _source_line(payload)

    goal_categories = {"goal", "but", "but_full", "but_scorer_only"}
    card_yellow = {"carton_jaune", "carton_jaune_full", "carton_jaune_unknown"}
    card_red = {"carton_rouge", "carton_rouge_full", "carton_rouge_unknown"}
    substitution = {"remplacement", "remplacement_full", "remplacement_entrant", "remplacement_sortant"}
    score_categories = {
        "score_update", "score_live_confirmé", "score_live_confirme",
        "score_live_two_logos", "score_live_one_logo", "score_live_no_logos",
        "score_live_no_minute",
    }

    if category in goal_categories:
        goal = payload.get("goal") if isinstance(payload.get("goal"), dict) else {}
        scorer = _plain(
            goal.get("player") or payload.get("scorer") or payload.get("buteur") or payload.get("player"),
            80,
        )
        assists = goal.get("assists") if isinstance(goal.get("assists"), list) else []
        assist = _plain(
            payload.get("assist") or payload.get("passeur")
            or (", ".join(str(x) for x in assists[:2]) if assists else ""),
            100,
        )
        qualifier = ""
        if goal.get("penalty") or payload.get("penalty"):
            qualifier = " <i>(pen.)</i>"
        elif goal.get("own_goal") or payload.get("own_goal"):
            qualifier = " <i>(c.s.c.)</i>"
        rows = []
        if score or minute:
            rows.append("<b>" + _esc(score or "Score actualisé") + ((" • " + _esc(minute)) if minute else "") + "</b>")
        if scorer:
            rows.append("🎯 Buteur : <b>" + _esc(scorer) + "</b>" + qualifier)
        if assist:
            rows.append("🅰️ Passe : " + _esc(assist))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category == "kickoff":
        rows = ["<b>Le match est lancé.</b>"]
        if score:
            rows.append("Score : <b>" + _esc(score) + "</b>")
        if minute:
            rows.append("⏱ " + _esc(minute))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category == "mi_temps":
        rows = []
        if score:
            rows.append("Score à la pause : <b>" + _esc(score) + "</b>")
        rows.append("💬 Votre avis sur cette première période ?")
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in score_categories:
        rows = []
        if score:
            rows.append("<b>" + _esc(score) + "</b>" + ((" • " + _esc(minute)) if minute else ""))
        status = _plain(payload.get("status"), 100)
        if status:
            rows.append(_esc(status))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {"poteau", "occasion_manquee", "arret_decisif"}:
        player = _plain(payload.get("player") or payload.get("scorer"), 80)
        rows = []
        if score or minute:
            rows.append("<b>" + _esc(score or "") + ((" • " + _esc(minute)) if minute else "") + "</b>")
        if player:
            rows.append("👤 " + _esc(player))
        info = _plain(payload.get("info") or payload.get("context"), 180)
        if info:
            rows.append(_esc(info))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in card_yellow | card_red:
        player = _plain(payload.get("player") or payload.get("card_player"), 80)
        reason = _plain(payload.get("reason") or payload.get("detail"), 130)
        rows = []
        if minute:
            rows.append("⏱ <b>" + _esc(minute) + "</b>")
        if player:
            rows.append("👤 <b>" + _esc(player) + "</b>")
        if reason:
            rows.append("Motif : " + _esc(reason))
        if score:
            rows.append("Score : <b>" + _esc(score) + "</b>")
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in substitution:
        entrant = _plain(payload.get("entrant") or payload.get("incoming") or payload.get("player_in"), 80)
        sortant = _plain(payload.get("sortant") or payload.get("outgoing") or payload.get("player_out"), 80)
        rows = []
        if minute:
            rows.append("⏱ <b>" + _esc(minute) + "</b>")
        if entrant:
            rows.append("🟢 Entre : <b>" + _esc(entrant) + "</b>")
        if sortant:
            rows.append("🔴 Sort : " + _esc(sortant))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {"intervention_medicale", "blessure_confirmee", "retour_au_jeu"}:
        player = _plain(payload.get("player"), 80)
        detail = _plain(payload.get("reason") or payload.get("status") or payload.get("info"), 180)
        rows = []
        if minute:
            rows.append("⏱ <b>" + _esc(minute) + "</b>")
        if player:
            rows.append("👤 <b>" + _esc(player) + "</b>")
        if detail:
            rows.append(_esc(detail))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {
        "match_suspendu", "match_interrompu", "match_interrompu_full",
        "match_interrompu_unknown", "suivi_interrompu", "match_reporté",
        "match_reporte", "match_annulé", "match_annule", "reprise_du_match",
        "reprise_match",
    }:
        detail = _plain(payload.get("reason") or payload.get("status") or payload.get("info"), 220)
        rows = []
        if detail:
            rows.append("<b>" + _esc(detail) + "</b>")
        if minute:
            rows.append("⏱ " + _esc(minute))
        if score:
            rows.append("Score au moment de l’arrêt : <b>" + _esc(score) + "</b>")
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {
        "temps_additionnel", "fin_de_la_1re_mi_temps", "fin_1re_mi_temps",
        "début_de_la_2e_mi_temps", "debut_2e_mi_temps",
        "fin_du_temps_réglementaire", "fin_temps_reglementaire",
        "prolongation", "mi_temps_de_la_prolongation", "mi_temps_prolongation",
    }:
        rows = []
        if score:
            rows.append("Score : <b>" + _esc(score) + "</b>")
        if minute:
            rows.append("⏱ " + _esc(minute))
        info = _plain(payload.get("info") or payload.get("status"), 160)
        if info:
            rows.append(_esc(info))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {
        "tirs_au_but", "tir_au_but_marqué", "tir_au_but_marque",
        "tir_au_but_manqué", "tir_au_but_manque", "fin_des_tirs_au_but",
        "fin_tirs_au_but",
    }:
        shootout = payload.get("shootout_scores") or payload.get("penalty_scores")
        shootout_text = ""
        if isinstance(shootout, (list, tuple)) and len(shootout) >= 2:
            shootout_text = f"{shootout[0]}–{shootout[1]}"
        player = _plain(payload.get("player"), 80)
        rows = []
        if score:
            rows.append("Score : <b>" + _esc(score) + "</b>")
        if shootout_text:
            rows.append("Tirs au but : <b>" + _esc(shootout_text) + "</b>")
        if player:
            rows.append("👤 " + _esc(player))
        info = _plain(payload.get("info") or payload.get("detail"), 150)
        if info:
            rows.append(_esc(info))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {
        "composition_probable", "composition_probable_full", "composition_probable_partial",
        "changement_de_composition", "changement_composition",
    }:
        players = payload.get("players") or payload.get("probable_xi") or payload.get("lineup")
        rows = []
        if isinstance(players, (list, tuple)) and players:
            names = []
            for item in players[:11]:
                if isinstance(item, dict):
                    name = _plain(item.get("name") or item.get("player_name"), 60)
                else:
                    name = _plain(item, 60)
                if name:
                    names.append(name)
            if names:
                rows.append("👥 " + ", ".join(_esc(x) for x in names))
        entrant = _plain(payload.get("in_player") or payload.get("entrant"), 80)
        sortant = _plain(payload.get("out_player") or payload.get("sortant"), 80)
        if entrant:
            rows.append("🟢 Entre dans le XI : <b>" + _esc(entrant) + "</b>")
        if sortant:
            rows.append("🔴 Sort du XI : " + _esc(sortant))
        formation = _plain(payload.get("formation"), 30)
        if formation:
            rows.append("Formation : <b>" + _esc(formation) + "</b>")
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {"absence_confirmée", "absence_confirmee", "retour_dans_le_groupe", "retour_groupe"}:
        player = _plain(payload.get("player"), 80)
        detail = _plain(payload.get("reason") or payload.get("status") or payload.get("info"), 190)
        rows = []
        if player:
            rows.append("👤 <b>" + _esc(player) + "</b>")
        if detail:
            rows.append(_esc(detail))
        return "\n\n".join(x for x in (_blockquote(rows), source_line) if x)

    if category in {"statistique", "statistique_avancee"}:
        headline = _plain(payload.get("headline") or payload.get("title"), 220)
        lines = payload.get("lines") if isinstance(payload.get("lines"), list) else []
        rows = []
        if headline:
            rows.append("<b>" + _esc(headline) + "</b>")
        rows.extend("• " + _esc(x, 180) for x in lines[:4] if _plain(x, 180))
        confidence = payload.get("confidence")
        if confidence not in (None, ""):
            rows.append("Confiance : <b>" + _esc(confidence) + "%</b>")
        return "\n\n".join(x for x in (_blockquote(rows), source_line, "<b>💬 Quelle statistique veux-tu voir demain ?</b>") if x)

    if category == "debat":
        summary = _plain(payload.get("summary"), 350)
        question = _plain(payload.get("question"), 240)
        return "\n\n".join(x for x in (
            _blockquote([_esc(summary)] if summary else []),
            ("<b>💬 " + _esc(question) + "</b>") if question else "",
            source_line,
        ) if x)

    if category in {"quiz", "sondage", "community_vote", "reaction"}:
        question = _plain(payload.get("question") or payload.get("reaction"), 260)
        return ("<blockquote><b>" + _esc(question) + "</b></blockquote>") if question else source_line

    info = _plain(payload.get("info") or payload.get("status") or payload.get("detail"), 250)
    return "\n\n".join(x for x in (_blockquote([_esc(info)] if info else []), source_line) if x)
