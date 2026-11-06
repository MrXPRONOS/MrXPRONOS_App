"""Free, bounded multi-market odds collection: BSD once + optional public board once.

No subscription or paywall. The optional OddsLink public board is a snapshot of
bookmaker offers, not proof that a particular user can access/accept those odds.
"""
from __future__ import annotations
from datetime import datetime,timezone
from math import isfinite
from .policy import V3Policy,utc_datetime
from .quotes import validate_quote

FREE_PUBLIC_BOARD="https://oddslink.app/v1/public/board/soccer"

class FreeMultiMarketOdds:
    def __init__(self, bsd_client, *, bookmaker_slug="consensus",
                 enable_public_board=False, session=None,
                 timeout=10, policy=V3Policy()):
        self.bsd_client=bsd_client
        self.bookmaker_slug=bookmaker_slug
        self.enable_public_board=enable_public_board
        self.session=session
        self.timeout=timeout
        self.policy=policy
        self._board=None
        self._board_error=None
        self._board_fetched=False
        self.stats={"bsd_events":0,"public_board_requests":0,
                    "board_matched":0,"accepted_quotes":0,
                    "source_breakdown":{}}

    def _public_board(self):
        if not self.enable_public_board:
            return None
        if self._board_fetched:
            return self._board
        self._board_fetched=True
        import requests
        self.session=self.session or requests.Session()
        self.stats["public_board_requests"]+=1
        try:
            reply=self.session.get(FREE_PUBLIC_BOARD,timeout=self.timeout,
                                   allow_redirects=False)
            if reply.status_code!=200:
                self._board_error="http_"+str(reply.status_code)
                return None
            obj=reply.json()
            if (not isinstance(obj,dict) or
                not isinstance(obj.get("fixtures"),list) or
                len(obj["fixtures"])>500):
                self._board_error="invalid_board_schema"
                return None
            self._board=obj
            return obj
        except (requests.RequestException,ValueError,TypeError):
            self._board_error="unavailable"
            return None

    def __call__(self,event,now):
        from bsd_v2_odds import fetch_event_odds
        from bsd_odds_fallback import match_fixture,from_oddslink_public
        now=utc_datetime(now)
        kickoff=utc_datetime(event["event_date"])
        # A single BSD call/page set supplies all goal/result/DC/BTTS markets.
        quotes,meta=fetch_event_odds(self.bsd_client,int(event["id"]),kickoff=kickoff,
                                     captured_at=now,bookmaker_slug=self.bookmaker_slug,
                                     max_age_hours=2)
        self.stats["bsd_events"]+=1
        offers={}
        for code,price in quotes.items():
            verified,reason=validate_quote(price,now=now,kickoff=kickoff,
                                           policy=self.policy)
            if verified:
                offers.setdefault(code,[]).append(verified)
        board=self._public_board()
        if board:
            for fixture in board["fixtures"]:
                if not isinstance(fixture,dict) or fixture.get("in_play") is not False:
                    continue
                if not match_fixture(fixture,event):
                    continue
                self.stats["board_matched"]+=1
                for code,price in from_oddslink_public(fixture,now).items():
                    verified,reason=validate_quote(price,now=now,kickoff=kickoff,
                                                   policy=self.policy)
                    if verified:
                        offers.setdefault(code,[]).append(verified)
                break
        selected={}
        for code,choices in offers.items():
            # Verified named sportsbook offer preferred to averaged consensus.
            # If same evidence tier, use the better observed price.
            best=max(choices,key=lambda q:(q["executable"],q["odds"]))
            selected[code]={"odds":best["odds"],"origin":best["origin"],
                            "bookmaker":best["bookmaker"],
                            "captured_at":best["captured_at"],
                            "updated_at":best["updated_at"],
                            "quote_timestamp_verified":True}
            origin=best["origin"]
            self.stats["source_breakdown"][origin]=(
                self.stats["source_breakdown"].get(origin,0)+1)
        self.stats["accepted_quotes"]+=len(selected)
        meta=dict(meta or {})
        meta.update({"source":"free_multi_market","public_board_used":bool(board),
                     "public_board_error":self._board_error,
                     "board_matched_count":self.stats["board_matched"],
                     "market_codes_observed":sorted(offers),
                     "bookmaker_offer_count":sum(len(rows) for rows in offers.values()),
                     "no_payment_required":True})
        return selected,meta
