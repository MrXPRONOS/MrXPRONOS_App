"""Isolated free Render ESPN live-data coverage benchmark. No database writes."""
import os, time, json, threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ESPN="https://site.api.espn.com/apis/site/v2/sports/soccer/all"
MAX_WORKERS=min(20,max(1,int(os.getenv("MAX_WORKERS","12"))))
cache={"last":None}
lock=threading.Lock()

def fetch(url):
    start=time.monotonic()
    try:
        req=Request(url,headers={"User-Agent":"MrXpronosCoverageTest/1.0","Accept":"application/json"})
        with urlopen(req,timeout=10) as response:
            data=json.load(response)
        return data,None,round((time.monotonic()-start)*1000)
    except Exception as e:
        return None,str(e)[:180],round((time.monotonic()-start)*1000)

def summarize(event):
    eid=str(event.get("id",""))
    data,error,ms=fetch(ESPN+"/summary?"+urlencode({"event":eid}))
    categories=set()
    if data:
        for box in data.get("boxscore",{}).get("players",[]) or []:
            for item in box.get("statistics",[]) or []:
                categories.update(item.get("names",[]) or [])
        for team in data.get("boxscore",{}).get("teams",[]) or []:
            for item in team.get("statistics",[]) or []:
                if isinstance(item,dict):
                    categories.add(str(item.get("name") or item.get("label") or ""))
    return {"id":eid,"name":event.get("name"),"stats_count":len(categories),"stats_keys":sorted(categories)[:40],"latency_ms":ms,"error":error}

def probe():
    begin=time.monotonic()
    day=datetime.now(timezone.utc).strftime("%Y%m%d")
    scoreboard,error,score_ms=fetch(ESPN+"/scoreboard?"+urlencode({"dates":day,"limit":1000}))
    events=(scoreboard or {}).get("events",[])
    # Do not silently truncate fixtures; one task per event.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures={pool.submit(summarize,e):str(e.get("id")) for e in events}
        rows=[f.result() for f in as_completed(futures)]
    rows.sort(key=lambda r:r["id"])
    return {"at_utc":datetime.now(timezone.utc).isoformat(),"source":"ESPN soccer/all","scope":"ESPN events only; not all football worldwide","fixture_count":len(events),"details_attempted":len(rows),"details_success":sum(r["error"] is None for r in rows),"matches_with_stats":sum(r["stats_count"]>0 for r in rows),"scoreboard_error":error,"scoreboard_latency_ms":score_ms,"workers":MAX_WORKERS,"duration_seconds":round(time.monotonic()-begin,2),"within_one_minute":time.monotonic()-begin<60,"items":rows}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/health"):
            self.reply({"ok":True,"service":"mrxpronos-live-coverage-probe"})
        elif self.path.startswith("/last"):
            self.reply(cache["last"] or {"status":"not_run"})
        elif self.path.startswith("/probe"):
            with lock:
                result=probe()
                cache["last"]=result
            print(json.dumps({k:v for k,v in result.items() if k!="items"}),flush=True)
            self.reply(result)
        else:self.reply({"endpoints":["/health","/probe","/last"]},404)
    def reply(self,obj,status=200):
        body=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__=="__main__":
    port=int(os.getenv("PORT","10000"))
    print("Render benchmark on",port,flush=True)
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
