"""Strict, bounded multi-source lists configured from GitHub Actions variables.

Accept @channel values separated by commas, semicolons, line breaks or JSON
arrays. The discovery engine never activates newly found sources automatically.
"""
from __future__ import annotations
import json
import re

_NAME = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
_SPLIT = re.compile(r"[,;\n\r\t ]+")


def source_list(*values: str, max_sources: int = 12) -> list[str]:
    result = []
    seen = set()
    for raw in values:
        raw = str(raw or "").strip()
        if not raw:
            continue
        if raw.startswith("["):
            try:
                names = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise ValueError("La liste JSON des sources Telegram est invalide.") from exc
            if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
                raise ValueError("Une liste JSON de sources doit contenir uniquement des textes.")
        else:
            names = _SPLIT.split(raw)
        for name in names:
            value = name.strip()
            if not value:
                continue
            if not _NAME.fullmatch(value):
                raise ValueError(f"Source Telegram invalide : {value!r} (format @identifiant requis).")
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
            if len(result) > max_sources:
                raise ValueError(f"Trop de sources Telegram : {max_sources} au maximum.")
    return result
