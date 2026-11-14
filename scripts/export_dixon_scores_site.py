#!/usr/bin/env python3
"""Export verified Dixon-Coles social video predictions for the public score page.

Only public, prospective pre-match fields leave CI. An actual rendered MP4 and its
SHA256-bound prediction/storyboard/manifest must all match. No fallback/fake picks.
This script does not push; the CI step publishes this sanitized JSON to gh-pages.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SCHEMA = "mrx-dixon-coles-video-scores-v1"
LOGO_HOSTS = frozenset(("crests.football-data.org", "upload.wikimedia.org", "a.espncdn.com"))
SCORE = re.compile(r"^(?:[0-9]|10)[:\-](?:[0-9]|10)$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA = re.compile(r"^[a-f0-9]{64}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_logo(raw: object) -> bool:
    if not isinstance(raw, str) or not raw or len(raw) > 500:
        return False
    try:
        u = urlsplit(raw)
        return (u.scheme == "https" and u.hostname in LOGO_HOSTS
                and not u.username and not u.password
                and u.port in (None, 443) and not u.query and not u.fragment)
    except ValueError:
        return False


def timestamp(raw: object) -> datetime:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise ValueError("UTC timestamp required")
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("UTC date required")
    return value


def export(manifest: dict, predictions: dict, storyboard: dict, video: Path) -> dict:
    day = manifest.get("target")
    if not isinstance(day, str) or not DAY.fullmatch(day) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid video target date")
    mode = manifest.get("publication_mode")
    n = manifest.get("count")
    if (mode not in ("strict", "flexible") or type(n) is not int or not 1 <= n <= 10
            or (mode == "strict" and n != 10)
            or manifest.get("status") != "READY" or manifest.get("ready_for_video") is not True
            or not isinstance(manifest.get("sha256"), str)
            or not SHA.fullmatch(manifest["sha256"])
            or not video.is_file() or video.suffix != ".mp4"
            or not 100_000 <= video.stat().st_size <= 24 * 1024 * 1024
            or sha256(video) != manifest["sha256"]):
        raise ValueError("Video production proof not valid")
    for raw, field in ((predictions, "predictions_sha256"), (storyboard, "storyboard_sha256")):
        original = raw.get("_source_path")
        if not isinstance(original, str):
            raise ValueError("Source path proof missing")
        expected = manifest.get(field)
        if not isinstance(expected, str) or not SHA.fullmatch(expected) or sha256(Path(original)) != expected:
            raise ValueError("Storyboard/prediction digest mismatch")
    if (predictions.get("status") != "READY" or storyboard.get("status") != "READY"
            or predictions.get("ready_for_video") is not True
            or storyboard.get("ready_for_video") is not True
            or predictions.get("date_local_africa_lome") != day
            or storyboard.get("date_local_africa_lome") != day
            or predictions.get("selected_count") != n
            or storyboard.get("selected_count") != n
            or predictions.get("publication_mode") != mode
            or storyboard.get("publication_mode") != mode):
        raise ValueError("Mismatched video and prediction dates/selection")
    generated_raw = predictions.get("generated_at_utc")
    generated = timestamp(generated_raw)
    if generated.date() > date.fromisoformat(day):
        raise ValueError("Predictions generated after match day")
    rows = predictions.get("selected")
    clips = storyboard.get("clips")
    if not isinstance(rows, list) or not isinstance(clips, list) or len(rows) != n or len(clips) != n:
        raise ValueError("Match count differs from rendered video")
    ids = manifest.get("match_ids")
    if (not isinstance(ids, list) or len(ids) != n
            or ids != [str(m.get("id")) for m in rows]
            or ids != [str(c.get("match_id")) for c in clips]
            or any(not v or v == "None" for v in ids) or len(set(ids)) != n):
        raise ValueError("Match identities inconsistent")
    evidence = manifest.get("render_evidence") or {}
    if (evidence.get("real_logo_instances") != 2 * n
            or evidence.get("placeholder_logo_instances") != 0
            or evidence.get("resolution") != "1080x1920"):
        raise ValueError("Actual video rendering evidence missing")
    items = []
    for match, clip in zip(rows, clips):
        forecast = match.get("forecast") or {}
        score = forecast.get("most_likely_score")
        if not isinstance(score, str) or not SCORE.fullmatch(score):
            raise ValueError("Invalid score")
        normalized = score.replace("-", ":")
        if clip.get("display_score") != score:
            raise ValueError("Score differs from the rendered video")
        home, away = match.get("home"), match.get("away")
        league = match.get("competition_name") or "Football"
        if (not all(isinstance(v, str) and 1 <= len(v.strip()) <= 120 for v in (home, away))
                or not isinstance(league, str) or len(league) > 140
                or clip.get("headline") != f"{home} - {away}"):
            raise ValueError("Club identity mismatch")
        kickoff_raw = match.get("kickoff_utc")
        kickoff = timestamp(kickoff_raw)
        if (kickoff.date() != date.fromisoformat(day) or kickoff <= generated
                or kickoff_raw != clip.get("kickoff_utc")):
            raise ValueError("Not a prospective prediction")
        home_logo = match.get("home_logo_url")
        away_logo = match.get("away_logo_url")
        if (not valid_logo(home_logo) or not valid_logo(away_logo)
                or home_logo != clip.get("home_logo_url")
                or away_logo != clip.get("away_logo_url")):
            raise ValueError("Unverified crest / mismatch")
        p = forecast.get("most_likely_probability")
        if type(p) not in (float, int) or not 0 < p <= 1:
            raise ValueError("Probability invalid")
        items.append({
            "id": str(match["id"]), "league": league.strip(),
            "home": home.strip(), "away": away.strip(),
            "home_logo": home_logo, "away_logo": away_logo,
            "kickoff_utc": kickoff_raw, "score": normalized,
            "probability": round(float(p), 6)
        })
    return {
        "schema_version": SCHEMA, "model": "dixon_coles_video",
        "origin": "verified_social_video_render",
        "status": "published", "date": day,
        "generated_at": generated_raw, "video_sha256": manifest["sha256"],
        "count": n, "matches": items
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--storyboard", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    preds = json.loads(args.predictions.read_text(encoding="utf-8"))
    story = json.loads(args.storyboard.read_text(encoding="utf-8"))
    preds["_source_path"] = str(args.predictions)
    story["_source_path"] = str(args.storyboard)
    public = export(manifest, preds, story, args.video)
    if args.out.name != public["date"] + ".json":
        raise ValueError("Output filename must match match day")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(public, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("DIXON_PUBLIC_SCORES_VERIFIED", public["date"], public["count"], public["video_sha256"][:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
