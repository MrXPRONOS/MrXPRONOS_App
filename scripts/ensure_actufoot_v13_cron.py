#!/usr/bin/env python3
"""Provision only the dedicated V1.3 cron-job.org task; never print headers."""
import json
import os
import urllib.error
import urllib.request

API = "https://api.cron-job.org"
BASE = "https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/"
TARGET = BASE + "actufoot-v13-supervision.yml/dispatches"
SOURCE = BASE + "bsd-v2-telegram-hourly.yml/dispatches"
SOURCE_ID = 8613158
TITLE = "Mr XPRONOS – Actu Foot V1.3 Supervision"
SCHEDULE = {"timezone": "Africa/Lome", "expiresAt": 0, "hours": list(range(24)),
            "mdays": [-1], "minutes": [7, 37], "months": [-1], "wdays": [-1]}
BODY = {"ref": "main", "inputs": {"external_schedule": True, "dry_run": False,
                                   "send_alerts": False, "test_private_alert": False}}


def request(method, path, payload=None):
    key = os.environ.get("CRONJOB_API_KEY", "").strip()
    if not key:
        raise RuntimeError("V13_CRON_KEY_MISSING")
    req = urllib.request.Request(API + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError("V13_CRON_HTTP_" + str(exc.code)) from None
    except (urllib.error.URLError, ValueError, TimeoutError):
        raise RuntimeError("V13_CRON_TRANSPORT_ERROR") from None


def ensure(call=request):
    jobs = call("GET", "/jobs").get("jobs")
    if not isinstance(jobs, list):
        raise RuntimeError("V13_CRON_LIST_INVALID")
    matches = [j for j in jobs if j.get("url") == TARGET or j.get("title") == TITLE]
    if len(matches) > 1 or any(j.get("url") != TARGET or j.get("title") != TITLE for j in matches):
        raise RuntimeError("V13_CRON_CONFLICT_MANUAL_REVIEW")
    source = call("GET", f"/jobs/{SOURCE_ID}").get("jobDetails", {})
    if source.get("url") != SOURCE:
        raise RuntimeError("V13_CRON_SOURCE_MISMATCH")
    headers = (source.get("extendedData") or {}).get("headers") or {}
    auth = next((v for k, v in headers.items() if k.casefold() == "authorization"), "")
    if not isinstance(auth, str) or not auth.strip():
        raise RuntimeError("V13_CRON_AUTH_MISSING")
    definition = {"enabled": True, "title": TITLE, "saveResponses": False,
        "url": TARGET, "requestTimeout": 60, "redirectSuccess": False,
        "schedule": SCHEDULE, "requestMethod": 1,
        "extendedData": {"headers": {"Authorization": auth,
            "Accept": "application/vnd.github+json", "Content-Type": "application/json"},
            "body": json.dumps(BODY, separators=(",", ":"))}}
    if matches:
        job_id = matches[0]["jobId"]
        call("PATCH", f"/jobs/{job_id}", {"job": definition})
        action = "updated"
    else:
        job_id = call("PUT", "/jobs", {"job": definition})["jobId"]
        action = "created"
    detail = call("GET", f"/jobs/{job_id}").get("jobDetails", {})
    actual = detail.get("schedule") or {}
    try:
        body = json.loads((detail.get("extendedData") or {}).get("body") or "")
    except (ValueError, TypeError):
        raise RuntimeError("V13_CRON_BODY_INVALID") from None
    if (detail.get("enabled") is not True or detail.get("url") != TARGET
            or detail.get("title") != TITLE or detail.get("requestMethod") != 1
            or any(actual.get(k) != v for k, v in SCHEDULE.items()) or body != BODY):
        raise RuntimeError("V13_CRON_READBACK_MISMATCH")
    return {"action": action, "job_id": job_id, "enabled": True,
            "minutes": [7, 37], "timezone": "Africa/Lome",
            "next_execution": detail.get("nextExecution")}


if __name__ == "__main__":
    print("V13_CRON_CONFIG " + json.dumps(ensure(), sort_keys=True))
