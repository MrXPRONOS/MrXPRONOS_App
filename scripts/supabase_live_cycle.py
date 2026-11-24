"""Safe production bridge to the existing Supabase LIVE Edge Function.

No Neon dependency. Public checks are read-only; only an explicitly enabled
GitHub Actions dispatch with CRON_SECRET can refresh or validate. Never print
tokens, SQL credentials or whole API responses.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_URL="https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/live"
PROBES={
    "/matches":"matches",
    "/opportunities":"opportunities",
    "/today":"data",
    "/predictions/history":"history",
    "/daily/today":"predictions",
    "/notifications":"notifications",
}
class LiveBackendError(RuntimeError):
    pass

def base_url(value: str) -> str:
    url=urllib.parse.urlsplit(value.rstrip("/"))
    if (url.scheme!="https" or not url.hostname
            or url.hostname!="nhwafcpndlufzzxexikh.supabase.co"
            or url.path!="/functions/v1/live"
            or url.username or url.password or url.query or url.fragment):
        raise LiveBackendError("Only the configured HTTPS Supabase LIVE function is allowed")
    return value.rstrip("/")

def _post(url: str, secret: str, path: str) -> dict:
    if not secret:
        raise LiveBackendError("CRON_SECRET missing; operation aborted")
    req=urllib.request.Request(
        url+path,method="POST",data=b"{}",
        headers={"content-type":"application/json","x-cron-secret":secret,"accept":"application/json"})
    return request_json(req,expected=(200,202))

def request_json(req: urllib.request.Request,*,expected=(200,)) -> dict:
    try:
        with urllib.request.urlopen(req,timeout=35) as response:
            raw=response.read(1_000_001)
            if len(raw)>1_000_000:raise LiveBackendError("Supabase response too large")
            if response.status not in expected:raise LiveBackendError("Unexpected backend status "+str(response.status))
            value=json.loads(raw)
            if not isinstance(value,dict):raise LiveBackendError("Invalid Supabase JSON object")
            return value
    except urllib.error.HTTPError as error:
        # Never dump response bodies which may include private diagnostic values.
        raise LiveBackendError("Supabase HTTP "+str(error.code)) from None
    except urllib.error.URLError as error:
        raise LiveBackendError("Supabase network failure "+type(error.reason).__name__) from None
    except (ValueError,UnicodeDecodeError) as error:
        raise LiveBackendError("Invalid Supabase JSON response") from error

def read_routes(url: str) -> dict:
    report={}
    for path,key in PROBES.items():
        obj=request_json(urllib.request.Request(url+path,headers={
            "accept":"application/json","Origin":"https://mrxpronos.github.io"}))
        if key not in obj:raise LiveBackendError("Missing LIVE response field "+path)
        if key!="data" and not isinstance(obj[key],list):
            raise LiveBackendError("Non-list LIVE response "+path)
        report[path]=len(obj[key]) if isinstance(obj[key],list) else "ok"
    print("SUPABASE_LIVE_READ_OK",json.dumps(report,sort_keys=True))
    return report

def check_refresh_state(service_url: str,key: str,started: dt.datetime,*,timeout: int=75) -> dict:
    if not key:
        raise LiveBackendError("SUPABASE_SERVICE_ROLE_KEY is required for genuine refresh verification")
    hostname=urllib.parse.urlsplit(service_url).hostname
    root="https://"+hostname
    deadline=time.monotonic()+timeout
    params=urllib.parse.urlencode({"select":"name,last_run_at,last_ok","name":"eq.live_refresh","limit":1})
    while True:
        req=urllib.request.Request(root+"/rest/v1/cron_runs?"+params,headers={
            "apikey":key,"authorization":"Bearer "+key,"accept":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=20) as response:
                payload=json.loads(response.read(100_000))
        except urllib.error.HTTPError as error:
            raise LiveBackendError("Supabase refresh ledger HTTP "+str(error.code)) from None
        except urllib.error.URLError:
            raise LiveBackendError("Supabase refresh ledger unreachable") from None
        if not isinstance(payload,list):raise LiveBackendError("Invalid refresh ledger response")
        if payload and isinstance(payload[0],dict):
            state=payload[0]
            timestamp=str(state.get("last_run_at") or "")
            try:
                observed=dt.datetime.fromisoformat(timestamp.replace("Z","+00:00"))
            except ValueError:
                observed=None
            if observed and observed.tzinfo is not None and observed>=started-dt.timedelta(seconds=10):
                if state.get("last_ok") is not True:raise LiveBackendError("Supabase background refresh failed")
                print("SUPABASE_LIVE_REFRESH_RECORDED",observed.isoformat())
                return {"updated_at":observed.isoformat(),"last_ok":True}
        if time.monotonic()>=deadline:raise LiveBackendError("Supabase background refresh was not confirmed")
        time.sleep(5)

def run(mode:str)->dict[str,Any]:
    service=base_url(os.getenv("SUPABASE_LIVE_URL",DEFAULT_URL))
    result={"backend":"supabase","mode":mode,"live_url":service}
    result["readiness"]=read_routes(service)
    if mode=="probe":
        return result
    if os.getenv("GITHUB_REF")!="refs/heads/main" or os.getenv("GITHUB_EVENT_NAME") not in {"workflow_dispatch","schedule"}:
        raise LiveBackendError("Production writes require trusted main workflow dispatch")
    secret=os.getenv("CRON_SECRET","")
    if mode=="cycle":
        started=dt.datetime.now(dt.timezone.utc)
        accepted=_post(service,secret,"/refresh")
        if accepted.get("accepted") is not True:
            raise LiveBackendError("Supabase did not accept live refresh")
        print("SUPABASE_LIVE_REFRESH_ACCEPTED")
        result["refresh"]=check_refresh_state(service,os.getenv("SUPABASE_SERVICE_ROLE_KEY",""),started)
    checked=_post(service,secret,"/validate")
    if checked.get("success") is not True:raise LiveBackendError("Supabase prediction validation rejected")
    result["validation"]={k:v for k,v in checked.items() if k in
        {"success","validated","failed","skipped","finalized_existing","checked","won","lost"}}
    print("SUPABASE_LIVE_VALIDATED",json.dumps(result["validation"],sort_keys=True))
    return result

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("probe","cycle","validate"),default="probe")
    args=parser.parse_args()
    try:
        result=run(args.mode)
        print("SUPABASE_LIVE_CYCLE",json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except LiveBackendError as error:
        print("SUPABASE_LIVE_FAILURE",str(error))
        return 1
if __name__=="__main__":raise SystemExit(main())
