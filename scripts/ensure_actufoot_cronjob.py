#!/usr/bin/env python3
"""Configure trois cadences Actu Foot sur cron-job.org.

Trois tâches assurent les cadences Actu Foot :
- full : toutes les 5 minutes, flux autonome du canal principal;
- lifecycle : toutes les 2 minutes, cycle LIVE léger;
- update-footnews : à H:09 et H:39, RSS vers les 10 canaux V1.
Les trois tournent 24h/24 en timezone Africa/Lome.
"""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.cron-job.org"
KEY = os.environ.get("CRONJOB_API_KEY", "").strip()
if not KEY:
    raise SystemExit("CRONJOB_API_KEY manquant")

HEADERS = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
TARGET_WF = "football-production.yml"
TARGET_URL = (
    "https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/"
    + TARGET_WF + "/dispatches"
)
SOURCE_JOB_ID = 8613158  # job GitHub dispatch existant, utilisé seulement pour reprendre les headers GitHub
FULL_TITLE = "Mr XPRONOS – Actu Foot Telegram"
LIFECYCLE_TITLE = "Mr XPRONOS – Actu Foot Cycle Match"
ALLOWED_TITLES = {FULL_TITLE, LIFECYCLE_TITLE}


def req(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(API + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"cron-job.org HTTP {exc.code} sur {path}: {body[:400]}") from exc


def wf_from_url(url):
    match = re.search(r"/actions/workflows/([^/]+)/dispatches", url or "")
    return match.group(1) if match else None


listing = req("GET", "/jobs")
target_jobs = [
    job for job in listing.get("jobs", [])
    if wf_from_url(job.get("url")) == TARGET_WF
]
unknown = [job for job in target_jobs if job.get("title") not in ALLOWED_TITLES]
if unknown:
    raise SystemExit(
        "SECURITE: tâche inconnue ciblant football-production.yml: "
        + ", ".join(str(job.get("title") or job.get("jobId")) for job in unknown)
    )

by_title = {}
for title in ALLOWED_TITLES:
    matches = [job for job in target_jobs if job.get("title") == title]
    if len(matches) > 1:
        raise SystemExit("SECURITE: plusieurs tâches cron-job.org nommées " + title)
    by_title[title] = matches[0] if matches else None

# Les headers GitHub sont repris d'un dispatch déjà fonctionnel; aucune valeur
# secrète n'est imprimée ni écrite dans le dépôt.
source = req("GET", f"/jobs/{SOURCE_JOB_ID}").get("jobDetails", {})
source_headers = ((source.get("extendedData") or {}).get("headers") or {})
if wf_from_url(source.get("url")) != "bsd-v2-telegram-hourly.yml":
    raise SystemExit("SECURITE: le job source GitHub attendu a changé")
if not source_headers:
    raise SystemExit("SECURITE: headers GitHub absents sur le job source")


def schedule(minutes):
    return {
        "timezone": "Africa/Lome",
        "expiresAt": 0,
        "hours": list(range(0, 24)),
        "mdays": [-1],
        "minutes": minutes,
        "months": [-1],
        "wdays": [-1],
    }


def dispatch_body(mode, trigger):
    return json.dumps({
        "ref": "main",
        "inputs": {
            "trigger_source": trigger,
            "dry_run": False,
            "force": False,
            "mode": mode,
            "destination": "production",
        },
    }, separators=(",", ":"))


def job_definition(title, minutes, mode, trigger):
    return {
        "enabled": True,
        "title": title,
        "saveResponses": False,
        "url": TARGET_URL,
        "requestTimeout": 60,
        "redirectSuccess": False,
        "schedule": schedule(minutes),
        "requestMethod": 1,
        "extendedData": {
            "headers": source_headers,
            "body": dispatch_body(mode, trigger),
        },
    }


def ensure(title, minutes, mode, trigger):
    definition = job_definition(title, minutes, mode, trigger)
    existing = by_title[title]
    if existing:
        job_id = existing["jobId"]
        req("PATCH", f"/jobs/{job_id}", {"job": definition})
        action = "updated"
    else:
        created = req("PUT", "/jobs", {"job": definition})
        job_id = created["jobId"]
        action = "created"

    details = req("GET", f"/jobs/{job_id}").get("jobDetails", {})
    actual = details.get("schedule") or {}
    extended = details.get("extendedData") or {}
    body_raw = extended.get("body") or ""
    try:
        body = json.loads(body_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Corps GitHub invalide sur le job {job_id}") from exc
    inputs = body.get("inputs") if isinstance(body, dict) else None
    expected_inputs = {
        "trigger_source": trigger,
        "dry_run": False,
        "force": False,
        "mode": mode,
        "destination": "production",
    }
    assert details.get("enabled") is True
    assert details.get("requestMethod") == 1
    assert wf_from_url(details.get("url")) == TARGET_WF
    assert actual.get("minutes") == minutes
    assert actual.get("hours") == list(range(0, 24))
    assert body.get("ref") == "main"
    assert inputs == expected_inputs, {
        "jobId": job_id,
        "expected": expected_inputs,
        "actual": inputs,
    }
    return {
        "action": action,
        "jobId": job_id,
        "title": details.get("title"),
        "enabled": details.get("enabled"),
        "targetWorkflow": TARGET_WF,
        "mode": mode,
        "dryRun": inputs.get("dry_run"),
        "triggerSource": inputs.get("trigger_source"),
        "schedule": actual,
        "nextExecution": details.get("nextExecution"),
    }


results = [
    ensure(FULL_TITLE, list(range(0, 60, 5)), "full", "cron-job.org"),
    ensure(LIFECYCLE_TITLE, list(range(0, 60, 2)), "lifecycle", "cron-job.org-lifecycle"),
]

# V1 multicanal : football-production/full ne lance PAS le routeur RSS.
# Il faut garder update-footnews.yml actif sur cron-job.org, en complément de
# l'horaire GitHub Actions natif (qui peut être retardé / omis). Le décalage
# H:09 / H:39 diminue les collisions avec le cron GitHub H:07 / H:37.
NEWS_WF = "update-footnews.yml"
NEWS_TITLE = "Mr XPRONOS – Update football news"
NEWS_URL = (
    "https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/"
    + NEWS_WF + "/dispatches"
)
news_matches = [
    job for job in listing.get("jobs", [])
    if wf_from_url(job.get("url")) == NEWS_WF
]
news_unknown = [job for job in news_matches if job.get("title") != NEWS_TITLE]
if news_unknown:
    raise SystemExit(
        "SECURITE: tâche RSS inconnue, revue manuelle nécessaire: "
        + ", ".join(str(j.get("jobId")) for j in news_unknown)
    )
if len(news_matches) > 1:
    raise SystemExit("SECURITE: plusieurs tâches RSS V1 ciblent update-footnews.yml")

news_minutes = [9, 39]
news_definition = {
    "enabled": True,
    "title": NEWS_TITLE,
    "saveResponses": False,
    "url": NEWS_URL,
    "requestTimeout": 60,
    "redirectSuccess": False,
    "schedule": schedule(news_minutes),
    "requestMethod": 1,
    "extendedData": {
        "headers": source_headers,
        "body": json.dumps({"ref": "main"}, separators=(",", ":")),
    },
}
if news_matches:
    news_id = news_matches[0]["jobId"]
    req("PATCH", f"/jobs/{news_id}", {"job": news_definition})
    news_action = "updated"
else:
    created = req("PUT", "/jobs", {"job": news_definition})
    news_id = created["jobId"]
    news_action = "created"

news_details = req("GET", f"/jobs/{news_id}").get("jobDetails", {})
news_actual_schedule = news_details.get("schedule") or {}
news_extended = news_details.get("extendedData") or {}
try:
    news_body = json.loads(news_extended.get("body") or "")
except (TypeError, ValueError) as exc:
    raise RuntimeError("Corps GitHub RSS invalide") from exc

assert news_details.get("enabled") is True
assert news_details.get("requestMethod") == 1
assert wf_from_url(news_details.get("url")) == NEWS_WF
assert news_actual_schedule.get("timezone") == "Africa/Lome"
assert news_actual_schedule.get("minutes") == news_minutes
assert news_actual_schedule.get("hours") == list(range(24))
assert news_body == {"ref": "main"}
results.append({
    "action": news_action,
    "jobId": news_id,
    "title": NEWS_TITLE,
    "enabled": True,
    "targetWorkflow": NEWS_WF,
    "schedule": news_actual_schedule,
    "nextExecution": news_details.get("nextExecution"),
})
print(json.dumps({
    "jobs": results,
    "checked_at": datetime.now(timezone.utc).isoformat(),
}, ensure_ascii=False, indent=2))


# Validation non destructive : vérifie que GitHub accepte le nouveau champ mode.
if os.environ.get("ACTUFOOT_TEST_DISPATCH", "").strip() == "1":
    test_body = json.dumps({
        "ref": "main",
        "inputs": {
            "trigger_source": "cron-job.org-lifecycle-test",
            "dry_run": True,
            "force": False,
            "mode": "lifecycle",
            "destination": "dry-run",
        },
    }).encode("utf-8")
    test_headers = {str(k): str(v) for k, v in source_headers.items()}
    test_headers.setdefault("Content-Type", "application/json")
    test_req = urllib.request.Request(
        TARGET_URL, data=test_body, headers=test_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(test_req, timeout=30) as response:
            response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub lifecycle dry-run dispatch HTTP {exc.code}: {body[:400]}") from exc
    if code not in (200, 204):
        raise RuntimeError(f"GitHub lifecycle dry-run dispatch inattendu: HTTP {code}")
    print(json.dumps({"lifecycle_dry_run_dispatch": "ok", "httpStatus": code}, ensure_ascii=False))
