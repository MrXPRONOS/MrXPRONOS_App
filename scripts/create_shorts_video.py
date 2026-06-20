#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mr XPRONOS - Create Shorts Video Generator

Objectif :
- Lire le data.json du programme principal Mr XPRONOS
- Sélectionner maximum 5 pronostics du jour
- Générer automatiquement une narration avec voix IA
- Créer une vidéo verticale 1080x1920 au design sombre/or

Utilisation :
    python scripts/create_shorts_video.py
    python scripts/create_shorts_video.py --data data.json --max 5
    python scripts/create_shorts_video.py --out daily_pronos_shorts.mp4

Notes :
- edge-tts nécessite internet.
- MoviePy nécessite FFmpeg.
- Pour une voix très humaine, mets voice_engine="elevenlabs" dans video_pronos_config.json
  puis définis $env:ELEVENLABS_API_KEY="TA_CLE_API" dans PowerShell.
"""

import argparse
import asyncio
import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# Dépendances chargées en lazy-import pour permettre --dry-run même avant installation complète.


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path.cwd()
# Racine du projet : utile quand le workflow lance `python scripts/create_shorts_video.py`
# depuis la racine du dépôt GitHub Actions.
BASE_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else ROOT_DIR

# Compatible avec GitHub Actions actuel :
# - le workflow lance : python scripts/create_shorts_video.py
# - l'artifact upload attendu peut rester : daily_pronos_shorts.mp4
DEFAULT_CONFIG_CANDIDATES = [
    ROOT_DIR / "video_pronos_config.json",
    SCRIPT_DIR / "video_pronos_config.json",
]
OUTPUT_DIR = Path(os.environ.get("VIDEO_WORK_DIR", str(ROOT_DIR / "telegram_out" / "video_work"))).resolve()
SCENES_DIR = OUTPUT_DIR / "scenes"
AUDIO_DIR = OUTPUT_DIR / "audio"
DEFAULT_OUT = Path(os.environ.get("VIDEO_OUT", str(ROOT_DIR / "daily_pronos_shorts.mp4"))).resolve()

EMBEDDED_CONFIG = {
    "brand_name": "Mr XPRONOS",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "background": "#0D0D0D",
    "card": "#1A1A1A",
    "card2": "#151515",
    "gold": "#D4AF37",
    "white": "#FFFFFF",
    "muted": "#AAAAAA",
    "danger": "#E53935",
    "green": "#22C55E",
    "font_regular": "",
    "font_bold": "",
    "voice_engine": os.environ.get("VOICE_ENGINE", "edge"),
    "voice": os.environ.get("TTS_VOICE", "fr-FR-RemyMultilingualNeural"),
    "voice_rate": os.environ.get("TTS_RATE", "-7%"),
    "voice_pitch": os.environ.get("TTS_PITCH", "-1Hz"),
    "voice_volume": os.environ.get("TTS_VOLUME", "+0%"),
    "humanize_tts": True,
    "tts_replacements": {
        "XPRONOS": "X pronos",
        "VIP": "V I P",
        "FCFA": "F C F A",
        "1X": "un X",
        "X2": "X deux",
        "Over": "au-dessus de",
        "Under": "en dessous de"
    },
    "elevenlabs_api_key_env": "ELEVENLABS_API_KEY",
    "elevenlabs_voice_id": os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
    "elevenlabs_model_id": "eleven_multilingual_v2",
    "elevenlabs_voice_settings": {
        "stability": 0.38,
        "similarity_boost": 0.82,
        "style": 0.35,
        "use_speaker_boost": True,
        "speed": 0.94
    },
    "max_pronos": 5,
    "watermark": "18+ • Divertissement seulement • Joue responsablement"
}


@dataclass
class Prono:
    index: int
    match_id: str
    date: str
    league: str
    home_team: str
    away_team: str
    home_logo: str
    away_logo: str
    prediction_text: str
    advantage_team: str
    winner_phrase: str
    confidence: int
    final_score: float
    category: str
    badge: str
    raw: Dict


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return default
    return json.loads(content)


def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = (value or "#000000").strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def find_font(size: int, bold: bool = False, custom_path: str = ""):
    candidates = []
    if custom_path:
        candidates.append(custom_path)

    if bold:
        candidates += [
            "C:/Windows/Fonts/Montserrat-Bold.ttf",
            "C:/Windows/Fonts/montserrat-bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates += [
            "C:/Windows/Fonts/Montserrat-Regular.ttf",
            "C:/Windows/Fonts/montserrat-regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for p in candidates:
        try:
            if p and Path(p).exists():
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def fit_text_lines(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    words = str(text or "").split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        box = draw.textbbox((0, 0), test, font=font)
        if (box[2] - box[0]) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_lines(draw, lines: List[str], font, x_center: int, y: int, fill, gap: int = 12):
    cur_y = y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        w = box[2] - box[0]
        h = box[3] - box[1]
        draw.text((x_center - w / 2, cur_y), line, font=font, fill=fill)
        cur_y += h + gap


def draw_rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_gradient_bg(w: int, h: int, bg_rgb, gold_rgb) -> Image.Image:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        factor = y / max(1, h - 1)
        base = np.array(bg_rgb, dtype=float)
        warm = np.array((22, 18, 9), dtype=float)
        color = base * (1 - factor * 0.55) + warm * (factor * 0.55)
        arr[y, :, :] = np.clip(color, 0, 255)
    img = Image.fromarray(arr)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-300, -220, 680, 700), fill=(*gold_rgb, 28))
    od.ellipse((620, 1120, 1460, 2120), fill=(*gold_rgb, 20))
    overlay = overlay.filter(ImageFilter.GaussianBlur(45))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def normalize_team_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip()) or "Équipe inconnue"


def prediction_to_text(pred: Dict) -> str:
    if not isinstance(pred, dict):
        return "Pronostic à vérifier"

    dc = pred.get("double_chance")
    over = pred.get("over_25")

    parts = []
    if dc in ("1X", "X2", "12"):
        parts.append(dc)
    if over is True:
        parts.append("Over 2.5")
    elif over is False:
        parts.append("Under 2.5")

    return " + ".join(parts) if parts else "Pronostic à vérifier"


def determine_advantage(match: Dict) -> Tuple[str, str]:
    """
    Retourne (team, phrase) sans promettre une victoire garantie.
    Le système principal produit souvent une double chance : 1X ou X2.
    Ici on transforme ça en phrase vocale : avantage home/away.
    """
    home = normalize_team_name(match.get("home_team"))
    away = normalize_team_name(match.get("away_team"))
    pred = match.get("prediction", {}) or {}
    dc = pred.get("double_chance")

    if dc == "1X":
        return home, f"avantage {home}, avec protection du nul"
    if dc == "X2":
        return away, f"avantage {away}, avec protection du nul"

    # Fallback si pas de double chance : on utilise la dominance H2H ou le score final.
    h2h = match.get("h2h_analysis", {}) or {}
    home_dom = float(h2h.get("home_dominance") or 0)
    away_dom = float(h2h.get("away_dominance") or 0)
    if home_dom > away_dom:
        return home, f"léger avantage {home}"
    if away_dom > home_dom:
        return away, f"léger avantage {away}"
    return "Match prudent", "match trop équilibré, prudence maximale"


def to_int_confidence(value) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def select_daily_pronos(data_path: Path, target_date: Optional[str], max_pronos: int) -> List[Prono]:
    data = load_json(data_path, {})
    matches = data.get("matches", [])
    if not isinstance(matches, list):
        raise ValueError("data.json invalide : la clé 'matches' doit être une liste.")

    if not target_date:
        target_date = datetime.now().date().isoformat()

    candidates = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        m_date = str(m.get("date") or "")[:10]
        if m_date != target_date:
            continue
        if not m.get("home_team") or not m.get("away_team"):
            continue
        # On évite les pronos indécis si possible.
        pred = m.get("prediction", {}) or {}
        if pred.get("double_chance") == "12":
            continue
        candidates.append(m)

    def score(m: Dict):
        pred = m.get("prediction", {}) or {}
        category_weight = {"vip": 300, "pro": 200, "simple": 100}.get(str(m.get("category", "simple")).lower(), 0)
        return (
            category_weight,
            float(m.get("final_score") or 0),
            float(m.get("xpronos_score") or 0),
            float(pred.get("confidence") or 0),
            str(m.get("event_date") or ""),
        )

    candidates = sorted(candidates, key=score, reverse=True)[:max_pronos]

    pronos: List[Prono] = []
    for idx, m in enumerate(candidates, start=1):
        pred = m.get("prediction", {}) or {}
        advantage_team, winner_phrase = determine_advantage(m)
        pronos.append(Prono(
            index=idx,
            match_id=str(m.get("id") or idx),
            date=str(m.get("date") or target_date),
            league=str(m.get("league") or m.get("competition") or "Football"),
            home_team=normalize_team_name(m.get("home_team")),
            away_team=normalize_team_name(m.get("away_team")),
            home_logo=str(m.get("home_logo") or ""),
            away_logo=str(m.get("away_logo") or ""),
            prediction_text=prediction_to_text(pred),
            advantage_team=advantage_team,
            winner_phrase=winner_phrase,
            confidence=to_int_confidence(pred.get("confidence") or m.get("final_score") or 0),
            final_score=float(m.get("final_score") or m.get("xpronos_score") or 0),
            category=str(m.get("category") or "simple").upper(),
            badge=str(m.get("badge") or ""),
            raw=m,
        ))
    return pronos


def build_scene_payloads(pronos: List[Prono], cfg: Dict, target_date: str) -> List[Dict]:
    """
    Mode direct : aucune intro, aucune outro.
    La vidéo commence par une phrase courte, puis enchaîne directement :
    "Voici les pronos du jour. Prono 1... Prono 2..."
    """
    if not pronos:
        return [{
            "kind": "empty",
            "title": "Aucun prono du jour",
            "subtitle": "Aucun match sélectionné pour cette date.",
            "narration": "Aucun prono du jour disponible pour le moment.",
        }]

    scenes = []
    for idx, p in enumerate(pronos, start=1):
        opening = "Voici les pronos du jour. " if idx == 1 else ""
        scenes.append({
            "kind": "prono",
            "title": f"PRONO {idx}",
            "subtitle": p.league,
            "prono": p,
            "narration": (
                f"{opening}"
                f"Prono {idx}. "
                f"{p.home_team} contre {p.away_team}. "
                f"{p.winner_phrase[:1].upper() + p.winner_phrase[1:]}. "
                f"Pronostic : {p.prediction_text}. "
                f"Confiance : environ {p.confidence} pour cent."
            ),
        })

    return scenes


def humanize_tts_text(text: str, cfg: Dict) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if cfg.get("humanize_tts", True):
        # Petites pauses par ponctuation. Edge TTS réagit bien à "...".
        t = re.sub(r"([.!?])\s+", r"\1 ... ", t)
        for key, value in (cfg.get("tts_replacements") or {}).items():
            t = t.replace(key, value)
    return t


async def generate_voice_edge(text: str, cfg: Dict, out_path: Path):
    try:
        import edge_tts
    except Exception as e:
        raise RuntimeError("edge-tts n'est pas installé. Lance : pip install -r requirements.txt") from e

    out_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(
        humanize_tts_text(text, cfg),
        voice=cfg.get("voice", "fr-FR-RemyMultilingualNeural"),
        rate=cfg.get("voice_rate", "-7%"),
        volume=cfg.get("voice_volume", "+0%"),
        pitch=cfg.get("voice_pitch", "-1Hz"),
    )
    await communicate.save(str(out_path))


def generate_voice_elevenlabs(text: str, cfg: Dict, out_path: Path):
    api_key = os.environ.get(cfg.get("elevenlabs_api_key_env", "ELEVENLABS_API_KEY"))
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY manquante. Mets la clé en variable d'environnement ou utilise voice_engine='edge'.")

    voice_id = cfg.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": humanize_tts_text(text, cfg),
        "model_id": cfg.get("elevenlabs_model_id", "eleven_multilingual_v2"),
        "voice_settings": cfg.get("elevenlabs_voice_settings", {}),
    }
    r = requests.post(url, headers=headers, json=payload, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"Erreur ElevenLabs {r.status_code}: {r.text[:300]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(r.content)


def generate_voice(text: str, cfg: Dict, out_path: Path):
    engine = str(cfg.get("voice_engine", "edge")).lower().strip()
    if engine == "elevenlabs":
        generate_voice_elevenlabs(text, cfg, out_path)
    else:
        asyncio.run(generate_voice_edge(text, cfg, out_path))


def resolve_asset_path(path_str: str, data_path: Path) -> Optional[Path]:
    if not path_str:
        return None
    p = Path(path_str.replace("\\", "/"))
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(data_path.parent / p)
        candidates.append(BASE_DIR / p)
        candidates.append(Path.cwd() / p)
    for c in candidates:
        if c.exists() and c.is_file() and c.stat().st_size > 100:
            return c
    return None


def load_logo_or_initials(path_str: str, team: str, data_path: Path, size: int, cfg: Dict) -> Image.Image:
    gold = hex_to_rgb(cfg.get("gold", "#D4AF37"))
    card = hex_to_rgb(cfg.get("card", "#1A1A1A"))
    white = hex_to_rgb(cfg.get("white", "#FFFFFF"))

    logo_path = resolve_asset_path(path_str, data_path)
    if logo_path:
        try:
            img = Image.open(logo_path).convert("RGBA")
            img = ImageOps.contain(img, (size, size))
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
            return canvas
        except Exception:
            pass

    # Fallback initials
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=card + (255,), outline=gold + (255,), width=4)
    initials = "".join([w[:1] for w in team.split()[:2]]).upper()[:2] or "FC"
    font = find_font(42, bold=True, custom_path=cfg.get("font_bold", ""))
    box = d.textbbox((0, 0), initials, font=font)
    d.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2 - 4), initials, font=font, fill=white + (255,))
    return img


def render_intro_or_outro(scene: Dict, cfg: Dict, out_path: Path):
    w = int(cfg.get("width", 1080))
    h = int(cfg.get("height", 1920))
    bg = hex_to_rgb(cfg.get("background", "#0D0D0D"))
    gold = hex_to_rgb(cfg.get("gold", "#D4AF37"))
    white = hex_to_rgb(cfg.get("white", "#FFFFFF"))
    muted = hex_to_rgb(cfg.get("muted", "#AAAAAA"))
    card = hex_to_rgb(cfg.get("card", "#1A1A1A"))

    img = make_gradient_bg(w, h, bg, gold).convert("RGBA")
    d = ImageDraw.Draw(img)

    font_brand = find_font(58, True, cfg.get("font_bold", ""))
    font_title = find_font(88, True, cfg.get("font_bold", ""))
    font_sub = find_font(40, False, cfg.get("font_regular", ""))
    font_small = find_font(26, False, cfg.get("font_regular", ""))

    d.text((70, 70), cfg.get("brand_name", "Mr XPRONOS"), font=font_brand, fill=gold)
    d.text((70, 142), "FOOT • PRONOS • HUMOUR NOIR", font=font_small, fill=muted)

    draw_rounded(d, (70, 470, w - 70, 1260), 44, fill=card + (230,), outline=gold + (255,), width=3)

    title_lines = fit_text_lines(scene.get("title", ""), font_title, w - 190, d)[:3]
    draw_centered_lines(d, title_lines, font_title, w // 2, 650, white, 18)

    sub_lines = fit_text_lines(scene.get("subtitle", ""), font_sub, w - 220, d)[:4]
    draw_centered_lines(d, sub_lines, font_sub, w // 2, 970, gold if scene.get("kind") == "intro" else white, 16)

    d.line((150, 1350, w - 150, 1350), fill=gold + (170,), width=3)
    note = "Ici, on n'enterre pas ton argent. On enterre les mauvais choix."
    note_lines = fit_text_lines(note, font_sub, w - 200, d)[:3]
    draw_centered_lines(d, note_lines, font_sub, w // 2, 1410, muted, 14)

    watermark = cfg.get("watermark", "18+ • Divertissement seulement • Joue responsablement")
    d.text((70, h - 90), watermark, font=font_small, fill=muted)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, quality=95)


def render_prono_scene(scene: Dict, cfg: Dict, data_path: Path, out_path: Path):
    p: Prono = scene["prono"]
    w = int(cfg.get("width", 1080))
    h = int(cfg.get("height", 1920))
    bg = hex_to_rgb(cfg.get("background", "#0D0D0D"))
    card = hex_to_rgb(cfg.get("card", "#1A1A1A"))
    card2 = hex_to_rgb(cfg.get("card2", "#151515"))
    gold = hex_to_rgb(cfg.get("gold", "#D4AF37"))
    white = hex_to_rgb(cfg.get("white", "#FFFFFF"))
    muted = hex_to_rgb(cfg.get("muted", "#AAAAAA"))
    danger = hex_to_rgb(cfg.get("danger", "#E53935"))
    green = hex_to_rgb(cfg.get("green", "#22C55E"))

    img = make_gradient_bg(w, h, bg, gold).convert("RGBA")
    d = ImageDraw.Draw(img)

    font_brand = find_font(50, True, cfg.get("font_bold", ""))
    font_title = find_font(48, True, cfg.get("font_bold", ""))
    font_team = find_font(52, True, cfg.get("font_bold", ""))
    font_vs = find_font(44, True, cfg.get("font_bold", ""))
    font_label = find_font(30, True, cfg.get("font_bold", ""))
    font_text = find_font(36, False, cfg.get("font_regular", ""))
    font_big = find_font(74, True, cfg.get("font_bold", ""))
    font_small = find_font(25, False, cfg.get("font_regular", ""))

    # Header
    d.text((65, 58), cfg.get("brand_name", "Mr XPRONOS"), font=font_brand, fill=gold)
    d.text((65, 122), scene.get("title", "PRONO"), font=font_small, fill=muted)

    # Category pill
    pill = p.category
    pb = d.textbbox((0, 0), pill, font=font_label)
    draw_rounded(d, (w - 70 - (pb[2] - pb[0]) - 46, 58, w - 70, 112), 24, fill=gold + (255,))
    d.text((w - 70 - (pb[2] - pb[0]) - 23, 68), pill, font=font_label, fill=(0, 0, 0))

    # Main card
    draw_rounded(d, (55, 235, w - 55, 1225), 42, fill=card + (238,), outline=gold + (255,), width=3)

    # League
    league_lines = fit_text_lines(p.league.upper(), font_label, w - 160, d)[:2]
    y = 285
    for line in league_lines:
        box = d.textbbox((0, 0), line, font=font_label)
        d.text(((w - (box[2] - box[0])) / 2, y), line, font=font_label, fill=muted)
        y += 36

    # Logos and teams
    logo_size = 190
    home_logo = load_logo_or_initials(p.home_logo, p.home_team, data_path, logo_size, cfg)
    away_logo = load_logo_or_initials(p.away_logo, p.away_team, data_path, logo_size, cfg)
    img.alpha_composite(home_logo, (175, 390))
    img.alpha_composite(away_logo, (w - 175 - logo_size, 390))

    d.text((w // 2 - 30, 455), "VS", font=font_vs, fill=gold)

    home_lines = fit_text_lines(p.home_team, font_team, 390, d)[:2]
    away_lines = fit_text_lines(p.away_team, font_team, 390, d)[:2]
    draw_centered_lines(d, home_lines, font_team, 270, 620, white, 8)
    draw_centered_lines(d, away_lines, font_team, w - 270, 620, white, 8)

    # Pronostic card
    draw_rounded(d, (105, 845, w - 105, 1145), 34, fill=card2 + (245,), outline=gold + (180,), width=2)
    d.text((140, 880), "PRONOSTIC", font=font_label, fill=muted)
    prono_lines = fit_text_lines(p.prediction_text, font_big, w - 300, d)[:2]
    draw_centered_lines(d, prono_lines, font_big, w // 2, 940, gold, 10)

    # Advantage and confidence blocks
    draw_rounded(d, (70, 1285, w - 70, 1535), 36, fill=card + (230,), outline=None)
    d.text((115, 1325), "AVANTAGE", font=font_label, fill=muted)
    adv_lines = fit_text_lines(p.advantage_team, font_team, w - 250, d)[:2]
    draw_centered_lines(d, adv_lines, font_team, w // 2, 1375, white, 10)

    # Confidence bar
    bar_x1, bar_y1, bar_x2, bar_y2 = 115, 1585, w - 115, 1645
    draw_rounded(d, (bar_x1, bar_y1, bar_x2, bar_y2), 30, fill=(45, 45, 45, 255))
    fill_w = int((bar_x2 - bar_x1) * (p.confidence / 100))
    bar_color = green if p.confidence >= 70 else gold if p.confidence >= 55 else danger
    draw_rounded(d, (bar_x1, bar_y1, bar_x1 + fill_w, bar_y2), 30, fill=bar_color + (255,))
    conf_text = f"Confiance : {p.confidence}%"
    cb = d.textbbox((0, 0), conf_text, font=font_label)
    d.text(((w - (cb[2] - cb[0])) / 2, 1662), conf_text, font=font_label, fill=white)

    # Note courte : pas d'intro/outro, on reste focalisé sur le prono.
    note = "Analyse rapide • 18+ • joue responsablement."
    note_lines = fit_text_lines(note, font_text, w - 150, d)[:2]
    draw_centered_lines(d, note_lines, font_text, w // 2, 1735, muted, 10)

    watermark = cfg.get("watermark", "18+ • Divertissement seulement • Joue responsablement")
    d.text((65, h - 80), watermark, font=font_small, fill=muted)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, quality=95)


def render_scene(scene: Dict, cfg: Dict, data_path: Path, out_path: Path):
    if scene.get("kind") == "prono":
        render_prono_scene(scene, cfg, data_path, out_path)
    else:
        render_intro_or_outro(scene, cfg, out_path)


def clip_set_duration(clip, duration: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def clip_set_audio(clip, audio):
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)


def build_video(scenes: List[Dict], cfg: Dict, data_path: Path, out_path: Path, dry_run: bool = False):
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
    except Exception:
        try:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
        except Exception as e:
            if not dry_run:
                raise RuntimeError("moviepy n'est pas installé. Lance : pip install -r requirements.txt") from e
            AudioFileClip = ImageClip = concatenate_videoclips = None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Sauvegarde utile pour vérifier/modifier le texte avant publication.
    narration_full = "\n\n".join([s.get("narration", "") for s in scenes])
    save_text(OUTPUT_DIR / "narration_pronos.txt", narration_full)

    if dry_run:
        print("\n=== NARRATION GÉNÉRÉE ===\n")
        print(narration_full)
        print("\nMode dry-run : aucune vidéo générée.")
        return

    video_clips = []
    for idx, scene in enumerate(scenes, start=1):
        scene_img = SCENES_DIR / f"scene_{idx:02d}.jpg"
        scene_audio = AUDIO_DIR / f"voice_{idx:02d}.mp3"

        print(f"🎨 Scène {idx}/{len(scenes)} : rendu image")
        render_scene(scene, cfg, data_path, scene_img)

        print(f"🎙️ Scène {idx}/{len(scenes)} : génération voix")
        generate_voice(scene.get("narration", ""), cfg, scene_audio)

        audio = AudioFileClip(str(scene_audio))
        duration = max(2.5, float(audio.duration) + 0.25)
        clip = ImageClip(str(scene_img))
        clip = clip_set_duration(clip, duration)
        clip = clip_set_audio(clip, audio)
        video_clips.append(clip)

    print("🎬 Assemblage vidéo...")
    final = concatenate_videoclips(video_clips, method="compose")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(out_path),
        fps=int(cfg.get("fps", 30)),
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
    )

    for clip in video_clips:
        try:
            clip.close()
        except Exception:
            pass
    try:
        final.close()
    except Exception:
        pass

    print(f"✅ Vidéo générée : {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Génère une vidéo avec maximum 5 pronos du jour depuis data.json")
    parser.add_argument("--data", default="data.json", help="Chemin vers data.json du programme principal")
    parser.add_argument("--config", default="", help="Chemin vers video_pronos_config.json (optionnel)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Fichier vidéo de sortie")
    parser.add_argument("--date", default="", help="Date à filtrer au format YYYY-MM-DD. Par défaut : aujourd'hui")
    parser.add_argument("--max", type=int, default=0, help="Nombre max de pronos. Par défaut : valeur config, max 5")
    parser.add_argument("--dry-run", action="store_true", help="Affiche seulement la narration générée")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    out_path = Path(args.out).resolve()

    cfg = dict(EMBEDDED_CONFIG)
    config_path = None
    if args.config.strip():
        config_path = Path(args.config).resolve()
    else:
        for candidate in DEFAULT_CONFIG_CANDIDATES:
            if candidate.exists():
                config_path = candidate.resolve()
                break
    if config_path and config_path.exists():
        cfg.update(load_json(config_path, {}))
    max_pronos = args.max or int(cfg.get("max_pronos", 5))
    max_pronos = max(1, min(5, max_pronos))
    target_date = args.date.strip() or datetime.now().date().isoformat()

    if not data_path.exists():
        raise FileNotFoundError(f"data.json introuvable : {data_path}")

    pronos = select_daily_pronos(data_path, target_date, max_pronos)
    print(f"📊 Pronos sélectionnés : {len(pronos)} / {max_pronos} pour {target_date}")
    for p in pronos:
        print(f" - {p.home_team} vs {p.away_team} | {p.prediction_text} | avantage {p.advantage_team} | conf {p.confidence}%")

    scenes = build_scene_payloads(pronos, cfg, target_date)
    build_video(scenes, cfg, data_path, out_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
