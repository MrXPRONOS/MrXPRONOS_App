"""1xBet pre-match grouped correct scores — explicit market templates, no invented odds.

Nine groups below were observed on an actual 1xBet football page; the quoted
market can vary by event. They MUST NOT be assumed offered for every fixture.
This is not the 1xBet TOTO market, nor the changing live group-bet market.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
import re
from urllib.parse import urlparse

MARKET="Correct Score - Group Bet"
GROUPS={
 "G1": ((0,0),(1,0),(0,1)),
 "G2": ((0,1),(0,2),(0,3)),
 "G3": ((0,4),(0,5),(0,6)),
 "G4": ((1,0),(2,0),(3,0)),
 "G5": ((1,2),(1,3),(1,4)),
 "G6": ((2,1),(3,1),(4,1)),
 "G7": ((2,3),(2,4),(3,4)),
 "G8": ((3,2),(4,2),(4,3)),
 "G9": ((4,0),(5,0),(6,0)),
}
OBSERVED_EXAMPLE="https://1xbet.bet.br/en/line/football/21317-africa-cup-of-nations/756687632-ghana-republic-of-the-gambia"

def normalize_scores(values):
    if not isinstance(values,(tuple,list)) or not values:
        raise ValueError("Scores of group must be a nonempty list")
    out=[]
    for val in values:
        if isinstance(val,str):
            parts=val.replace(":","-").split("-")
        elif isinstance(val,(list,tuple)):
            parts=val
        else:
            raise ValueError("Invalid score syntax")
        if len(parts)!=2 or any(not str(x).isdigit() for x in parts):
            raise ValueError("Invalid exact score")
        h,a=int(parts[0]),int(parts[1])
        if h>16 or a>16:
            raise ValueError("Unsupported exact score")
        out.append((h,a))
    if len(out)!=len(set(out)):
        raise ValueError("Duplicate scores within a group")
    return tuple(out)

def score_outcome(score):
    h,a=score
    return "1" if h>a else "2" if h<a else "X"

def group_probability(matrix,scores):
    vals=normalize_scores(scores)
    if not matrix or not all(isfinite(p) and p>=0 for p in matrix.values()):
        raise ValueError("Invalid score matrix")
    return sum(matrix.get(s,0.) for s in vals)

def group_hit(scores,result):
    return normalize_scores([result])[0] in normalize_scores(scores)

def direction_probabilities(matrix):
    probs={"1":0.,"X":0.,"2":0.}
    for score,p in matrix.items():
        probs[score_outcome(score)]+=p
    total=sum(probs.values())
    return {k:probs[k]/total for k in probs}

def double_chance_direction(probs,min_dc=.69,min_gap=.09):
    """Choose camp using 1/X/2 jointly, not blindly from the 1X/X2 sign.

    1X does NOT assert team 1 wins; 12 does NOT indicate either camp.
    """
    if set(probs)!={"1","X","2"}:
        raise ValueError("Missing 1X2 vector")
    p={k:float(v) for k,v in probs.items()}
    if not all(isfinite(v) and 0<=v<=1 for v in p.values()):
        raise ValueError("Invalid outcome probabilities")
    t=sum(p.values())
    if t<=0:raise ValueError("Empty outcome probabilities")
    p={k:v/t for k,v in p.items()}
    dc={"1X":p["1"]+p["X"],"X2":p["X"]+p["2"],"12":p["1"]+p["2"]}
    direction="neutral"
    if p["X"]>=max(p["1"],p["2"]):
        direction="draw"
    elif p["1"]-p["2"]>=min_gap and dc["1X"]>=min_dc and p["1"]>p["X"]:
        direction="home"
    elif p["2"]-p["1"]>=min_gap and dc["X2"]>=min_dc and p["2"]>p["X"]:
        direction="away"
    label=max(dc,key=dc.get) if max(dc.values())>=min_dc else "uncertain"
    allowed={"home":("1","X"),"away":("2","X"),"draw":("X",),
             "neutral":("1","X","2")}[direction]
    return {"direction":direction,"double_chance":label,
            "outcomes":p,"double_chance_probabilities":dc,"allowed_outcomes":allowed}

def evaluate_groups(matrix,available,*,direction=None,min_aligned_share=.62):
    """Score only explicitly available selections; never synthesize bookmaker odds."""
    result=[]
    for item in available:
        scores=normalize_scores(item["scores"])
        p=group_probability(matrix,scores)
        consistent_mass=sum(matrix.get(s,0.) for s in scores
                            if direction is None or score_outcome(s) in direction["allowed_outcomes"])
        aligned=consistent_mass/p if p>0 else 0.
        odds=item.get("odds")
        if odds is not None and (type(odds) not in (int,float) or
                                 not isfinite(odds) or not 1.01<=odds<=1000):
            raise ValueError("Invalid group odds")
        source=item.get("quote_source","unavailable")
        actual=odds if source=="documented_1xbet_snapshot" else None
        value=p*actual-1 if actual is not None else None
        row={"group_id":item.get("group_id"),"scores":[list(s) for s in scores],
             "probability":round(p,7),"direction_share":round(aligned,6),
             "direction_eligible":aligned>=min_aligned_share,
             "quote_documented":source=="documented_1xbet_snapshot",
             "odds":actual,"quote_source":source,
             "fair_odds":round(1/p,4) if p>0 else None,
             "expected_value":round(value,6) if value is not None else None,
             "odds_captured_utc":item.get("captured_utc") if actual is not None else None}
        result.append(row)
    return sorted(result,key=lambda x:(-x["direction_eligible"],-x["probability"],x["group_id"] or ""))

def template_groups():
    """For research comparisons ONLY; never a claim of book availability."""
    return [{"group_id":k,"scores":[list(v) for v in vals],
             "odds":None,"quote_source":"research_template_only"}
            for k,vals in GROUPS.items()]

def validate_1xbet_snapshot(document,*,event_id,kickoff,now):
    """Accept only strongly sourced, timestamped pre-match per-fixture quotes.

    A human-entered snapshot is auditable but still provenance-attested,
    not independently checked against 1xBet's live website.
    """
    if not isinstance(document,dict) or document.get("bookmaker")!="1xbet":
        raise ValueError("1xBet snapshot required")
    if str(document.get("bsd_event_id"))!=str(event_id) or not document.get("bookmaker_event_id"):
        raise ValueError("Match identity not verified")
    if document.get("market")!=MARKET or document.get("period")!="FT":
        raise ValueError("Wrong market or period")
    url=urlparse(str(document.get("source_url","")))
    if url.scheme!="https" or not url.hostname or not (
        url.hostname=="1xbet.com" or url.hostname.endswith(".1xbet.com")
        or url.hostname=="1xbet.bet.br" or url.hostname.endswith(".1xbet.bet.br")
    ):
        raise ValueError("Untrusted bookmaker source URL")
    stamp=datetime.fromisoformat(str(document["captured_utc"]).replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timezone missing")
    if stamp>=kickoff or stamp>now or (now-stamp).total_seconds()>48*3600:
        raise ValueError("Invalid or stale pre-match quote")
    bookid=str(document["bookmaker_event_id"]).strip()
    if not bookid.isdigit() or bookid not in url.path:
        raise ValueError("Bookmaker match id missing from fixture URL")
    observed_kickoff=datetime.fromisoformat(str(document["kickoff_utc"]).replace("Z","+00:00"))
    if observed_kickoff.tzinfo is None or abs((observed_kickoff-kickoff).total_seconds())>600:
        raise ValueError("Bookmaker and BSD kickoffs must match within 10 minutes")
    if str(document.get("capture_reference","")).strip()=="":
        raise ValueError("Auditable capture reference is required")
    seen=set()
    items=[]
    for item in document.get("selections",[]):
        gid=item.get("group_id")
        if not isinstance(gid,str) or gid in seen:
            raise ValueError("Missing or duplicate bookmaker selection identifier")
        is_reference=gid in GROUPS
        is_custom=bool(re.fullmatch(r"XBET_[A-Z0-9_]{1,20}",gid))
        if not is_reference and not (
            is_custom and document.get("market_variant")=="per_fixture_grouping"
        ):
            raise ValueError("Unknown 1xBet score group requires explicit per-fixture definition")
        scores=normalize_scores(item["scores"])
        if is_reference and set(scores)!=set(GROUPS[gid]):
            raise ValueError("Observed reference group differs from 1xBet template")
        if is_custom and not (2<=len(scores)<=6):
            raise ValueError("A dynamic grouped selection must enumerate 2-6 exact scores")
        quote=item.get("odds")
        if type(quote) not in (int,float) or not isfinite(quote) or not 1.01<=quote<=1000:
            raise ValueError("Real decimal odd required")
        seen.add(gid)
        items.append({"group_id":gid,
                      "scores":[list(x) for x in (GROUPS[gid] if is_reference else scores)],
                      "odds":quote,"quote_source":"documented_1xbet_snapshot",
                      "captured_utc":stamp.astimezone(timezone.utc).isoformat(),
                      "source_url":document["source_url"],
                      "bookmaker_event_id":bookid,
                      "dynamic_group":bool(is_custom)})
    if not items:
        raise ValueError("No available bookmaker selection documented")
    return items
