#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
api_utils.py - Module partagé pour les requêtes API avec rotation de clés
Utilisé par tous les scripts qui appellent SportData API.
"""

import os
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        raise ValueError("Aucune clé API trouvée. Définissez SPORTDATA_API_KEY ou SPORTDATA_API_KEY_1 à SPORTDATA_API_KEY_5")

def make_request(method, url, params=None, data=None, headers=None, timeout=30):
    """
    Effectue une requête HTTP avec une clé API choisie aléatoirement.
    Gère les retries en cas d'erreur 429, 500, etc.
    """
    # Choisir une clé aléatoire
    api_key = random.choice(API_KEYS)
    request_headers = {"x-api-key": api_key}
    if headers:
        request_headers.update(headers)

    # Créer une session avec retry
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        if method.upper() == 'GET':
            resp = session.get(url, headers=request_headers, params=params, timeout=timeout)
        elif method.upper() == 'POST':
            resp = session.post(url, headers=request_headers, params=params, data=data, timeout=timeout)
        else:
            raise ValueError(f"Méthode non supportée: {method}")
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"❌ Erreur lors de la requête {url} avec clé {api_key[:8]}...: {e}")
        raise