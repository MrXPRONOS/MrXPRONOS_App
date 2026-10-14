#!/usr/bin/env python3
"""Acquire CC0 football.TXT match RESULTS for uncovered leagues (no scraping).

Original licensed sources:
  https://github.com/openfootball/world/blob/master/LICENSE.md
  https://github.com/openfootball/south-america/blob/master/LICENSE.md

Curated exact raw GitHub paths (checked 2026-10-14). Fetch only .txt on
raw.githubusercontent.com, with budget/timeouts; never crawl or scrape a site.
Historic source TXT sometimes supplies LOCAL clock only, or no timezone:
we record DATE ONLY for conservative 23:59 UTC availability in BSD adapter.
No scores are inferred; schedules/unplayed games are never admitted.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote
import requests

BASE="https://raw.githubusercontent.com/openfootball"
# Explicit, independently verified files; recent years prioritized per league.
SOURCES=(
 ("world","africa/nigeria","Nigeria Professional Football League",("2025-26_ng1.txt","2024-25_ng1.txt","2023-24_ng1.txt")),
 ("world","africa/nigeria","Nigeria National League",("2025-26_ng2.txt","2024-25_ng2.txt")),
 ("world","africa/morocco","Botola Pro 1",("2024-25_ma1.txt","2023-24_ma1.txt")),
 ("world","africa/egypt","Egyptian Premier League",("2024-25_eg1.txt","2023-24_eg1.txt")),
 ("world","africa/algeria","Algerian Ligue 1",("2024-25_dz1.txt","2023-24_dz1.txt")),
 ("world","africa/south-africa","South African Premiership",("2024-25_za1.txt",)),
 ("world","africa/ghana","Ghana Premier League",("2024-25_gh1.txt","2023-24_gh1.txt")),
 ("world","africa/senegal","Senegal Ligue 1",("2025-26_sn1.txt","2024-25_sn1.txt")),
 ("world","asia/japan","J1 League",("2025_jp1.txt","2024_jp1.txt","2023_jp1.txt")),
 ("world","asia/china","Chinese Super League",("2025_cn1.txt","2024_cn1.txt","2023_cn1.txt")),
 ("world","north-america/mexico","Liga MX",("2024-25_mx1.txt","2023-24_mx1.txt")),
 ("world","north-america/major-league-soccer","Major League Soccer",("2025_mls.txt","2024_mls.txt")),
 ("south-america","brazil","Brasileiro Série A",("2026_br1.txt","2025_br1.txt","2024_br1.txt")),
 ("south-america","brazil","Brasileiro Série B",("2025_br2.txt","2024_br2.txt")),
 ("south-america","argentina","Argentine Primera Division",("2025_ar1.txt","2024_ar1.txt","2023_ar1.txt")),
 ("south-america","colombia","Colombian Primera A",("2025_co1.txt","2024_co1.txt","2023_co1.txt")),
)
MONTHS={x:i for i,x in enumerate(("jan","feb","mar","apr","may","jun",
                                   "jul","aug","sep","oct","nov","dec"),1)}
DAY=re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
# Fixed-width legacy soccer text files use >=2 spaces around the 'v'.
MATCH=re.compile(r"^\s*(?:\d{1,2}:\d{2}\s+)?(.+?)\s{2,}v\s+(.+?)\s{2,}(\d{1,2})-(\d{1,2})(?:\s*(?:\(|$))")
SOURCE_TAG="openfootball"
MAX_FILES=48


def safe_source_url(repository: str, folder: str, filename: str) -> str:
    if repository not in ("world","south-america"):
        raise ValueError("Unapproved source repository")
    if not re.fullmatch(r"[a-z0-9-]+(?:/[a-z0-9-]+){1,3}",folder):
        raise ValueError("Invalid directory")
    if not re.fullmatch(r"(?:20\d\d(?:-20?\d\d)?_[a-z0-9]+)\.txt",filename):
        raise ValueError("Invalid filename")
    return f"{BASE}/{repository}/master/{folder}/{filename}"


def parse_txt(txt: str, *, league: str, path: str) -> tuple[list[dict],dict]:
    if not isinstance(txt,str) or len(txt)>3_000_000:
        raise ValueError("Untrusted text payload too large")
    basename=path.rsplit("/",1)[-1]
    m=re.match(r"^(20\d\d)(?:-(\d\d))?_",basename)
    if not m:
        raise ValueError("Invalid season label")
    first_year=int(m.group(1))
    season_end=first_year+1 if m.group(2) else first_year
    current=None
    observed=Counter()
    rows=[]
    for linenum,line in enumerate(txt.splitlines(),1):
        datehit=DAY.match(line)
        if datehit:
            month=MONTHS.get(datehit.group(1).lower())
            day=int(datehit.group(2))
            explicit=datehit.group(3)
            if month is None:
                current=None
                continue
            year=(int(explicit) if explicit else
                  (first_year if (first_year==season_end or month>=7) else season_end))
            try:
                current=date(year,month,day)
            except ValueError:
                current=None
                observed["invalid_date"]+=1
            continue
        scoreline=MATCH.match(line)
        if scoreline:
            if current is None:
                observed["score_without_date"]+=1
                continue
            home=scoreline.group(1).strip()
            away=scoreline.group(2).strip()
            h,a=int(scoreline.group(3)),int(scoreline.group(4))
            if not home or not away or home.casefold()==away.casefold() or h>30 or a>30:
                observed["invalid_result"]+=1
                continue
            if len(home)>110 or len(away)>110:
                observed["oversized_team"]+=1
                continue
            origin=f"{path}:{linenum}"
            rows.append({
                "source":SOURCE_TAG, "source_id":hashlib.sha256(origin.encode()).hexdigest()[:24],
                "status":"finished",
                "match_date":current.isoformat(), "league":league,
                "home_team":home,"away_team":away,
                "home_score":h,"away_score":a,
                "time_precision":"day", "original_source_file":path,
            })
            observed["finished"]+=1
        elif " v " in line and current is not None:
            observed["unparsed_or_unfinished_fixture"]+=1
    return rows,dict(observed)


def import_history(*, max_files: int = 40, session=None) -> tuple[list[dict],dict]:
    if not 1<=max_files<=MAX_FILES:
        raise ValueError("max_files out of allowed budget")
    session=session or requests.Session()
    rows=[]
    counts=Counter()
    source_errors=[]
    # Round-robin: each league first gets its newest year, then the previous year.
    longest=max(len(years) for _,_,_,years in SOURCES)
    jobs=[(repository,folder,league,years[y]) for y in range(longest)
          for repository,folder,league,years in SOURCES if y<len(years)]
    for repository,folder,league,filename in jobs[:max_files]:
        url=safe_source_url(repository,folder,filename)
        try:
            response=session.get(url,timeout=(8,20),headers={"User-Agent":"MrXPRONOS-CC0-HistoryResearch/1.0"})
            response.raise_for_status()
            parsed,health=parse_txt(response.text,league=league,path=f"{repository}/{folder}/{filename}")
            rows.extend(parsed)
            counts["files_with_results"]+=bool(parsed)
            counts["historic_result_rows"]+=len(parsed)
            counts["unparsed_result_like_lines"]+=health.get("unparsed_or_unfinished_fixture",0)
        except (requests.RequestException, ValueError, TypeError) as exc:
            counts["download_or_parse_failures"]+=1
            source_errors.append(f"{repository}/{folder}/{filename}: {type(exc).__name__}")
        counts["http_requests"]+=1
    # Only aggregate counts and error class/name; no private provider data exists.
    return rows,{
        "source":"openfootball World + South America CC0",
        "files_attempted":counts["http_requests"],
        "files_with_results":counts["files_with_results"],
        "historic_result_rows":counts["historic_result_rows"],
        "download_or_parse_failures":counts["download_or_parse_failures"],
        "unparsed_result_like_lines":counts["unparsed_result_like_lines"],
        "failed_files":source_errors[:12],
        "matches_are_date_only":True,
        "licensed_for_commercial_reuse":"CC0-1.0",
        "api_calls_to_limited_football_providers":0,
        "no_predictions_generated":True,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--max-files",type=int,default=40)
    p.add_argument("--out",required=True)
    p.add_argument("--report",required=True)
    a=p.parse_args()
    rows,summary=import_history(max_files=a.max_files)
    destination=Path(a.out)
    if destination.name=="data.json":
        p.error("Never overwrite production data.json")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("w",encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    out=Path(a.report)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("OPENFOOTBALL_WORLD_CC0_IMPORTED",json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    main()
