#!/usr/bin/env python3
"""Actu Foot V1.3: non-destructive per-channel monitoring and guarded private alerts.

Reads the shared Cloudflare D1 publication ledger and verifies Telegram publisher
rights. Never changes the V1/V1.1/V1.2 publication pipelines. Alert delivery is
explicitly opt-in; each alert is claimed atomically in D1 before Telegram POST.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from actufoot_v1_router import load_config, verify_channels, bot_call, ROLES
from d1_publication_ledger import D1Ledger

TZ = ZoneInfo("Africa/Lome")
CONFIG = ROOT / "config" / "actufoot_v1_channels.json"
RSS = "actu_foot_multichannel_v1_article"
LIVE = "actufoot_v11_live_event"
RSS_QUOTA = "actu_foot_multichannel_v1_daily"
LIVE_QUOTA = "actufoot_v11_daily_quota"
MAIN = "actu_foot_flash_v2"
ALERT_KIND = "actufoot_v13_private_alert"
EXPECTED = tuple(ROLES)
KINDS = (RSS, LIVE, RSS_QUOTA, LIVE_QUOTA)
LIMITS = {"rss": 24, "live": 20, "scores_live": 48}
MAX_ALERTS = 12
MAX_AGE_MINUTES = 15


def utcnow():
    return datetime.now(timezone.utc)


def validate_channels(channels: dict) -> None:
    if not isinstance(channels, dict) or set(channels) != set(EXPECTED):
        raise ValueError("V13_INVALID_ROLES")
    values = list(channels.values())
    if (len({x.casefold() for x in values if isinstance(x, str)}) != 10
            or any(not isinstance(x, str) or not re.fullmatch(
                r"@[A-Za-z][A-Za-z0-9_]{4,31}", x) for x in values)):
        raise ValueError("V13_INVALID_DESTINATIONS")


def read_aggregates(ledger, now):
    """One bounded SQL aggregate, never fetch raw publication identities."""
    day = now.astimezone(TZ).date()
    start = (day - timedelta(days=1)).isoformat()
    end = day.isoformat()
    threshold = int((now - timedelta(minutes=MAX_AGE_MINUTES)).timestamp())
    sql = (
        "SELECT kind,ref_date,"
        "CASE WHEN instr(ref_id,':')>0 THEN substr(ref_id,1,instr(ref_id,':')-1) "
        "ELSE '' END AS channel,"
        "CASE WHEN kind=? AND instr(ref_id,':v12:')>0 THEN 'v12' "
        "WHEN kind=? THEN 'rss' WHEN kind=? THEN 'live' "
        "WHEN kind=? THEN 'rss_quota' WHEN kind=? THEN 'live_quota' "
        "ELSE 'other' END AS lane,"
        "delivery_status,COUNT(*) AS total,"
        "MAX(CASE WHEN delivery_status='sent' THEN published_at END) AS latest_sent,"
        "SUM(CASE WHEN delivery_status IN ('reserved','uncertain') "
        "AND CAST(strftime('%s',sent_at) AS INTEGER)<=? THEN 1 ELSE 0 END) AS stale "
        "FROM telegram_sent WHERE ref_date BETWEEN ? AND ? AND kind IN (?,?,?,?) "
        "GROUP BY kind,ref_date,channel,lane,delivery_status"
    )
    params = (LIVE, RSS, LIVE, RSS_QUOTA, LIVE_QUOTA, threshold,
              start, end, *KINDS)
    result = ledger.query(sql, params)
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise ValueError("V13_INVALID_D1_RESULT")
    return result["results"]


def _parse_time(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


def build_report(now, channels, aggregates, allowed, failed, *, main_verified=True):
    """A missing article or a quiet editorial channel is NOT an incident."""
    validate_channels(channels)
    day = now.astimezone(TZ).date().isoformat()
    yesterday = (now.astimezone(TZ).date() - timedelta(days=1)).isoformat()
    if not isinstance(aggregates, list):
        raise ValueError("V13_INVALID_METRICS")
    reverse = {v.casefold(): k for k, v in channels.items()}
    results = {
        role: {"handle": channels[role], "rights": "ok" if role in allowed else "failed",
               "today": {"rss": 0, "live": 0, "v12": 0},
               "yesterday": {"rss": 0, "live": 0, "v12": 0},
               "statuses": {}, "stale_pending": 0,
               "quota": {"rss": 0, "live": 0}, "quota_yesterday": {"rss": 0, "live": 0},
               "quota_limits": {"rss": LIMITS["rss"], "live": LIMITS["scores_live"] if role == "scores" else LIMITS["live"]}, "last_sent": None,
               "level": "ok", "alerts": []}
        for role in EXPECTED
    }
    global_errors = []
    if not main_verified:
        global_errors.append({"code": "MAIN_UNVERIFIED", "severity": "critical"})
    for role in sorted(set(failed)):
        if role in results:
            results[role]["rights"] = "failed"
    for row in aggregates:
        if not isinstance(row, dict):
            raise ValueError("V13_INVALID_ROW")
        handle = str(row.get("channel") or "").casefold()
        role = reverse.get(handle)
        if not role or str(row.get("ref_date")) not in {day, yesterday}:
            continue
        lane = str(row.get("lane") or "")
        status = str(row.get("delivery_status") or "")
        try:
            amount = int(row.get("total") or 0)
            stale = int(row.get("stale") or 0)
            if not (0 <= amount <= 10000000 and 0 <= stale <= amount):
                raise ValueError("negative counts")
        except (ValueError, TypeError):
            raise ValueError("V13_INVALID_COUNT") from None
        item = results[role]
        if lane in {"rss", "live", "v12"}:
            item["statuses"][status] = item["statuses"].get(status, 0) + amount
            if status == "sent":
                key = "today" if row["ref_date"] == day else "yesterday"
                item[key][lane] += amount
                observed = _parse_time(row.get("latest_sent"))
                old = _parse_time(item["last_sent"])
                if observed and (not old or observed > old):
                    item["last_sent"] = observed.isoformat()
            if status in {"reserved", "uncertain"}:
                item["stale_pending"] += stale
        elif lane in {"rss_quota", "live_quota"}:
            quota_key = "quota" if row["ref_date"] == day else "quota_yesterday"
            item[quota_key]["rss" if lane == "rss_quota" else "live"] += amount

    alerts = []
    for role in EXPECTED:
        item = results[role]
        candidate = []
        if item["rights"] != "ok":
            candidate.append(("RIGHTS_MISSING", "critical"))
        if item["stale_pending"] > 0:
            candidate.append(("STUCK_RESERVATIONS", "critical"))
        if item["statuses"].get("uncertain", 0) > 0:
            candidate.append(("UNCERTAIN_DELIVERIES", "critical"))
        if item["statuses"].get("rejected", 0) > 0:
            candidate.append(("TELEGRAM_REJECTIONS", "critical"))
        if item["statuses"].get("failed", 0) > 0:
            candidate.append(("FAILED_PUBLICATIONS", "warning"))
        for lane, used in item["quota"].items():
            limit = item["quota_limits"][lane]
            if used >= limit:
                candidate.append(("QUOTA_EXHAUSTED_" + lane.upper(), "warning"))
            elif used >= int(limit * 0.9 + 0.999):
                candidate.append(("QUOTA_NEAR_" + lane.upper(), "warning"))
        for code, severity in candidate:
            a = {"role": role, "code": code, "severity": severity}
            alerts.append(a)
            item["alerts"].append(a)
        item["level"] = (
            "critical" if any(a["severity"] == "critical" for a in item["alerts"])
            else "warning" if item["alerts"] else "ok"
        )
    alerts = global_errors + alerts
    return {
        "version": "V1.3", "observed_at": now.isoformat(),
        "date_lome": day, "coverage": "current_and_previous_calendar_day",
        "main_verified": bool(main_verified),
        "roles_verified": len(allowed & set(EXPECTED)),
        "channels": results, "alerts": alerts,
        "summary": {"critical": sum(a["severity"] == "critical" for a in alerts),
                    "warning": sum(a["severity"] == "warning" for a in alerts),
                    "messages_today": sum(sum(c["today"].values()) for c in results.values())},
        "note": "Absence de publication sans événement éditorial = information, pas incident.",
    }


def markdown(report):
    out = ["# Actu Foot V1.3 — supervision", "",
           "Rapport UTC : " + report["observed_at"], "",
           "| Canal | Droits | RSS | LIVE | Débrief/classement | Quota RSS | Quota LIVE | LIVE hier | Réservations >15 min | Niveau |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for role, item in report["channels"].items():
        t = item["today"]
        out.append("| " + role + " | " + item["rights"] + " | " +
                   str(t["rss"]) + " | " + str(t["live"]) + " | " +
                   str(t["v12"]) + " | " +
                   str(item["quota"]["rss"]) + "/" + str(item["quota_limits"]["rss"]) + " | " +
                   str(item["quota"]["live"]) + "/" + str(item["quota_limits"]["live"]) + " | " +
                   str(item["quota_yesterday"]["live"]) + "/" + str(item["quota_limits"]["live"]) + " | " + str(item["stale_pending"]) +
                   " | " + item["level"] + " |")
    out += ["", "Droits : " + str(report["roles_verified"]) + "/10",
            "Alertes critiques : " + str(report["summary"]["critical"]),
            "Avertissements : " + str(report["summary"]["warning"]), ""]
    out += ["Notification privée : " + report.get("private_alert_delivery", "non évaluée"), ""]
    if report["alerts"]:
        out.append("## Alertes")
        for alert in report["alerts"][:40]:
            out.append("- [" + alert["severity"] + "] " +
                       alert.get("role", "principal") + " : " + alert["code"])
    else:
        out.append("Aucune anomalie détectée sur les indicateurs observables.")
    out += ["", "_Canal silencieux ≠ panne. Les événements football réels restent à vérifier séparément._"]
    return "\n".join(out) + "\n"


def alert_message(report):
    count = report["summary"]
    entries = report["alerts"][:MAX_ALERTS]
    lines = ["<b>🚨 Actu Foot V1.3 — supervision</b>",
             "Critiques : " + str(count["critical"]) + " · Avertissements : " + str(count["warning"])]
    for item in entries:
        lines.append("• " + html.escape(item.get("role", "principal")) +
                     " : " + html.escape(item["code"]))
    if len(report["alerts"]) > MAX_ALERTS:
        lines.append("• +" + str(len(report["alerts"]) - MAX_ALERTS) + " alertes")
    return "\n".join(lines)


PRIVATE_FAILURES = {"disabled_private_destination", "disabled_missing_bot_token",
                    "not_private", "chat_not_found", "bot_blocked", "telegram_forbidden",
                    "telegram_unauthorized", "telegram_rate_limited", "telegram_bad_request",
                    "telegram_rejected", "preflight_unavailable", "uncertain",
                    "previous_rejected", "previous_uncertain", "previous_pending",
                    "ledger_unavailable"}


def telegram_failure(response, payload):
    """Return only allowlisted codes, never raw Telegram descriptions or URLs."""
    code = response.status_code
    description = str(payload.get("description", "")).lower()
    if code == 400 and "chat not found" in description:
        return "chat_not_found"
    if code == 403 and "blocked" in description:
        return "bot_blocked"
    return {400: "telegram_bad_request", 401: "telegram_unauthorized",
            403: "telegram_forbidden", 429: "telegram_rate_limited"}.get(
                code, "telegram_rejected")


def private_preflight(session, token, destination):
    try:
        response = session.post(
            "https://api.telegram.org/bot" + token + "/getChat",
            data={"chat_id": destination}, timeout=(7, 20))
        payload = response.json()
        if not isinstance(payload, dict):
            return "preflight_unavailable"
        if response.status_code != 200 or payload.get("ok") is not True:
            return telegram_failure(response, payload)
        chat = payload.get("result")
        if not isinstance(chat, dict):
            return "preflight_unavailable"
        if chat.get("type") != "private" or str(chat.get("id")) != destination:
            return "not_private"
        return "ok"
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return "preflight_unavailable"


def send_private_alert(report, ledger, session, token, destination, *, dry_run, test=False):
    """One daily delivery per fingerprint; never retry ambiguous delivery."""
    if dry_run:
        return "dry_run"
    if not re.fullmatch(r"[1-9]\d{4,19}", destination or ""):
        return "disabled_private_destination"
    if not token:
        return "disabled_missing_bot_token"
    preflight = private_preflight(session, token, destination)
    if preflight != "ok":
        return preflight
    if not report["alerts"] and not test:
        return "no_alert"
    import hashlib
    fingerprint = "manual-test" if test else hashlib.sha256(json.dumps(
        sorted((a.get("role", "main"), a["code"]) for a in report["alerts"])
    ).encode()).hexdigest()[:20]
    ref = "v13:private:" + destination + ":" + fingerprint
    day = report["date_lome"]
    try:
        if not ledger.claim(ALERT_KIND, ref, day):
            rows = ledger.rows(ALERT_KIND, day, ref_id=ref)
            status = rows[0].get("delivery_status") if len(rows) == 1 else None
            return {"sent": "already_reserved", "rejected": "previous_rejected",
                    "uncertain": "previous_uncertain"}.get(status, "previous_pending")
    except Exception:
        return "ledger_unavailable"
    try:
        response = session.post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data={"chat_id": destination,
                  "text": ("Actu Foot V1.3 : test privé de notification. Aucun incident simulé."
                           if test else alert_message(report)),
                  "parse_mode": "HTML", "disable_web_page_preview": "true"},
            timeout=(7, 20))
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid receipt")
        if response.status_code != 200 or payload.get("ok") is not True:
            if 400 <= response.status_code < 500 and payload.get("ok") is False:
                if not ledger.set_status(ALERT_KIND, ref, day, "rejected"):
                    return "uncertain"
                return telegram_failure(response, payload)
            raise ValueError("ambiguous receipt")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("invalid receipt")
        message_id = result.get("message_id")
        chat = result.get("chat")
        if (type(message_id) is not int or message_id <= 0 or
                not isinstance(chat, dict) or chat.get("type") != "private" or
                str(chat.get("id")) != destination):
            raise ValueError("unverified receipt")
        ledger.mark(ALERT_KIND, ref, day, message_id=message_id)
        return "sent"
    except Exception:
        try:
            ledger.set_status(ALERT_KIND, ref, day, "uncertain")
        except Exception:
            pass
        return "uncertain"


def main_can_publish(session, token, main_chat):
    """Check the principal channel's bot posting rights, not just its identity."""
    try:
        me = bot_call(session, token, "getMe")
        if me.get("is_bot") is not True or type(me.get("id")) is not int:
            return False
        member = bot_call(session, token, "getChatMember", {
            "chat_id": main_chat, "user_id": str(me["id"])})
        return (member.get("status") == "creator" or
                member.get("status") == "administrator" and
                member.get("can_post_messages") is True)
    except (RuntimeError, KeyError, ValueError, TypeError):
        return False


def run(now, *, ledger, session, token, main_chat, channels,
        alert_chat="", send_alerts=False, dry_run=True, test_alert=False):
    validate_channels(channels)
    if not token or not main_chat:
        raise RuntimeError("V13_PREFLIGHT_MISSING_TELEGRAM_CREDENTIALS")
    # Reuse the V1 11-channel identity check (main + ten specialized channels).
    try:
        accepted, failed = verify_channels(session, token, main_chat, channels)
        main_identity_ok = True
    except RuntimeError:
        # A failed Bot API preflight must produce a visible CRITICAL incident,
        # not an apparently healthy table or an uninformative missing artifact.
        accepted, failed = {}, list(EXPECTED)
        main_identity_ok = False
    aggregates = read_aggregates(ledger, now)
    report = build_report(now, channels, aggregates, set(accepted), failed,
                          main_verified=main_identity_ok and
                          main_can_publish(session, token, main_chat))
    report["private_alert_delivery"] = (
        send_private_alert(report, ledger, session, token, alert_chat, dry_run=dry_run, test=test_alert)
        if send_alerts else "disabled")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="read D1 but never send private alerts")
    p.add_argument("--send-alerts", action="store_true", help="allow private alerts if configured")
    p.add_argument("--test-private-alert", action="store_true", help="explicit private test, once per day")
    p.add_argument("--output", type=Path, default=Path("actufoot-v13-report.json"))
    args = p.parse_args()
    if args.test_private_alert and (args.dry_run or not args.send_alerts):
        p.error("private test requires --send-alerts without --dry-run")
    now = utcnow()
    # Do not write partial reports that could be mistaken for complete supervision.
    report = run(now, ledger=D1Ledger(), session=requests.Session(),
                 token=os.getenv("FOOTBALL_NEWS_BOT_TOKEN", ""),
                 main_chat=os.getenv("FOOTBALL_NEWS_CHAT_ID", ""),
                 channels=load_config(CONFIG),
                 alert_chat=os.getenv("ACTUFOOT_V13_ALERT_CHAT_ID", ""),
                 send_alerts=args.send_alerts, dry_run=args.dry_run, test_alert=args.test_private_alert)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = markdown(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)
    print("ACTUFOOT_V13 " + json.dumps({
        "roles_verified": report["roles_verified"], "summary": report["summary"],
        "private_alert_delivery": report["private_alert_delivery"]}, sort_keys=True))
    for alert in report["alerts"]:
        if os.getenv("GITHUB_ACTIONS") == "true":
            # Static tokens only; no sensitive ref IDs or bot URLs.
            print("::warning title=Actu Foot V1.3::" +
                  alert.get("role", "principal") + ": " + alert["code"])
    if report["private_alert_delivery"] in PRIVATE_FAILURES:
        print("::error title=Actu Foot V1.3 notification privée::" + report["private_alert_delivery"])
        raise SystemExit("V13_PRIVATE_ALERT_FAILURE")
    if report["summary"]["critical"]:
        raise SystemExit("V13_CRITICAL_HEALTH_ALERT")


if __name__ == "__main__":
    main()
