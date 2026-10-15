#!/usr/bin/env python3
"""Analyse locale d'exports HAR/JSON. Aucun appel réseau ni authentification."""
import argparse,json,pathlib,re
from urllib.parse import urlsplit
from validation import validate

SENSITIVE=re.compile(r"(authorization|cookie|token|secret|api.?key|password|session|signature|credential)",re.I)
HOSTS={"sportybet.com":"sportybet","1xbet.com":"1xbet"}
def provider_for(url):
    host=(urlsplit(url).hostname or "").lower()
    for domain,name in HOSTS.items():
        if host==domain or host.endswith("."+domain):return name
    return None

def extract_entries(payload):
    if isinstance(payload,dict) and isinstance(payload.get("log"),dict):
        for entry in payload["log"].get("entries",[]):
            request=entry.get("request",{})
            url=request.get("url","")
            provider=provider_for(url)
            if not provider:continue
            response=entry.get("response",{})
            content=response.get("content",{})
            raw=content.get("text")
            if not isinstance(raw,str) or content.get("encoding")=="base64":continue
            try: obj=json.loads(raw)
            except json.JSONDecodeError:continue
            yield provider,urlsplit(url).path,obj
    else:
        yield "unknown","offline_json",payload

def build_report(payload,source):
    rows=[]
    for provider,path,obj in extract_entries(payload):
        if provider=="unknown":
            for test_provider in ("sportybet","1xbet"):
                v=validate(obj,test_provider)
                rows.append({"provider":test_provider,"path":path,"valid":v["valid"],"findings":v["findings"],"counts":v["analysis"]["counts"] if v["analysis"] else None})
        else:
            v=validate(obj,provider)
            rows.append({"provider":provider,"path":path,"valid":v["valid"],"findings":v["findings"],"counts":v["analysis"]["counts"] if v["analysis"] else None})
    return {"source_type":source,"network_tested_by_script":False,"responses_examined":len(rows),"data":rows,
      "limitations":"Une capture HAR peut contenir des secrets: ne pas publier les captures brutes."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=pathlib.Path)
    ap.add_argument("--output",type=pathlib.Path,default=pathlib.Path("odds_diagnostic_results/har_report.json"))
    args=ap.parse_args()
    payload=json.loads(args.source.read_text(encoding="utf-8"))
    report=build_report(payload,"har" if "log" in payload else "json")
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"responses_examined":report["responses_examined"],"output":str(args.output)}))
if __name__=="__main__": main()
