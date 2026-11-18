#!/usr/bin/env python3
"""Refresh genuine TMDB film/TV poster thumbnails for the Cine Radar home marquee.
Never fabricate film availability in Telegram channels. No personal data or Telegram calls.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT=Path(__file__).resolve().parent / "assets" / "poster_showcase.json"
PATH_RE=re.compile(r"^/[a-zA-Z0-9_-]{8,100}\.(?:jpg|jpeg|png|webp)$")
BASE="https://api.themoviedb.org/3"

def usable(row,kind):
    poster=str(row.get("poster_path") or "")
    if row.get("adult") is True or not PATH_RE.fullmatch(poster):
        return None
    name=str(row.get("title") or row.get("name") or "").strip()[:95]
    if not name or not isinstance(row.get("id"),int):
        return None
    return {
        "id":str(kind)+"-"+str(row["id"]),
        "title":name,
        "type":kind,
        "poster":"https://image.tmdb.org/t/p/w342"+poster,
        "tmdb":"https://www.themoviedb.org/"+("movie" if kind=="films" else "tv")+"/"+str(row["id"])
    }

def build(fetch):
    final=[]
    seen=set()
    for kind,path,max_count in (
        ("films","/trending/movie/week",9),
        ("series","/trending/tv/week",7),
        ("animes","/discover/tv?with_genres=16&sort_by=popularity.desc",7)
    ):
        payload=fetch(path)
        if not isinstance(payload,dict) or not isinstance(payload.get("results"),list):
            raise RuntimeError("Invalid TMDB feed for "+kind)
        count=0
        for raw in payload["results"]:
            if not isinstance(raw,dict):continue
            candidate=usable(raw,kind)
            if not candidate:continue
            image=candidate["poster"]
            if image in seen:continue
            seen.add(image)
            final.append(candidate)
            count+=1
            if count>=max_count:break
    if len(final)<10:raise RuntimeError("Insufficient verified TMDB posters (need 10+)")
    return {"version":1,"source":"TMDB","updated_at":datetime.now(timezone.utc).isoformat(),
            "notice":"Visuels de films et séries pour illustrer l'univers du cinéma, pas la disponibilité sur un canal Telegram.",
            "items":final}

def main():
    key=os.getenv("TMDB_API_KEY","").strip()
    if not key:raise RuntimeError("TMDB_API_KEY secret missing; retaining previous manifest")
    session=requests.Session()
    session.headers.update({"User-Agent":"CineRadarPosterShowcase/1.0"})
    def fetch(path):
        delimiter="&" if "?" in path else "?"
        url=BASE+path+delimiter+"api_key="+key+"&language=fr-FR"
        response=session.get(url,timeout=(8,25))
        if response.status_code!=200:
            raise RuntimeError("TMDB feed unavailable: HTTP "+str(response.status_code))
        return response.json()
    data=build(fetch)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("TMDB_SHOWCASE_UPDATED",len(data["items"]), {kind:sum(x["type"]==kind for x in data["items"]) for kind in ("films","series","animes")})
if __name__=="__main__":
    main()
