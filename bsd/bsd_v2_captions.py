"""Telegram HTML captions shared by day, night, two-leg and verified win cards.

Telegram captions use parse_mode=HTML (bold, italic, blockquote). User- and
provider-controlled match/market strings must always be HTML-escaped.
These are forecasts; amounts never imply accepted bets or paid winnings.
"""
from __future__ import annotations

from datetime import timezone
from html import escape
from math import isfinite

from bsd_h2h import _utc
from bsd_v2_stakes import single_stake, combination_stake, money
from bsd_v2_labels import market_label

PARSE_MODE = "HTML"
MAX_CAPTION_LENGTH = 1024  # Telegram photo caption limit after entity parsing.


def _safe(value, limit=76):
    """Escape dynamic data; truncate long or multiline values before escaping."""
    text = " ".join(str(value or "—").split())
    if len(text) > limit:
        text = text[:limit-1].rstrip() + "…"
    return escape(text, quote=False)


def _quote(value):
    if isinstance(value, bool):
        return "—"
    try:
        price = float(value)
        if isfinite(price) and 1.01 <= price <= 100:
            return f"{price:.2f}".replace(".", ",")
    except (ValueError, TypeError):
        pass
    return "—"


def _kickoff(value):
    try:
        return _utc(value).strftime("%d/%m à %Hh%M") + " (Togo)"
    except (ValueError, TypeError):
        return "Horaire à confirmer"


def _fixture(match):
    return _safe(match.get("home_team"), 51) + " – " + _safe(match.get("away_team"), 51)


def _selection(match):
    pick=match.get("prediction") or {}
    return _safe(market_label(pick.get("selection_key"),
                      pick.get("type") or pick.get("label") or "Pronostic"),100)


def _closing():
    return "<i>🔞 18+ · Parier responsablement.</i>"


def single_caption(match, *, night=False):
    """A separate, consistently styled caption for each individual selection."""
    pick=match.get("prediction") or {}
    price=pick.get("odds")
    stake=single_stake(price)
    source_label="Cote indicative Mr XPRONOS (non bookmaker)" if pick.get("odds_source")=="mrxpronos_model" else "Cote BSD"
    label="🌙 Coupons nuit" if night else "☀️ Coupon du jour"
    intro=("<i>Les sélections de la nuit, de 21h à 05h.</i>"
           if night else "<i>Notre sélection football avant-match.</i>")
    return "\n".join((
        f"<b>{label} · MR XPRONOS</b>",
        intro,
        "",
        f"<b>⚽ {_fixture(match)}</b>",
        "<blockquote>"
        f"🎯 {_selection(match)}\n"
        f"📊 {source_label} : <b>{_quote(price)}</b>\n"
        f"💰 Mise indicative : <b>{money(stake)}</b>"
        "</blockquote>",
        f"🕒 <i>{_kickoff(match.get('event_date'))}</i>",
        "",
        _closing(),
    ))


def combo_caption(combo, *, night=False):
    """Dark two-leg coupon; only actual BSD prices are shown."""
    legs=combo.get("legs") or []
    if len(legs)!=2:
        raise ValueError("Un combiné Telegram doit contenir exactement deux matchs")
    headline="🌙 Coupons nuit · Combiné" if night else "🎟️ Combiné du jour"
    start=[f"<b>{headline} · MR XPRONOS</b>",
           "<i>Deux rencontres · deux sélections.</i>", ""]
    details=[]
    for idx,leg in enumerate(legs,1):
        details.extend((
            f"<b>{idx}.</b> ⚽ {_fixture(leg)}",
            f"🎯 {_selection(leg)} · <b>{_quote((leg.get('prediction') or {}).get('odds'))}</b>",
        ))
    total=_quote(combo.get("combined_odds"))
    return "\n".join(start+[
        "<blockquote>"+"\n".join(details)+"</blockquote>",
        f"📊 Cote combinée : <b>{total}</b>",
        f"💰 Mise indicative : <b>{money(combination_stake())}</b>",
        f"🕒 <i>Premier match : {_kickoff(combo.get('event_date'))}</i>",
        "",
        _closing(),
    ])


def gain_caption(match):
    """Report verified selection victory, never a fictional paid bookmaker win."""
    pick=match.get("prediction") or {}
    score=(f"{int(match['home_score'])}–{int(match['away_score'])}"
           if type(match.get("home_score")) is int and
              type(match.get("away_score")) is int else "Score à confirmer")
    return "\n".join((
        "<b>✅ PRONOSTIC GAGNANT · MR XPRONOS</b>",
        "<i>Résultat vérifié après la rencontre.</i>",
        "",
        f"<b>⚽ {_fixture(match)}</b>",
        "<blockquote>"
        f"🎯 {_selection(match)}\n"
        f"🏁 Score final : <b>{score}</b>\n"
        f"📊 {'Cote indicative du modèle' if pick.get('odds_source')=='mrxpronos_model' else 'Cote BSD publiée'} : <b>{_quote(pick.get('odds'))}</b>"
        "</blockquote>",
        "<i>Pronostic réussi, sans attestation de pari encaissé.</i>",
        "",
        _closing(),
    ))
