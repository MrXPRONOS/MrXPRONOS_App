"""Multi-provider prematch odds with conservative fixture/market matching.

The router consumes quotes only. BSD V2 chooses a market BEFORE calling it.
Absence of a quote must never become a fabricated bookmaker price.
"""
from __future__ import annotations
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from requests import Session

ORDER = ("goaldir", "pinnwire", "oddslink", "moviodds", "oddsharvester")
CODES = {"home": "1X2_HOME_FT", "draw": "1X2_DRAW_FT", "away": "1X2_AWAY_FT",
         "1x": "DC_1X_FT", "x2": "DC_X2_FT",
         "btts_yes": "BTTS_YES_FT", "btts_no": "BTTS_NO_FT"}
for _line in ("1.5", "2.5", "3.5", "4.5"):
    for _side in ("over", "under"):
        CODES[f"{_side}_{_line}"] = f"OU_{_line}_{_side.upper()}_FT"


def clean(name):
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]", "", s)


def utc(value):
    try:
        v = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def match_fixture(row, event):
    def team(v):
        if isinstance(v, dict): return v.get("name")
        return v
    h = team(event.get("home_team"))
    a = team(event.get("away_team"))
    if not (clean(h) and clean(a) and clean(h) == clean(row.get("home") or row.get("home_team"))
            and clean(a) == clean(row.get("away") or row.get("away_team"))):
        return False
    expected = utc(event.get("event_date"))
    actual = utc(row.get("kickoff_utc") or row.get("starts") or row.get("commence_time"))
    return bool(expected and actual and abs((expected - actual).total_seconds()) <= 7200)


def decimal(v):
    try:
        n = float(v)
        return n if 1.01 <= n <= 100 and n == n and n != float("inf") else None
    except (TypeError, ValueError):
        return None


def quote(price, origin, captured, *, updated=None):
    n = decimal(price)
    at = utc(updated) if updated else captured
    if n is None or at is None or at > captured or (captured-at).total_seconds() > 48 * 3600:
        return None
    return {"odds": n, "origin": origin, "bookmaker": origin,
            "updated_at": at.isoformat(), "captured_at": captured.isoformat(),
            "bookmaker_selection_code": None}


def add(out, key, price, origin, captured, updated=None):
    code = CODES.get(key)
    q = quote(price, origin, captured, updated=updated) if code else None
    if q: out[code] = q


def from_pinnwire(item, captured):
    out = {}
    period = (item.get("periods") or {}).get("num_0") or {}
    updated = item.get("last_odds_update") or None
    line = period.get("money_line") or {}
    for k in ("home", "draw", "away"):
        add(out, k, line.get(k), "pinnwire", captured, updated)
    for entry in (period.get("totals") or {}).values():
        if not isinstance(entry, dict): continue
        points = str(entry.get("points"))
        for side in ("over", "under"):
            add(out, f"{side}_{points}", entry.get(side), "pinnwire", captured, updated)
    return out


def from_oddslink(item, captured):
    out = {}
    for book in item.get("bookmakers") or []:
        updated = book.get("last_update")
        for market in book.get("markets") or []:
            if market.get("period") not in (None, "", "full"): continue
            key = market.get("key")
            for row in market.get("outcomes") or []:
                name = clean(row.get("name"))
                code = None
                if key == "h2h":
                    if name == clean(item.get("home_team")): code = "home"
                    elif name == clean(item.get("away_team")): code = "away"
                    elif name == "draw": code = "draw"
                elif key == "totals" and row.get("point") is not None:
                    if name in ("over", "under"):
                        code = f"{name}_{row['point']}"
                if code:
                    add(out, code, row.get("price"), "oddslink", captured,
                        market.get("last_update") or updated)
        if out: break   # never combine different bookmakers into a fake book
    return out


def from_movi(item, captured):
    out = {}
    for row in item.get("quotes") or []:
        if row.get("suspended") is True: continue
        group = clean(row.get("group_name"))
        label = clean(row.get("label"))
        side = clean(row.get("side"))
        line = row.get("line")
        key = None
        if group in ("fulltimeresult", "matchresult"):
            key = "home" if label == clean(item.get("home")) else (
                "away" if label == clean(item.get("away")) else ("draw" if label in ("draw", "x") else None))
        elif group == "doublechance":
            key = "1x" if label in ("1x", "homedraw") else ("x2" if label in ("x2", "awaydraw") else None)
        elif group in ("bothteamstoscore", "bothteamstoscoreyesno"):
            key = "btts_yes" if label == "yes" else ("btts_no" if label == "no" else None)
        elif group in ("goalsoverunder", "matchgoals", "totalgoals", "alternativetotalgoals"):
            if line is not None and side in ("over", "under"): key = f"{side}_{line}"
        if key:
            add(out, key, row.get("odds_dec"), "moviodds", captured,
                item.get("polled_at") or row.get("ts"))
    return out


def from_harvester(item, captured):
    """Only an explicitly fresh and independently generated JSON snapshot."""
    out = {}
    observed = utc(item.get("scraped_at"))
    if observed is None or (captured-observed).total_seconds() not in range(0, 1801): return out
    markets = item.get("odds") or item.get("bookmakers") or []
    if isinstance(markets, dict): markets = [markets]
    for bookmaker in markets:
        if not isinstance(bookmaker, dict): continue
        blocked = bookmaker.get("blocked_outcomes") or []
        for side, key in (("1","home"), ("X","draw"), ("2","away")):
            if side not in blocked: add(out, key, bookmaker.get(side), "oddsharvester", captured, observed.isoformat())
        if out: break
    return out


class OddsRouter:
    def __init__(self, bsd_fetch, session=None, order=ORDER):
        self.bsd_fetch = bsd_fetch
        self.session = session or Session()
        self.order = tuple(order)
        self.cache = {}
        self.disabled = set()
        self.usage = {}
        self.events = []

    def get(self, name, url, headers=None):
        if name in self.disabled: return None
        if name in self.cache: return self.cache[name]
        try:
            response = self.session.get(url, headers=headers or {}, timeout=12)
            self.usage[name] = self.usage.get(name, 0) + 1
            if response.status_code in (401, 402, 403, 429):
                self.disabled.add(name)
                self.events.append((name, "disabled_http_" + str(response.status_code)))
                return None
            response.raise_for_status()
            data = response.json()
            self.cache[name] = data
            self.events.append((name, "ok"))
            return data
        except Exception as ex:
            self.disabled.add(name)  # avoid repeatedly retrying a dead provider in one run
            self.events.append((name, type(ex).__name__))
            return None

    def fetch(self, event, captured):
        for name in self.order:
            try:
                rows = {}
                if name == "goaldir":
                    rows = self.bsd_fetch(event, captured)[0]
                    # BSD might return empty for this particular market
                elif name == "pinnwire":
                    key = os.getenv("PINNWIRE_API_KEY", "")
                    if not key: continue
                    data = self.get(name, "https://pinnwire.com/kit/v1/prematch/fixtures?sport_id=1",
                                    {"x-api-key":key})
                    for row in (data or {}).get("events", []):
                        if match_fixture(row, event):
                            rows = from_pinnwire(row, captured)
                            break
                elif name == "oddslink":
                    key = os.getenv("ODDSLINK_API_KEY", "")
                    if not key: continue
                    data = self.get(name, "https://oddslink.app/v1/sports/soccer/odds?oddsFormat=decimal",
                                    {"X-API-Key":key})
                    for row in data if isinstance(data,list) else []:
                        if match_fixture(row, event):
                            rows = from_oddslink(row, captured)
                            break
                elif name == "moviodds":
                    data = self.get(name, "https://moviodds.com/odds?sport=soccer")
                    for row in (data or {}).get("matches", []):
                        if row.get("in_play") is False and match_fixture(row, event):
                            rows = from_movi(row, captured)
                            break
                elif name == "oddsharvester":
                    path = os.getenv("ODDSHARVESTER_JSON", "")
                    if not path: continue
                    snapshot = Path(path)
                    if not snapshot.is_file(): continue
                    if "oddsharvester" not in self.cache:
                        self.cache["oddsharvester"] = json.loads(snapshot.read_text(encoding="utf-8"))
                    for row in self.cache["oddsharvester"]:
                        if match_fixture(row, event):
                            rows = from_harvester(row, captured)
                            break
                if rows:
                    self.events.append((name, "selected"))
                    return rows, {"provider":name, "fallback_events":self.events[-15:],
                                  "request_counts":dict(self.usage)}
            except Exception as ex:
                self.events.append((name, type(ex).__name__))
                if name == "goaldir" and ("429" in str(ex) or "quota" in str(ex).lower()):
                    self.disabled.add(name)
                continue
        return {}, {"provider":None, "fallback_events":self.events[-15:],
                    "request_counts":dict(self.usage)}
