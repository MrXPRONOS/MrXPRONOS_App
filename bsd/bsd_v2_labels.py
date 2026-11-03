"""Libellés des sélections BSD V2 conformes aux marchés de pari football.

Ne JAMAIS transformer les clés internes utilisées pour les cotes et la
validation (1X, X2, 12, BTTS_YES, OVER_15, etc.). Ce module ne change que
les libellés visibles dans data.json, les images et les messages Telegram.

1X, X2 et 12 : double chance ; 1, X, 2 : résultat sec.
"""
from __future__ import annotations

import re

FIXED_LABELS = {
    "1": "1",
    "X": "X",
    "2": "2",
    "1X": "1X",
    "X2": "X2",
    "12": "12",
    "BTTS_YES": "Les deux équipes marquent : Oui",
    "BTTS_NO": "Les deux équipes marquent : Non",
}

TOTAL_RE = re.compile(r"^(OVER|UNDER)_(15|25|35|45)$")
DISPLAY_FIELDS = ("type", "label", "name")


def market_label(selection_key, fallback=None):
    """Libellé public d'un code de sélection connu, sans toucher à ce code.

    Unknown markets are left unchanged: never pretend a different market was
    selected merely because a label has similar words.
    """
    code = str(selection_key or "").upper().strip()
    if code in FIXED_LABELS:
        return FIXED_LABELS[code]
    match = TOTAL_RE.fullmatch(code)
    if match:
        direction, line_code = match.groups()
        line = f"{line_code[0]},{line_code[1]}"
        return f"Total buts : {direction.title()} {line}"
    return str(fallback if fallback is not None else selection_key or "Pronostic")


def normalize_selection(selection):
    """Return a shallow copy with canonical public labels; preserve prices,
    market codes, probabilities, selection keys, sources and result semantics.
    """
    if not isinstance(selection, dict):
        return selection
    code = selection.get("selection_key") or selection.get("key")
    original = selection.get("type") or selection.get("label") or selection.get("name")
    label = market_label(code, original)
    result = dict(selection)
    for field in DISPLAY_FIELDS:
        if field in result:
            result[field] = label
    return result


def normalize_match(match):
    """Normalize every public selection on a fixture (single, second, combo)."""
    if not isinstance(match, dict):
        return match
    copy = dict(match)
    for field in ("prediction", "combo_prediction"):
        if isinstance(copy.get(field), dict):
            copy[field] = normalize_selection(copy[field])
    if isinstance(copy.get("predictions"), list):
        copy["predictions"] = [normalize_selection(p) for p in copy["predictions"]]
    return copy
