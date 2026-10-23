#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Settle exact production short-video batches and publish validation videos.

Only exact matches previously recorded by send_short_production_telegram.py are
validated. A result video is published when the batch has 0 or 1 loss, matching
the requested Mr XPRONOS rule. With 2+ losses, the batch is closed silently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bsd"))

from bsd.bsd_api import BSDClient
from bsd.bsd_v2_verify_telegram import _leg_verdict
from scripts.create_validation_shorts_from_telegram import (
    _snapshots,
    build_video,
    render_exact_validated_cards,
)

UTC = timezone.utc
KIND = "shorts_video_coupon"


def sb_headers(key: str):
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }


def canonical_ref(ref: str):
    text = str(ref or "")
    slot, sep, remainder = text.partition(":")
    if not sep or slot not in {"evening", "morning"}:
        return None, None
    ident = remainder
    if not ident.startswith("bsd:"):
        return None, None
    return slot, ident


def pending_rows(session, base, key):
    from scripts.neon_telegram_ledger import records
    since=(datetime.now(UTC).date()-timedelta(days=4)).isoformat()
    rows=records(KIND,since,limit=200)
    return [row for row in rows if row.get("validation_sent") is False]


def mark_rows(session, base, key, row_ids):
    from scripts.neon_telegram_ledger import mark_verified
    for row_id in row_ids:
        mark_verified(row_id,KIND,was_unverified=False)


def restore_matches(feed_path: Path, wanted_ids):
    wanted = set(wanted_ids)
    found = {}
    for snapshot in _snapshots(feed_path, max_commits=120):
        for match in snapshot.get("matches") or []:
            if not isinstance(match, dict):
                continue
            ident = str(match.get("id") or "")
            if ident in wanted and ident not in found:
                found[ident] = match
        if wanted.issubset(found):
            break
    return found


def official_events_for_day(day: str):
    target_day = date.fromisoformat(day)
    client = BSDClient(max_requests=120)
    page = client.list_events(target_day, target_day, max_pages=12, ttl=0)
    if not page.complete:
        raise RuntimeError("Résultats BSD incomplets pour " + day)
    events = {}
    for event in page.events:
        if isinstance(event, dict) and event.get("id") is not None:
            events[str(event["id"])] = event
    return events, client.requests_made


def send_video(session, token, chat, video: Path, target: str, slot: str, summary: str):
    label = "lot publié la veille" if slot == "evening" else "lot publié le matin"
    caption = (
        f"📊 Résultats Mr XPRONOS — {target}\n"
        f"{summary}\n"
        f"{label} · 18+ · Joue responsablement."
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "Voir les pronostics 🔥",
             "url": "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"}
        ]]
    }
    with video.open("rb") as fh:
        r = session.post(
            "https://api.telegram.org/bot" + token + "/sendVideo",
            data={
                "chat_id": chat,
                "caption": caption[:1024],
                "supports_streaming": "true",
                "reply_markup": json.dumps(keyboard, ensure_ascii=False),
            },
            files={"video": (video.name, fh, "video/mp4")},
            timeout=600,
        )
    r.raise_for_status()
    body = r.json()
    if body.get("ok") is not True:
        raise RuntimeError("Telegram a refusé la vidéo de validation")
    return (body.get("result") or {}).get("message_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", default="data.json")
    ap.add_argument("--work-dir", default="telegram_out/production_validation")
    ap.add_argument("--no-send", action="store_true")
    args = ap.parse_args()

    base = ""
    key = ""
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not os.getenv("NEON_DATABASE_URL"):
        raise RuntimeError("NEON_DATABASE_URL manquant")
    if not args.no_send and (not token or not chat):
        raise RuntimeError("Secrets Telegram production manquants")

    session = requests.Session()
    rows = pending_rows(session, base, key)
    groups = defaultdict(list)
    for row in rows:
        slot, ident = canonical_ref(row.get("ref_id"))
        if not slot or not ident:
            continue
        groups[(slot, str(row.get("ref_date") or ""))].append({**row, "match_id": ident})

    work_root = Path(args.work_dir)
    work_root.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "groups": [],
        "published": [],
        "pending_count": 0,
        "silent_closed": 0,
    }

    for (slot, target), group_rows in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
        wanted = [row["match_id"] for row in group_rows]
        definitions = restore_matches(Path(args.feed), wanted)
        missing = [ident for ident in wanted if ident not in definitions]
        if missing:
            report["groups"].append({
                "slot": slot, "target": target, "status": "missing_definition",
                "missing": missing,
            })
            continue

        events, api_calls = official_events_for_day(target)
        settled = []
        unresolved = []
        for ident in wanted:
            match = definitions[ident]
            raw_id = ident.removeprefix("bsd:")
            result = _leg_verdict(match, events.get(raw_id))
            if result is None:
                unresolved.append(ident)
                continue
            won, home, away = result
            settled.append((
                bool(won),
                {**match, "home_score": home, "away_score": away,
                 "status": "finished", "is_finished": True},
            ))

        if unresolved:
            report["pending_count"] += 1
            report["groups"].append({
                "slot": slot, "target": target, "status": "pending",
                "resolved": len(settled), "total": len(wanted),
                "unresolved": unresolved, "api_calls": api_calls,
            })
            continue

        winners = [match for won, match in settled if won]
        losses = sum(1 for won, _match in settled if not won)
        total = len(settled)
        row_ids = [row["id"] for row in group_rows]

        if losses > 1 or not winners:
            if not args.no_send:
                mark_rows(session, base, key, row_ids)
            report["silent_closed"] += 1
            report["groups"].append({
                "slot": slot, "target": target, "status": "closed_silent",
                "wins": len(winners), "losses": losses, "total": total,
                "reason": "more_than_one_loss_or_no_winner",
            })
            continue

        summary = (
            f"{total}/{total} VALIDÉS · AUCUN PERDU"
            if losses == 0
            else f"{len(winners)}/{total} VALIDÉS · 1 PERDU"
        )
        group_dir = work_root / f"{target}-{slot}"
        cards, pack = render_exact_validated_cards(winners, group_dir / "cards", datetime.now(UTC))
        video = work_root / f"validation-{target}-{slot}.mp4"
        build_video(
            cards, video, group_dir, summary,
            total_original=total, losses=losses,
        )

        message_id = None
        if not args.no_send:
            message_id = send_video(session, token, chat, video, target, slot, summary)
            mark_rows(session, base, key, row_ids)

        item = {
            "slot": slot, "target": target, "status": "published" if not args.no_send else "ready",
            "summary": summary, "wins": len(winners), "losses": losses,
            "total": total, "video": str(video), "bookmaker_pack": pack,
            "message_id": message_id, "row_ids": row_ids,
        }
        report["groups"].append(item)
        report["published"].append(item)
        print("SHORTS_VALIDATION_BATCH_READY", json.dumps(item, ensure_ascii=False))

    manifest = work_root / "manifest.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SHORTS_PRODUCTION_VALIDATION", json.dumps({
        "groups": len(report["groups"]),
        "published": len(report["published"]),
        "pending": report["pending_count"],
        "silent_closed": report["silent_closed"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
