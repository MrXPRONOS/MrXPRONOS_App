"""Find interesting football *leads* (not verified facts) from an RSS index.

Headlines are inspiration only: NEVER used as voice-over claims or reuploaded
content. Journalism and club claims need a reviewed factual dossier, with links,
before the topic can pass the narrative producer's editorial gate.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import requests

FOOTBALL_FEEDS = (
    'https://feeds.bbci.co.uk/sport/football/rss.xml',
    'https://feeds.bbci.co.uk/sport/football/champions-league/rss.xml',
)
CATEGORIES = {
    'record': ('record','first ever','all-time','historic','history','most goals','milestone'),
    'rivalry': ('derby','rivalry','clash','classico','clásico','vs ','versus'),
    'comeback': ('comeback','fightback','late winner','stoppage time','turnaround','dramatic win'),
    'performance': ('hat-trick','hat trick','three goals','brace','double','four goals','hero'),
    'portrait': ('star','talent','rising','youngster','breakthrough','player of the'),
    'analysis': ('tactics','analysis','why','explained','how ','statistics','numbers'),
}


def classify_headline(headline:str)->tuple[str,...]:
    text=' '.join(str(headline).casefold().split())
    return tuple(k for k,terms in CATEGORIES.items() if any(term in text for term in terms))


def _parsedate(value:str)->str | None:
    try:
        return parsedate_to_datetime(value).astimezone(dt.timezone.utc).date().isoformat()
    except (ValueError,TypeError,OverflowError):
        return None


def parse_feed_xml(xml:bytes,today:dt.date|None=None,days=5)->list[dict]:
    today=today or dt.datetime.now(dt.timezone.utc).date()
    if len(xml)>1_000_000:raise ValueError('Flux RSS anormalement volumineux')
    root=ET.fromstring(xml)
    results=[]
    for item in root.findall('./channel/item')[:50]:
        title=' '.join((item.findtext('title') or '').split())[:180]
        url=(item.findtext('link') or '').strip()
        when=_parsedate(item.findtext('pubDate') or '')
        host=(urlparse(url).hostname or '').lower()
        if not title or not when or not host.endswith('.bbc.co.uk'):continue
        age=(today-dt.date.fromisoformat(when)).days
        if not 0<=age<=days:continue
        tags=classify_headline(title)
        if not tags:continue
        results.append({'id':hashlib.sha256(url.encode()).hexdigest()[:14],
                        'date':when,'headline_for_review':title,'source_url':url,
                        'categories':tags,'verified':False,'ready_to_script':False,
                        'reason':'Signal éditorial seulement : articles/sources à vérifier avant écriture.'})
    return results


def discover_news_leads(today:dt.date|None=None,urls=FOOTBALL_FEEDS)->list[dict]:
    found={}
    for url in urls:
        try:
            response=requests.get(url,timeout=12,headers={'User-Agent':'MrXPRONOS-FootballStories/3.0 editorial-research'})
            response.raise_for_status()
            for lead in parse_feed_xml(response.content,today=today):
                found[lead['id']]=lead
        except (requests.RequestException,ET.ParseError,ValueError) as exc:
            print('[INFO] Flux RSS indisponible :',url.rsplit('/',2)[-2:],type(exc).__name__)
    return sorted(found.values(),key=lambda x:(x['date'],len(x['categories']),x['id']),reverse=True)[:25]
