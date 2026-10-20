"""Encrypted measured-xG historical cache for isolated single-score research.

Measured xG is admitted only after settlement and only for future fixtures.
The archive never stores an upcoming fixture's shots or goals.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,math
from bsd_archive import cipher
from bsd_v2_core import fixture_datetime
from bsd_h2h import _team_id

PATH=Path("bsd/single_exact_score_xg_history.enc.json")
FORMAT="mrx-single-exact-measured-xg-v1"

def empty():
    return {"format":FORMAT,"records":{}}

def read(path=PATH,secret=None):
    path=Path(path)
    if not path.exists():return empty()
    payload=json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format")!=FORMAT or not isinstance(payload.get("encrypted"),str):
        raise ValueError("Refusing plaintext or unrelated xG history")
    data=json.loads((secret or cipher()).decrypt(payload["encrypted"].encode("ascii")))
    if data.get("format")!=FORMAT or not isinstance(data.get("records"),dict):
        raise ValueError("Unexpected encrypted xG archive schema")
    return data

def save(data,path=PATH,secret=None):
    if data.get("format")!=FORMAT or not isinstance(data.get("records"),dict):
        raise ValueError("Bad xG history model/schema")
    for key,row in data["records"].items():
        if not isinstance(row,dict) or not valid(row):
            raise ValueError("Invalid measured xG row: "+str(key))
    token=(secret or cipher()).encrypt(json.dumps(data,sort_keys=True,
                separators=(",",":"),ensure_ascii=False).encode()).decode("ascii")
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps({"format":FORMAT,"encrypted":token}),encoding="utf-8")
    temp.chmod(0o600);temp.replace(path)

def _utc(text):
    at=datetime.fromisoformat(str(text).replace("Z","+00:00"))
    if at.tzinfo is None:raise ValueError("Timestamp must carry timezone")
    return at.astimezone(timezone.utc)

def valid(row):
    try:
        if not all(type(row.get(k)) in (float,int) and
                   math.isfinite(row[k]) and 0<=row[k]<=8 for k in ("home_xg","away_xg")):
            return False
        at=_utc(row["kickoff_utc"])
        observed=_utc(row["captured_at_utc"])
        return (observed>=at+timedelta(hours=4) and
                int(row["home_team_id"])>0 and int(row["away_team_id"])>0 and
                int(row["home_team_id"])!=int(row["away_team_id"]))
    except (ValueError,TypeError,KeyError,OverflowError):
        return False

def apply(index,data,now):
    count=0
    for available,event in index.global_games:
        row=data["records"].get(str(event.get("id")))
        if not isinstance(row,dict) or not valid(row):continue
        at=fixture_datetime(event)
        if not (available<=now.timestamp() and
                _utc(row["captured_at_utc"])<=now and
                _utc(row["kickoff_utc"])==at and
                row["home_team_id"]==_team_id(event,"home") and
                row["away_team_id"]==_team_id(event,"away")):
            continue
        event["home_xg_live"]=row["home_xg"]
        event["away_xg_live"]=row["away_xg"]
        event["xg_estimated"]=False
        count+=1
    return count

def add(data,new):
    inserted=0
    for key,row in new.items():
        key=str(key)
        if not valid(row):continue
        if key in data["records"]:continue
        data["records"][key]=row
        inserted+=1
    return inserted
