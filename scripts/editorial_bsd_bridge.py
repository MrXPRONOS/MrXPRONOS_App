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

def _past_verified_results(match, history, now):
    """Anonymized, read-only sporting context from completed archive fixtures.

    Never count matches at/after target kickoff or at/after generation time;
    always match teams by original numeric identifiers, not by club names.
    This is sporting context, NOT historical publication proof.
    """
    cutoff = kickoff(match)
    if cutoff is None or not isinstance(history,list):
        return {"home": [], "away": [], "meetings": []}
    cutoff = min(cutoff, now.astimezone(timezone.utc))
    try:
        home_id, away_id = int(match["home_team_id"]), int(match["away_team_id"])
    except (KeyError, ValueError, TypeError):
        return {"home": [], "away": [], "meetings": []}
    if home_id <= 0 or away_id <= 0 or home_id == away_id:
        return {"home": [], "away": [], "meetings": []}
    collected={"home": [], "away": [], "meetings": []}
    seen=set()
    for item in history:
        if not isinstance(item,dict) or clean(item.get("status")).lower() != "finished":
            continue
        raw_id=item.get("id")
        if raw_id is None or str(raw_id) in seen:
            continue
        try:
            hid=int(item["home_team_id"])
            aid=int(item["away_team_id"])
            score_h=item["home_score"]
            score_a=item["away_score"]
            if (not isinstance(score_h,int) or isinstance(score_h,bool)
                or not isinstance(score_a,int) or isinstance(score_a,bool)
                or score_h<0 or score_a<0):
                continue
            played=kickoff(item)
        except (KeyError, ValueError, TypeError):
            continue
        if played is None or played>=cutoff:
            continue
        if (cutoff-played).days > 3*366:
            continue
        seen.add(str(raw_id))
        summary=(played,hid,aid,score_h,score_a)
        if {hid,aid}=={home_id,away_id}:
            collected["meetings"].append(summary)
        if (cutoff-played).days <= 366:
            if home_id in (hid,aid):collected["home"].append(summary)
            if away_id in (hid,aid):collected["away"].append(summary)
    for field in collected:
        collected[field].sort(key=lambda row: row[0], reverse=True)
    return collected


def _form_sentence(team_name, team_id, rows):
    rows=rows[:5]
    if len(rows)<3:
        return f"{team_name} : moins de trois résultats vérifiés disponibles sur la dernière année."
    wins=draws=losses=goals_for=goals_against=0
    for _,hid,aid,hs,aws in rows:
        gf,ga=(hs,aws) if hid==team_id else (aws,hs)
        goals_for+=gf
        goals_against+=ga
        if gf>ga:wins+=1
        elif gf<ga:losses+=1
        else:draws+=1
    return (f"{team_name} — {len(rows)} derniers matchs vérifiés disponibles : "
        f"{wins} victoire(s), {draws} nul(s), {losses} défaite(s), "
        f"{goals_for} but(s) marqué(s), {goals_against} encaissé(s).")


def _h2h_sentence(home_name, away_name, home_id, rows):
    rows=rows[:10]
    if len(rows)<2:
        return "Moins de deux confrontations directes confirmées sur les trois dernières années."
    hwin=draw=awin=0
    for _,hid,aid,hs,aws in rows:
        hg,ag=(hs,aws) if hid==home_id else (aws,hs)
        if hg>ag:hwin+=1
        elif hg<ag:awin+=1
        else:draw+=1
    return (f"Sur {len(rows)} confrontations terminées vérifiées : "
        f"{home_name} {hwin} victoire(s), {draw} match(s) nul(s), "
        f"{away_name} {awin} victoire(s).")



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

def factual_article(match,now,history=None):
    h,a=name(match,"home"),name(match,"away")
    dt=kickoff(match)
    assert dt is not None
    event_id=re.sub(r"[^a-zA-Z0-9-]","-",str(match["id"]).removeprefix("bsd:"))[:80]
    slug="bsd-match-"+event_id
    league=clean(match.get("league"))[:95] if isinstance(match.get("league"),str) else ""
    local=dt.astimezone(TZ).strftime("%d/%m/%Y à %Hh%M")
    description=f"{h} – {a} : présentation de la rencontre du {local} (heure du Togo)."
    # All assertions below are derived from the dated match feed. Do not turn
    # a generated overview into invented standings, H2H or form statistics.
    home_score=match.get("home_score")
    away_score=match.get("away_score")
    status=clean(match.get("status")).lower()
    final=status in {"finished","ft","full_time"} and (
        isinstance(home_score,int) and not isinstance(home_score,bool) and
        isinstance(away_score,int) and not isinstance(away_score,bool))
    history_rows=_past_verified_results(match,history,now)
    can_compare=bool(history_rows["home"] or history_rows["away"])
    try:
        home_id=int(match.get("home_team_id") or 0)
        away_id=int(match.get("away_team_id") or 0)
    except (ValueError,TypeError):
        home_id=away_id=0
    form_home=_form_sentence(h,home_id,history_rows["home"])
    form_away=_form_sentence(a,away_id,history_rows["away"])
    h2h_line=_h2h_sentence(h,a,home_id,history_rows["meetings"])
    pred=match.get("prediction")
    confidence=(pred or {}).get("confidence") if isinstance(pred,dict) else None
    eligible=(match.get("category") in {"pro","vip"} and
        match.get("recommendation_eligible") is True and not final and
        isinstance(pred,dict) and pred.get("recommendation_eligible") is not False and
        bool(pred.get("selection_key")) and
        isinstance(confidence,(int,float)) and not isinstance(confidence,bool) and
        79 <= confidence <= 100)
    label=clean(pred.get("label") or pred.get("type")) if isinstance(pred,dict) else ""
    lines=[
       f"# {h} – {a}", "",
       "## 1. Présentation de la rencontre",
       f"**Date et heure :** {local} (GMT, Togo).",
       f"**Compétition :** {league or 'Non précisée'}.",
       f"**Équipes :** {h} et {a}.", "",
       "## 2. Contexte et enjeux",
       f"Cette rencontre oppose {h} à {a}" + (f" en {league}." if league else "."),
       "Le classement, la qualification et les enjeux précis ne sont pas confirmés dans les informations disponibles pour cette fiche.", "",
       "## 3. Forme récente",
       form_home, form_away,
       "Bilan établi uniquement à partir des matchs terminés et identifiés avant cette rencontre ; il ne représente pas forcément la totalité de la saison.", "",
       "## 4. Confrontations directes",
       h2h_line,
       "La synthèse prend uniquement en compte les rencontres terminées antérieures à cette affiche.", "",
       "## 5. Statistiques disponibles",
    ]
    if final:
        lines.append(f"**Résultat final confirmé :** {h} {home_score} – {away_score} {a}.")
    else:
        lines.append("Le score final n'est pas encore disponible ou n'est pas confirmé.")
    lines.extend([
       "Les chiffres de tirs, de possession, d'occasions et de corners ne sont pas publiés sans confirmation.", "",
       "## 6. Points de vigilance",
       ("Les échantillons de forme ou de confrontations peuvent être incomplets ; "
        "leur taille est indiquée dans cette analyse. "
        "Ils ne suffisent pas à garantir l'issue du match." if can_compare else
        "L'absence de statistiques fiables sur la forme et les confrontations limite toute conclusion sportive forte."),
       "Les cotes et les compositions peuvent évoluer : il faut vérifier les informations au moment de la rencontre.", "",
       "## 7. Notre lecture",
       ("Cette analyse tient également compte des résultats historiques vérifiés présentés ci-dessus, "
        "sans en déduire de certitude sportive." if can_compare else
        "Les éléments confirmés sont l'affiche, la compétition lorsqu'elle est renseignée, la date et, le cas échéant, le score final."),
       "Sans données supplémentaires vérifiées, il serait trompeur de présenter une équipe comme favorite sur des critères chiffrés.", "",
       "## 8. Pronostic associé",
    ])
    if eligible and label:
        lines.append(f"**Sélection Pro/VIP publiée dans le flux courant :** {label} (confiance estimée {confidence:g} %).")
        lines.append("Ce pourcentage est une estimation, pas une garantie. Consultez la page Pronostics pour vérifier la sélection disponible.")
    elif final:
        lines.append("Le match est terminé. Consultez la page Résultats pour connaître les sélections évaluées et leurs preuves lorsqu'elles existent.")
    else:
        lines.append("Aucune sélection Pro/VIP admissible n'est présentée pour cette rencontre dans cette fiche.")
    lines.extend([
       "", "Cette présentation est informative : elle ne constitue ni une promesse de gain ni une validation rétroactive d'un pronostic.",
       "**18+ — Les paris sportifs comportent un risque de perte.**"
    ])
    body="\n".join(lines)
    reading_time=max(1,(len(body.split())+199)//200)
    return {
      "slug":slug,"title":f"{h} vs {a} : analyse du match",
      "date":now.isoformat(),"author":"Mr XPRONOS","reading_time":reading_time,
      "excerpt":description,"meta_description":description[:160],
      "keywords":", ".join(filter(None,("football","analyse de match",league,h,a)))[:230],
      "content":body,"active":True,"type":"match",
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
    # Decrypted results exist only in the private BSD production job.
    # The editorial-only standalone job remains functional without them.
    private_history=root/"bsd/all_matches_bsd.json"
    history=[]
    if private_history.is_file():
        try:
            loaded=json.loads(private_history.read_text(encoding="utf-8"))
            if isinstance(loaded,list):
                history=loaded
        except (OSError,ValueError):
            history=[]
    selected=select_matches(dataset,now,limit)
    result["selected"]=len(selected)
    existing={str(x.get("slug")):x for x in current if isinstance(x,dict)}
    additions=[]
    for event in selected:
        article=factual_article(event,now,history=history)
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
