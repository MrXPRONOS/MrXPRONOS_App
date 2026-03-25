#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Générateur de contenu IA Mr XPRONOS (SEO)
- 1 article match du jour (allscores, scoring popularité)
- 1 article evergreen (anti répétition + anti similarité)
- Images 1200x630 : Pixazo (fallback) / (Mistral image via SDK non obligatoire)
- Texte Mistral via HTTP (PAS de dépendance mistralai)
"""

import os
import json
import re
import uuid
import time
import random
import hashlib
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any, Tuple

import requests
from PIL import Image, ImageOps

UTC = timezone.utc
today = datetime.now(UTC).date()

BASE_SITE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/"
CODE_PROMO = "XPVIP"

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"

ASSET_IMG_DIR = "assets/images"
ARTICLE_IMG_DIR = os.path.join(ASSET_IMG_DIR, "articles")
os.makedirs(ARTICLE_IMG_DIR, exist_ok=True)

# ====== KEYS ======
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
PIXAZO_API_KEY = os.environ.get("PIXAZO_API_KEY")
SPORTDATA_API_KEY = os.environ.get("SPORTDATA_API_KEY")  # ✅ 1 seule clé ici

# ====== SportData V1 allscores ======
SPORTDATA_V1_ALLSCORES = "https://v1.football.sportsapipro.com/games/allscores"

POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
]

# ===== Evergreen topics =====
TOPICS_FILE = "evergreen_topics.json"

def load_topics():
    d = load_json(TOPICS_FILE, {})
    return d.get("topics", []) if isinstance(d, dict) else []

SIMILARITY_JACCARD_THRESHOLD = 0.62
SIMILARITY_SEQ_THRESHOLD = 0.86
MAX_EVERGREEN_RETRIES = 2

TARGET_W, TARGET_H = 1200, 630


# =======================================================
# Utils
# =======================================================

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            c = f.read().strip()
            return json.loads(c) if c else default
    except Exception:
        return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or f"post-{uuid.uuid4().hex[:6]}"

def excerpt_from_text(text: str, length=160) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()
    return (t[:length] + "...") if len(t) > length else t

def reading_time_minutes(text: str) -> int:
    words = len(re.findall(r"\w+", text or ""))
    return max(1, round(words / 200))

def content_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

def tokenize(text: str) -> set:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return set(tokens)

def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0

def is_similar(a: str, b: str) -> bool:
    ta = tokenize(a)
    tb = tokenize(b)
    if jaccard(ta, tb) >= SIMILARITY_JACCARD_THRESHOLD:
        return True
    seq = SequenceMatcher(None, (a or "")[:1200], (b or "")[:1200]).ratio()
    return seq >= SIMILARITY_SEQ_THRESHOLD

def load_existing_articles() -> list:
    d = load_json(ARTICLES_FILE, [])
    return d if isinstance(d, list) else []

def save_articles(articles: list):
    save_json(ARTICLES_FILE, articles[:80])

def get_bookmakers_from_data() -> list:
    d = load_json(DATA_FILE, {})
    b = d.get("bookmakers", [])
    if isinstance(b, list) and b:
        return b
    return [
        {"name": "1xBet", "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "url": "https://bwredir.com/299Y"},
    ]

def pick_bookmaker() -> dict:
    books = get_bookmakers_from_data()
    return random.choice(books) if books else {"name": "1xBet", "url": BASE_SITE_URL}


# =======================================================
# Mistral HTTP (texte) - sans SDK
# =======================================================

def call_mistral_text_http(prompt: str, temperature=0.7, max_tokens=2400, retries=2) -> Optional[str]:
    if not MISTRAL_API_KEY:
        return None

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=45)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"⚠️ Mistral HTTP tentative {attempt+1}/{retries+1} échouée: {e}")
            if attempt == retries:
                return None
            time.sleep(1)

    return None

def call_mistral_json(prompt: str, retries=2) -> Optional[dict]:
    txt = call_mistral_text_http(prompt, temperature=0.55, max_tokens=2600, retries=retries)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{[\s\S]*\}\s*$", txt.strip())
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


# =======================================================
# Pixazo image 1200x630 (fallback)
# =======================================================

def generate_image_pixazo(prompt: str) -> Optional[str]:
    if not PIXAZO_API_KEY:
        return None

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Ocp-Apim-Subscription-Key": PIXAZO_API_KEY
    }
    payload = {
        "prompt": prompt,
        "negative_prompt": "Low-quality, blurry, distorted, ugly, watermark, text, logo, cartoon",
        "height": TARGET_H,
        "width": TARGET_W,
        "num_steps": 22,
        "guidance_scale": 7,
        "seed": random.randint(1, 1000000)
    }

    try:
        resp = requests.post(
            "https://gateway.pixazo.ai/getImage/v1/getSDXLImage",
            json=payload, headers=headers, timeout=80
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data.get("imageUrl")
        if not image_url:
            return None

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        filename = os.path.join(ARTICLE_IMG_DIR, f"img-{uuid.uuid4().hex[:10]}.png")
        with open(filename, "wb") as f:
            f.write(img_resp.content)

        return ensure_1200x630(filename)
    except Exception as e:
        print(f"❌ Pixazo image error: {e}")
        return None

def ensure_1200x630(path: str) -> Optional[str]:
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)

        target_ratio = TARGET_W / TARGET_H
        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif current_ratio < target_ratio:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)

        out = os.path.splitext(path)[0] + "-1200x630.png"
        img.save(out, "PNG", optimize=True)
        return out
    except Exception as e:
        print(f"⚠️ Image resize error: {e}")
        return path


# =======================================================
# SportData allscores : match du jour par popularité
# =======================================================

def fetch_allscores_today() -> Optional[dict]:
    if not SPORTDATA_API_KEY:
        return None

    params = {
        "startDate": today.strftime("%d/%m/%Y"),
        "endDate": today.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }

    try:
        r = requests.get(
            SPORTDATA_V1_ALLSCORES,
            params=params,
            headers={"x-api-key": SPORTDATA_API_KEY},
            timeout=30
        )
        if r.status_code != 200:
            print(f"⚠️ allscores HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        print(f"⚠️ allscores error: {e}")
        return None

def build_popularity_maps(payload: dict) -> Tuple[dict, dict]:
    comp_pop = {}
    team_pop = {}
    comps = payload.get("competitions", [])
    if isinstance(comps, list):
        for c in comps:
            cid = c.get("id")
            if cid is None:
                continue
            comp_pop[str(cid)] = {
                "popularityRank": c.get("popularityRank", 0) or 0,
                "name": c.get("name", "")
            }

    teams = payload.get("competitors", [])
    if isinstance(teams, list):
        for t in teams:
            tid = t.get("id")
            if tid is None:
                continue
            team_pop[str(tid)] = {
                "popularityRank": t.get("popularityRank", 0) or 0,
                "name": t.get("name", "")
            }

    return comp_pop, team_pop

def score_game(game: dict, comp_pop: dict, team_pop: dict) -> float:
    comp_id = str(game.get("competitionId") or "")
    home = game.get("homeCompetitor") or {}
    away = game.get("awayCompetitor") or {}
    hid = str(home.get("id") or "")
    aid = str(away.get("id") or "")

    comp_rank = (comp_pop.get(comp_id, {}) or {}).get("popularityRank", 0) or 0
    home_rank = (team_pop.get(hid, {}) or {}).get("popularityRank", 0) or 0
    away_rank = (team_pop.get(aid, {}) or {}).get("popularityRank", 0) or 0

    comp_name = (game.get("competitionDisplayName") or "")
    boost = 0
    if any(l.lower() in comp_name.lower() for l in POPULAR_LEAGUES):
        boost = 50_000_000

    return float(comp_rank * 2 + home_rank + away_rank + boost)

def pick_best_match_today() -> Optional[dict]:
    payload = fetch_allscores_today()
    if not payload:
        return None

    games = payload.get("games", [])
    if not isinstance(games, list) or not games:
        return None

    comp_pop, team_pop = build_popularity_maps(payload)

    best = None
    best_score = -1.0
    for g in games:
        s = score_game(g, comp_pop, team_pop)
        if s > best_score:
            best_score = s
            best = g

    if not best:
        return None

    home = best.get("homeCompetitor") or {}
    away = best.get("awayCompetitor") or {}
    return {
        "id": str(best.get("id")),
        "home_team": home.get("name", "Équipe A"),
        "away_team": away.get("name", "Équipe B"),
        "league": best.get("competitionDisplayName", "Championnat"),
        "event_date": best.get("startTime") or "",
    }


# =======================================================
# Prompts
# =======================================================

def internal_links_section(bookmaker: dict) -> str:
    bm_name = bookmaker.get("name", "Bookmaker")
    bm_url = bookmaker.get("url", BASE_SITE_URL)

    return f"""
## Liens utiles
- Pronostics du jour : {BASE_SITE_URL}pronos.html
- Bonus & promotions : {BASE_SITE_URL}bonus.html
- Accès LIVE VIP : {BASE_SITE_URL}live.html

## Bonus recommandé
Teste **{bm_name}** avec le code promo **{CODE_PROMO}** :
{bm_url}
""".strip()

def prompt_match_article(match: dict, bookmaker: dict) -> str:
    ht, at = match["home_team"], match["away_team"]
    league = match.get("league", "Championnat")
    dt = match.get("event_date", "")
    links = internal_links_section(bookmaker)

    return f"""
Génère un JSON STRICT (sans texte autour) avec les clés :
- title (string)
- slug (string)
- meta_description (string <= 160)
- keywords (array 6 à 10 strings)
- faq (array 3 objets {{q,a}})
- content_markdown (string) 800-1200 mots

Sujet : Pronostic {ht} vs {at} ({league}) - {dt}

Contraintes :
- Style professionnel, moderne, sans promesse "garanti".
- H2/H3, analyse, forme, H2H, joueurs à suivre.
- Section "Conseil de pari Mr XPRONOS" (double chance prudente).
- Gestion bankroll (exemples FCFA).
- Section "Bonus & bookmakers" mentionnant {CODE_PROMO}.
- Ajoute à la fin : {links}

Réponds UNIQUEMENT en JSON valide.
""".strip()

def prompt_evergreen(topic: dict, bookmaker: dict, constraints: str) -> str:
    links = internal_links_section(bookmaker)
    return f"""
Génère un JSON STRICT avec :
- title (string) unique
- slug (string)
- meta_description (string <=160)
- keywords (array 6-12)
- faq (array 3 objets {{q,a}})
- content_markdown (string) 900-1400 mots evergreen

Thème :
- topic_id: {topic["id"]}
- titre: {topic["title_template"]}

Contraintes :
- Ajouter au moins 1 tableau Markdown.
- Exemples en FCFA.
- Mentionne bonus et choix bookmaker intelligemment (sans exagération).
- Ajoute à la fin : {links}

Anti-similarité :
{constraints}

Réponds UNIQUEMENT en JSON valide.
""".strip()


# =======================================================
# Build / Save
# =======================================================

def build_article_object(js: dict, image_url: str, extra: dict) -> dict:
    title = (js.get("title") or "Article").strip()
    slug = js.get("slug") or slugify(title)
    content = js.get("content_markdown") or ""
    meta_desc = (js.get("meta_description") or "")[:160].strip()
    keywords = js.get("keywords") or []
    faq = js.get("faq") or []

    excerpt = excerpt_from_text(content, 170)
    rt = reading_time_minutes(content)

    return {
        "slug": slug,
        "title": title,
        "date": datetime.utcnow().isoformat() + "Z",
        "author": "Mr XPRONOS",
        "reading_time": rt,
        "excerpt": excerpt,
        "meta_description": meta_desc or excerpt[:160],
        "keywords": ", ".join([str(k) for k in keywords]) if isinstance(keywords, list) else str(keywords),
        "faq": faq if isinstance(faq, list) else [],
        "content": content,
        "image_url": image_url,
        "og_image": image_url,
        "active": True,
        "content_hash": content_hash(content[:2000]),
        **extra
    }

def is_duplicate(new_slug: str, new_title: str, new_content: str, existing: list) -> bool:
    new_slug = (new_slug or "").strip()
    new_title = (new_title or "").strip().lower()
    new_h = content_hash((new_content or "")[:2000])

    for a in existing:
        if not isinstance(a, dict):
            continue
        if new_slug and a.get("slug") == new_slug:
            return True
        if new_title and (a.get("title") or "").strip().lower() == new_title:
            return True
        if a.get("content_hash") == new_h:
            return True
        if a.get("title") and is_similar(new_title, (a["title"] or "").lower()):
            return True
    return False

def pick_unused_topic(existing: list) -> dict:
    used = {a.get("topic_id") for a in existing if isinstance(a, dict) and a.get("type") == "evergreen"}
    candidates = [t for t in EVERGREEN_TOPICS if t["id"] not in used]
    return random.choice(candidates) if candidates else random.choice(EVERGREEN_TOPICS)

def build_constraints(existing: list) -> str:
    snippets = []
    for a in existing:
        if isinstance(a, dict) and a.get("type") == "evergreen":
            c = re.sub(r"\s+", " ", (a.get("content") or ""))
            snippets.append(c[:220])
    if not snippets:
        return "- Aucun."
    return "\n".join([f"- Ne pas reproduire ce style: «{s}...»" for s in snippets[:6]])


# =======================================================
# MAIN
# =======================================================

def main():
    print("=" * 60)
    print("🚀 GÉNÉRATION CONTENU IA (Match du jour + Evergreen, SEO + images 1200x630)")
    print("=" * 60)

    if not MISTRAL_API_KEY:
        print("❌ MISTRAL_API_KEY manquante -> impossible de générer le texte.")
        return

    existing = load_existing_articles()
    bookmaker = pick_bookmaker()

    # 1) Match du jour (allscores)
    match = pick_best_match_today()
    if not match:
        print("⚠️ Impossible de récupérer un match via allscores. Pas d'article match aujourd'hui.")
    else:
        print(f"⚽ Match du jour: {match['home_team']} vs {match['away_team']} ({match.get('league','')})")
        js = call_mistral_json(prompt_match_article(match, bookmaker))
        if not js:
            print("❌ Échec génération JSON match.")
        else:
            js["slug"] = js.get("slug") or slugify(js.get("title", "pronostic"))
            body = js.get("content_markdown", "") or ""
            if is_duplicate(js["slug"], js.get("title",""), body, existing):
                print("⚠️ Article match doublon -> ignoré.")
            else:
                img = generate_image_pixazo(
                    f"Football match poster, realistic, dynamic stadium atmosphere, "
                    f"{match['home_team']} vs {match['away_team']}, {match.get('league','League')}, "
                    f"no text, no watermark, cinematic lighting, high quality, 1200x630"
                )
                if not img:
                    print("❌ Image match impossible -> article match ignoré.")
                else:
                    art = build_article_object(js, img, {
                        "type": "match",
                        "match": f"{match['home_team']} vs {match['away_team']}",
                        "league": match.get("league",""),
                    })
                    existing.insert(0, art)
                    save_articles(existing)
                    print(f"✅ Article match sauvegardé: {art['title']} (slug={art['slug']})")

    # 2) Evergreen anti répétition / similarité
    topic = pick_unused_topic(existing)
    constraints = build_constraints(existing)

    recent_ev = [(a.get("content") or "")[:4000] for a in existing if isinstance(a, dict) and a.get("type") == "evergreen"][:10]

    for attempt in range(MAX_EVERGREEN_RETRIES + 1):
        print(f"🧠 Evergreen: topic={topic['id']} tentative {attempt+1}/{MAX_EVERGREEN_RETRIES+1}")
        js = call_mistral_json(prompt_evergreen(topic, bookmaker, constraints))
        if not js:
            print("❌ Échec génération JSON evergreen.")
            break

        js["slug"] = js.get("slug") or slugify(js.get("title", f"evergreen-{topic['id']}"))
        body = js.get("content_markdown", "") or ""

        too_similar = any(is_similar(body, t) for t in recent_ev)
        if too_similar:
            print("⚠️ Evergreen trop similaire -> régénération.")
            constraints += "\n- Change complètement la structure et le tableau."
            continue

        if is_duplicate(js["slug"], js.get("title",""), body, existing):
            print("⚠️ Evergreen doublon -> régénération.")
            continue

        img = generate_image_pixazo(
            "Sports betting strategy illustration, modern premium style, realistic, "
            "football themed, dark and gold color palette, no text, no watermark, 1200x630"
        )
        if not img:
            print("❌ Image evergreen impossible -> evergreen ignoré.")
            break

        art = build_article_object(js, img, {"type": "evergreen", "topic_id": topic["id"]})
        existing.insert(0, art)
        save_articles(existing)
        print(f"✅ Evergreen sauvegardé: {art['title']} (topic={topic['id']})")
        break

    print("✅ Génération terminée.")


if __name__ == "__main__":
    main()