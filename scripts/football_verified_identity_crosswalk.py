#!/usr/bin/env python3
"""Evidence-backed team name equivalences for historic multisource BSD V2 input.

NEVER use edit-distance or mere club-name similarity. Require at least two
DISTINCT independently observed completed historical fixtures with:
same competition and day, accurate UTC kickoff +/-30m, identical FT result,
and one EXACT same-name team that anchors the other team's equivalence.
Every match needs a unique reciprocal counterpart in the compared provider.
All observations must have passed provider licensing and time gates upstream.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_multi_api_history_inputs import aware

PREFERENCE = ("bsd","openfootball","api_football","espn","sportscore",
              "thesportsdb","openligadb")
MAX_START_DELTA_SECONDS = 30 * 60


def raw_key(r: dict) -> tuple:
    return (competition(str(r.get("league") or "")),
            str(r.get("match_date") or ""),
            canonical_team(str(r.get("home_team") or "")),
            canonical_team(str(r.get("away_team") or "")))


def strong_pair(a: dict, b: dict) -> bool:
    if a.get("source") == b.get("source"):
        return False
    if a.get("source_id") is None or b.get("source_id") is None:
        return False
    if a.get("status") != "finished" or b.get("status") != "finished":
        return False
    ka, kb = raw_key(a), raw_key(b)
    if not ka[0] or ka[:2] != kb[:2] or ka[2] == ka[3] or kb[2] == kb[3]:
        return False
    if not ((ka[2] == kb[2]) != (ka[3] == kb[3])):
        # Exactly ONE anchored same-name team; two equal teams carry no
        # alias information; two different teams offer no reliable evidence.
        return False
    aa, ab = a.get("home_score"), a.get("away_score")
    ba, bb = b.get("home_score"), b.get("away_score")
    if any(type(x) is not int or not 0 <= x <= 30 for x in (aa, ab, ba, bb)):
        return False
    if (aa, ab) != (ba, bb):
        return False
    ta, tb = aware(a.get("kickoff_utc")), aware(b.get("kickoff_utc"))
    return ta is not None and tb is not None and abs((ta-tb).total_seconds()) <= MAX_START_DELTA_SECONDS


def generate(rows: list[dict], *, min_distinct_matches: int = 2) -> tuple[dict,dict]:
    if min_distinct_matches < 2:
        raise ValueError("Require at least two independent historical matches")
    groups = defaultdict(list)
    for r in rows:
        if not isinstance(r,dict):
            continue
        key=raw_key(r)
        if key[0] and key[1]:
            groups[key[:2]].append(r)
    evidence=defaultdict(set)
    reviewed=Counter()
    for (league,day),group in groups.items():
        if len(group) > 40:
            reviewed["oversized_competition_day_skipped"] += 1
            continue
        # Each individual provider fixture may match at most ONE fixture
        # from a different source; otherwise same-score schedule coincidences
        # could falsely create team aliases.
        matches=defaultdict(list)
        for i,j in combinations(range(len(group)),2):
            if strong_pair(group[i],group[j]):
                matches[i].append(j)
                matches[j].append(i)
        for i,j in combinations(range(len(group)),2):
            if j not in matches[i] or len(matches[i])!=1 or len(matches[j])!=1:
                continue
            x,y=group[i],group[j]
            ka,kb=raw_key(x),raw_key(y)
            side=2 if ka[2]!=kb[2] else 3
            # Prefer native BSD label where already tied to official ID.
            # Otherwise public-domain OpenFootball preferred to other API
            # labels, with deterministic order.
            try:
                px=PREFERENCE.index(x["source"])
                py=PREFERENCE.index(y["source"])
            except ValueError:
                continue
            alias,reference = (ka[side],kb[side]) if px>py else (kb[side],ka[side])
            if alias==reference:
                continue
            # Include fixed and changing opponent + independent date. Two
            # games same day can't count as two distinct confirmations.
            other=ka[3] if side==2 else ka[2]
            signature=(day,other,min(str(x["source_id"]),str(y["source_id"])),
                       max(str(x["source_id"]),str(y["source_id"])))
            evidence[(league,alias,reference)].add(signature)
            reviewed["unambiguous_single_match_evidence"]+=1

    confirmed=defaultdict(set)
    for (league,alias,reference),sources in evidence.items():
        if len({(e[0],e[1]) for e in sources}) >= min_distinct_matches:
            confirmed[(league,alias)].add(reference)
    mapping={}
    for (league,alias),targets in confirmed.items():
        if len(targets)==1:
            mapping.setdefault(league,{})[alias]=next(iter(targets))
        else:
            reviewed["conflicting_alias_targets"]+=1
    # Prevent simultaneous contradictory chains A->B and B->A.
    for league,defs in list(mapping.items()):
        for alias,target in list(defs.items()):
            if defs.get(target) == alias:
                defs.pop(alias,None)
                defs.pop(target,None)
                reviewed["cyclic_alias_refused"]+=1
        if not defs:
            mapping.pop(league,None)
    report={
        "historical_rows_considered":len(rows),
        "single_match_evidence":reviewed["unambiguous_single_match_evidence"],
        "confirmed_aliases":sum(len(v) for v in mapping.values()),
        "conflicts_blocked":reviewed["conflicting_alias_targets"]+reviewed["cyclic_alias_refused"],
        "leagues_with_confirmed_aliases":len(mapping),
        "evidence_required_per_alias":min_distinct_matches,
        "production_active":False,
        "no_fuzzy_name_matching":True,
        "no_h2h_weight_added":True,
    }
    return mapping, report


def resolve(league: str, name: str, mapping: dict) -> str:
    title=competition(league)
    club=canonical_team(name)
    defs=mapping.get(title,{})
    target=defs.get(club)
    # Only one-hop, no dynamic alias-chaining based on uncertain evidence.
    return target if isinstance(target,str) and target else club
