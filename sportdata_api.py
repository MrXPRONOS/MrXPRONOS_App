#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Client SportData robuste pour Mr XPRONOS.

Objectifs :
- utiliser l'URL canonique SportsAPI Pro V1 ;
- conserver le sous-domaine historique en secours ;
- effectuer une rotation réelle des clés, y compris quand HTTP 200 contient
  une erreur métier ;
- distinguer une réponse valide vide d'une réponse invalide ;
- ne jamais afficher les clés API dans les logs.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import requests

CANONICAL_ALLSCORES_URL = (
    "https://api.sportsapipro.com/v1/football/games/allscores"
)
LEGACY_ALLSCORES_URL = (
    "https://v1.football.sportsapipro.com/games/allscores"
)
CANONICAL_STATUS_URL = (
    "https://api.sportsapipro.com/v1/football/status"
)
ALTERNATE_STATUS_URL = (
    "https://api.sportsapipro.com/v1/football/account/status"
)

ERROR_WORDS = (
    "api key",
    "invalid key",
    "unauthorized",
    "forbidden",
    "quota",
    "rate limit",
    "daily limit",
    "subscription",
    "expired",
    "access denied",
)


@dataclass
class FetchResult:
    games: List[Dict[str, Any]] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    ok: bool = False
    endpoint: str = ""
    status_code: Optional[int] = None
    reason: str = ""
    payload_keys: List[str] = field(default_factory=list)
    normalized_keys: List[str] = field(default_factory=list)
    schema_path: str = ""
    key_index: Optional[int] = None


def get_api_keys() -> List[str]:
    keys: List[str] = []
    seen = set()

    for i in range(1, 6):
        key = (os.getenv(f"SPORTDATA_API_KEY_{i}") or "").strip()
        if key and key not in seen:
            keys.append(key)
            seen.add(key)

    fallback = (os.getenv("SPORTDATA_API_KEY") or "").strip()
    if fallback and fallback not in seen:
        keys.append(fallback)

    return keys


def _log(logger, level: str, message: str, *args) -> None:
    if logger is not None:
        fn = getattr(logger, level, None)
        if callable(fn):
            fn(message, *args)
            return

    rendered = message % args if args else message
    print(rendered)


def _body_preview(response: requests.Response, max_len: int = 350) -> str:
    try:
        text = response.text or ""
    except Exception:
        return "<corps illisible>"
    return " ".join(text.split())[:max_len]


def _extract_error(payload: Any) -> Optional[str]:
    """Détecte une erreur métier, y compris dans une enveloppe ``data``."""
    if not isinstance(payload, dict):
        return "La réponse JSON n'est pas un objet."

    if payload.get("success") is False:
        return str(
            payload.get("error")
            or payload.get("message")
            or payload.get("detail")
            or "success=false"
        )

    error_value = payload.get("error") or payload.get("errors")
    if error_value:
        return str(error_value)

    message = str(payload.get("message") or payload.get("detail") or "")
    lowered = message.lower()
    if message and any(word in lowered for word in ERROR_WORDS):
        return message

    for wrapper_key in ("data", "result", "response", "payload"):
        child = payload.get(wrapper_key)
        if isinstance(child, dict):
            nested_error = _extract_error(child)
            if nested_error:
                return nested_error

    return None


def _unwrap_data_envelope(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Normalise les réponses SportsAPI Pro.

    Schémas pris en charge :
    - ancien : ``{"games": [...], ...}`` ;
    - actuel : ``{"success": true, "data": {"games": [...], ...}}`` ;
    - enveloppes équivalentes ``result``, ``response`` ou ``payload``.
    """
    if not isinstance(payload, dict):
        return None, ""

    queue: List[Tuple[Dict[str, Any], str, int]] = [(payload, "root", 0)]
    visited = set()

    while queue:
        node, path, depth = queue.pop(0)
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)

        if isinstance(node.get("games"), list):
            return node, path

        if depth >= 4:
            continue

        # Les clés d'enveloppe connues sont prioritaires.
        for key in ("data", "result", "response", "payload"):
            child = node.get(key)
            if isinstance(child, dict):
                queue.append((child, f"{path}.{key}", depth + 1))

    return None, ""


def _looks_like_valid_allscores(payload: Dict[str, Any]) -> bool:
    """Valide le corps normalisé de ``/games/allscores``."""
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        return False

    metadata_fields = {
        "lastUpdateId",
        "requestedUpdateId",
        "ttl",
        "liveGamesCount",
        "summary",
        "sports",
        "countries",
        "competitions",
        "competitors",
        "bookmakers",
    }

    # Une liste non vide suffit. Pour games=[], on exige au moins une métadonnée
    # afin de ne pas prendre une erreur déguisée pour une réponse valide.
    if payload["games"]:
        return True
    return bool(metadata_fields.intersection(payload.keys()))

def fetch_games(
    date_from: date,
    date_to: date,
    *,
    logger=None,
    timeout: int = 30,
    show_odds: bool = False,
    only_major_games: bool = False,
    sleep_between_attempts: float = 0.25,
) -> FetchResult:
    """
    Récupère les matchs sur une plage courte.

    Retour :
    - ok=True et games peut être vide : réponse API valide ;
    - ok=False : aucune clé/URL n'a fourni une réponse allscores valide.
    """
    keys = get_api_keys()
    if not keys:
        return FetchResult(ok=False, reason="Aucune clé SportData configurée.")

    params = {
        "startDate": date_from.strftime("%d/%m/%Y"),
        "endDate": date_to.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": str(bool(show_odds)).lower(),
        "onlyMajorGames": str(bool(only_major_games)).lower(),
    }

    endpoints = [CANONICAL_ALLSCORES_URL, LEGACY_ALLSCORES_URL]
    last_result = FetchResult(ok=False, reason="Aucune tentative effectuée.")
    first_valid_empty: Optional[FetchResult] = None

    for endpoint in endpoints:
        for key_index, api_key in enumerate(keys, start=1):
            headers = {
                "x-api-key": api_key,
                "Accept": "application/json",
                "User-Agent": "MrXPRONOS/2026",
            }

            try:
                response = requests.get(
                    endpoint,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                last_result = FetchResult(
                    ok=False,
                    endpoint=endpoint,
                    reason=f"Erreur réseau: {exc}",
                    key_index=key_index,
                )
                _log(
                    logger,
                    "warning",
                    "[SportData] clé #%s, erreur réseau sur %s: %s",
                    key_index,
                    endpoint,
                    exc,
                )
                time.sleep(sleep_between_attempts)
                continue

            status = response.status_code
            _log(
                logger,
                "info",
                "[SportData] clé #%s | HTTP %s | %s | %s -> %s",
                key_index,
                status,
                endpoint,
                params["startDate"],
                params["endDate"],
            )

            if status != 200:
                preview = _body_preview(response)
                last_result = FetchResult(
                    ok=False,
                    endpoint=endpoint,
                    status_code=status,
                    reason=f"HTTP {status}: {preview}",
                    key_index=key_index,
                )
                _log(
                    logger,
                    "warning",
                    "[SportData] réponse refusée clé #%s: %s",
                    key_index,
                    preview,
                )
                time.sleep(sleep_between_attempts)
                continue

            try:
                payload = response.json()
            except ValueError:
                preview = _body_preview(response)
                last_result = FetchResult(
                    ok=False,
                    endpoint=endpoint,
                    status_code=status,
                    reason=f"JSON invalide: {preview}",
                    key_index=key_index,
                )
                _log(
                    logger,
                    "warning",
                    "[SportData] HTTP 200 mais JSON invalide, clé #%s: %s",
                    key_index,
                    preview,
                )
                time.sleep(sleep_between_attempts)
                continue

            payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
            api_error = _extract_error(payload)
            if api_error:
                last_result = FetchResult(
                    ok=False,
                    endpoint=endpoint,
                    status_code=status,
                    reason=f"Erreur API: {api_error}",
                    payload_keys=payload_keys,
                    key_index=key_index,
                )
                _log(
                    logger,
                    "warning",
                    "[SportData] HTTP 200 mais erreur API, clé #%s: %s",
                    key_index,
                    api_error,
                )
                time.sleep(sleep_between_attempts)
                continue

            normalized_payload, schema_path = _unwrap_data_envelope(payload)
            if normalized_payload is None or not _looks_like_valid_allscores(normalized_payload):
                preview = json.dumps(payload, ensure_ascii=False)[:350]
                last_result = FetchResult(
                    ok=False,
                    endpoint=endpoint,
                    status_code=status,
                    reason=(
                        "Schéma allscores invalide : aucune liste `games` trouvée "
                        "à la racine ou dans une enveloppe `data`."
                    ),
                    payload_keys=payload_keys,
                    key_index=key_index,
                )
                _log(
                    logger,
                    "warning",
                    "[SportData] schéma inattendu, clé #%s, clés=%s, aperçu=%s",
                    key_index,
                    payload_keys,
                    preview,
                )
                time.sleep(sleep_between_attempts)
                continue

            games = normalized_payload.get("games", [])
            normalized_keys = sorted(normalized_payload.keys())
            current_result = FetchResult(
                games=games,
                payload=normalized_payload,
                ok=True,
                endpoint=endpoint,
                status_code=status,
                reason=f"Réponse allscores valide ({schema_path}).",
                payload_keys=payload_keys,
                normalized_keys=normalized_keys,
                schema_path=schema_path,
                key_index=key_index,
            )

            _log(
                logger,
                "info",
                "[SportData] réponse valide: %s match(s), clé #%s, hôte=%s, schéma=%s",
                len(games),
                key_index,
                endpoint,
                schema_path,
            )

            if games:
                return current_result

            # Une clé peut être valide mais avoir une couverture/autorisation
            # différente. On continue la rotation pour chercher une réponse
            # non vide, tout en conservant cette réponse vide comme fallback.
            if first_valid_empty is None:
                first_valid_empty = current_result

            time.sleep(sleep_between_attempts)

    return first_valid_empty or last_result


def check_account_status(
    *,
    logger=None,
    timeout: int = 20,
) -> List[Dict[str, Any]]:
    """
    Vérifie chaque clé sans jamais l'afficher.
    """
    results: List[Dict[str, Any]] = []
    keys = get_api_keys()

    for key_index, api_key in enumerate(keys, start=1):
        row = None
        last_error = None

        for status_url in (CANONICAL_STATUS_URL, ALTERNATE_STATUS_URL):
            try:
                response = requests.get(
                    status_url,
                    headers={
                        "x-api-key": api_key,
                        "Accept": "application/json",
                        "User-Agent": "MrXPRONOS/2026",
                    },
                    timeout=timeout,
                )
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}

                error = _extract_error(payload)
                status_payload = payload
                if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                    status_payload = payload["data"]
                if not isinstance(status_payload, dict):
                    status_payload = {}

                usage = status_payload.get("usage", {}) or {}
                account = status_payload.get("account", {}) or {}
                plan = status_payload.get("plan", {}) or {}

                candidate = {
                    "key_index": key_index,
                    "http_status": response.status_code,
                    "ok": response.status_code == 200 and not error,
                    "error": error,
                    "account_type": account.get("account_type"),
                    "plan": plan.get("name"),
                    "daily_limit": usage.get("daily_limit"),
                    "remaining_today": usage.get("remaining_today"),
                    "quota_reset_at": usage.get("quota_reset_at"),
                    "endpoint": status_url,
                }

                row = candidate
                if candidate["ok"]:
                    break
            except requests.RequestException as exc:
                last_error = str(exc)

        if row is None:
            row = {
                "key_index": key_index,
                "http_status": None,
                "ok": False,
                "error": last_error or "Endpoint status inaccessible.",
            }

        results.append(row)
        _log(
            logger,
            "info",
            "[SportData status] clé #%s | ok=%s | HTTP=%s | plan=%s | restant=%s | erreur=%s",
            row.get("key_index"),
            row.get("ok"),
            row.get("http_status"),
            row.get("plan") or row.get("account_type"),
            row.get("remaining_today"),
            row.get("error"),
        )

    return results
