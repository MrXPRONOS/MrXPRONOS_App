#!/usr/bin/env python3
"""Read-only diagnostics for the 15-format Telegram cinema system.

No post/sendPhoto/sendPoll calls: safe for automated GitHub Actions runs.
Never prints tokens or API keys, including inside exception messages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Callable

import requests

TEST_CHAT = "@predict_mrxp"
TMDB_BASE = "https://api.themoviedb.org/3"


@dataclass
class CheckResult:
    name: str
    passed: bool
    note: str


def _tg(session, token: str, method: str, payload: dict):
    # Never include the token in exceptions or status output.
    try:
        response = session.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload, timeout=15,
        )
        body = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError(f"Telegram {method}: échec réseau ou réponse illisible") from None
    if not response.ok or not isinstance(body, dict) or not body.get("ok"):
        code = int(getattr(response, "status_code", 0) or 0)
        raise RuntimeError(f"Telegram {method}: requête rejetée (HTTP {code})")
    result = body.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Telegram {method}: résultat incorrect")
    return result


def check_telegram(session, token: str, chat: str = TEST_CHAT) -> CheckResult:
    if not token:
        return CheckResult("telegram", False, "Secret CINEMA_TELEGRAM_BOT_TOKEN ou TELEGRAM_BOT_TOKEN absent")
    try:
        me = _tg(session, token, "getMe", {})
        bot_id = me.get("id")
        if not bot_id or not me.get("is_bot"):
            raise RuntimeError("Token non reconnu comme bot")
        details = _tg(session, token, "getChat", {"chat_id": chat})
        if details.get("type") != "channel":
            raise RuntimeError("Destination Telegram non reconnue comme un canal")
        if (details.get("username") or "").lower() != chat.lstrip("@").lower():
            raise RuntimeError("Nom du canal différent de la destination de test")
        membership = _tg(session, token, "getChatMember", {"chat_id": chat, "user_id": bot_id})
        if membership.get("status") not in ("administrator", "creator"):
            raise RuntimeError("Bot non administrateur du canal de test")
        if membership.get("can_post_messages") is False:
            raise RuntimeError("Droit 'Publier des messages' désactivé")
        return CheckResult("telegram", True, "Bot administrateur autorisé dans @predict_mrxp")
    except RuntimeError as exc:
        return CheckResult("telegram", False, str(exc))


def check_tmdb(session, key: str) -> CheckResult:
    if not key:
        return CheckResult("tmdb", False, "Secret TMDB_API_KEY absent")
    try:
        response = session.get(TMDB_BASE + "/movie/popular", params={
            "api_key": key, "language": "fr-FR", "page": 1,
        }, timeout=15)
        data = response.json()
    except (requests.RequestException, ValueError):
        return CheckResult("tmdb", False, "Connexion ou JSON TMDB invalide")
    if not response.ok or not isinstance(data, dict):
        return CheckResult("tmdb", False, "TMDB a rejeté la requête (HTTP %s)" % response.status_code)
    titles = data.get("results") or []
    if not isinstance(titles, list) or not any(
        isinstance(item, dict) and item.get("id") and item.get("title")
        and item.get("poster_path") for item in titles
    ):
        return CheckResult("tmdb", False, "Aucun film avec affiche originale retourné")
    return CheckResult("tmdb", True, "API répond et retourne des films avec affiches")


def diagnose(env=None, session=None):
    env = dict(os.environ if env is None else env)
    session = session or requests.Session()
    token = env.get("CINEMA_TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN") or ""
    key = env.get("TMDB_API_KEY") or ""
    return [check_telegram(session, token), check_tmdb(session, key)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diagnostic sans publication - cinéma Telegram")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    outcomes = diagnose()
    if args.format == "json":
        print(json.dumps([vars(item) for item in outcomes], ensure_ascii=False))
    else:
        for item in outcomes:
            print(("OK" if item.passed else "ÉCHEC") + " - " + item.name + ": " + item.note)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("## Santé de l'automatisation Cinéma Telegram\n\n")
            fh.write("| Service | État | Information |\n|---|---|---|\n")
            for item in outcomes:
                fh.write("| %s | %s | %s |\n" % (item.name, "OK" if item.passed else "ÉCHEC", item.note))
            fh.write("\n*Aucun message Telegram n'a été envoyé par ce diagnostic.*\n")
    return 0 if all(item.passed for item in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())