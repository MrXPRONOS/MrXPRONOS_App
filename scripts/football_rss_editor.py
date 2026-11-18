#!/usr/bin/env python3
"""Validate finished French football news; use NVIDIA NIM only with RSS facts."""
from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from urllib.parse import urlparse

import requests

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "mistralai/mistral-large-4-1t-a52b"
MAX_BODY = 750
ENGLISH_HOSTS = ("feeds.bbci.co.uk", "www.skysports.com", "skysports.com",
                 "www.theguardian.com", "theguardian.com", "feeds.theguardian.com")
CLIPPED_END = re.compile(r"(?:\(\s*(?:\.{3,}|…)\s*\)|(?:\.{3,}|…))\s*[»”\"']?\s*$")
ELLIPSES = re.compile(r"(?:\.{3,}|…)")
NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")
TERMINAL = re.compile(r"[.!?][»”\"']?$")


class EditorialHold(ValueError):
    """No reliable complete news: don't publish."""


def sanitize(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<a\b[^>]*>(.*?)</a>", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(\s*https?://[^)]+\)", r"\1", text)
    text = re.sub(r"(?i)(?:https?://|www\.)[^\s<>\]\)]+", "", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r]+", " ", text).strip()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_english_feed(item):
    language = str(item.get("feed_language") or "").strip().lower()
    if language in ("fr", "en"):
        return language == "en"
    host = (urlparse(str(item.get("source_feed") or "")).hostname or "").lower()
    return host in ENGLISH_HOSTS


def clipped(value):
    return bool(CLIPPED_END.search(sanitize(value)))


def complete_sentences(value, max_chars=MAX_BODY):
    """Keep only original completed sentences, never fabricate missing endings."""
    value = CLIPPED_END.sub("", sanitize(value)).rstrip(" ,;:–—-")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÙÛÜŸŒ«“0-9])", value)
    result = []
    for part in parts:
        part = part.strip()
        if ELLIPSES.search(part) or not TERMINAL.search(part):
            break
        if part.count("«") > part.count("»") or part.count("“") > part.count("”"):
            break
        if len(" ".join(result + [part])) > max_chars:
            break
        result.append(part)
    return " ".join(result).strip()


def _french(value):
    try:
        from langdetect import detect_langs, DetectorFactory
        DetectorFactory.seed = 0
        return any(x.lang == "fr" and x.prob >= .75 for x in detect_langs(value))
    except (ImportError, ValueError, TypeError):
        return False


def _valid_result(original_title, original_body, title, body):
    title, body = sanitize(title), sanitize(body)
    if not (12 <= len(title) <= 200 and 40 <= len(body) <= MAX_BODY):
        raise EditorialHold("invalid_editorial_length")
    if ELLIPSES.search(title + " " + body) or not TERMINAL.search(body):
        raise EditorialHold("unfinished_editorial_content")
    if body.count("«") != body.count("»") or body.count("“") != body.count("”"):
        raise EditorialHold("unfinished_quote")
    if not _french(title + ". " + body):
        raise EditorialHold("not_french")
    source_nums = Counter(NUMBERS.findall(original_title + " " + original_body))
    output_nums = Counter(NUMBERS.findall(title + " " + body))
    if any(num not in source_nums for num in output_nums):
        raise EditorialHold("new_number")
    if not set(NUMBERS.findall(original_title)).issubset(
            set(NUMBERS.findall(title + " " + body))):
        raise EditorialHold("headline_number_lost")
    return title, body


def _nim(session, key, title, excerpt, model=MODEL):
    instructions = (
        "Tu es un éditeur de brèves football en français. À partir UNIQUEMENT du "
        "titre et de l'extrait RSS fournis, écris une brève française autonome. "
        "Ne devine jamais la suite d'un extrait coupé par (…) ou des points de "
        "suspension, et ne reconstitue pas l'article absent. Résume uniquement "
        "les faits explicitement présents, sans inventer de date, de score, de "
        "citation, de nom, d'équipe ni de contexte. Conserve les incertitudes "
        "('selon', 'serait', 'pourrait', 'rumeur') et les chiffres. Si les faits "
        "sont trop incomplets pour une brève cohérente, réponds {\"reject\":true}. "
        "Sinon réponds UNIQUEMENT au format JSON avec les deux champs "
        "title_fr et summary_fr : titre complet en français puis deux à "
        "quatre phrases françaises terminées, maximum 600 caractères. "
        "Pas d'URL, pas de liens, pas de points de suspension."
    )
    response = session.post(
        ENDPOINT,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        json={"model": model, "temperature": 0, "max_tokens": 650, "stream": False,
              "messages": [
                  {"role": "system", "content": instructions},
                  {"role": "user", "content": json.dumps({
                      "titre_rss": title, "extrait_rss": excerpt[:3600]
                  }, ensure_ascii=False)},
              ]},
        timeout=(7, 55),
    )
    response.raise_for_status()
    raw = (response.json().get("choices") or [{}])[0].get("message", {}).get("content")
    if not isinstance(raw, str):
        raise EditorialHold("missing_nim_answer")
    fence = chr(96) * 3
    raw = raw.strip().removeprefix(fence + "json").removeprefix(fence).removesuffix(fence).strip()
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise EditorialHold("invalid_nim_json") from exc
    if not isinstance(result, dict) or result.get("reject") is True:
        raise EditorialHold("nim_rejected_incomplete_excerpt")
    return result.get("title_fr"), result.get("summary_fr")


def prepare(item, *, session=None, api_key=None):
    """Return an edited copy, or fail closed without Telegram/D1 side effects."""
    title = sanitize(item.get("title"))
    body = sanitize(item.get("rss_excerpt_original") or item.get("content")
                    or item.get("telegram_summary") or item.get("summary"))
    if not title or not body:
        raise EditorialHold("missing_rss_facts")
    english = is_english_feed(item)
    needs_nim = english or clipped(body) or clipped(title) or len(body) > MAX_BODY
    if ELLIPSES.search(title + " " + body):
        needs_nim = True
    key = (api_key if api_key is not None else os.getenv("NVIDIA_API_KEY", "")).strip()
    if needs_nim and key:
        try:
            model = os.getenv("FOOTBALL_NIM_MODEL", MODEL).strip() or MODEL
            rewritten_title, rewritten_body = _nim(
                session or requests.Session(), key, title, body, model)
            t, b = _valid_result(title, body, rewritten_title, rewritten_body)
            return {**item, "telegram_title_fr": t, "telegram_content_fr": b,
                    "editorial_verified_fr": True}
        except (requests.RequestException, ValueError, TypeError, KeyError):
            pass
    # Never post raw English when translation fails, and never "repair" an
    # incomplete French headline merely by adding punctuation.
    if english:
        raise EditorialHold("english_translation_unavailable")
    if clipped(title) or ELLIPSES.search(title):
        raise EditorialHold("unfinished_rss_headline")
    conservative = complete_sentences(body)
    if len(conservative) < 40 or ELLIPSES.search(conservative):
        raise EditorialHold("no_complete_sentence")
    return {**item, "telegram_title_fr": title,
            "telegram_content_fr": conservative, "editorial_verified_fr": True}
