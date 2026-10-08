"""Client HTTP BSD football v2 indépendant du moteur SportData.

Documentation: https://sports.bzzoiro.com/docs/conventions/
Aucune écriture dans data.json, aucun envoi Telegram.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

BASE_URL = "https://sports.bzzoiro.com/api/v2"
DEFAULT_CACHE_DIR = Path("bsd/cache")


class BSDAPIError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


class BSDQuotaError(BSDAPIError):
    """Quota journalier BSD épuisé : ne surtout pas réessayer en boucle."""


class BSDRequestBudgetError(BSDAPIError):
    """Budget de requêtes du lancement atteint."""


@dataclass
class BSDPage:
    events: List[Dict[str, Any]]
    total_reported: int
    pages_fetched: int
    complete: bool


def _rate_limit_remaining(value: str) -> Optional[int]:
    """Lit r dans le champ BSD documenté: "football";r=7213;t=52800."""
    for part in (value or "").split(";"):
        key, sep, number = part.strip().partition("=")
        if sep and key.strip() == "r":
            try:
                return max(0, int(number.strip()))
            except ValueError:
                return None
    return None


class BSDClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        cache_dir: Optional[Path] = None,
        max_requests: int = 12,
        timeout: int = 20,
        min_interval: float = 0.15,
        max_retries: int = 2,
        session: Optional[Any] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("BSD_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError("BSD_API_KEY absent : ajouter la clé dans GitHub Secrets.")
        if not (1 <= max_requests <= 7500):
            raise ValueError("max_requests doit être compris entre 1 et 7500")
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self.max_requests = max_requests
        self.timeout = timeout
        self.min_interval = max(0.0, min_interval)
        self.max_retries = max(0, max_retries)
        self.sleep = sleep
        self.clock = clock
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({
            "Authorization": "Token " + self.api_key,
            "Accept": "application/json",
            "User-Agent": "MrXPRONOS-BSD-Diagnostic/1.0",
        })
        self.requests_made = 0
        self.cache_hits = 0
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_header = ""
        self._last_call_at: Optional[float] = None

    def _cache_file(self, path: str, params: Dict[str, Any]) -> Path:
        key = json.dumps([path, params], sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / (digest + ".json")

    def _cached(self, path: str, params: Dict[str, Any], ttl: int) -> Optional[Any]:
        if ttl <= 0:
            return None
        p = self._cache_file(path, params)
        try:
            saved = json.loads(p.read_text(encoding="utf-8"))
            if self.clock() - saved["saved_at"] <= ttl:
                self.cache_hits += 1
                return saved["payload"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def _save_cache(self, path: str, params: Dict[str, Any], payload: Any) -> None:
        p = self._cache_file(path, params)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"saved_at": self.clock(), "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(p)

    def _pace(self) -> None:
        if self._last_call_at is not None:
            delay = self.min_interval - (self.clock() - self._last_call_at)
            if delay > 0:
                self.sleep(delay)

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None, *, ttl: int = 0) -> Any:
        if not path.startswith("/") or ".." in path or "://" in path or "?" in path:
            raise ValueError("Chemin BSD non autorisé")
        params = dict(params or {})
        cached = self._cached(path, params, ttl)
        if cached is not None:
            return cached
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            if self.requests_made >= self.max_requests:
                raise BSDRequestBudgetError(
                    "Budget du lancement atteint (" + str(self.max_requests) + " appels HTTP)."
                )
            self._pace()
            self.requests_made += 1
            self._last_call_at = self.clock()
            try:
                response = self.session.get(
                    BASE_URL + path,
                    params=params,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                if attempt + 1 < attempts:
                    self.sleep(min(2 ** attempt, 5))
                    continue
                raise BSDAPIError("Connexion BSD impossible : " + type(exc).__name__) from exc

            self.rate_limit_header = response.headers.get("RateLimit", "")
            remaining = _rate_limit_remaining(self.rate_limit_header)
            if remaining is not None:
                self.rate_limit_remaining = remaining
            status = response.status_code

            if 300 <= status < 400:
                raise BSDAPIError("Redirection BSD inattendue", status=status)

            try:
                payload = response.json()
            except (ValueError, TypeError) as exc:
                if status in (500, 502, 503, 504) and attempt + 1 < attempts:
                    self.sleep(min(2 ** attempt, 5))
                    continue
                raise BSDAPIError("Réponse BSD non-JSON", status=status) from exc

            error_code = ""
            if isinstance(payload, dict):
                error_code = str(payload.get("code") or "")
            if status == 429:
                if error_code == "taster_exhausted" or self.rate_limit_remaining == 0:
                    raise BSDQuotaError("Quota quotidien BSD épuisé. Arrêt sans attente.", status, error_code)
                if attempt + 1 < attempts:
                    retry_raw = response.headers.get("Retry-After", "1")
                    try:
                        retry_delay = max(1.0, min(float(retry_raw), 15.0))
                    except ValueError:
                        retry_delay = 1.0
                    self.sleep(retry_delay)
                    continue
                raise BSDAPIError("Limite temporaire BSD (429)", status, error_code)

            if status in (500, 502, 503, 504) and attempt + 1 < attempts:
                self.sleep(min(2 ** attempt, 5))
                continue
            if status != 200:
                detail = ""
                if isinstance(payload, dict):
                    detail = str(payload.get("detail") or payload.get("message") or "")[:180]
                raise BSDAPIError("BSD HTTP " + str(status) + ": " + detail, status, error_code)
            if not isinstance(payload, (dict, list)):
                raise BSDAPIError("Réponse BSD invalide (objet/liste attendu)", status)
            if isinstance(payload, dict) and payload.get("error") is True:
                raise BSDAPIError("BSD signale une erreur métier", status, error_code)
            if ttl > 0:
                self._save_cache(path, params, payload)
            return payload
        raise BSDAPIError("Échec BSD après tentatives")  # sécurité

    def list_events(
        self,
        date_from: date,
        date_to: date,
        *,
        page_size: int = 200,
        max_pages: int = 2,
        ttl: int = 180,
    ) -> BSDPage:
        if date_from > date_to:
            raise ValueError("date_from doit précéder date_to")
        if not 1 <= page_size <= 200 or max_pages < 1:
            raise ValueError("Pagination BSD invalide")
        events: List[Dict[str, Any]] = []
        seen = set()
        total: Optional[int] = None
        for page_idx in range(max_pages):
            payload = self.get_json(
                "/events/",
                {
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "limit": page_size,
                    "offset": page_idx * page_size,
                },
                ttl=ttl,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise BSDAPIError("Schéma événements BSD inattendu : results absent")
            if not isinstance(payload.get("count"), int) or payload["count"] < 0:
                raise BSDAPIError("Schéma événements BSD inattendu : count absent")
            total = payload["count"]
            rows = payload["results"]
            for item in rows:
                if not isinstance(item, dict):
                    raise BSDAPIError("Événement BSD non-objet")
                event_id = item.get("id")
                if event_id is None:
                    raise BSDAPIError("Événement BSD sans id")
                if str(event_id) not in seen:
                    seen.add(str(event_id))
                    events.append(item)
            if len(events) >= total or not rows or len(rows) < page_size:
                break
        return BSDPage(
            events=events,
            total_reported=total if total is not None else 0,
            pages_fetched=page_idx + 1,
            complete=len(events) >= (total if total is not None else 0),
        )

    def list_leagues(self, *, ttl: int = 3600, page_size: int = 100) -> Any:
        return self.get_json("/leagues/", {"limit": page_size, "offset": 0}, ttl=ttl)

    def get_h2h(self, event_id: int, *, ttl: int = 86400) -> Any:
        if int(event_id) <= 0:
            raise ValueError("Identifiant BSD invalide")
        return self.get_json("/events/" + str(int(event_id)) + "/h2h/", ttl=ttl)
