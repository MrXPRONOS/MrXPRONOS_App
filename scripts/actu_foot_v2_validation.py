"""Bounded, recursive domain validation for encrypted Actu Foot V2 records.

Do not serialize access tokens, passwords, recovery words or personal credentials
to GitHub, even encrypted. Validation is intentionally strict on types and time.
"""
from __future__ import annotations
import math
import re
from datetime import datetime
from urllib.parse import urlsplit

from scripts.actu_foot_github_vault import VaultError

BANNED = re.compile(r"(^|_)(password|passwd|private_key|api_key|auth_token|access_token|refresh_token|secret|mnemonic|seed_phrase|authorization|service_role_key)($|_)", re.I)
MATCH_STATES = {"scheduled", "not_started", "live", "half_time", "finished", "postponed", "cancelled", "abandoned", "unknown"}
PUBLICATION_STATES = {"pending", "claimed", "sent", "failed", "uncertain", "archived"}
LIVE_KINDS = {"kickoff", "goal", "mi_temps", "mi_temps_prolongation", "debut_2e_mi_temps",
              "temps_additionnel", "prolongation", "carton_rouge", "carton_jaune", "remplacement",
              "resultat", "resultat_final", "score_update", "composition", "changement_composition",
              "tirs_au_but", "tir_au_but_marque", "tir_au_but_manque", "fin_tirs_au_but",
              "suivi_interrompu"}


def _date(value, key):
    if not isinstance(value, str):
        raise VaultError("Timestamp must be a string: " + key)
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VaultError("Invalid timestamp: " + key) from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise VaultError("Timestamp without timezone: " + key)
    return moment


def _text(value, key, maximum=250):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise VaultError("Invalid nonempty text: " + key)
    if any(ord(ch) < 32 and ch not in "\t\n" for ch in value):
        raise VaultError("Control characters in " + key)


def _number(value, key, maximum=99999999):
    if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= maximum:
        raise VaultError("Invalid numeric value: " + key)


def _walk(obj, depth=0):
    if depth > 9:
        raise VaultError("Record nesting limit exceeded")
    if isinstance(obj, dict):
        if len(obj) > 250:
            raise VaultError("Record field limit exceeded")
        for k, v in obj.items():
            if not isinstance(k, str) or len(k) > 120:
                raise VaultError("Invalid field name")
            if BANNED.search(k):
                raise VaultError("Credential field not allowed in encrypted repository")
            _walk(v, depth + 1)
    elif isinstance(obj, list):
        if len(obj) > 1000:
            raise VaultError("Oversized list")
        for value in obj:
            _walk(value, depth + 1)
    elif isinstance(obj, str):
        if len(obj) > 16000:
            raise VaultError("Oversized string")
    elif obj is not None and type(obj) not in {bool, int, float}:
        raise VaultError("Unsupported JSON record value")
    elif type(obj) is float and not math.isfinite(obj):
        raise VaultError("Non-finite floating-point value")


def validate_domain(collection: str, records: dict) -> None:
    for key, rec in records.items():
        _walk(rec)
        for field in ("event_date", "kickoff_utc", "created_at", "updated_at",
                      "occurred_at", "published_at", "sent_at", "last_seen_at"):
            if field in rec and rec[field] is not None:
                _date(rec[field], field)
        if collection in {"matches", "live_events"}:
            home = rec.get("home_team")
            away = rec.get("away_team")
            _text(home, "home_team")
            _text(away, "away_team")
            if home.strip().casefold() == away.strip().casefold():
                raise VaultError("Identical home and away teams")
            for field in ("home_score", "away_score"):
                if field in rec and rec[field] is not None:
                    if type(rec[field]) is not int or not 0 <= rec[field] <= 30:
                        raise VaultError("Out-of-range score")
            if "minute" in rec and rec["minute"] is not None:
                _number(rec["minute"], "minute", 160)
            if "state" in rec and rec["state"] not in MATCH_STATES:
                raise VaultError("Unknown normalized match state")
            if "provider" in rec:
                _text(rec["provider"], "provider", 80)
            if collection == "live_events" and "kind" in rec and rec["kind"] not in LIVE_KINDS:
                raise VaultError("Unknown live event kind")
        elif collection == "publications":
            if rec.get("status") not in PUBLICATION_STATES:
                raise VaultError("Unknown publication state")
            if "telegram_message_id" in rec and rec["telegram_message_id"] is not None:
                if type(rec["telegram_message_id"]) is not int or rec["telegram_message_id"] <= 0:
                    raise VaultError("Invalid Telegram message ID")
            if "attempts" in rec:
                if type(rec["attempts"]) is not int or not 0 <= rec["attempts"] <= 50:
                    raise VaultError("Invalid attempt count")
        elif collection == "news":
            for label in ("title", "headline"):
                if label in rec:
                    _text(rec[label], label, 600)
            for label in ("url", "source_url"):
                if label in rec:
                    value = rec[label]
                    if (not isinstance(value, str) or len(value) > 2048
                            or urlsplit(value).scheme != "https" or not urlsplit(value).hostname):
                        raise VaultError("Invalid news HTTPS source URL")
        elif collection == "statistics":
            for field in ("home_corners", "away_corners", "home_shots", "away_shots",
                          "home_possession", "away_possession", "confidence"):
                if field in rec and rec[field] is not None:
                    _number(rec[field], field, 100 if field in
                            {"home_possession", "away_possession", "confidence"} else 300)
            if "home_possession" in rec and "away_possession" in rec:
                if all(rec.get(k) is not None for k in ("home_possession", "away_possession")):
                    if abs(rec["home_possession"] + rec["away_possession"] - 100) > 2:
                        raise VaultError("Inconsistent possession percentages")
        elif collection == "audit":
            if type(rec.get("sequence")) is not int or rec["sequence"] <= 0:
                raise VaultError("Invalid audit sequence")
            for field in ("entry_hash", "previous_hash"):
                if not isinstance(rec.get(field), str) or not re.fullmatch(r"[a-f0-9]{64}", rec[field]):
                    raise VaultError("Invalid audit hash")
            _text(rec.get("operation"), "operation", 80)
            _date(rec.get("occurred_at"), "occurred_at")
