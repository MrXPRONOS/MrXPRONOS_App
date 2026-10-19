"""Deliberately conservative, deterministic French news synopsis.

No opaque paid translation API, no unreviewed claim derived from article bodies.
The original attributable English headline and source URL are always in Telegram.
"""
from __future__ import annotations
import re


def exchange_synopsis(exchange: str, title: str, category: str) -> str:
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,12}", exchange):
        raise ValueError("Invalid exchange")
    t = title.casefold()
    if category == "ACCÈS & SERVICES":
        if "withdrawal" in t:
            return f"{exchange} : information concernant les retraits"
        if "deposit" in t:
            return f"{exchange} : information concernant les dépôts"
        if "outage" in t:
            return f"{exchange} : perturbation de service signalée"
        return f"{exchange} : changement annoncé dans ses services"
    if category == "SÉCURITÉ":
        return f"{exchange} : incident de sécurité rapporté"
    if category == "FRAIS & TRADING":
        if "fee" in t or "maker" in t or "taker" in t:
            return f"{exchange} : annonce sur les frais de trading"
        if "listing" in t or "list " in t or "lists " in t:
            return f"{exchange} : annonce concernant les cotations"
        return f"{exchange} : actualité liée aux opérations de trading"
    if category == "INNOVATION":
        if "wallet" in t:
            return f"{exchange} : nouveauté annoncée pour les portefeuilles"
        if "payment" in t:
            return f"{exchange} : nouveauté annoncée sur les paiements"
        return f"{exchange} : nouveau service ou projet annoncé"
    raise ValueError("Unreviewed or unsupported news classification")


def breaking_synopsis(topic: str, title: str) -> str:
    from crypto.export_breaking_v2 import event_signature
    event = event_signature(title)
    if topic not in ("bitcoin", "ethereum") or event is None:
        raise ValueError("Article has no unambiguous event signature")
    action, subject = event
    names = {
        "approved": "une approbation annoncée",
        "rejected": "un refus annoncé",
        "proposal": "une proposition évoquée",
        "hack": "un incident de sécurité signalé",
        "outage": "une perturbation signalée",
        "upgrade": "une mise à niveau annoncée",
        "acquisition": "une acquisition annoncée",
        "liquidation": "des liquidations rapportées",
        "launch": "un lancement annoncé",
    }
    subjects = {
        "etf": "d'ETF", "sec": "concernant la SEC",
        "network": "sur le réseau", "reserve": "liée aux réserves",
        "foundation": "de la fondation",
    }
    return f"{topic.capitalize()} : {names[action]} {subjects[subject]}"


def validate_synopsis(out: str):
    if not isinstance(out, str) or not 20 <= len(out) <= 105:
        raise ValueError("French synopsis not supported by title")
    if re.search(r"[<>]", out):
        raise ValueError("Unsafe synopsis")
    return out
