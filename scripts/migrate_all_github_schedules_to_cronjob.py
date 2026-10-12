#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone

API="https://api.cron-job.org"
KEY=os.environ.get("CRONJOB_API_KEY","").strip()
if not KEY:
    raise SystemExit("CRONJOB_API_KEY manquant")
HEADERS={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}
GH_BASE="https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/"
SOURCE_JOB_ID=8613158

def req(method,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    r=urllib.request.Request(API+path,data=data,headers=HEADERS,method=method)
    try:
        with urllib.request.urlopen(r,timeout=30) as resp:
            raw=resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"cron-job.org HTTP {e.code} sur {path}: {body[:500]}")

def wf_from_url(url):
    m=re.search(r"/actions/workflows/([^/]+)/dispatches",url or "")
    return m.group(1) if m else None

def parse_body(details):
    body=((details.get("extendedData") or {}).get("body") or "")
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {}

def sched(hours, minutes):
    return {
        "timezone":"Africa/Sao_Tome","expiresAt":0,
        "hours":hours,"mdays":[-1],"minutes":minutes,"months":[-1],"wdays":[-1]
    }

def body(inputs=None):
    d={"ref":"main"}
    if inputs is not None:
        d["inputs"]=inputs
    return json.dumps(d,separators=(",",":"))

source=req("GET",f"/jobs/{SOURCE_JOB_ID}").get("jobDetails",{})
source_headers=((source.get("extendedData") or {}).get("headers") or {})
if wf_from_url(source.get("url"))!="bsd-v2-telegram-hourly.yml" or not source_headers:
    raise SystemExit("SECURITE: impossible de reutiliser l'auth GitHub du job source")

desired=[
    # Déjà présents sur cron-job.org : on les vérifie/met à jour sans les dupliquer.
    {"title":"Génération quotidienne BSD V2","workflow":"bsd-v2-production.yml",
     "schedule":sched([0],[5]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"Archive historique BSD","workflow":"bsd-backfill.yml",
     "schedule":sched([1],[35]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"Settlement BSD V2","workflow":"bsd-v2-settlement.yml",
     "schedule":sched([7],[50]),"inputs":{"trigger_source":"cron-job.org"}},

    # Planifications encore uniquement GitHub avant cette migration.
    {"title":"BSD V2 – Settlement watchdog","workflow":"bsd-v2-settlement-watchdog.yml",
     "schedule":sched([0,4,8,12,16,20],[20]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"BSD V2 – Shadow daily","workflow":"bsd-v2-shadow.yml",
     "schedule":sched([6],[15]),"inputs":{"selection_mode":"reliability","max_odds_events":"15"}},
    {"title":"Mr XPRONOS – Nettoyage cache","workflow":"clean-cache.yml",
     "schedule":sched([0],[0]),"inputs":None},
    {"title":"Mr XPRONOS – Push matin","workflow":"push-notifications.yml",
     "schedule":sched([7],[0]),"inputs":{"notification_type":"morning"}},
    {"title":"Mr XPRONOS – Push soir","workflow":"push-notifications.yml",
     "schedule":sched([18],[0]),"inputs":{"notification_type":"evening"}},
    {"title":"Mr XPRONOS – Refresh social tokens","workflow":"refresh-social-tokens.yml",
     "schedule":sched([4],[20]),"inputs":None},
    {"title":"Mr XPRONOS – Update football news","workflow":"update-footnews.yml",
     "schedule":sched([0,3,6,9,12,15,18,21],[23]),"inputs":None},
    {"title":"Mr XPRONOS – Validation predictions","workflow":"validate_predictions.yml",
     "schedule":sched([-1],[0,5,10,15,20,25,30,35,40,45,50,55]),"inputs":None},
]

listing=req("GET","/jobs").get("jobs",[])
details_cache={}
for j in listing:
    try:
        details_cache[j["jobId"]]=req("GET",f"/jobs/{j['jobId']}").get("jobDetails",{})
    except Exception:
        pass

def identity_match(spec, details):
    if wf_from_url(details.get("url")) != spec["workflow"]:
        return False
    if spec["workflow"]=="push-notifications.yml":
        parsed=parse_body(details)
        got=((parsed.get("inputs") or {}).get("notification_type"))
        want=(spec["inputs"] or {}).get("notification_type")
        return got==want
    return True

results=[]
for spec in desired:
    matches=[(jid,d) for jid,d in details_cache.items() if identity_match(spec,d)]
    if len(matches)>1:
        raise SystemExit(f"SECURITE: doublons cron-job.org déjà présents pour {spec['title']}: {[x[0] for x in matches]}")
    payload={
        "enabled":True,
        "title":spec["title"],
        "saveResponses":False,
        "url":GH_BASE+spec["workflow"]+"/dispatches",
        "requestTimeout":60,
        "redirectSuccess":False,
        "schedule":spec["schedule"],
        "requestMethod":1,
        "extendedData":{
            "headers":source_headers,
            "body":body(spec["inputs"]),
        },
    }
    if matches:
        jid=matches[0][0]
        req("PATCH",f"/jobs/{jid}",{"job":payload})
        action="updated"
    else:
        created=req("PUT","/jobs",{"job":payload})
        jid=created["jobId"]
        action="created"
    verify=req("GET",f"/jobs/{jid}").get("jobDetails",{})
    if not verify.get("enabled") or wf_from_url(verify.get("url"))!=spec["workflow"]:
        raise SystemExit(f"ECHEC validation {spec['title']}")
    if verify.get("schedule")!=spec["schedule"]:
        raise SystemExit(f"ECHEC planning {spec['title']}: {verify.get('schedule')}")
    results.append({
        "title":spec["title"],"workflow":spec["workflow"],"jobId":jid,
        "action":action,"schedule":verify.get("schedule"),"nextExecution":verify.get("nextExecution")
    })

# Vérification finale : exactement un job par identité désirée.
all_jobs=req("GET","/jobs").get("jobs",[])
all_details=[]
for j in all_jobs:
    try:
        d=req("GET",f"/jobs/{j['jobId']}").get("jobDetails",{})
        all_details.append((j["jobId"],d))
    except Exception:
        pass
for spec in desired:
    found=[jid for jid,d in all_details if identity_match(spec,d)]
    if len(found)!=1:
        raise SystemExit(f"ECHEC final {spec['title']}: {found}")

print(json.dumps({
    "migrated_at":datetime.now(timezone.utc).isoformat(),
    "count":len(results),
    "results":results
},ensure_ascii=False,indent=2))
