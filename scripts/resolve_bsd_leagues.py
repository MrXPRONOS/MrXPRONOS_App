"""Resolve only authentic BSD league names; never manufacture a football league.

BSD /events/ may omit all display-name fields while retaining league_id.
Join to an unambiguous name in the current sealed archive or the official
/leagues/{id}/ and paginated /leagues/ endpoints, with bounded requests.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any

MAX_DETAILS = 40
MAX_PAGES = 12


def league_id(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        i = int(value)
    except (ValueError, TypeError):
        return None
    return i if i > 0 and str(i) == str(value).strip() else None


def label(value):
    if isinstance(value,dict):
        for key in ("league_name","name","competition_name","tournament_name","short_name"):
            text=label(value.get(key))
            if text:return text
        return ""
    if not isinstance(value,str):
        return ""
    text=value.strip()
    if not 2<=len(text)<=140 or text.casefold() in (
        "football","soccer","league","unknown","tbd","-", "championnat"):
        return ""
    return text


def event_label(e):
    if not isinstance(e,dict):return ""
    for key in ("league_name","competition_name","tournament_name","league","competition"):
        val=label(e.get(key))
        if val:return val
    return ""


def resolve_league_labels(events,history,client):
    """Return copies enriched with VERIFIED official league_name, and audit.

    Provider-ID collisions are quarantined rather than resolved by guessing.
    Events with unresolved league IDs remain unchanged and will be excluded
    by the downstream genuine Hybrid V3 selector.
    """
    if not isinstance(events,list) or not isinstance(history,list):
        raise ValueError("Expected raw BSD provider event and historic lists")
    names=defaultdict(set)
    for e in history:
        if not isinstance(e,dict):continue
        ident=league_id(e.get("league_id"))
        name=event_label(e)
        if ident and name:names[ident].add(name)
    # Prefer labels attached to other events of the same live provider batch.
    for e in events:
        if not isinstance(e,dict):continue
        ident=league_id(e.get("league_id"))
        name=event_label(e)
        if ident and name:names[ident].add(name)
    missing={league_id(e.get("league_id")) for e in events if isinstance(e,dict)
             and not event_label(e)}
    missing.discard(None)
    # A single archival spelling is acceptable; conflicting spellings or
    # ambiguous club/league assignments are rejected as unsafe joins.
    to_lookup=sorted(i for i in missing if len(names.get(i,set()))!=1)
    request_details=0
    for ident in to_lookup[:MAX_DETAILS]:
        try:
            doc=client.get_json(f"/leagues/{ident}/",ttl=900)
            official=label(doc)
            if official:
                names[ident]={official}
            request_details+=1
        except Exception:
            # No fallback name invented. Retry remaining IDs through catalog.
            continue
    still={i for i in missing if len(names.get(i,set()))!=1}
    catalog_pages=0
    if still:
        for offset in range(0,MAX_PAGES*100,100):
            try:
                value=client.get_json("/leagues/",{"limit":100,"offset":offset},ttl=900)
            except Exception:
                break
            catalog_pages+=1
            rows=(value.get("results") if isinstance(value,dict) else value)
            if not isinstance(rows,list):break
            for e in rows:
                if not isinstance(e,dict):continue
                ident=league_id(e.get("id"))
                if ident in still:
                    actual=label(e)
                    if actual:
                        names[ident]={actual}
            still={i for i in missing if len(names.get(i,set()))!=1}
            if not still or len(rows)<100:break
    out=[]
    updated=0
    for raw in events:
        if not isinstance(raw,dict):out.append(raw);continue
        e=dict(raw)
        ident=league_id(e.get("league_id"))
        if not event_label(e) and ident and len(names.get(ident,set()))==1:
            e["league_name"]=next(iter(names[ident]))
            updated+=1
        out.append(e)
    return out,{
        "missing_before":len([e for e in events if isinstance(e,dict) and not event_label(e)]),
        "official_league_labels_added":updated,
        "still_missing":len([e for e in out if isinstance(e,dict) and not event_label(e)]),
        "official_detail_calls":request_details,
        "official_catalog_pages":catalog_pages,
        "unique_missing_league_ids":len(missing),
    }
