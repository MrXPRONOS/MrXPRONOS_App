"""Actu Foot V3: deterministic indexes, secure filtering and stable cursor pages.

Indexes are derived in memory from decrypted V2 data; NEVER persist plaintext
or expose indexes on a public GitHub branch. Only allowlisted fields are queryable.
"""
from __future__ import annotations
import base64
import hashlib
import json
from typing import Any
from scripts.actu_foot_v2_store import canonical, validate_records, VaultError

FIELDS={
 "matches":("home_team","away_team","league","competition","state","status","provider","kickoff_utc","event_date"),
 "live_events":("home_team","away_team","league","kind","provider","last_seen_at","event_date"),
 "publications":("status","category","fixture_key","sent_at","created_at"),
 "news":("title","headline","source","published_at","created_at"),
 "statistics":("fixture_key","provider","created_at"),
 "settings":("type","updated_at"),
 "audit":("operation","occurred_at"),
}
SORT_FIELDS={name:fields+("id",) for name,fields in FIELDS.items()}
MAX_PAGE=100
MAX_QUERY_TEXT=160
MAX_CURSOR=4000


def _normalized(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value,str):
        return " ".join(value.casefold().split())
    if type(value) in (int,float,bool):
        return str(value).casefold()
    return ""


def build_indexes(collection: str, records: dict) -> dict:
    validate_records(collection,records)
    indexes={field:{} for field in FIELDS[collection]}
    for identifier,row in records.items():
        for field in FIELDS[collection]:
            token=_normalized(row.get(field))
            if token:
                indexes[field].setdefault(token,set()).add(identifier)
    return indexes


def _cursor_encode(payload: dict) -> str:
    return base64.urlsafe_b64encode(canonical(payload)).decode("ascii").rstrip("=")


def _cursor_decode(cursor: str) -> dict:
    if not isinstance(cursor,str) or len(cursor)>MAX_CURSOR:
        raise VaultError("Invalid query cursor")
    try:
        data=json.loads(base64.urlsafe_b64decode(cursor+"="*((-len(cursor))%4)))
        if not isinstance(data,dict) or set(data)!={"fingerprint","offset","generation"}:
            raise ValueError("wrong cursor schema")
        if type(data["offset"]) is not int or data["offset"]<0:
            raise ValueError("invalid cursor offset")
        if type(data["generation"]) is not int or data["generation"]<0:
            raise ValueError("invalid cursor generation")
        return data
    except (ValueError,UnicodeDecodeError,TypeError) as exc:
        raise VaultError("Malformed query cursor") from exc


def query(collection: str, records: dict, *, filters: dict|None=None,
          text: str="", sort_by: str="id", descending: bool=False,
          limit: int=50, cursor: str|None=None, generation: int=0) -> dict:
    validate_records(collection,records)
    filters=filters or {}
    if not isinstance(filters,dict) or set(filters)-set(FIELDS[collection]):
        raise VaultError("Unsupported query filter")
    if type(limit) is not int or not 1<=limit<=MAX_PAGE:
        raise VaultError("Invalid query page size")
    if not isinstance(text,str) or len(text)>MAX_QUERY_TEXT:
        raise VaultError("Invalid search text")
    if sort_by not in SORT_FIELDS[collection]:
        raise VaultError("Unsupported sort field")
    if type(descending) is not bool or type(generation) is not int or generation<0:
        raise VaultError("Invalid query metadata")
    terms=[]
    for field,value in filters.items():
        if not isinstance(value,(str,int,float,bool)) or len(str(value))>MAX_QUERY_TEXT:
            raise VaultError("Invalid filter value")
        terms.append((field,_normalized(value)))
    needle=_normalized(text)
    spec={"collection":collection,"filters":sorted(terms),"needle":needle,
          "sort":sort_by,"descending":descending,"limit":limit}
    fingerprint=hashlib.sha256(canonical(spec)).hexdigest()
    offset=0
    if cursor:
        data=_cursor_decode(cursor)
        if data["fingerprint"]!=fingerprint or data["generation"]!=generation:
            raise VaultError("Stale or mismatched query cursor")
        offset=data["offset"]
    indexes=build_indexes(collection,records)
    selected=set(records)
    for field,token in terms:
        selected.intersection_update(indexes[field].get(token,set()))
    if needle:
        selected={ident for ident in selected if needle in _normalized(ident) or any(
            needle in _normalized(value) for key,value in records[ident].items()
            if key in FIELDS[collection])}
    def sort_key(identifier):
        value=identifier if sort_by=="id" else records[identifier].get(sort_by)
        return (_normalized(value),identifier)
    ordered=sorted(selected,key=sort_key,reverse=descending)
    page=ordered[offset:offset+limit]
    next_cursor=_cursor_encode({"fingerprint":fingerprint,"generation":generation,
                                "offset":offset+limit}) if offset+limit<len(ordered) else None
    return {"items":[{"id":key,**records[key]} for key in page],
            "count":len(ordered),"next_cursor":next_cursor,
            "generation":generation}
