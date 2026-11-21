"""Explicit, auditable Anime aliases; no fuzzy automatic series merge."""
from __future__ import annotations

from .episode_identity import canonical_title, series_title


def alias_keys(value: str) -> set[str]:
    raw = canonical_title(value)
    cleaned = canonical_title(series_title(value))
    return {key for key in (raw, cleaned) if key}


def resolve_alias(state: dict, raw: str) -> str:
    aliases = state.get("series_aliases", {}) or {}
    keys = alias_keys(raw)
    name = next((key for key in sorted(keys) if key in aliases),
                canonical_title(raw))
    seen = set()
    while name in aliases:
        if name in seen:
            raise RuntimeError("Cyclic anime title alias.")
        seen.add(name)
        name = str(aliases[name])
    return name


def add_alias(state: dict, variant: str, target: str):
    """Only manual approval can merge an unverified source-title variant."""
    variants = alias_keys(variant)
    new = canonical_title(target)
    if not variants or not new or new in variants:
        raise ValueError("Distinct, explicit canonical names required.")
    if new not in state.get("series", {}):
        raise ValueError("Alias target must already exist as a verified series.")
    if any(key in state.get("series", {}) for key in variants):
        raise RuntimeError("Variant already owns receipts; manual migration required.")
    aliases = state.setdefault("series_aliases", {})
    if any(key in aliases and aliases[key] != new for key in variants):
        raise RuntimeError("Alias already points to a different series.")
    for key in variants:
        aliases[key] = new
    if resolve_alias(state, variant) != new:
        raise RuntimeError("Alias cycle or ambiguity.")
    return aliases
