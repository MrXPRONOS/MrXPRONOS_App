#!/usr/bin/env python3
"""Real film/series/anime poster metadata for Cine Radar's illustrative home carousel.
TMDB is preferred when an authorized API key is present. Public SampleAPIs movie data
and TVmaze show posters are the no-key fallback. No invented films or channel availability.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

OUT=Path(__file__).resolve().parent/"assets"/"poster_showcase.json"
POSTER_RE=re.compile(r"^/[a-zA-Z0-9_-]{8,100}\.(?:jpg|jpeg|png|webp)$")
ALLOWED={"image.tmdb.org","m.media-amazon.com","images-na.ssl-images-amazon.com","static.tvmaze.com"}
GENRES=["films","series","animes"]

def valid_poster(url):
    try:
        p=urlparse(str(url or ""))
        return p.scheme=="https" and p.hostname in ALLOWED and not p.username and not p.password and not p.query and not p.fragment and len(url)<950
    except (ValueError,TypeError):return False

def item(kind,source_id,name,poster,reference):
    if kind not in GENRES or not name or not valid_poster(poster):return None
    if not str(reference).startswith("https://"):return None
    return {"id":kind+"-"+str(source_id),"title":str(name).strip()[:95],
            "type":kind,"poster":str(poster),"tmdb":str(reference)}

def tmdb_results(session,key):
    result=[];seen=set()
    for kind,path,limit in [
      ("films","/trending/movie/week",9),
      ("series","/trending/tv/week",7),
      ("animes","/discover/tv?with_genres=16&sort_by=popularity.desc",7)]:
        sep="&" if "?" in path else "?"
        response=session.get("https://api.themoviedb.org/3"+path+sep+"api_key="+key+"&language=fr-FR",timeout=(8,25))
        response.raise_for_status()
        payload=response.json()
        for raw in payload.get("results",[]):
            if len([x for x in result if x["type"]==kind])>=limit:break
            poster=str(raw.get("poster_path") or "")
            if not POSTER_RE.fullmatch(poster) or raw.get("adult") is True:continue
            x=item(kind,raw.get("id"),raw.get("title") or raw.get("name"),
              "https://image.tmdb.org/t/p/w342"+poster,
              "https://www.themoviedb.org/"+("movie" if kind=="films" else "tv")+"/"+str(raw.get("id")))
            if x and x["poster"] not in seen:result.append(x);seen.add(x["poster"])
    if len(result)<10:raise RuntimeError("tmdb_results_insufficient")
    return result,"TMDB"

def public_results(session):
    result=[];seen=set()
    def add(x):
        if x and x["poster"] not in seen:result.append(x);seen.add(x["poster"])
    # Movie source, public documentation explicitly documents posterURL & imdbId.
    for category,kind,max_count in [("action-adventure","films",10),("animation","animes",7)]:
        try:
            response=session.get("https://api.sampleapis.com/movies/"+category,timeout=(8,24))
            response.raise_for_status()
            rows=response.json()
            if not isinstance(rows,list):continue
            count=0
            for raw in rows:
                if count>=max_count:break
                if not isinstance(raw,dict):continue
                imdb=str(raw.get("imdbId") or "")
                poster=str(raw.get("posterURL") or raw.get("posterUrl") or "")
                if not re.fullmatch(r"tt[0-9]{6,11}",imdb):continue
                x=item(kind,imdb,raw.get("title"),poster,"https://www.imdb.com/title/"+imdb+"/")
                if x and x["poster"] not in seen:add(x);count+=1
        except (requests.RequestException,ValueError):
            print("PUBLIC_POSTER_SOURCE_UNAVAILABLE",category)
    # Real series and Japanese anime art, served as stable TVmaze profile images.
    queries=[
      ("series","Lupin"),("series","Black Doves"),("series","Stranger Things"),
      ("series","The Last of Us"),("series","Wednesday"),("series","Breaking Bad"),
      ("animes","One Piece"),("animes","Bleach"),("animes","Jujutsu Kaisen"),
      ("animes","Black Clover"),("animes","Attack on Titan"),("animes","Naruto")
    ]
    for kind,name in queries:
        try:
            response=session.get("https://api.tvmaze.com/search/shows",params={"q":name},timeout=(8,20))
            response.raise_for_status()
            rows=response.json()
            for entry in rows[:6]:
                show=entry.get("show") or {}
                show_name=str(show.get("name") or "")
                if not show_name or name.casefold().split()[0] not in show_name.casefold():continue
                poster=str((show.get("image") or {}).get("medium") or "")
                x=item(kind,show.get("id"),show_name,poster,show.get("url"))
                if x:add(x);break
        except (requests.RequestException,ValueError):
            print("TVMAZE_POSTER_SOURCE_UNAVAILABLE")
    if len(result)<10:raise RuntimeError("public_poster_sources_insufficient")
    return result[:28],"SampleAPIs + TVmaze"

def main():
    session=requests.Session()
    session.headers.update({"User-Agent":"CineRadarPosterShowcase/2.0","Accept":"application/json"})
    key=os.getenv("TMDB_API_KEY","").strip()
    items=None;source=None
    if key:
        try:items,source=tmdb_results(session,key)
        except (requests.RequestException,ValueError,RuntimeError):
            print("TMDB_POSTERS_UNAVAILABLE_FALLING_BACK")
    if items is None:items,source=public_results(session)
    payload={"version":2,"source":source,"updated_at":datetime.now(timezone.utc).isoformat(),
      "notice":"Images originales de fiches films/séries pour l'ambiance visuelle. Leur présence ne garantit pas la disponibilité dans un canal Telegram.",
      "items":items}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("POSTER_SHOWCASE_UPDATED",{"source":source,"count":len(items),"category_counts":{t:sum(x["type"]==t for x in items) for t in GENRES}})
if __name__=="__main__":main()
