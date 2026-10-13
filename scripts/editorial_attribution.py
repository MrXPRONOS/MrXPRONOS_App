#!/usr/bin/env python3
"""Agrégats de vrais événements Supabase; aucune donnée individuelle publiée.

Mesure des atterrissages sociaux ET du clic sur le code promo; ni taux
d'inscription, ni gains, ni comparaison expérimentale causale.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/data/editorial_performance.json"
KINDS = frozenset(("article", "conseil"))
SOURCES = frozenset(("telegram", "facebook", "instagram", "threads", "whatsapp", "youtube", "tiktok"))
VARIANTS = frozenset(("v1", "v2", "v3", "legacy"))
EVENTS = frozenset(("editorial_view", "editorial_promo_copy"))
AB_EVENTS = frozenset(("editorial_ab_exposure", "editorial_ab_click"))
SAFE_SLUG = re.compile(r"^[A-Za-z0-9_-]{2,180}$")


def parse_event(event):
    if not isinstance(event, dict) or event.get("event_type") not in EVENTS | AB_EVENTS:
        return None
    parts = str(event.get("page") or "").split("|")
    if len(parts) != 4:
        return None
    kind, slug, source, variant = parts
    if kind not in KINDS or not SAFE_SLUG.fullmatch(slug):
        return None
    if event["event_type"] in AB_EVENTS:
        if source != "onsite" or variant not in ("a","b"):return None
    elif source not in SOURCES or variant not in VARIANTS:
        return None
    return kind, slug, source, variant, event["event_type"]


def summarize(events, *, now=None, lookback_days=30):
    now = now or datetime.now(timezone.utc)
    groups = defaultdict(lambda: {"attributed_visits": 0, "promo_copy_actions": 0})
    per_content = defaultdict(lambda: {"attributed_visits": 0, "promo_copy_actions": 0})
    ab_records = defaultdict(lambda: {"impressions":0,"opens":0})
    rejected = 0
    for event in events:
        parsed = parse_event(event)
        if not parsed:
            rejected += 1
            continue
        kind, slug, source, variant, name = parsed
        if name in AB_EVENTS:
            metric = "impressions" if name=="editorial_ab_exposure" else "opens"
            ab_records[(kind,slug,variant)][metric] += 1
        else:
            metric = "attributed_visits" if name == "editorial_view" else "promo_copy_actions"
            groups[(source, variant)][metric] += 1
            per_content[(kind, slug, source, variant)][metric] += 1

    by_source_variant = []
    for (source, variant), counts in sorted(groups.items()):
        views = counts["attributed_visits"]
        actions = counts["promo_copy_actions"]
        by_source_variant.append({
            "source": source, "variant": variant, **counts,
            "promo_copy_per_visit": round(actions / views, 4) if views else None,
            "note": "Non randomisé; ce taux n'est pas un taux d'inscription."
        })
    content_rows = []
    for (kind, slug, source, variant), counts in sorted(per_content.items()):
        if counts["attributed_visits"] or counts["promo_copy_actions"]:
            content_rows.append({"kind": kind, "slug": slug, "source": source, "variant": variant, **counts})
    ab_tests = []
    designs=sorted({(kind,slug) for kind,slug,_ in ab_records})
    for kind,slug in designs:
        a=ab_records.get((kind,slug,"a"),{"impressions":0,"opens":0})
        b=ab_records.get((kind,slug,"b"),{"impressions":0,"opens":0})
        for variant,counts in (("a",a),("b",b)):
            impressions=counts["impressions"]
            ab_tests.append({"kind":kind,"slug":slug,"variant":variant,
              **counts,
              "open_rate":round(counts["opens"]/impressions,4) if impressions else None,
              "status":"insufficient_data" if impressions<30 else "descriptive_only"})
    total_visits = sum(c["attributed_visits"] for c in groups.values())
    total_actions = sum(c["promo_copy_actions"] for c in groups.values())
    return {
        "period_days": lookback_days,
        "generated_at": now.isoformat(),
        "data_origin": "Supabase analytics events; anonymous attributed page reads",
        "attributed_visits": total_visits,
        "promo_copy_actions": total_actions,
        "promo_copy_per_visit": round(total_actions / total_visits, 4) if total_visits else None,
        "unique_visitors": None,
        "registrations": None,
        "deposits": None,
        "ab_significance": None,
        "ab_limitation": "Assignation aléatoire par session aux listes Blog/Conseils ; événements d’impressions et clics, pas visiteurs uniques. Significativité non calculée ; aucune causalité affirmée.",
        "ab_tests": ab_tests,
        "groups": by_source_variant,
        "content": content_rows,
        "invalid_events_skipped": rejected,
    }


def fetch_events(session=requests, max_rows=4000, lookback_days=30):
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc.endswith(".supabase.co") or not key:
        return None
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    endpoint = url + "/rest/v1/analytics"
    headers = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    collected = []
    for offset in range(0, max_rows, 500):
        params = {
            "select": "event_type,page,created_at",
            "event_type": "in.(editorial_view,editorial_promo_copy,editorial_ab_exposure,editorial_ab_click)",
            "created_at": "gte." + since.isoformat(),
            "order": "id.desc",
            "limit": 500,
            "offset": offset,
        }
        result = session.get(endpoint, headers=headers, params=params, timeout=(8, 25))
        result.raise_for_status()
        rows = result.json()
        if not isinstance(rows, list):
            raise ValueError("Format de réponse Supabase non valide")
        collected.extend(rows)
        if len(rows) < 500:
            break
    return collected


def export(root=ROOT, session=requests, *, lookback_days=30):
    events = fetch_events(session=session, lookback_days=lookback_days)
    if events is None:
        print("EDITORIAL_ATTRIBUTION_NOT_CONFIGURED: nothing written")
        return None
    output = summarize(events, lookback_days=lookback_days)
    dest = root / "assets/data/editorial_performance.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    # L'horodatage change à chaque collecte: ne réécrire que si métriques changent.
    if dest.is_file():
        try:
            previous = json.loads(dest.read_text(encoding="utf-8"))
            previous.pop("generated_at", None)
            comparable = dict(output)
            comparable.pop("generated_at", None)
            if comparable == previous:
                print("EDITORIAL_ATTRIBUTION_UNCHANGED",len(events))
                return output
        except (OSError, ValueError):
            pass
    dest.write_text(serialized, encoding="utf-8")
    print("EDITORIAL_ATTRIBUTION_OK", output["attributed_visits"], output["promo_copy_actions"])
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=30)
    args = parser.parse_args()
    export(lookback_days=min(max(args.lookback_days, 1), 90))
