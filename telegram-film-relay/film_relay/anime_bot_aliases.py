"""Explicit, auditable Anime aliases; no fuzzy automatic series merge."""
from __future__ import annotations

from .episode_identity import canonical_title


def resolve_alias(state: dict, raw: str) -> str:
    aliases = state.get("series_aliases", {}) or {}
    name = canonical_title(raw)
    seen = set()
    while name in aliases:
        if name in seen:
            raise RuntimeError("Cyclic anime title alias.")
        seen.add(name)
        name = str(aliases[name])
    return name


def add_alias(state: dict, variant: str, target: str):
    """Only manual approval can merge an unverified source-title variant."""
    old = canonical_title(variant)
    new = canonical_title(target)
    if not old or not new or old == new:
        raise ValueError("Distinct, explicit canonical names required.")
    if new not in state.get("series", {}):
        raise ValueError("Alias target must already exist as a verified series.")
    if old in state.get("series", {}):
        raise RuntimeError("Source variant already owns receipts; manual migration required.")
    aliases = state.setdefault("series_aliases", {})
    if old in aliases and aliases[old] != new:
        raise RuntimeError("Alias already points to a different series.")
    aliases[old] = new
    if resolve_alias(state, old) != new:
        raise RuntimeError("Alias cycle or ambiguity.")
    return aliases
