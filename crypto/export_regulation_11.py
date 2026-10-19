"""Mr XPRONOS #11 — regulation of cryptoassets in Africa, TEST ONLY.

Eight existing free publisher RSS feeds. An article is never a legal verdict:
no assertion about entry into force, jurisdiction or local permissibility.
Only currently published, Africa-related, regulation-related headlines qualify.
No production channel, no production scheduler and no fabricated real stories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import feedparser
import requests
from crypto import export_regulation_v2 as base
from crypto.news_sources_v2 import EDITORIAL_FEEDS

UTC=timezone.utc
ROOT=Path("crypto/generated/test")
STATE=Path("crypto/regulation_11_test_state.json")
AGE_H=96
PUBLICATION=11
FEEDS=EDITORIAL_FEEDS

# Full words only: "Niger" is not "Nigeria"; "Congo" is not "DR Congo".
REGIONS={
    "TOGO":r"\b(togo|togolese|togolais)\b",
    "BÉNIN":r"\b(benin|beninese|bénin|béninois)\b",
    "CÔTE D'IVOIRE":r"\b(ivory coast|c[oô]te d.ivoire|ivorian|ivoirien)\b",
    "SÉNÉGAL":r"\b(senegal|s[eé]n[eé]gal|senegalese|s[eé]n[eé]galais)\b",
    "BURKINA FASO":r"\b(burkina(?:\s+faso)?|burkinab[eè])\b",
    "MALI":r"\b(mali|malian|malien)\b",
    "NIGER":r"\b(niger|nig[eé]rien)\b",
    "GUINÉE-BISSAU":r"\b(guinea.bissau|guin[eé]e.bissau)\b",
    "NIGÉRIA":r"\b(nigeria|nigerian|nig[eé]ria)\b",
    "GHANA":r"\b(ghana|ghanaian|ghan[eé]en)\b",
    "CAMEROUN":r"\b(cameroon|cameroun|cameroonian|camerounais)\b",
    "GABON":r"\b(gabon|gabonese|gabonais)\b",
    "TCHAD":r"\b(chad|tchad|chadian|tchadien)\b",
    "CONGO":r"\b(republic of the congo|republic of congo|congo.brazzaville)\b",
    "RDC":r"\b(democratic republic of (the )?congo|d\.r\. congo|drc|congo.kinshasa)\b",
    "CENTRAFRIQUE":r"\b(central african republic|centrafrique)\b",
    "GUINÉE ÉQUATORIALE":r"\b(equatorial guinea|guin[eé]e [eé]quatoriale)\b",
    "AFRIQUE DU SUD":r"\b(south africa|south african|afrique du sud)\b",
    "KENYA":r"\b(kenya|kenyan)\b",
    "OUGANDA":r"\b(uganda|ugandan)\b",
    "RWANDA":r"\b(rwanda|rwandan)\b",
    "ÉTHIOPIE":r"\b(ethiopia|ethiopian|[eé]thiopie)\b",
}
REGIONAL={
    "UEMOA":r"\b(uemoa|waemu|west african economic and monetary union)\b",
    "CEMAC":r"\b(cemac|central african economic and monetary community)\b",
    "CEDEAO":r"\b(cedeao|ecowas|economic community of west african states)\b",
    "BCEAO":r"\b(bceao|central bank of west african states)\b",
    "BEAC":r"\b(beac|bank of central african states)\b",
    "AFRIQUE":r"\b(africa|african|afrique|africain)\b",
}
CRYPTO=re.compile(r"\b(crypto(?:currency|currencies|asset|assets)?|bitcoin|"
                  r"stablecoins?|digital assets?|virtual assets?|vasps?|"
                  r"cryptomonnaies?|cryptocurrency|blockchain|cbdc)\b",re.I)
LAW=re.compile(r"\b(regulat(?:ion|ions|ory|ors|or|e|ed)|licen[sc](?:e|es|ing|ed)|"
               r"law|laws|legislation|policy|rules?|bill|bills|"
               r"central bank|ban|bans|banned|tax|taxes|taxation|"
               r"supervision|compliance|aml|kyc|legal|illegal|"
               r"guidance|consultation|framework|approved|adopted|"
               r"restrict(?:ion|ions|ed)?|oversight|regulator|authorization)\b",re.I)
EXCLUDED=("price prediction","technical analysis","opinion:","sponsored","advertorial",
          "rumor","rumour","unconfirmed","how to buy","price analysis",
          "weekly roundup","daily roundup","could bitcoin","will bitcoin")
HIGH_IMPACT=re.compile(r"\b(legal|illegal|banned|ban|prohibited|law passed|"
                       r"now allows|legalized|entered into force|took effect|"
                       r"officially approved)\b",re.I)
LABELS=(("FISCALITÉ",r"\b(tax|taxes|taxation|fiscal)\b"),
        ("LICENCES & AGRÉMENTS",r"\b(licen[sc]|authorization|approval|vasp)\b"),
        ("BANQUE CENTRALE",r"\b(central bank|bceao|beac|monetary)\b"),
        ("PROJET DE LOI",r"\b(proposal|draft|bill|consultation|parliament)\b"),
        ("CADRE RÉGLEMENTAIRE",r"\b(regulation|rules|framework|policy|law)\b"))

def regions_of(title):
    explicit=[key for key,pattern in REGIONS.items() if re.search(pattern,title,re.I)]
    if explicit:
        return explicit[0] if len(explicit)==1 else "PLUSIEURS PAYS AFRICAINS"
    regional=[key for key,pattern in REGIONAL.items() if re.search(pattern,title,re.I)]
    return regional[0] if len(regional)==1 else ("AFRIQUE" if regional else None)

def topic_of(title):
    for label,pattern in LABELS:
        if re.search(pattern,title,re.I):
            return label
    return "RÉGLEMENTATION"

def parse_entry(entry,source,now):
    if source not in FEEDS:
        raise ValueError("Untrusted publisher")
    title=base.clean(entry.get("title"),190)
    if (len(title)<28 or any(w in title.lower() for w in EXCLUDED)
        or not CRYPTO.search(title) or not LAW.search(title)):
        raise ValueError("Not a qualifying African crypto regulation headline")
    region=regions_of(title)
    if region is None:
        raise ValueError("Africa not explicitly established in article headline")
    url=base.canonical_url(entry.get("link"),source)
    stamp=entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published") or entry.get("updated")
    date=base.iso_time(stamp,now)
    dt=datetime.fromisoformat(date)
    if (now-dt).total_seconds()>AGE_H*3600:
        raise ValueError("Regulatory article too old")
    return {"source":source,"title":title,"url":url,"published_at":date,
            "region":region,"topic":topic_of(title),
            "legal_status_confirmed":False,
            "high_impact":bool(HIGH_IMPACT.search(title))}

def fingerprint(article):
    return hashlib.sha256(article["url"].encode()).hexdigest()[:24]

def fetch_feed(source,url,now,getter=requests.get):
    try:
        response=getter(url,headers=base.HEADERS,timeout=(8,18))
        response.raise_for_status()
        if not 0<len(response.content)<2_000_000: raise ValueError("Invalid RSS size")
        parsed=feedparser.parse(response.content)
        if parsed.bozo or not parsed.entries: raise ValueError("Invalid or empty RSS")
        found=[]
        for entry in parsed.entries[:90]:
            try: found.append(parse_entry(entry,source,now))
            except (ValueError,TypeError,KeyError,OverflowError): pass
        print("REG11_RSS",source,"entries",len(parsed.entries),"eligible",len(found))
        return found
    except (requests.RequestException,ValueError,TypeError) as exc:
        print("REG11_SOURCE_UNAVAILABLE",source,type(exc).__name__)
        return []

def build(article, now=None, demo=False):
    now=now or datetime.now(UTC)
    if demo:
        return {"publication":11,"status":"demo","is_demo":True,
                "collected_at":now.isoformat(),"main":article,
                "fingerprint":"DEMO_FAKE","source_count":0,
                "legal_status_confirmed":False,
                "synopsis_fr":"EXEMPLE FICTIF : veille sur les règles crypto en Afrique."}
    # High-impact legal assertions need a primary official publication. Do not
    # imply factual verification from an RSS headline alone.
    if article["high_impact"]:
        raise ValueError("Unconfirmed claim of legal force, ban or authorization")
    region=article["region"]
    synopsis=("Une actualité sur les règles encadrant les cryptoactifs "
              + ("en "+region.title() if region not in ("UEMOA","CEMAC","CEDEAO","BCEAO","BEAC","AFRIQUE") and not region.startswith("PLUSIEURS")
                 else "dans la zone "+region if region not in ("AFRIQUE","PLUSIEURS PAYS AFRICAINS")
                 else "en Afrique")+".")
    result={"publication":11,"status":"attributed_press","is_demo":False,
            "collected_at":now.isoformat(),"main":article,
            "fingerprint":fingerprint(article),"source_count":1,
            "legal_status_confirmed":False,"synopsis_fr":synopsis}
    validate_real(result,now)
    return result

def validate_real(d,now=None):
    now=now or datetime.now(UTC)
    if d.get("publication")!=11 or d.get("status")!="attributed_press" or d.get("is_demo") is not False:
        raise ValueError("Only real source-attributed #11 can pass")
    a=d.get("main")
    if not isinstance(a,dict) or a.get("source") not in FEEDS or
        a.get("legal_status_confirmed") is not False:
        raise ValueError("Invalid publisher or unsupported legal certainty")
    if a.get("high_impact") is not False or d.get("legal_status_confirmed") is not False:
        raise ValueError("High-impact legal claim requires official verification")
    row=parse_entry({"title":a["title"],"link":a["url"],"published":a["published_at"]},
                     a["source"],now)
    for key in ("url","region","topic","title","high_impact"):
        if row[key]!=a.get(key):raise ValueError("Tampered source article "+key)
    if d.get("fingerprint")!=fingerprint(a) or d.get("source_count")!=1:
        raise ValueError("Invalid attribution or fingerprint")
    if not isinstance(d.get("synopsis_fr"),str) or len(d["synopsis_fr"])>180 or
        "actualité" not in d["synopsis_fr"]:
        raise ValueError("Unverifiable French overview")
    since=(now-datetime.fromisoformat(d["collected_at"])).total_seconds()
    if not -300<=since<=3600: raise ValueError("Stale JSON")
    return True

def demo_report(now=None):
    now=now or datetime.now(UTC)
    article={"source":"SIMULATION QA","title":"Exemple fictif : le Bénin étudie un projet de règles crypto",
             "url":"https://example.org/qa-simulation-non-reelle","region":"BÉNIN",
             "published_at":now.isoformat(),"topic":"PROJET DE LOI","legal_status_confirmed":False,
             "high_impact":False}
    return build(article,now,demo=True)

def select(rows,state=None,now=None):
    now=now or datetime.now(UTC)
    seen=set((state or {}).get("sent_urls",[]))
    items=sorted(rows,key=lambda x:x["published_at"],reverse=True)
    for row in items:
        if fingerprint(row) in seen:continue
        try:return build(row,now)
        except ValueError:continue
    return None

def export(demo=False):
    ROOT.mkdir(parents=True,exist_ok=True)
    path=ROOT/("regulation_11_demo.json" if demo else "regulation_11_data.json")
    path.unlink(missing_ok=True)
    if demo: data=demo_report()
    else:
        now=datetime.now(UTC)
        state={"sent_urls":[]}
        if STATE.is_file():
            state=json.loads(STATE.read_text(encoding="utf8"))
            if not isinstance(state.get("sent_urls"),list) or not all(isinstance(x,str) for x in state["sent_urls"]):
                raise ValueError("Invalid #11 duplicate registry")
        data_rows=[]
        for source,(url,_) in FEEDS.items():data_rows.extend(fetch_feed(source,url,now))
        data=select(data_rows,state,now)
    if data is None:
        print("REG11_NO_VERIFIABLE_FRESH_AFRICAN_NEWS")
        return False
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("REG11_DATA_EXPORTED",data["status"],data["main"]["region"],data["main"]["source"],path)
    return True

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--demo",action="store_true")
    opts=parser.parse_args()
    export(demo=opts.demo)
