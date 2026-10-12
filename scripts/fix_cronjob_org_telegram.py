#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone

API="https://api.cron-job.org"
KEY=os.environ.get("CRONJOB_API_KEY","").strip()
if not KEY:
    raise SystemExit("CRONJOB_API_KEY manquant")
HEADERS={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}

EXPECTED={
    8613284:"telegram-daily-xpvip-promo.yml",
    8613285:"telegram-day-based-bookmaker-promos.yml",
    8613320:"telegram-daily-bookmaker-bonus-ads.yml",
    8613322:"telegram-daily-bookmaker-guide.yml",
    8613158:"bsd-v2-telegram-hourly.yml",
    8613085:"bsd-v2-telegram-wins.yml",
}

def request(method,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(API+path,data=data,headers=HEADERS,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"cron-job.org HTTP {e.code} sur {path}: {body[:400]}")

def workflow_from_url(url):
    m=re.search(r"/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/([^/]+)/dispatches",url or "",re.I)
    return m.group(1) if m else None

# Fail closed: verify all six known jobs still point to the expected workflows.
before={}
for jid,wf in EXPECTED.items():
    details=request("GET",f"/jobs/{jid}").get("jobDetails",{})
    actual=workflow_from_url(details.get("url"))
    if actual != wf:
        raise SystemExit(f"SECURITE: job {jid} cible {actual!r}, attendu {wf!r}; aucune modification")
    before[jid]={
        "title":details.get("title"),
        "enabled":details.get("enabled"),
        "workflow":actual,
        "schedule":details.get("schedule"),
    }

daily=lambda hour: {
    "timezone":"Africa/Sao_Tome",
    "expiresAt":0,
    "hours":[hour],
    "mdays":[-1],
    "minutes":[0],
    "months":[-1],
    "wdays":[-1],
}

# Correct the only two cron-job.org issues found by the audit.
request("PATCH","/jobs/8613285",{"job":{"enabled":True,"schedule":daily(6)}})
request("PATCH","/jobs/8613322",{"job":{"enabled":True,"schedule":daily(10)}})

after={}
for jid,wf in EXPECTED.items():
    details=request("GET",f"/jobs/{jid}").get("jobDetails",{})
    after[jid]={
        "title":details.get("title"),
        "enabled":details.get("enabled"),
        "workflow":workflow_from_url(details.get("url")),
        "schedule":details.get("schedule"),
        "nextExecution":details.get("nextExecution"),
    }

# Assertions on the two corrected jobs.
assert after[8613285]["enabled"] is True
assert after[8613285]["schedule"]["hours"] == [6]
assert after[8613285]["schedule"]["minutes"] == [0]
assert after[8613322]["enabled"] is True
assert after[8613322]["schedule"]["hours"] == [10]
assert after[8613322]["schedule"]["minutes"] == [0]

print(json.dumps({
    "updated_at":datetime.now(timezone.utc).isoformat(),
    "changes":{
        "8613285":"enabled; daily at 06:00 Africa/Sao_Tome",
        "8613322":"enabled; daily at 10:00 Africa/Sao_Tome",
    },
    "before":before,
    "after":after,
},ensure_ascii=False,indent=2))
