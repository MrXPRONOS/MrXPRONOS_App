#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
api_utils.py - Module partagé pour les requêtes API avec rotation de clés
Utilisé par tous les scripts qui appellent SportData API.
"""

import os
import time
import requests
from typing import Optional, Dict, Any

# Récupération des clés API depuis les variables d'environnement
API_KEYS = []
for i in range(1, 6):
    key = os.environ.get(f"SPORTDATA_API_KEY_{i}")
    if key:
        API_KEYS.append(key)

# Fallback sur l'ancienne variable si aucune clé n'est trouvée
if not API_KEYS:
    single_key = os.environ.get("SPORTDATA_API_KEY")
    if single_key:
        API_KEYS = [single_key]
    else:
        raise ValueError(
            "Aucune clé API trouvée. Définissez SPORTDATA_API_KEY "
            "ou SPORTDATA_API_KEY_1 à SPORTDATA_API_KEY_5"
        )


def make_request_with_rotation(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    max_retries: int = 1
):
    """
    Effectue une requête HTTP avec rotation de clés API.
    1 seul cycle logique par défaut :
    - essaie chaque clé une seule fois
    - retourne la réponse si succès
    - sinon retourne None
    """
    method = method.upper()

    for attempt in range(max_retries):
        for i, api_key in enumerate(API_KEYS):
            request_headers = {"x-api-key": api_key}
            if headers:
                request_headers.update(headers)

            try:
                if method == "GET":
                    resp = requests.get(
                        url,
                        headers=request_headers,
                        params=params,
                        timeout=timeout
                    )
                elif method == "POST":
                    resp = requests.post(
                        url,
                        headers=request_headers,
                        params=params,
                        data=data,
                        timeout=timeout
                    )
                else:
                    raise ValueError(f"Méthode non supportée: {method}")

                if resp.status_code == 200:
                    return resp

                print(f"⚠️ Clé {i} -> HTTP {resp.status_code} sur {url}")

            except Exception as e:
                print(f"⚠️ Clé {i} échoue sur {url}: {e}")

            time.sleep(0.2)

        if attempt < max_retries - 1:
            time.sleep(1)

    return None


def make_request(method, url, **kwargs):
    return make_request_with_rotation(method, url, **kwargs)