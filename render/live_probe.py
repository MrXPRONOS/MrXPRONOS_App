"""Isolated Render Free LIVE coverage and throughput probe. No Supabase writes."""
import os, json, time, threading, re
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ESPN="https://site.api.espn.com/apis/site/v2/sports/soccer/all"
SPORTSCORE="https://sportscore.com/api/v1"
WORKERS=min(12,max(1,int(os.getenv("MAX_WORKERS","8"))))
TIMEOUT=float(os.getenv("REQUEST_TIMEOUT","9"))
CORE=("corner_kicks","total_shots","shots_on_target","fouls","yellow_cards","red_cards","ball_possession")
ALIASES={
 "corners":"corner_kicks","cornerkicks":"corner_kicks","woncorners":"corner_kicks",
 "totalshots":"total_shots","shots":"total_shots","shotstotal":"total_shots",
 "shotsontarget":"shots_on_target","shotsongoal":"shots_on_target","shotsontargettotal":"shots_on_target",
 "fouls":"fouls","foulscommitted":"fouls",
 "yellowcards":"yellow_cards","redcards":"red_cards",
 "possession":"ball_possession","possessionpct":"ball_possession","possessionpercentage":"ball_possession","ballpossession":"ball_possession"}
cache={"last":None}
run_lock=threading.Lock()
quota_stop=threading.Event()

def fetch(url):
    start=time.monotonic()
    if quota_stop.is_set():return None,"provider rate limit detected; skipped",0
    try:
        req=Request(url,headers={"User-Agent":"MrXpronosCoverageTest/1.0","Accept":"application/json"})
        with urlopen(req,timeout=TIMEOUT) as resp:
            data=json.load(resp)
        return data,None,round(time.monotonic()-start,3)
    except HTTPError as e:
        if e.code==429:quota_stop.set()
        return None,"HTTP "+str(e.code),round(time.monotonic()-start,3)
    except Exception as e:
        return None,(type(e).__name__+": "+str(e))[:160],round(time.monotonic()-start,3)

def state(v):
    s=str(v or "").lower()
    if s in ("in","live","playing","inprogress","in-progress") or "half" in s or "live" in s:return "in"
    if s in ("post","final","finished","ft") or "finish" in s or "complete" in s:return "post"
    return "pre"

def flatten_stats(container):
    out={}
    for k,v in (container.items() if isinstance(container,dict) else []):
        field=ALIASES.get(re.sub(r"[^a-z0-9]","",str(k).lower()))
        if field:
            try:
                n=float(str(v).replace("%","").strip())
                if n>=0:out[field]=n
            except (ValueError,TypeError):pass
    if isinstance(container,list):
        for row in container:
            if not isinstance(row,dict):continue
            key=row.get("name") or row.get("label") or row.get("type") or row.get("abbreviation")
            field=ALIASES.get(re.sub(r"[^a-z0-9]","",str(key or "").lower()))
            if field:
                try:
                    value=row.get("displayValue",row.get("value"))
                    n=float(str(value).replace("%","").strip())
                    if n>=0:out[field]=n
                except (TypeError,ValueError):pass
    return out

def normalize_espn(event,body):
    teams=((body or {}).get("boxscore") or {}).get("teams") or []
    parsed=[flatten_stats(t.get("statistics") or []) for t in teams if isinstance(t,dict)]
    if len(parsed)!=2:return {}
    return {k:[parsed[0][k],parsed[1][k]] for k in CORE if k in parsed[0] and k in parsed[1]}

def normalize_sportscore(body):
    payload=(body or {}).get("data") or body or {}
    root=payload.get("match") or payload
    if not isinstance(root,dict):return {}
    for key in ("stats","statistics","team_stats","teamStats","match_statistics"):
        part=root.get(key)
        if not part:continue
        if isinstance(part,dict):
            h=flatten_stats(part.get("home") or part.get("home_team") or {})
            a=flatten_stats(part.get("away") or part.get("away_team") or {})
            if h or a:return {k:[h[k],a[k]] for k in CORE if k in h and k in a}
        if isinstance(part,list):
            out={}
            for row in part:
                if not isinstance(row,dict):continue
                field=ALIASES.get(re.sub(r"[^a-z0-9]","",str(row.get("name") or row.get("label") or row.get("type") or "").lower()))
                if not field:continue
                try:
                    h=float(str(row.get("home",row.get("homeValue"))).replace("%",""))
                    a=float(str(row.get("away",row.get("awayValue"))).replace("%",""))
                    if h>=0 and a>=0:out[field]=[h,a]
                except (TypeError,ValueError):pass
            if out:return out
    return {}

def detail(source,event):
    if source=="espn":
        uid=str(event.get("id",""))
        url=ESPN+"/summary?"+urlencode({"event":uid})
    else:
        uid=str(event.get("id") or event.get("match_id") or "")
        path=str(event.get("url") or event.get("match_url") or "")
        match=re.search(r"/match/([^/?#]+)/",path)
        slug=event.get("slug") or event.get("match_slug") or (match.group(1) if match else "")
        url=SPORTSCORE+"/match/?"+urlencode({"sport":"football","slug":slug}) if slug else None
    if not url:
        return {"source":source,"id":uid,"error":"no fixture slug","stats":{},"duration":0}
    body,error,duration=fetch(url)
    stats=(normalize_espn(event,body) if source=="espn" else normalize_sportscore(body)) if body else {}
    return {"source":source,"id":uid,"error":error,"stats":stats,"duration":duration}

def probe():
    with run_lock:
        quota_stop.clear()
        start=time.monotonic()
        now=datetime.now(timezone.utc)
        days=[now.strftime("%Y%m%d")]
        if now.hour<7:days.insert(0,(now-timedelta(days=1)).strftime("%Y%m%d"))
        discovery=[]
        jobs=[]
        espn_events={}
        for d in days:
            p,e,lat=fetch(ESPN+"/scoreboard?"+urlencode({"dates":d,"limit":500}))
            events=p.get("events",[]) if isinstance(p,dict) else []
            discovery.append({"source":"espn","date":d,"events":len(events),"error":e,"seconds":lat})
            for evt in events:
                if evt.get("id"):espn_events[str(evt["id"])]=evt
        for evt in espn_events.values():
            status=(((evt.get("status") or {}).get("type") or {}).get("state") or "")
            if state(status)=="in":jobs.append(("espn",evt))
        raw,err,lat=fetch(SPORTSCORE+"/fixtures/?"+urlencode({"sport":"football","date":now.strftime("%Y-%m-%d"),"status":"live","limit":200}))
        rows=[]
        if isinstance(raw,dict):
            rows=next((raw[k] for k in ("matches","fixtures","results") if isinstance(raw.get(k),list)),[])
        discovery.append({"source":"sportscore","date":now.strftime("%Y-%m-%d"),"events":len(rows),"error":err,"seconds":lat,
                          "pagination_unverified":True,"requested_limit":200})
        for evt in rows:
            if not isinstance(evt,dict):continue
            if state(evt.get("status") or evt.get("status_text"))=="in":jobs.append(("sportscore",evt))
        real_live_count=len(jobs)
        sample_used=False
        if not jobs:
            finished=[e for e in espn_events.values()
                if state((((e.get("status") or {}).get("type") or {}).get("state") or ""))=="post"]
            jobs=[("espn",e) for e in finished[:5]]
            sample_used=True
        results=[]
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            fs=[pool.submit(detail,source,evt) for source,evt in jobs]
            for f in as_completed(fs):
                try:results.append(f.result())
                except Exception as e:results.append({"source":"unknown","id":"","error":str(e),"stats":{},"duration":0})
        by_source={}
        for source in ("espn","sportscore"):
            subset=[r for r in results if r["source"]==source]
            by_source[source]={
                "details":len(subset),"ok":sum(not r["error"] for r in subset),
                "with_stat_pairs":sum(bool(r["stats"]) for r in subset),
                "complete_core_7":sum(len(r["stats"])==7 for r in subset),
                "available_stat_fields":{k:sum(k in r["stats"] for r in subset) for k in CORE}}
        duration=round(time.monotonic()-start,2)
        result={"at_utc":datetime.now(timezone.utc).isoformat(),"coverage":"ESPN + SportScore feeds only; NOT all football worldwide",
                "discovery":discovery,"live_detail_tasks":real_live_count,
                "historical_sanity_sample":sample_used,
                "details_attempted":len(results),
                "details_ok":sum(r["error"] is None for r in results),
                "details_with_stats":sum(bool(r["stats"]) for r in results),
                "workers":WORKERS,"duration_seconds":duration,
                "completed_under_60s":duration<60,
                "rate_limit_hit":quota_stop.is_set(),"by_source":by_source,
                "failures":[{"source":r["source"],"id":r["id"],"error":r["error"]} for r in results if r["error"]][:15],
                "match_samples":[{"source":r["source"],"id":r["id"],"stat_fields":list(r["stats"])} for r in results[:10]]}
        cache["last"]=result
        print("LIVE_PROBE_RESULT "+json.dumps(result,ensure_ascii=False),flush=True)
        return result

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route=urlparse(self.path).path
        if route=="/health":self.reply({"ok":True,"service":"MrXPRONOS isolated Render coverage test"})
        elif route=="/last":self.reply(cache["last"] or {"status":"startup probe not yet complete"})
        elif route=="/probe":self.reply(probe())
        else:self.reply({"endpoints":["/health","/last","/probe"]},404)
    def reply(self,body,status=200):
        raw=json.dumps(body,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

if __name__=="__main__":
    print("LIVE_PROBE_BOOT",datetime.now(timezone.utc).isoformat(),flush=True)
    if os.getenv("RUN_PROBE_ON_STARTUP","1")=="1":
        threading.Thread(target=probe,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",int(os.getenv("PORT","10000"))),Handler).serve_forever()
