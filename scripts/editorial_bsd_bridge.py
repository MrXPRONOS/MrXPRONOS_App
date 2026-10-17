#!/usr/bin/env python3
"""Articles de match factuels alimentés EXCLUSIVEMENT par le flux public BSD V2.

N'invente ni score, ni cote, ni statistique. Ne lance aucun appel API payant.
La génération est idempotente par ID de match et respectueuse de la sélection BSD.
"""
from __future__ import annotations
import argparse,json,re,sys,unicodedata
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

# -----------------------------------------------------------------------
# Sélection éditoriale des GRANDES AFFICHES
# -----------------------------------------------------------------------
# Le moteur de pronostics peut recommander des matchs de n'importe quel
# championnat. Pour le canal éditorial, on applique une seconde couche:
# notoriété des équipes + importance de la compétition + phase du tournoi
# + derby/rivalité. Un bon signal de pari ne suffit donc plus à faire d'un
# match une "grande affiche".
MIN_EDITORIAL_IMPORTANCE = 300

MAJOR_TEAMS = {
    # Europe — ultra premium
    "real madrid": (300, ("real madrid",)),
    "barcelona": (300, ("barcelona", "fc barcelona")),
    "manchester city": (290, ("manchester city", "man city")),
    "manchester united": (290, ("manchester united", "man united", "man utd")),
    "liverpool": (290, ("liverpool", "liverpool fc")),
    "arsenal": (285, ("arsenal", "arsenal fc")),
    "chelsea": (280, ("chelsea", "chelsea fc")),
    "bayern munich": (295, ("bayern munich", "bayern munchen", "fc bayern")),
    "psg": (290, ("paris saint germain", "paris st germain", "psg")),
    "inter milan": (280, ("inter milan", "internazionale", "inter")),
    "ac milan": (280, ("ac milan", "milan")),
    "juventus": (275, ("juventus",)),
    "atletico madrid": (270, ("atletico madrid", "atletico de madrid")),
    # Europe — grands clubs
    "tottenham": (235, ("tottenham", "tottenham hotspur", "spurs")),
    "newcastle": (220, ("newcastle", "newcastle united")),
    "borussia dortmund": (250, ("borussia dortmund", "dortmund")),
    "bayer leverkusen": (225, ("bayer leverkusen", "leverkusen")),
    "rb leipzig": (210, ("rb leipzig", "leipzig")),
    "napoli": (235, ("napoli", "ssc napoli")),
    "roma": (220, ("as roma", "roma")),
    "lazio": (205, ("lazio",)),
    "marseille": (225, ("olympique de marseille", "marseille", "om")),
    "lyon": (200, ("olympique lyonnais", "lyon")),
    "monaco": (195, ("as monaco", "monaco")),
    "benfica": (235, ("benfica", "sl benfica")),
    "porto": (235, ("porto", "fc porto")),
    "sporting": (225, ("sporting cp", "sporting lisbon", "sporting clube de portugal")),
    "ajax": (220, ("ajax", "afc ajax")),
    "psv": (210, ("psv", "psv eindhoven")),
    "feyenoord": (205, ("feyenoord",)),
    "galatasaray": (220, ("galatasaray",)),
    "fenerbahce": (215, ("fenerbahce",)),
    "besiktas": (190, ("besiktas",)),
    "celtic": (195, ("celtic", "celtic fc")),
    "rangers": (195, ("rangers", "rangers fc")),
    # Amériques
    "river plate": (235, ("river plate",)),
    "boca juniors": (235, ("boca juniors", "boca")),
    "flamengo": (235, ("flamengo",)),
    "palmeiras": (230, ("palmeiras",)),
    "corinthians": (215, ("corinthians",)),
    "sao paulo": (205, ("sao paulo",)),
    "fluminense": (195, ("fluminense",)),
    "gremio": (190, ("gremio",)),
    "internacional": (190, ("internacional", "sc internacional")),
    # Afrique
    "al ahly": (240, ("al ahly", "alahly")),
    "zamalek": (215, ("zamalek",)),
    "wydad": (220, ("wydad", "wydad casablanca", "wydad ac")),
    "raja": (215, ("raja casablanca", "raja ca", "raja club athletic")),
    "esperance tunis": (215, ("esperance tunis", "esperance de tunis", "esperance sportive de tunis")),
    "mamelodi sundowns": (215, ("mamelodi sundowns", "sundowns")),
    "tp mazembe": (210, ("tp mazembe", "mazembe")),
    # Golfe / Asie
    "al hilal": (220, ("al hilal",)),
    "al nassr": (215, ("al nassr",)),
    "al ittihad": (205, ("al ittihad",)),
    "al ahli": (195, ("al ahli",)),
    # Sélections nationales majeures
    "argentina": (285, ("argentina", "argentine")),
    "brazil": (285, ("brazil", "bresil")),
    "france": (285, ("france",)),
    "spain": (275, ("spain", "espagne")),
    "england": (275, ("england", "angleterre")),
    "germany": (270, ("germany", "allemagne")),
    "italy": (270, ("italy", "italie")),
    "portugal": (270, ("portugal",)),
    "netherlands": (255, ("netherlands", "pays bas", "holland")),
    "belgium": (235, ("belgium", "belgique")),
    "croatia": (235, ("croatia", "croatie")),
    "uruguay": (235, ("uruguay",)),
    "morocco": (260, ("morocco", "maroc")),
    "senegal": (245, ("senegal",)),
    "nigeria": (245, ("nigeria",)),
    "egypt": (240, ("egypt", "egypte")),
    "algeria": (235, ("algeria", "algerie")),
    "ivory coast": (240, ("ivory coast", "cote d ivoire")),
    "cameroon": (235, ("cameroon", "cameroun")),
    "ghana": (225, ("ghana",)),
    "south africa": (205, ("south africa", "afrique du sud")),
}

RIVALRIES = {
    frozenset(("real madrid","barcelona")),
    frozenset(("real madrid","atletico madrid")),
    frozenset(("manchester united","liverpool")),
    frozenset(("manchester united","manchester city")),
    frozenset(("arsenal","tottenham")),
    frozenset(("liverpool","everton")),
    frozenset(("inter milan","ac milan")),
    frozenset(("juventus","inter milan")),
    frozenset(("roma","lazio")),
    frozenset(("bayern munich","borussia dortmund")),
    frozenset(("psg","marseille")),
    frozenset(("benfica","porto")),
    frozenset(("benfica","sporting")),
    frozenset(("porto","sporting")),
    frozenset(("ajax","feyenoord")),
    frozenset(("galatasaray","fenerbahce")),
    frozenset(("celtic","rangers")),
    frozenset(("boca juniors","river plate")),
    frozenset(("flamengo","fluminense")),
    frozenset(("palmeiras","corinthians")),
    frozenset(("al ahly","zamalek")),
    frozenset(("wydad","raja")),
    frozenset(("al hilal","al nassr")),
}

def _norm(value):
    value=unicodedata.normalize("NFKD",str(value or ""))
    value=value.encode("ascii","ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()

def _team_identity(raw):
    n=_norm(raw)
    padded=f" {n} "
    best=("",0,0)
    for canonical,(weight,aliases) in MAJOR_TEAMS.items():
        for alias in aliases:
            a=_norm(alias)
            # Les alias courts ("om", "psg") doivent être des mots entiers.
            if n==a or f" {a} " in padded:
                specificity=len(a)
                if weight>best[1] or (weight==best[1] and specificity>best[2]):
                    best=(canonical,weight,specificity)
    return best[0] or n,best[1]

def _metadata_text(event):
    values=[]
    keys=("league","competition","competition_name","tournament","tournament_name",
          "round","round_name","roundName","stage","stage_name","stageName",
          "phase","phase_name","phaseName","group","event_name")
    for key in keys:
        value=event.get(key)
        if isinstance(value,dict):
            for sub in ("name","title","round","stage","phase"):
                if value.get(sub):values.append(value.get(sub))
        elif value:
            values.append(value)
    return _norm(" ".join(map(str,values)))

def _competition_importance(meta):
    # Compétitions internationales: les qualifications ont volontairement
    # un poids inférieur à la phase finale.
    qualifier=any(x in meta for x in ("qualif","qualifying","qualification","preliminary"))
    rules=[
        (("fifa club world cup","club world cup"),600,"Coupe du monde des clubs"),
        (("fifa world cup","world cup"),320 if qualifier else 650,"Coupe du monde"),
        (("uefa champions league",),550,"Ligue des champions"),
        (("caf champions league",),460,"Ligue des champions CAF"),
        (("afc champions league",),410,"Ligue des champions AFC"),
        (("copa libertadores",),470,"Copa Libertadores"),
        (("uefa europa league",),420,"Europa League"),
        (("uefa conference league","europa conference league"),350,"Conference League"),
        (("uefa euro","european championship"),330 if qualifier else 600,"Euro"),
        (("copa america",),580,"Copa America"),
        (("africa cup of nations","afcon","coupe d afrique","can "),330 if qualifier else 580,"CAN"),
        (("concacaf gold cup","gold cup"),420,"Gold Cup"),
        (("uefa nations league",),360,"Nations League"),
        (("caf confederation cup",),350,"Coupe de la Confédération CAF"),
    ]
    best=(0,"")
    for patterns,score,label in rules:
        if any(p in meta for p in patterns) and score>best[0]:
            best=(score,label)

    # Championnats / coupes domestiques. Exact ou formes connues pour éviter
    # de confondre "Egyptian Premier League" avec la Premier League anglaise.
    domestic=[
        (("premier league","english premier league","england premier league"),320,"Premier League"),
        (("laliga","la liga","spanish la liga","primera division spain"),315,"LaLiga"),
        (("serie a","italian serie a","serie a italy"),305,"Serie A"),
        (("bundesliga","german bundesliga"),305,"Bundesliga"),
        (("ligue 1","french ligue 1"),295,"Ligue 1"),
        (("fa cup","fa community shield"),340,"FA Cup / Community Shield"),
        (("copa del rey",),340,"Copa del Rey"),
        (("coppa italia",),330,"Coppa Italia"),
        (("dfb pokal",),330,"DFB-Pokal"),
        (("coupe de france",),325,"Coupe de France"),
        (("primeira liga","liga portugal"),235,"Liga Portugal"),
        (("eredivisie",),225,"Eredivisie"),
        (("super lig","turkish super lig"),220,"Süper Lig"),
        (("brasileirao","brazilian serie a"),235,"Brasileirão"),
        (("argentinian primera division","liga profesional"),225,"Argentine Primera"),
        (("major league soccer","mls"),185,"MLS"),
        (("saudi pro league",),205,"Saudi Pro League"),
        (("caf super cup",),410,"Super Coupe CAF"),
        (("uefa super cup",),450,"Super Coupe UEFA"),
    ]
    generic_prefixes={"premier league","laliga","la liga","serie a","bundesliga","ligue 1","mls"}
    for patterns,score,label in domestic:
        matched=False
        for p in patterns:
            if p in generic_prefixes:
                matched = meta==p or meta.startswith(p+" ")
            else:
                matched = p in meta
            if matched: break
        if matched and score>best[0]:
            best=(score,label)
    return best

def _stage_importance(meta):
    # Ordre important: "semi-final" contient "final".
    if re.search(r"\b(semi ?finals?|demi ?finale?s?|1 2 finale?s?)\b",meta):
        return 850,"Demi-finale"
    if re.search(r"\b(quarter ?finals?|quart?s? de finale?s?|1 4 finale?s?)\b",meta):
        return 650,"Quart de finale"
    if re.search(r"\b(round of 16|last 16|huitieme?s? de finale?s?|octavos|1 8 finale?s?)\b",meta):
        return 460,"Huitième de finale"
    if re.search(r"\b(third place|3rd place|petite finale)\b",meta):
        return 500,"Match pour la 3e place"
    if re.search(r"\b(finals?|finale?s?)\b",meta):
        return 1050,"Finale"
    if any(x in meta for x in ("knockout","elimination directe","playoff","play off","barrage")):
        return 300,"Phase à élimination directe"
    return 0,""

def editorial_importance(event):
    home=name(event,"home");away=name(event,"away")
    hcanon,hweight=_team_identity(home)
    acanon,aweight=_team_identity(away)
    meta=_metadata_text(event)
    comp_score,comp_reason=_competition_importance(meta)
    stage_score,stage_reason=_stage_importance(meta)

    score=hweight+aweight+comp_score+stage_score
    # Pour le public Mr XPRONOS, la notoriété des grands clubs prime.
    # Un grand club doit passer même face à un adversaire modeste.
    major_club = max(hweight,aweight)>=190
    if major_club:
        score+=950
    if hweight>=190 and aweight>=190:
        score+=450
    reasons=[]
    if major_club:reasons.append("priorité grand club")
    if hweight:reasons.append(f"club/sélection majeure: {home}")
    if aweight:reasons.append(f"club/sélection majeure: {away}")
    if comp_score:reasons.append(comp_reason)
    if stage_score:reasons.append(stage_reason)

    if frozenset((hcanon,acanon)) in RIVALRIES:
        score+=700;reasons.append("derby/rivalité majeure")
    elif hweight>=220 and aweight>=220:
        score+=180;reasons.append("choc entre deux grandes équipes")

    # Le signal de pronostic reste un petit bonus, jamais le critère principal.
    if event.get("recommendation_eligible"):
        score+=35
    pred=event.get("prediction")
    if isinstance(pred,dict) and pred.get("selection_key"):
        score+=10

    combined=_norm(" ".join((home,away,meta)))
    penalty=0
    if re.search(r"\bu(?:17|18|19|20|21|23)\b",combined) or re.search(r"\b(reserve|reserves|academy)\b",combined):
        penalty+=800;reasons.append("équipe de jeunes/réserve")
    if re.search(r"\bii\b",_norm(home)) or re.search(r"\bii\b",_norm(away)):
        penalty+=650;reasons.append("équipe II")
    if any(x in meta for x in ("friendly","amical","club friendly")):
        penalty+=350;reasons.append("match amical")
    if re.search(r"\b(women|womens|feminine)\b",combined):
        penalty+=180;reasons.append("compétition féminine")
    secondary=("league two","league one","2 bundesliga","bl2","serie b",
               "ligue 2","segunda division","championship")
    if any(meta==x or meta.startswith(x+" ") for x in secondary):
        penalty+=220;reasons.append("division secondaire")
    score-=penalty
    return int(score),reasons

def select_matches(dataset,now,limit=5):
    if not isinstance(dataset,dict) or dataset.get("source")!="bsd" or dataset.get("model_version")!="bsd-v2-isolated":
        return []
    ranked=[]
    for e in dataset.get("matches",[]):
        if not isinstance(e,dict) or e.get("source")!="bsd" or not e.get("id"):continue
        when=kickoff(e)
        if not when or when<now-timedelta(days=2) or when>now+timedelta(days=3):continue
        if not name(e,"home") or not name(e,"away"):continue
        if clean(e.get("status")).lower() in BAD_STATUSES:continue
        importance,reasons=editorial_importance(e)
        if importance<MIN_EDITORIAL_IMPORTANCE:
            continue
        ranked.append((importance,e,reasons))

    ranked.sort(key=lambda row:(
        -int(max(_team_identity(name(row[1],"home"))[1],_team_identity(name(row[1],"away"))[1])>=190),
        -row[0],
        -int(bool(row[1].get("recommendation_eligible"))),
        abs((kickoff(row[1])-now).total_seconds()),
        str(row[1].get("id"))
    ))
    selected=[]
    for importance,event,reasons in ranked[:max(limit,0)]:
        enriched=dict(event)
        enriched["_editorial_importance"]=importance
        enriched["_editorial_reasons"]=reasons
        enriched["_editorial_role"]="match_du_jour" if not selected else "grande_affiche"
        selected.append(enriched)
    return selected

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
      "editorial_importance":int(match.get("_editorial_importance") or 0),
      "editorial_reasons":list(match.get("_editorial_reasons") or []),
      "editorial_role":str(match.get("_editorial_role") or "grande_affiche"),
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
