#!/usr/bin/env python3
"""Refresh only the exact published BSD V2 markets with *newly observed* odds.

This is not an odds generator: absent, stale or unidentified quotes remain absent.
The canonical data.json is never modified. The refreshed document lives only
inside the current GitHub Actions runner and is not published to the website.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from bsd.bsd_v2_montante import (BANNED_KEYS, MIN_LEAD_MINUTES, POLICY,
                                  _unique_picks, number, utc)
from bsd.bsd_v2_publication_policy import eligible_feed_match, eligible_feed_selection
from bsd.bsd_v2_guardrails import VERIFIED_ODDS_SOURCES

MAX_EVENTS = 16
MAX_BSD_CALLS = 80
MAX_QUOTE_AGE = timedelta(hours=6)


def event_number(match):
    raw = match.get('source_event_id')
    if type(raw) is int and raw > 0:
        return raw
    if type(raw) is str and raw.isdecimal() and int(raw) > 0:
        return int(raw)
    return None


def published_markets(match):
    """Only original published markets; don't generate or substitute new legs."""
    if not eligible_feed_match(match) or match.get('source') != 'bsd':
        return []
    if match.get('combo_only') or match.get('recommendation_eligible') is not True:
        return []
    market_codes = []
    for pick in _unique_picks(match):
        if (eligible_feed_selection(match, pick)
                and pick.get('recommendation_eligible') is True
                and pick.get('selection_key') not in BANNED_KEYS
                and isinstance(pick.get('market_code'), str)
                and pick.get('market_code')):
            market_codes.append(pick['market_code'])
    return market_codes


def refresh_prices(feed, *, now, fetcher, limit=MAX_EVENTS, days=None):
    """Return feed copy and diagnostics. fetcher(event_id,kickoff,now)->market quotes.

    The injected fetcher is allowed to fail; no failure can create a quote.
    """
    if now.tzinfo is None:
        raise ValueError('Current timestamp must have timezone')
    now = now.astimezone(timezone.utc)
    if not isinstance(feed, dict) or not isinstance(feed.get('matches'), list):
        raise ValueError('Invalid BSD V2 feed')
    if not 1 <= limit <= 50:
        raise ValueError('Invalid request budget')
    result = deepcopy(feed)
    stats = {'events_eligible_for_quote_probe': 0, 'events_queried': 0,
             'exact_real_quotes_refreshed': 0, 'quote_errors': 0,
             'stale_or_invalid_live_quotes': 0, 'other_market_ignored': 0,
             'already_selected': False, 'limit': limit}
    if isinstance(days, dict) and now.date().isoformat() in days:
        stats['already_selected'] = True
        return result, stats
    candidates = []
    for match in result['matches']:
        if not isinstance(match, dict) or match.get('status') not in ('upcoming', 'notstarted') or match.get('is_finished'):
            continue
        kickoff = utc(match.get('event_date'))
        if (kickoff is None or kickoff.date() != now.date()
                or kickoff <= now + timedelta(minutes=MIN_LEAD_MINUTES)):
            continue
        ident = event_number(match)
        markets = published_markets(match)
        if ident is None or not markets:
            continue
        strength = max((number(p.get('conservative_probability')) or 0)
                       for p in _unique_picks(match) if p.get('market_code') in markets)
        candidates.append((-(strength if strength <= 1 else strength/100), kickoff, ident, match))
    candidates.sort(key=lambda t:(t[0],t[1],t[2]))
    stats['events_eligible_for_quote_probe'] = len(candidates)
    for _, kickoff, event_id, match in candidates[:limit]:
        stats['events_queried'] += 1
        try:
            quotes = fetcher(event_id, kickoff, now)
        except Exception:
            stats['quote_errors'] += 1
            continue
        if not isinstance(quotes, dict):
            stats['quote_errors'] += 1
            continue
        codes = set(published_markets(match))
        stats['other_market_ignored'] += len(set(quotes) - codes)
        for pick in _unique_picks(match):
            code = pick.get('market_code')
            if code not in codes:
                continue
            q = quotes.get(code)
            if not isinstance(q, dict):
                continue
            price = number(q.get('odds'))
            timestamp = utc(q.get('updated_at'))
            source = q.get('origin')
            if (source not in VERIFIED_ODDS_SOURCES or price is None or not 1.20 < price <= 100
                    or timestamp is None or timestamp > now or timestamp >= kickoff
                    or now - timestamp > MAX_QUOTE_AGE):
                stats['stale_or_invalid_live_quotes'] += 1
                continue
            # Do not reprice any other event or market, and preserve probability.
            pick.update({'odds':price, 'odds_source':source, 'estimated_odds':False,
                         'odds_updated_at': timestamp.isoformat(),
                         'odds_bookmaker': q.get('bookmaker'),
                         'odds_timestamp_type': 'market_update'})
            stats['exact_real_quotes_refreshed'] += 1
    return result, stats


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed',default='data.json')
    parser.add_argument('--ledger',default='montante/ledger.json')
    parser.add_argument('--output',default='tmp/montante-refreshed-feed.json')
    parser.add_argument('--stats',default='tmp/montante-quote-refresh.json')
    args=parser.parse_args(argv)
    data=json.loads(Path(args.feed).read_text(encoding='utf-8'))
    lp=Path(args.ledger)
    ledger=json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else {'schema':POLICY,'days':{}}
    now=datetime.now(timezone.utc)
    key=os.getenv('BSD_API_KEY','').strip()
    if key:
        # Imports only required for a real network run, not for unit tests.
        from bsd_api import BSDClient
        from bsd_v2_odds import fetch_event_odds
        client=BSDClient(api_key=key,max_requests=MAX_BSD_CALLS,min_interval=.1)
        def fetcher(event_id,kickoff,captured):
            return fetch_event_odds(client,event_id,kickoff=kickoff,captured_at=captured,
                                    max_pages=5,max_age_hours=6)[0]
        updated,stats=refresh_prices(data,now=now,fetcher=fetcher,days=ledger.get('days'))
        stats['provider_api_requests']=client.requests_made
    else:
        updated,stats=refresh_prices(data,now=now,
                fetcher=lambda *unused: {},limit=MAX_EVENTS,days=ledger.get('days'))
        stats['provider_api_requests']=0
        stats['price_api_configured']=False
    for name,output in ((args.output,updated),(args.stats,stats)):
        path=Path(name)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Stats only; never print API keys or private match history.
    print('MONTANTE_PRICE_REFRESH '+json.dumps(stats,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())