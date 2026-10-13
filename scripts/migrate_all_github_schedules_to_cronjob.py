#!/usr/bin/env python3
import json, os, re, time, urllib.request, urllib.error
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
    request=urllib.request.Request(API+path,data=data,headers=HEADERS,method=method)
    try:
        with urllib.request.urlopen(request,timeout=30) as resp:
            raw=resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"cron-job.org HTTP {e.code} sur {path}: {body[:500]}")

def wf_from_url(url):
    m=re.search(r"/actions/workflows/([^/]+)/dispatches",url or "")
    return m.group(1) if m else None

def sched(hours, minutes):
    return {"timezone":"Africa/Sao_Tome","expiresAt":0,"hours":hours,"mdays":[-1],
            "minutes":minutes,"months":[-1],"wdays":[-1]}

def dispatch_body(inputs=None):
    d={"ref":"main"}
    if inputs is not None:
        d["inputs"]=inputs
    return json.dumps(d,separators=(",",":"))

desired=[
    {"title":"Génération quotidienne BSD V2","workflow":"bsd-v2-production.yml","schedule":sched([0],[5]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"Archive historique BSD","workflow":"bsd-backfill.yml","schedule":sched([1],[35]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"Settlement BSD V2","workflow":"bsd-v2-settlement.yml","schedule":sched([7],[50]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"BSD V2 – Settlement watchdog","workflow":"bsd-v2-settlement-watchdog.yml","schedule":sched([0,4,8,12,16,20],[20]),"inputs":{"trigger_source":"cron-job.org"}},
    {"title":"BSD V2 – Shadow daily","workflow":"bsd-v2-shadow.yml","schedule":sched([6],[15]),"inputs":{"selection_mode":"reliability","max_odds_events":"15"}},
    {"title":"Mr XPRONOS – Nettoyage cache","workflow":"clean-cache.yml","schedule":sched([0],[0]),"inputs":None},
    {"title":"Mr XPRONOS – Push matin","workflow":"push-notifications.yml","schedule":sched([7],[0]),"inputs":{"notification_type":"morning"}},
    {"title":"Mr XPRONOS – Push soir","workflow":"push-notifications.yml","schedule":sched([18],[0]),"inputs":{"notification_type":"evening"}},
    {"title":"Mr XPRONOS – Refresh social tokens","workflow":"refresh-social-tokens.yml","schedule":sched([4],[20]),"inputs":None},
    {"title":"Mr XPRONOS – Update football news","workflow":"update-footnews.yml","schedule":sched([0,3,6,9,12,15,18,21],[23]),"inputs":None},
    {"title":"Mr XPRONOS – Validation predictions","workflow":"validate_predictions.yml","schedule":sched([-1],[0,5,10,15,20,25,30,35,40,45,50,55]),"inputs":None},
    {"title":"Editorial – Free Studio","workflow":"editorial-free.yml","schedule":sched([5],[41]),"inputs":None},
    {"title":"Editorial – Analytics","workflow":"editorial-analytics.yml","schedule":sched([6],[17]),"inputs":None},
    {"title":"Editorial – Telegram","workflow":"editorial-telegram.yml","schedule":sched([8],[12]),"inputs":{"trigger_source":"cron-job.org","publish":False}},
    {"title":"Editorial – Facebook","workflow":"editorial-facebook.yml","schedule":sched([9],[12]),"inputs":{"trigger_source":"cron-job.org","publish":False}},
    {"title":"Editorial – Threads","workflow":"editorial-threads.yml","schedule":sched([10],[22]),"inputs":{"trigger_source":"cron-job.org","publish":False}},
]

listing=req("GET","/jobs").get("jobs",[])

def matches(spec):
    same=[j for j in listing if wf_from_url(j.get("url"))==spec["workflow"]]
    if spec["workflow"]=="push-notifications.yml":
        same=[j for j in same if j.get("title")==spec["title"]]
    return same

# Détecter précisément ce qui nécessite encore un appel d'écriture.
todo=[]
kept=[]
for spec in desired:
    same=matches(spec)
    if len(same)>1:
        raise SystemExit(f"SECURITE: doublons existants pour {spec['title']}: {[j['jobId'] for j in same]}")
    if same:
        j=same[0]
        if j.get("enabled") is True and j.get("schedule")==spec["schedule"]:
            kept.append({"title":spec["title"],"workflow":spec["workflow"],"jobId":j["jobId"],"action":"kept"})
            continue
        todo.append(("update",spec,j["jobId"]))
    else:
        todo.append(("create",spec,None))

# Si tout existe déjà, aucun besoin de lire les headers sensibles du job source.
source_headers=None
if todo:
    source=req("GET",f"/jobs/{SOURCE_JOB_ID}").get("jobDetails",{})
    source_headers=((source.get("extendedData") or {}).get("headers") or {})
    if wf_from_url(source.get("url"))!="bsd-v2-telegram-hourly.yml" or not source_headers:
        raise SystemExit("SECURITE: impossible de reutiliser l'auth GitHub du job source")

results=list(kept)
for action,spec,jid in todo:
    payload={
        "enabled":True,"title":spec["title"],"saveResponses":False,
        "url":GH_BASE+spec["workflow"]+"/dispatches","requestTimeout":60,
        "redirectSuccess":False,"schedule":spec["schedule"],"requestMethod":1,
        "extendedData":{"headers":source_headers,"body":dispatch_body(spec["inputs"])},
    }
    if action=="update":
        req("PATCH",f"/jobs/{jid}",{"job":payload})
        results.append({"title":spec["title"],"workflow":spec["workflow"],"jobId":jid,"action":"updated"})
    else:
        created=req("PUT","/jobs",{"job":payload})
        results.append({"title":spec["title"],"workflow":spec["workflow"],"jobId":created["jobId"],"action":"created"})
    # Éviter de dépasser la limite d'écriture de cron-job.org.
    time.sleep(1.2)

print(json.dumps({
    "migrated_at":datetime.now(timezone.utc).isoformat(),
    "count":len(results),
    "writes":len(todo),
    "results":results
},ensure_ascii=False,indent=2))
