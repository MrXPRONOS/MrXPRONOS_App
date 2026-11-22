#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventaire CINEX des canaux administrés : classification locale et rapport privé.

Aucun téléchargement de média, transfert ou inscription à des canaux.
Les titres privés et les éventuelles descriptions restent uniquement dans
les Messages enregistrés du compte Telegram propriétaire.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone

from telethon.errors import FloodWaitError, PeerFloodError


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(value))


def exclude(name: str, username: str = "") -> bool:
    """L'exclusion Torrent9 vaut pour les canaux publics ET privés."""
    return "torrent9" in compact(name) or "torrent9" in compact(username)


# Les titres connus servent uniquement à repérer les canaux consacrés à une œuvre.
# Cette liste est révisable : un titre inconnu reste « à vérifier ».
DEDICATED_TITLES = {
    "animes": (
        "one piece", "black clover", "bleach", "naruto", "boruto",
        "jujutsu kaisen", "jojos bizarre", "jojo bizarre", "dragon ball",
        "demon slayer", "kimetsu no yaiba", "attack on titan", "shingeki no kyojin",
        "death note", "solo leveling", "hunter x hunter", "fairy tail",
        "my hero academia", "boku no hero", "chainsaw man", "tokyo revengers",
    ),
    "series": (
        "lupin", "black doves", "squid game", "stranger things",
        "game of thrones", "breaking bad", "the boys", "money heist",
        "la casa de papel", "the walking dead", "peaky blinders", "wednesday",
    ),
    "films": (
        "fast and furious", "fast & furious", "john wick",
        "harry potter", "mission impossible", "avengers endgame",
        "avatar the way of water", "le roi lion",
    ),
}

CATEGORY_TERMS = {
    "animes": (
        "anime", "animes", "manga", "otaku", "shonen", "shojo",
        "seinen", "isekai", "anim jap", "animezone",
    ),
    "series": (
        "serie", "series", "saison", "episode", "kdrama", "k drama",
        "drama coreen", "tv show", "tvshows", "feuilleton",
    ),
    "films": (
        "film", "films", "cinema", "cine", "movie", "movies",
        "hollywood", "videotheque", "long metrage", "africacine",
    ),
}
GENRE_TERMS = {
    "action": ("action", "combat"),
    "aventure": ("aventure", "adventure"),
    "comédie": ("comedie", "humour", "funny"),
    "romance": ("romance", "romantique", "amour", "desir"),
    "horreur": ("horreur", "horror", "epouvante"),
    "thriller": ("thriller", "suspense"),
    "science-fiction": ("science fiction", "sciencefiction", "sci fi", "scifi"),
    "fantastique": ("fantastique", "fantasy"),
    "drame": ("drame", "drama"),
    "documentaire": ("documentaire", "documentary"),
    "animation": ("animation", "dessin anime"),
    "shōnen": ("shonen",),
    "shōjo": ("shojo",),
    "seinen": ("seinen",),
    "isekai": ("isekai",),
    "coréen": ("coreen", "korean", "kdrama", "k drama"),
    "africain": ("africain", "african", "africacine"),
    "historique": ("historique", "history"),
    "familial": ("familial", "famille", "family"),
}
LANG_TERMS = {"VF": (" vf ", "francais"), "VOSTFR": ("vostfr",), "VO": (" vo ",)}
SINGLE_DESCRIPTION = re.compile(
    r"(?:dedie(?:e)?\s+(?:exclusivement\s+)?a|consacre(?:e)?\s+a|"
    r"uniquement\s+(?:la\s+serie|le\s+film|l.anime))\s+"
    r"([^.!?\n]{3,65})", re.I,
)


def has_term(text: str, phrase: str) -> bool:
    # Comparaison par mots pour éviter « action » dans un autre mot.
    clean = re.sub(r"[^a-z0-9]+", " ", fold(text)).strip()
    term = re.sub(r"[^a-z0-9]+", " ", fold(phrase)).strip()
    return bool(term and f" {term} " in f" {clean} ")


def title_match(name: str) -> tuple[str, str] | None:
    for category, titles in DEDICATED_TITLES.items():
        for title in sorted(titles, key=len, reverse=True):
            if has_term(name, title):
                return category, title
    return None


def likely_cinema(name: str) -> bool:
    n = fold(name)
    return bool(title_match(n) or "cinex" in compact(n) or any(
        has_term(n, term) for terms in CATEGORY_TERMS.values() for term in terms
    ) or any(has_term(n, term) for terms in GENRE_TERMS.values() for term in terms))


def classify_channel(title: str, username: str | None, about: str = "") -> dict | None:
    title = str(title or "").strip()[:160]
    username = str(username or "").strip().lstrip("@")[:40]
    if not title or exclude(title, username):
        return None
    name = fold(title)
    text = fold(title + " " + (about or "")[:800])
    dedicated = title_match(name)
    cats = []
    for category in ("films", "series", "animes"):
        if any(has_term(text, term) for term in CATEGORY_TERMS[category]):
            cats.append(category)
    ck = compact(name)
    if dedicated:
        cats = [dedicated[0]]
    elif not cats and ("cinex" in ck or "cine" in ck):
        # Les canaux de la famille CinéX sans mot de catégorie explicite
        # sont orientés films, mais restent à contrôler manuellement.
        cats = ["films"]

    genres = sorted(
        genre for genre, terms in GENRE_TERMS.items()
        if any(has_term(text, term) for term in terms)
        or ("cinex" in ck and genre in ("comédie", "romance")
            and (("comedie" in ck and genre == "comédie")
                 or ("desir" in ck and genre == "romance")))
    )
    language = next((
        lang for lang, terms in LANG_TERMS.items()
        if any(term in (" " + text + " ") for term in terms)
    ), "non précisée")
    single = dedicated[1] if dedicated else None
    if not single:
        match = SINGLE_DESCRIPTION.search(fold(about))
        if match and cats:
            single = match.group(1).strip()[:65]
    scope = "dédié à une œuvre" if single else (
        "thématique" if genres else "général" if cats else "à vérifier"
    )
    return {
        "title": title,
        "username": username or None,
        "visibility": "public" if username else "privé",
        "categories": cats or ["autres"],
        "genres": genres or (["général / à confirmer"] if cats else []),
        "language": language,
        "scope": scope,
        "dedicated_title": single,
        "needs_review": not cats or (cats and not genres and not single),
    }


def format_catalog(rows: list[dict], day: str) -> str:
    sections = [f"INVENTAIRE DES CANAUX ADMINISTRÉS — {day}",
                "Torrent9 exclu. Classification indicative (nom et description).",
                "Pas de partage ni de transfert automatique de films.",
                "Les canaux consacrés à une œuvre sont isolés des canaux par genre."]
    for visibility in ("public", "privé"):
        subset = [r for r in rows if r["visibility"] == visibility]
        sections.append(f"\n===== CANAUX {visibility.upper()}S ({len(subset)}) =====")
        for category, label in (
            ("films", "FILMS"), ("series", "SÉRIES"), ("animes", "ANIMÉS"),
            ("autres", "AUTRES CANAUX"),
        ):
            entries = [r for r in subset if category in r["categories"] and not r["dedicated_title"]]
            sections.append(f"\n--- {label} ({len(entries)}) ---")
            for r in sorted(entries, key=lambda x: fold(x["title"])):
                url = f" https://t.me/{r['username']}" if r["username"] else ""
                genres = ", ".join(r["genres"]) or "non déterminé"
                review = " [à vérifier]" if r["needs_review"] else ""
                sections.append(
                    f"• {r['title']}{url}\n  Types à publier : {genres}"
                    f" | langue : {r['language']}{review}"
                )
        specific = [r for r in subset if r["dedicated_title"]]
        sections.append(f"\n--- CANAUX RÉSERVÉS À UN TITRE / UNE FRANCHISE ({len(specific)}) ---")
        for r in sorted(specific, key=lambda x: fold(x["title"])):
            url = f" https://t.me/{r['username']}" if r["username"] else ""
            sections.append(
                f"• {r['title']}{url} | {', '.join(r['categories'])}"
                f" | œuvre : {r['dedicated_title']}"
            )
    sections.append("\nNOTE : les catégories et genres sont des suggestions. Vérifier la ligne "
                    "éditoriale et les droits de diffusion avant toute publication.")
    return "\n".join(sections).strip() + "\n"


async def send_private_catalog(client, rows: list[dict]) -> bool:
    """Un seul fichier TXT dans Messages enregistrés, jamais dans les logs GitHub."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    marker = f"CINEX-ADMIN-CATALOG-{day}"
    async for message in client.iter_messages("me", limit=30):
        if marker in str(getattr(message, "raw_text", "") or ""):
            return False  # Déjà transmis aujourd'hui.

    report = format_catalog(rows, day)
    document = io.BytesIO(report.encode("utf-8"))
    document.name = f"cinex-canaux-admin-{day}.txt"
    counts = Counter(r["visibility"] for r in rows)
    caption = (
        f"📂 {marker}\n"
        f"Canaux administrés (hors Torrent9) : {len(rows)} "
        f"— publics : {counts['public']} ; privés : {counts['privé']}.\n"
        "Le fichier joint détaille films, séries, animés, genres et canaux dédiés."
    )
    await client.send_file("me", document, caption=caption, force_document=True)
    return True
