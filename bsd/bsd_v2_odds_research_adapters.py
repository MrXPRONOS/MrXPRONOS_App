"""Strict RESEARCH-only extended odds adapters for BSD V2 extra markets.

The production router stays unchanged. Provider schemas:
PinnWire num_0.spreads + team_total/team_totals and num_1.totals.
OddsLink public board sportsbooks[*].markets.spreads. Price timestamps
remain provider/book timestamps, never model prediction timestamps.
"""
from __future__ import annotations

from math import isfinite

from bsd_odds_fallback import (from_pinnwire,from_oddslink_public,
    american_to_decimal,clean,quote,utc,match_fixture,
    MAX_PINNWIRE_SNAPSHOT_AGE_SECONDS,MAX_COMPARABLE_QUOTE_AGE_SECONDS)

NEW_CODES=frozenset({
 'HOME_TEAM_OVER_0.5_FT','AWAY_TEAM_OVER_0.5_FT',
 'HOME_TEAM_UNDER_1.5_FT','AWAY_TEAM_UNDER_1.5_FT',
 'ASIAN_HANDICAP_HOME_+1.5_FT','ASIAN_HANDICAP_AWAY_+1.5_FT',
 'DRAW_NO_BET_HOME_FT','DRAW_NO_BET_AWAY_FT',
 'TOTAL_UNDER_1.5_HT',
})

def number(value):
    try:
        if isinstance(value,bool):return None
        result=float(value)
        return result if isfinite(result) else None
    except (TypeError,ValueError):return None

def _entries(value):
    if isinstance(value,dict):return [x for x in value.values() if isinstance(x,dict)]
    if isinstance(value,list):return [x for x in value if isinstance(x,dict)]
    return []

def from_pinnwire_extended(item,captured,snapshot_generated_at=None):
    """Only published period-specific odds with a genuinely recent snapshot."""
    current=utc(snapshot_generated_at)
    if (current is None or not -30 <= (captured-current).total_seconds() <= MAX_PINNWIRE_SNAPSHOT_AGE_SECONDS
        or item.get('event_type') not in ('prematch',None,'')
        or item.get('is_have_odds') is False
        or item.get('status') in ('suspended','closed','cancelled')):
        return {}
    result=from_pinnwire(item,captured,snapshot_generated_at=snapshot_generated_at)
    observed=min(current,captured)
    periods=item.get('periods') or {}
    ft=periods.get('num_0') or {}
    ht=periods.get('num_1') or {}
    def record(code,price):
        q=quote(price,'pinnwire',captured,updated=observed.isoformat())
        if q is None:return
        q.update({
           'bookmaker':'Pinnacle (via PinnWire)',
           'quote_timestamp_type':'provider_snapshot',
           'per_market_update_verified':False,
           'source_snapshot_generated_at':current.isoformat(),
        })
        result[code]=q
    # Asian spreads: hdp denotes HOME handicap; opposite handicap for AWAY.
    for row in _entries(ft.get('spreads')):
        hdp=number(row.get('hdp'))
        if hdp is None:continue
        if abs(hdp-1.5)<1e-8:
            record('ASIAN_HANDICAP_HOME_+1.5_FT',row.get('home'))
        if abs(hdp+1.5)<1e-8:
            record('ASIAN_HANDICAP_AWAY_+1.5_FT',row.get('away'))
        if abs(hdp)<1e-8:
            record('DRAW_NO_BET_HOME_FT',row.get('home'))
            record('DRAW_NO_BET_AWAY_FT',row.get('away'))
    # FT team totals primary and alternative prices. Never interpret
    # whole-match total as a team total.
    primary=ft.get('team_total') or {}
    alternates=ft.get('team_totals') or {}
    for team in ('home','away'):
        lines=[]
        value=primary.get(team) if isinstance(primary,dict) else None
        if isinstance(value,dict):lines.append(value)
        alt=alternates.get(team) if isinstance(alternates,dict) else None
        lines.extend(_entries(alt))
        for line in lines:
            n=number(line.get('points'))
            if n is None:continue
            tag='HOME' if team=='home' else 'AWAY'
            if abs(n-0.5)<1e-8:
                record(f'{tag}_TEAM_OVER_0.5_FT',line.get('over'))
            if abs(n-1.5)<1e-8:
                record(f'{tag}_TEAM_UNDER_1.5_FT',line.get('under'))
    # Half-time score goals are period num_1, never full time totals.
    for line in _entries(ht.get('totals')):
        n=number(line.get('points'))
        if n is not None and abs(n-1.5)<1e-8:
            record('TOTAL_UNDER_1.5_HT',line.get('under'))
    return result

def from_oddslink_public_extended(item,captured):
    """Add only supported sportsbook spreads to original OddsLink board parser."""
    result=from_oddslink_public(item,captured,market_code=None)
    home=clean(item.get('home_team'))
    away=clean(item.get('away_team'))
    for book in item.get('bookmakers') or []:
        if not isinstance(book,dict) or book.get('kind')!='sportsbook':continue
        bookmaker=str(book.get('key') or '').strip()
        last=utc(book.get('last_update'))
        if (not bookmaker or last is None
            or not 0 <= (captured-last).total_seconds() <= MAX_COMPARABLE_QUOTE_AGE_SECONDS):
            continue
        markets=book.get('markets') or {}
        spreads=markets.get('spreads') if isinstance(markets,dict) else None
        if not isinstance(spreads,list):continue
        for row in spreads:
            if not isinstance(row,dict):continue
            point=number(row.get('point'))
            label=clean(row.get('name'))
            if point is None:continue
            code=None
            if label==home:
                if abs(point-1.5)<1e-8:code='ASIAN_HANDICAP_HOME_+1.5_FT'
                elif abs(point)<1e-8:code='DRAW_NO_BET_HOME_FT'
            elif label==away:
                if abs(point-1.5)<1e-8:code='ASIAN_HANDICAP_AWAY_+1.5_FT'
                elif abs(point)<1e-8:code='DRAW_NO_BET_AWAY_FT'
            if code is None:continue
            price=american_to_decimal(row.get('price'))
            q=quote(price,'oddslink_public',captured,updated=last.isoformat())
            if q is None:continue
            q['bookmaker']=bookmaker
            q['odds_format_original']='american'
            if code not in result or q['odds']>result[code]['odds']:
                result[code]=q
    return result

def fetch_research_all(router,event,captured,provider):
    """Use existing cached HTTP client and native strict fixture identity match."""
    if provider=='pinnwire':
        import os
        key=(os.getenv('PINNWIRE_API_KEY') or '').strip()
        if not key or (key.lower()=='demo' and os.getenv('PINNWIRE_USE_DEMO','0')!='1'):
            return {},'pinnwire_key_unavailable'
        data=router.get('pinnwire','https://pinnwire.com/kit/v1/prematch/fixtures?sport_id=1',
                       {'x-api-key':key})
        if not isinstance(data,dict):return {},'pinnwire_unavailable'
        for item in data.get('events') or []:
            if (isinstance(item,dict) and match_fixture(item,event)
                and item.get('event_type') in (None,'prematch')):
                return from_pinnwire_extended(item,captured,data.get('generated_at')),'matched'
        return {},'fixture_not_found_in_pinnwire_snapshot'
    if provider=='oddslink_public':
        data=router.get('oddslink_public','https://oddslink.app/v1/public/board/soccer')
        if not isinstance(data,dict):return {},'oddslink_public_unavailable'
        for item in data.get('fixtures') or []:
            if isinstance(item,dict) and item.get('in_play') is False and match_fixture(item,event):
                return from_oddslink_public_extended(item,captured),'matched'
        return {},'fixture_not_found_on_public_board'
    # Existing production sources retain their own exact-match parsers;
    # market_code=None returns their full matched-fixture market map.
    rows,diagnostic=router.fetch(event,captured,market_code=None)
    return (rows if isinstance(rows,dict) else {}),str((diagnostic or {}).get('provider') or 'unavailable')
