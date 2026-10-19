#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a daily vertical football-news video for Mr XPRONOS.

MVP pipeline:
- fetch reputable football RSS feeds
- normalize + deduplicate headlines
- rank stories with deterministic heuristics
- select 2-3 strong stories
- synthesize French narration with edge-tts (silent fallback)
- render 1080x1920 MP4 with Mr XPRONOS branding
- write a manifest for audit/debugging

No article image is downloaded in this MVP. This intentionally avoids building
an automated copyright-sensitive image scraper before the editorial format has
been validated.
"""
from __future__ import annotations

import argparse
import asyncio
import email.utils
import html
import json
import math
import re
import subprocess
import sys
import textwrap
import wave
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
FPS = 30
UTC = timezone.utc

SOURCES = [
    ("BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml", 15),
    ("Sky Sports Football", "https://www.skysports.com/rss/12040", 13),
    ("ESPN Soccer", "https://www.espn.com/espn/rss/soccer/news", 12),
]

BIG_ENTITIES = [
    "real madrid", "barcelona", "manchester united", "manchester city",
    "liverpool", "arsenal", "chelsea", "bayern", "psg", "paris saint-germain",
    "inter", "milan", "juventus", "napoli", "mbappe", "mbappé", "haaland",
    "vinicius", "vinícius", "yamal", "messi", "ronaldo", "salah",
    "champions league", "premier league", "la liga", "serie a",
]

HIGH_IMPACT = [
    "official", "confirmed", "signs", "signed", "transfer", "sack", "sacked",
    "injury", "injured", "suspended", "ban", "banned", "final", "winner",
    "wins", "record", "breaks record", "resigns", "appointed", "coach",
    "manager", "deal", "agrees", "retire", "retires", "return",
]

VIRAL = [
    "shock", "stunning", "dramatic", "controversy", "controversial",
    "red card", "derby", "clasico", "clásico", "record", "historic",
    "late winner", "comeback", "hat-trick", "hat trick",
]


@dataclass
class Story:
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    score: int = 0
    score_reasons: list[str] | None = None


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_date(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.now(UTC)
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def fetch_feed(name: str, url: str, trust: int, timeout: int = 20) -> list[Story]:
    headers = {"User-Agent": "MrXPRONOS-NewsBot/1.0 (+daily football video)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out: list[Story] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title = strip_html(item.findtext("title") or "")
        link = strip_html(item.findtext("link") or "")
        desc = strip_html(item.findtext("description") or "")
        pub = item.findtext("pubDate") or item.findtext("date") or ""
        if title and link:
            out.append(Story(
                title=title,
                summary=desc,
                source=name,
                url=link,
                published_at=parse_date(pub).isoformat(),
                score_reasons=[f"source:{trust}"],
            ))

    # Atom fallback
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns):
        title = strip_html(entry.findtext("a:title", default="", namespaces=ns))
        summary = strip_html(entry.findtext("a:summary", default="", namespaces=ns))
        updated = entry.findtext("a:updated", default="", namespaces=ns)
        link = ""
        link_el = entry.find("a:link", ns)
        if link_el is not None:
            link = str(link_el.attrib.get("href") or "")
        if title and link:
            out.append(Story(
                title=title,
                summary=summary,
                source=name,
                url=link,
                published_at=parse_date(updated).isoformat(),
                score_reasons=[f"source:{trust}"],
            ))
    return out


def tokenize(title: str) -> set[str]:
    words = re.findall(r"[a-zà-ÿ0-9]+", title.lower())
    stop = {
        "the","a","an","of","to","and","in","on","for","with","as","at","is",
        "le","la","les","de","des","du","un","une","et","en","pour","sur","au",
    }
    return {w for w in words if len(w) >= 3 and w not in stop}


def similarity(a: Story, b: Story) -> float:
    aa, bb = tokenize(a.title), tokenize(b.title)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def dedupe(stories: Iterable[Story]) -> list[Story]:
    ordered = sorted(stories, key=lambda s: s.published_at, reverse=True)
    kept: list[Story] = []
    for story in ordered:
        if any(similarity(story, old) >= 0.48 for old in kept):
            continue
        kept.append(story)
    return kept


def rank_story(story: Story, now: datetime) -> Story:
    text = (story.title + " " + story.summary).lower()
    trust = 10
    for src, _url, src_trust in SOURCES:
        if story.source == src:
            trust = src_trust
            break

    published = datetime.fromisoformat(story.published_at)
    age_h = max(0.0, (now - published).total_seconds() / 3600.0)
    if age_h <= 3:
        freshness = 20
    elif age_h <= 8:
        freshness = 17
    elif age_h <= 16:
        freshness = 13
    elif age_h <= 24:
        freshness = 9
    elif age_h <= 36:
        freshness = 5
    else:
        freshness = 1

    impact_hits = sum(1 for k in HIGH_IMPACT if k in text)
    impact = min(25, 7 + impact_hits * 5)

    entity_hits = sum(1 for k in BIG_ENTITIES if k in text)
    audience = min(20, 5 + entity_hits * 4)

    viral_hits = sum(1 for k in VIRAL if k in text)
    viral = min(15, 3 + viral_hits * 4)

    score = min(100, trust + freshness + impact + audience + viral)
    reasons = [
        f"trust={trust}", f"freshness={freshness}",
        f"impact={impact}", f"audience={audience}", f"viral={viral}",
    ]
    story.score = int(score)
    story.score_reasons = reasons
    return story


def clean_summary(story: Story) -> str:
    value = strip_html(story.summary)
    if not value:
        value = story.title
    # Remove common source suffixes / boilerplate.
    value = re.sub(r"\s+-\s+BBC Sport$", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > 250:
        value = value[:247].rsplit(" ", 1)[0] + "..."
    return value


def choose_stories(stories: list[Story], now: datetime, max_items: int, min_score: int) -> list[Story]:
    ranked = [rank_story(s, now) for s in dedupe(stories)]
    ranked.sort(key=lambda s: (s.score, s.published_at), reverse=True)
    strong = [s for s in ranked if s.score >= min_score]
    # Test/MVP guarantee: if live sources worked but threshold is too strict,
    # fill from the best real stories rather than inventing fake news.
    if len(strong) < min(2, max_items):
        strong = ranked[:max_items]
    return strong[:max_items]


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_gradient() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    top = (5, 26, 47)
    bottom = (2, 8, 17)
    for y in range(H):
        p = y / max(1, H - 1)
        row = tuple(int(top[i] * (1 - p) + bottom[i] * p) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def add_brand(canvas: Image.Image, label: str):
    draw = ImageDraw.Draw(canvas, "RGBA")
    logo_path = ROOT / "assets/images/mrxpronos-logo-maquette.png"
    if logo_path.is_file():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((185, 68), Image.Resampling.LANCZOS)
            canvas.paste(logo, (62, 54), logo)
        except Exception:
            draw.text((62, 66), "MR XPRONOS", font=_font(32, True), fill=(255,255,255,255))
    else:
        draw.text((62, 66), "MR XPRONOS", font=_font(32, True), fill=(255,255,255,255))

    f = _font(26, True)
    bbox = draw.textbbox((0,0), label, font=f)
    x2 = 1018
    x1 = x2 - (bbox[2]-bbox[0]) - 34
    draw.rounded_rectangle((x1, 52, x2, 112), radius=18, fill=(10,68,116,220))
    draw.text((x1+17, 68), label, font=f, fill=(255,255,255,255))


def save_intro(path: Path, count: int, now: datetime):
    img = draw_gradient()
    draw = ImageDraw.Draw(img, "RGBA")
    add_brand(img, "ACTU FOOT")
    draw.text((74, 430), "L’ACTU", font=_font(112, True), fill=(248,251,255,255))
    draw.text((74, 548), "FOOT", font=_font(160, True), fill=(53,167,255,255))
    draw.rounded_rectangle((74, 780, 1000, 915), radius=34, fill=(255,255,255,18), outline=(255,255,255,40), width=2)
    sub = f"LES {count} INFOS À RETENIR AUJOURD’HUI"
    draw.text((112, 820), sub, font=_font(38, True), fill=(240,247,255,255))
    date_text = now.strftime("%d.%m.%Y")
    draw.text((76, 1710), date_text, font=_font(30, False), fill=(162,190,215,255))
    draw.text((76, 1760), "Actualités sélectionnées automatiquement • sources affichées", font=_font(23, False), fill=(120,151,178,255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def save_story_card(path: Path, story: Story, index: int, total: int):
    img = draw_gradient()
    draw = ImageDraw.Draw(img, "RGBA")
    add_brand(img, "ACTU FOOT")

    # giant editorial number
    num = f"{index:02d}"
    draw.text((62, 190), num, font=_font(190, True), fill=(24,67,103,150))

    # source badge
    source = story.source.upper()
    sf = _font(24, True)
    sb = draw.textbbox((0,0), source, font=sf)
    draw.rounded_rectangle((70, 390, 100+sb[2], 442), radius=16, fill=(53,167,255,220))
    draw.text((85, 404), source, font=sf, fill=(255,255,255,255))

    title_font = _font(63, True)
    title_lines = wrap(draw, story.title.upper(), title_font, 920)[:5]
    y = 500
    for line in title_lines:
        draw.text((72, y), line, font=title_font, fill=(248,251,255,255))
        y += 78

    y = max(y + 54, 910)
    draw.rounded_rectangle((70, y-26, 1010, y+380), radius=30, fill=(255,255,255,15), outline=(255,255,255,30), width=2)
    summary_font = _font(33, False)
    summary_lines = wrap(draw, clean_summary(story), summary_font, 860)[:7]
    yy = y + 22
    for line in summary_lines:
        draw.text((110, yy), line, font=summary_font, fill=(210,225,238,255))
        yy += 51

    # score bar and provenance
    draw.text((74, 1538), f"SCORE ACTU  {story.score}/100", font=_font(26, True), fill=(123,197,255,255))
    draw.rounded_rectangle((74, 1588, 925, 1602), radius=7, fill=(255,255,255,35))
    fill = 74 + int((925-74) * story.score / 100)
    draw.rounded_rectangle((74, 1588, fill, 1602), radius=7, fill=(53,167,255,240))

    host = urlparse(story.url).netloc.replace("www.","")
    draw.text((74, 1660), f"Source : {story.source}  •  {host}", font=_font(23, False), fill=(142,171,196,255))
    draw.text((74, 1710), f"{index}/{total}", font=_font(30, True), fill=(247,250,255,255))
    draw.text((840, 1710), "@mr_xpronos", font=_font(26, True), fill=(247,250,255,255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def save_outro(path: Path):
    img = draw_gradient()
    draw = ImageDraw.Draw(img, "RGBA")
    add_brand(img, "ACTU FOOT")
    draw.text((74, 600), "TU VEUX", font=_font(76, True), fill=(245,250,255,255))
    draw.text((74, 700), "L’ESSENTIEL", font=_font(92, True), fill=(53,167,255,255))
    draw.text((74, 810), "DU FOOT ?", font=_font(92, True), fill=(245,250,255,255))
    draw.text((78, 1035), "Suis @mr_xpronos", font=_font(46, True), fill=(245,250,255,255))
    draw.text((78, 1110), "Actualités • Pronostics • Résultats", font=_font(28, False), fill=(155,184,209,255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


async def edge_tts_save(text: str, path: Path, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+6%")
    await communicate.save(str(path))


def make_silence(path: Path, seconds: float):
    sr = 44100
    n = int(sr * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n)


def tts_or_silence(text: str, mp3_path: Path, wav_fallback: Path, voice: str) -> Path:
    try:
        asyncio.run(edge_tts_save(text, mp3_path, voice))
        if mp3_path.is_file() and mp3_path.stat().st_size > 1000:
            return mp3_path
    except Exception as exc:
        print("TTS_FALLBACK", type(exc).__name__, str(exc)[:160])
    words = max(1, len(text.split()))
    duration = max(2.6, min(11.0, words / 2.5))
    make_silence(wav_fallback, duration)
    return wav_fallback


def narration_for(story: Story, index: int) -> str:
    summary = clean_summary(story)
    intro = ["Première info.", "Deuxième info.", "Troisième info."][min(index-1,2)]
    return f"{intro} {story.title}. {summary}"


def render_video(stories: list[Story], output: Path, work: Path, voice: str):
    # MoviePy 1.x
    from moviepy.editor import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips

    now = datetime.now(UTC)
    intro_png = work / "intro.png"
    outro_png = work / "outro.png"
    save_intro(intro_png, len(stories), now)
    save_outro(outro_png)

    clips = []

    intro_text = f"Voici les {len(stories)} infos foot à retenir aujourd'hui."
    intro_audio = tts_or_silence(intro_text, work/"intro.mp3", work/"intro.wav", voice)
    ia = AudioFileClip(str(intro_audio))
    intro_d = max(2.6, ia.duration + 0.15)
    clips.append(ImageClip(str(intro_png)).set_duration(intro_d).set_audio(ia))

    for idx, story in enumerate(stories, 1):
        png = work / f"story_{idx:02d}.png"
        save_story_card(png, story, idx, len(stories))
        text = narration_for(story, idx)
        audio_path = tts_or_silence(text, work/f"story_{idx:02d}.mp3", work/f"story_{idx:02d}.wav", voice)
        audio = AudioFileClip(str(audio_path))
        duration = max(6.0, min(13.0, audio.duration + 0.35))
        clips.append(ImageClip(str(png)).set_duration(duration).set_audio(audio))

    outro_text = "Abonne-toi à Mr XPRONOS pour suivre l'essentiel du foot chaque jour."
    outro_audio = tts_or_silence(outro_text, work/"outro.mp3", work/"outro.wav", voice)
    oa = AudioFileClip(str(outro_audio))
    outro_d = max(3.0, oa.duration + 0.15)
    clips.append(ImageClip(str(outro_png)).set_duration(outro_d).set_audio(oa))

    final = concatenate_videoclips(clips, method="compose")
    output.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="4500k",
        threads=4,
        ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"],
        verbose=False,
        logger="bar",
    )
    try:
        final.close()
        for clip in clips:
            clip.close()
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="football_news_test.mp4")
    ap.add_argument("--work-dir", default="telegram_out/football_news_test")
    ap.add_argument("--max", type=int, default=3)
    ap.add_argument("--hours", type=float, default=36.0)
    ap.add_argument("--min-score", type=int, default=55)
    ap.add_argument("--voice", default="fr-FR-HenriNeural")
    args = ap.parse_args()

    now = datetime.now(UTC)
    stories: list[Story] = []
    source_report = []
    for name, url, trust in SOURCES:
        try:
            rows = fetch_feed(name, url, trust)
            source_report.append({"source": name, "ok": True, "count": len(rows)})
            stories.extend(rows)
        except Exception as exc:
            source_report.append({"source": name, "ok": False, "error": str(exc)[:220]})
            print("SOURCE_ERROR", name, type(exc).__name__, str(exc)[:220])

    cutoff = now.timestamp() - args.hours * 3600
    recent = []
    for story in stories:
        try:
            if datetime.fromisoformat(story.published_at).timestamp() >= cutoff:
                recent.append(story)
        except Exception:
            pass

    selected = choose_stories(recent, now, max(2, min(3, args.max)), args.min_score)
    if len(selected) < 2:
        raise SystemExit("Pas assez d'actualités réelles récentes pour générer une vidéo fiable.")

    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": now.isoformat(),
        "sources": source_report,
        "candidate_count": len(recent),
        "selected_count": len(selected),
        "selection": [asdict(s) for s in selected],
        "editorial_rule": {
            "max_items": 3,
            "target_min_score": args.min_score,
            "dedupe_similarity": 0.48,
            "images": "none_in_mvp",
        },
    }
    (work/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FOOTBALL_NEWS_SELECTION", json.dumps({
        "candidate_count": len(recent),
        "selected": [
            {"title": s.title, "source": s.source, "score": s.score}
            for s in selected
        ],
    }, ensure_ascii=False))

    render_video(selected, Path(args.out), work, args.voice)
    print("FOOTBALL_NEWS_VIDEO_READY", json.dumps({
        "video": args.out,
        "selected_count": len(selected),
        "manifest": str(work/"manifest.json"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
