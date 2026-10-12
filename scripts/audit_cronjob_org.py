#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone
API="https://api.cron-job.org"
KEY=os.environ.get("CRONJOB_API_KEY","").strip()
if not KEY:
    raise SystemExit("CRONJOB_API_KEY manquant")
HEADERS={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"}

def get(path):
    req=urllib.request.Request(API+path,headers=HEADERS,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError(f"cron-job.org HTTP {e.code} sur {path}: {body[:300]}")

def iso(ts):
    if not ts: return None
    return datetime.fromtimestamp(int(ts),timezone.utc).isoformat()

def target(url):
    m=re.search(r"/repos/MrXPRONOS/MrXPRONOS_App/actions/workflows/([^/]+)/dispatches",url or "",re.I)
    return m.group(1) if m else None

listing=get("/jobs")
result={"generated_at":datetime.now(timezone.utc).isoformat(),"someFailed":listing.get("someFailed"),"jobs":[]}
for j in listing.get("jobs",[]):
    wf=target(j.get("url"))
    title=(j.get("title") or "").lower()
    if not (wf or any(x in title for x in ("telegram","mrxpronos","bsd","xpvip","bookmaker"))):
        continue
    jid=j["jobId"]
    item={"jobId":jid,"title":j.get("title"),"enabled":j.get("enabled"),"targetWorkflow":wf,
          "requestMethod":j.get("requestMethod"),"schedule":j.get("schedule"),
          "lastStatus":j.get("lastStatus"),"lastExecution":iso(j.get("lastExecution")),
          "nextExecution":iso(j.get("nextExecution"))}
    try:
        d=get(f"/jobs/{jid}").get("jobDetails",{})
        item["requestMethod"]=d.get("requestMethod",item["requestMethod"])
        item["schedule"]=d.get("schedule",item["schedule"])
        body=((d.get("extendedData") or {}).get("body") or "")
        try: parsed=json.loads(body) if body else {}
        except Exception: parsed={}
        safe={}
        if isinstance(parsed,dict):
            if "ref" in parsed: safe["ref"]=parsed.get("ref")
            inputs=parsed.get("inputs")
            if isinstance(inputs,dict):
                safe["inputs"]={k:v for k,v in inputs.items() if not any(s in k.lower() for s in ("token","secret","password","key"))}
        item["dispatchBody"]=safe
        hist=get(f"/jobs/{jid}/history")
        item["history"]=[{"date":iso(x.get("date")),"datePlanned":iso(x.get("datePlanned")),
                          "status":x.get("status"),"statusText":x.get("statusText"),
                          "httpStatus":x.get("httpStatus"),"durationMs":x.get("duration")}
                         for x in (hist.get("history") or [])[:8]]
        item["predictions"]=[iso(x) for x in (hist.get("predictions") or [])]
    except Exception as e:
        item["auditError"]=str(e)
    result["jobs"].append(item)

groups={}
for item in result["jobs"]:
    k=(item.get("targetWorkflow"),json.dumps(item.get("schedule"),sort_keys=True))
    groups.setdefault(k,[]).append(item["jobId"])
result["duplicateGroups"]=[{"targetWorkflow":k[0],"schedule":json.loads(k[1]),"jobIds":v}
                           for k,v in groups.items() if k[0] and len(v)>1]
os.makedirs("audit",exist_ok=True)
with open("audit/cronjob_org_audit.json","w",encoding="utf-8") as f:
    json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
