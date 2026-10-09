"""Stockage privé d'historiques BSD dans Supabase Storage (jamais dans GitHub Pages).

Le bucket est créé *privé* si absent. Toute configuration publique est refusée.
Utilise une clé de serveur (service_role), jamais une clé publique.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


BUCKET = "mrxpronos-bsd-history"


class BSDStorageError(RuntimeError):
    pass


def _check_status(response, accepted, label):
    if response.status_code not in accepted:
        raise BSDStorageError("%s : HTTP %s" % (label, response.status_code))


def _key(league_id: int, season_id: int) -> str:
    if int(league_id) <= 0 or int(season_id) <= 0:
        raise ValueError("IDs BSD invalides")
    return "seasons/league_%d_season_%d.json.gz" % (int(league_id), int(season_id))


class BSDPrivateStorage:
    def __init__(self, url: Optional[str] = None, service_key: Optional[str] = None,
                 *, session=None, timeout: int = 30):
        raw_url = (url if url is not None else os.getenv("SUPABASE_URL", "")).strip().rstrip("/")
        key = (service_key if service_key is not None
               else os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
        parsed = urlparse(raw_url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or parsed.path not in ("", "/")
                or not parsed.hostname.endswith(".supabase.co")):
            raise ValueError("SUPABASE_URL doit être une URL de projet https://*.supabase.co")
        if not key:
            raise ValueError("Clé de service Supabase absente")
        self.root = raw_url + "/storage/v1"
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({
            "apikey": key, "Authorization": "Bearer " + key,
        })
        self.timeout = timeout
        self.checked_private = False

    def _request(self, method, path, **kwargs):
        try:
            return self.session.request(
                method, self.root + path, timeout=self.timeout,
                allow_redirects=False, **kwargs,
            )
        except requests.RequestException as exc:
            raise BSDStorageError("Connexion Supabase Storage impossible") from exc

    def ensure_private_bucket(self, *, create_if_missing: bool = False):
        r = self._request("GET", "/bucket/" + BUCKET)
        if r.status_code == 404:
            if not create_if_missing:
                raise BSDStorageError("Bucket privé absent : lancer la synchronisation manuelle initiale")
            created = self._request("POST", "/bucket", json={
                "id": BUCKET,
                "name": BUCKET,
                "public": False,
                "file_size_limit": 10485760,
            })
            if created.status_code not in (200, 201, 409):
                _check_status(created, (200, 201), "Création bucket privé")
            r = self._request("GET", "/bucket/" + BUCKET)
        _check_status(r, (200,), "Vérification bucket BSD")
        try:
            obj = r.json()
        except ValueError as exc:
            raise BSDStorageError("Bucket BSD : réponse invalide") from exc
        if not isinstance(obj, dict) or obj.get("public") is not False:
            raise BSDStorageError("Refus de stocker dans un bucket public ou non vérifiable")
        self.checked_private = True

    def download(self, league_id: int, season_id: int):
        if not self.checked_private:
            raise BSDStorageError("Vérifier le bucket privé avant téléchargement")
        key = _key(league_id, season_id)
        r = self._request("GET", "/object/authenticated/" + BUCKET + "/" + key)
        if r.status_code == 404:
            return None
        _check_status(r, (200,), "Lecture historique BSD")
        if len(r.content) > 10485760:
            raise BSDStorageError("Archive historique trop grande")
        try:
            obj = json.loads(gzip.decompress(r.content))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            raise BSDStorageError("Archive historique BSD corrompue") from exc
        self._validate(obj, league_id, season_id)
        return obj

    @staticmethod
    def _validate(obj: Any, league_id: int, season_id: int):
        if (not isinstance(obj, dict) or obj.get("provider") != "BSD"
                or obj.get("league_id") != int(league_id)
                or obj.get("season_id") != int(season_id)
                or not isinstance(obj.get("events"), list)):
            raise BSDStorageError("Archive étrangère ou schéma invalide")
        ids = set()
        for e in obj["events"]:
            if not isinstance(e, dict) or e.get("id") is None:
                raise BSDStorageError("Événement historique invalide")
            k = str(e["id"])
            if k in ids:
                raise BSDStorageError("Archive historique contenant des IDs dupliqués")
            ids.add(k)

    def upload(self, league_id: int, season_id: int, obj: Dict[str, Any]):
        if not self.checked_private:
            raise BSDStorageError("Vérifier le bucket privé avant import")
        self._validate(obj, league_id, season_id)
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        body = gzip.compress(raw, compresslevel=6, mtime=0)
        if len(body) > 10485760:
            raise BSDStorageError("Archive trop grande pour le bucket")
        key = _key(league_id, season_id)
        r = self._request(
            "POST", "/object/" + BUCKET + "/" + key, data=body,
            headers={"content-type": "application/gzip", "x-upsert": "true"},
        )
        _check_status(r, (200, 201), "Écriture historique BSD")
        # Relecture obligatoire : garantit que l'historique survivra au runner.
        saved = self._request("GET", "/object/authenticated/" + BUCKET + "/" + key)
        _check_status(saved, (200,), "Vérification sauvegarde BSD")
        if hashlib.sha256(saved.content).digest() != hashlib.sha256(body).digest():
            raise BSDStorageError("Archive sauvegardée différente de l'archive envoyée")
        return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
