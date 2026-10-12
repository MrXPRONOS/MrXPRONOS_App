#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone

API="https://api.cron-job.org"
KEY=os.environ.get("CRONJOB_API_KEY","").strip()
if not KEY:
    raise SystemExit("CRONJOB_API_KEY manquant")
HEADERS={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}
TARGET_WF="football-production.yml"
TARGET_URL="https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/"+TARGET_WF+"/dispatches"
SOURCE_JOB_ID=8613158  # job GitHub dispatch existant, utilisé uniquement pour reprendre les headers GitHub

def req(method,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    r=urllib.request.Request(API+path,data=data,headers=HEADERS,method=method)
    try:
        with urllib.request.urlopen(r,timeout=30) as resp:
            raw=resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"cron-job.org HTTP {e.code} sur {path}: {body[:400]}")

def wf_from_url(url):
    m=re.search(r"/actions/workflows/([^/]+)/dispatches",url or "")
    return m.group(1) if m else None

listing=req("GET","/jobs")
existing=[]
for j in listing.get("jobs",[]):
    if wf_from_url(j.get("url"))==TARGET_WF:
        existing.append(j)

if len(existing)>1:
    raise SystemExit("SECURITE: plusieurs tâches cron-job.org ciblent déjà football-production.yml")

source=req("GET",f"/jobs/{SOURCE_JOB_ID}").get("jobDetails",{})
source_headers=((source.get("extendedData") or {}).get("headers") or {})
if wf_from_url(source.get("url"))!="bsd-v2-telegram-hourly.yml":
    raise SystemExit("SECURITE: le job source GitHub attendu a changé")
if not source_headers:
    raise SystemExit("SECURITE: headers GitHub absents sur le job source")

schedule={
    "timezone":"Africa/Sao_Tome",
    "expiresAt":0,
    "hours":list(range(7,24)),
    "mdays":[-1],
    "minutes":[0,30],
    "months":[-1],
    "wdays":[-1],
}
body=json.dumps({
    "ref":"main",
    "inputs":{
        "trigger_source":"cron-job.org",
        "dry_run":False,
        "force":False,
    }
},separators=(",",":"))

job={
    "enabled":True,
    "title":"Mr XPRONOS – Actu Foot Telegram",
    "saveResponses":False,
    "url":TARGET_URL,
    "requestTimeout":60,
    "redirectSuccess":False,
    "schedule":schedule,
    "requestMethod":1,
    "extendedData":{"headers":source_headers,"body":body},
}

if existing:
    jid=existing[0]["jobId"]
    req("PATCH",f"/jobs/{jid}",{"job":job})
    action="updated"
else:
    created=req("PUT","/jobs",{"job":job})
    jid=created["jobId"]
    action="created"

details=req("GET",f"/jobs/{jid}").get("jobDetails",{})
safe={
    "action":action,
    "jobId":jid,
    "title":details.get("title"),
    "enabled":details.get("enabled"),
    "targetWorkflow":wf_from_url(details.get("url")),
    "schedule":details.get("schedule"),
    "nextExecution":details.get("nextExecution"),
    "checked_at":datetime.now(timezone.utc).isoformat(),
}
assert safe["enabled"] is True
assert safe["targetWorkflow"]==TARGET_WF
assert safe["schedule"]["minutes"]==[0,30]
assert safe["schedule"]["hours"]==list(range(7,24))
print(json.dumps(safe,ensure_ascii=False,indent=2))

# Validation non destructive : même authentification que cron-job.org, mais workflow en dry-run.
if os.environ.get("ACTUFOOT_TEST_DISPATCH","").strip()=="1":
    test_body=json.dumps({
        "ref":"main",
        "inputs":{
            "trigger_source":"cron-job.org-test",
            "dry_run":True,
            "force":False,
        }
    }).encode("utf-8")
    test_headers={str(k):str(v) for k,v in source_headers.items()}
    test_headers.setdefault("Content-Type","application/json")
    test_req=urllib.request.Request(TARGET_URL,data=test_body,headers=test_headers,method="POST")
    try:
        with urllib.request.urlopen(test_req,timeout=30) as resp:
            resp.read()
            code=resp.status
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"GitHub dry-run dispatch HTTP {e.code}: {body[:400]}")
    if code not in (200,204):
        raise RuntimeError(f"GitHub dry-run dispatch inattendu: HTTP {code}")
    print(json.dumps({"dry_run_dispatch":"ok","httpStatus":code},ensure_ascii=False))
