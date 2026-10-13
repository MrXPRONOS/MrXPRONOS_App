#!/usr/bin/env python3
"""Articles de match factuels alimentés EXCLUSIVEMENT par le flux public BSD V2.

N'invente ni score, ni cote, ni statistique. Ne lance aucun appel API payant.
La génération est idempotente par ID de match et respectueuse de la sélection BSD.
"""
from __future__ import annotations
import argparse,json,re,sys
from urllib.parse import urlsplit
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bsd.bsd_v2_assets import image_fields
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data.json"
ARTICLES=ROOT/"articles.json"
REPORT=ROOT/"assets/data/bsd_editorial_bridge_report.json"
TZ=ZoneInfo("Africa/Lome")
BAD_STATUSES={"cancelled","postponed","abandoned"}

def kickoff(event):
    raw=event.get("event_date") or event.get("start_time")
    if not raw:return None
    try:
        dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def name(event,side):
    raw=event.get(side+"_team")
    if isinstance(raw,dict):raw=raw.get("name")
    return str(raw or "").strip()[:85]

# Les emblèmes ne viennent que de champs du match BSD V2; jamais de recherche
# arbitraire de clubs homonymes ni de remplacement par un faux badge.
TRUSTED_BADGE_HOSTS = frozenset((
    "r2.thesportsdb.com", "www.thesportsdb.com",
    "media.api-sports.io", "cdn.sofascore.com", "api.sofascore.com",
    "img.sofascore.com", "images.fotmob.com", "sports.bzzoiro.com",
))
def verified_badge_url(raw):
    if not isinstance(raw,str) or len(raw)>600:return ""
    try:
        parsed=urlsplit(raw)
        if parsed.scheme!="https" or parsed.hostname not in TRUSTED_BADGE_HOSTS:
            return ""
        if parsed.username or parsed.password or parsed.port not in (None,443):return ""
        if not parsed.path.startswith("/") or not parsed.path:return ""
        return raw
    except (ValueError,TypeError):
        return ""

def badge_url(match,side):
    team=match.get(side+"_team")
    options=[match.get(side+"_"+key) for key in ("team_logo","logo","team_badge","badge","team_image","image")]
    if isinstance(team,dict):
        options.extend(team.get(key) for key in ("logo","logo_url","badge","badge_url","crest","image","image_url"))
    for value in options:
        valid=verified_badge_url(value)
        if valid:return valid
    # BSD V2 propose un proxy officiel gratuit indexé uniquement par ID numérique.
    # Ne jamais déduire cet ID du nom du club : ne lire que l'identifiant du match.
    return verified_badge_url(image_fields(match).get(side+"_logo"))


def clean(value):
    return re.sub(r"\s+"," ",str(value or "")).strip()

def select_matches(dataset,now,limit=5):
    if not isinstance(dataset,dict) or dataset.get("source")!="bsd" or dataset.get("model_version")!="bsd-v2-isolated":
        return []
    eligible=[]
    for e in dataset.get("matches",[]):
        if not isinstance(e,dict) or e.get("source")!="bsd" or not e.get("id"):continue
        when=kickoff(e)
        if not when or when<now-timedelta(days=2) or when>now+timedelta(days=3):continue
        if not name(e,"home") or not name(e,"away"):continue
        if clean(e.get("status")).lower() in BAD_STATUSES:continue
        eligible.append(e)
    eligible.sort(key=lambda e:(-int(bool(e.get("recommendation_eligible"))),abs((kickoff(e)-now).total_seconds()),str(e.get("id"))))
    return eligible[:max(limit,0)]

def factual_article(match,now):
    h,a=name(match,"home"),name(match,"away")
    dt=kickoff(match)
    assert dt is not None
    event_id=re.sub(r"[^a-zA-Z0-9-]","-",str(match["id"]).removeprefix("bsd:"))[:80]
    slug="bsd-match-"+event_id
    league=clean(match.get("league"))[:95] if isinstance(match.get("league"),str) else ""
    local=dt.astimezone(TZ).strftime("%d/%m/%Y à %Hh%M")
    description=f"{h} – {a} : affiche vérifiée dans le flux football BSD V2, le {local} (heure du Togo)."
    lines=[f"# {h} – {a}","",f"**Date et heure :** {local} (GMT, Togo).",f"**Compétition :** {league or 'Non précisée dans les données BSD'}.",
       f"**Source des données :** BSD V2, identifiant {clean(match.get('source_event_id') or match['id'])}.",""]
    home_score=match.get("home_score");away_score=match.get("away_score")
    status=clean(match.get("status")).lower()
    if status in {"finished","ft","full_time"} and isinstance(home_score,int) and isinstance(away_score,int):
        lines.extend([f"**Score final BSD :** {h} {home_score} – {away_score} {a}.",""])
    else:
        lines.extend(["**Statut :** rencontre programmée ou en cours selon le dernier flux BSD disponible.",""])
    pred=match.get("prediction")
    if isinstance(pred,dict) and pred.get("selection_key"):
        label=clean(pred.get("label") or pred.get("type"))
        if label:
            lines.extend(["## Signal calculé par le moteur BSD V2",f"**Marché identifié :** {label}.",
              "Il s'agit d'une estimation du modèle, pas d'un résultat certain. Vérifie l'état du match et les cotes au moment de consulter le site.",""])
    lines.extend(["## Consulter les données en direct",
        "Retrouve les éventuelles mises à jour sur la page Pronostics de Mr XPRONOS.",
        "",
        "**18+ — Les paris sportifs comportent un risque de perte.**"])
    return {
      "slug":slug,"title":f"{h} vs {a} : fiche match BSD V2",
      "date":now.isoformat(),"author":"Mr XPRONOS","reading_time":1,
      "excerpt":description,"meta_description":description[:160],
      "keywords":", ".join(filter(None,("football","BSD V2",league,h,a)))[:230],
      "content":"\n".join(lines),"active":True,"type":"match",
      "source":"bsd","match":f"{h} vs {a}","league":league,
      "bsd_event_id":str(match.get("source_event_id") or match["id"]),
      "bsd_match_date":dt.isoformat(),
      "home_logo":badge_url(match,"home"),
      "away_logo":badge_url(match,"away"),
    }

def run(root=ROOT,now=None,limit=5,dry_run=False):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:now=now.replace(tzinfo=timezone.utc)
    data_path=root/"data.json";articles_path=root/"articles.json"
    result={"source":"bsd-v2-isolated","selected":0,"created":0,"updated":0,"skipped":0,"badge_pairs":0,"dry_run":dry_run}
    try:
        dataset=json.loads(data_path.read_text(encoding="utf-8"))
        current=json.loads(articles_path.read_text(encoding="utf-8"))
        if not isinstance(current,list):raise ValueError("articles.json n'est pas une liste")
    except (ValueError,OSError) as exc:
        result["error"]=type(exc).__name__;print("BSD_EDITORIAL_BRIDGE",json.dumps(result));return result
    selected=select_matches(dataset,now,limit)
    result["selected"]=len(selected)
    existing={str(x.get("slug")):x for x in current if isinstance(x,dict)}
    additions=[]
    for event in selected:
        article=factual_article(event,now)
        if article["home_logo"] and article["away_logo"]:result["badge_pairs"]+=1
        slug=article["slug"]
        previous=existing.get(slug)
        if previous is None:
            additions.append(article);result["created"]+=1
        elif any(previous.get(key)!=article.get(key) for key in ("content","home_logo","away_logo","match","league","bsd_match_date")):
            previous.update({k:v for k,v in article.items() if k not in ("date",)})
            result["updated"]+=1
        else: result["skipped"]+=1
    if not dry_run:
        # Le contenu original (non BSD) ne sera jamais supprimé.
        all_articles=additions+current
        if additions or result["updated"]:
            articles_path.write_text(json.dumps(all_articles,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        dest=root/"assets/data/bsd_editorial_bridge_report.json"
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BSD_EDITORIAL_BRIDGE",json.dumps(result,ensure_ascii=False))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--limit",type=int,default=5);p.add_argument("--dry-run",action="store_true")
    args=p.parse_args();run(limit=min(max(args.limit,0),12),dry_run=args.dry_run)
