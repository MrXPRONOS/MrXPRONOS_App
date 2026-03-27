#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Mr XPRONOS
Version finale robuste avec parsing texte structuré (plus fiable que JSON strict)

Fonctionnalités :
- 1 article match du jour
- 1 article evergreen
- 3 conseils
- Match du jour : data.json en priorité, fallback allscores via api_utils
- Texte : Mistral SDK -> fallback HTTP
- Images : HF -> Mistral SDK image -> Pixazo
- Format final 1200x630
- Parsing robuste des métadonnées :
    SLUG:
    META_DESCRIPTION:
    MOTS_CLES:
    FAQ_JSON:
"""

import os
import re
import json
import time
import uuid
import random
import hashlib
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Tuple

import requests
from PIL import Image, ImageOps

try:
    from api_utils import make_request
except Exception:
    make_request = None

# =======================================================
# CONFIG
# =======================================================

UTC = timezone.utc
TODAY = datetime.now(UTC).date()

BASE_SITE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/"
CODE_PROMO = "XPVIP"

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"
CONSEILS_FILE = "conseils.json"
TOPICS_FILE = "evergreen_topics.json"

ASSET_IMG_DIR = "assets/images"
ARTICLE_IMG_DIR = os.path.join(ASSET_IMG_DIR, "articles")
CONSEIL_IMG_DIR = os.path.join(ASSET_IMG_DIR, "conseils")
os.makedirs(ARTICLE_IMG_DIR, exist_ok=True)
os.makedirs(CONSEIL_IMG_DIR, exist_ok=True)

SPORTDATA_V1_ALLSCORES = "https://v1.football.sportsapipro.com/games/allscores"

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_MODEL = os.environ.get("HF_MODEL", "SG161222/RealVisXL_V4.0")
PIXAZO_API_KEY = os.environ.get("PIXAZO_API_KEY")

GEN_W, GEN_H = 1024, 576
OUT_W, OUT_H = 1200, 630

SIMILARITY_JACCARD_THRESHOLD = 0.62
SIMILARITY_SEQ_THRESHOLD = 0.86
MAX_EVERGREEN_RETRIES = 2
MAX_ARTICLES_KEEP = 80
MAX_CONSEILS_KEEP = 120

POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
]

CONSEIL_TOPICS = [
    "gestion de bankroll en FCFA",
    "comment éviter le tilt",
    "comment analyser un match rapidement",
    "double chance : quand l’utiliser",
    "comment choisir un bookmaker fiable",
    "comment utiliser un bonus sans se piéger",
    "les erreurs fréquentes sur les combinés",
    "comment lire les cotes sans se tromper",
    "les pièges des favoris à petite cote",
    "comment parier en live avec discipline"
]

# =======================================================
# MISTRAL SDK INIT
# =======================================================

mistral_client = None
image_agent_id = None

def init_mistral_sdk():
    global mistral_client, image_agent_id
    if not MISTRAL_API_KEY:
        return False
    try:
        from mistralai import Mistral
        mistral_client = Mistral(api_key=MISTRAL_API_KEY)

        try:
            agent = mistral_client.beta.agents.create(
                model="mistral-medium-2505",
                name="Image Agent",
                description="Generate images",
                instructions="Use image generation tool when asked to create images.",
                tools=[{"type": "image_generation"}],
                completion_args={"temperature": 0.3, "top_p": 0.95}
            )
            image_agent_id = agent.id
        except Exception:
            image_agent_id = None

        print("✅ Mistral SDK initialisé")
        return True
    except Exception as e:
        print(f"⚠️ Mistral SDK indisponible : {e}")
        mistral_client = None
        image_agent_id = None
        return False


# =======================================================
# UTILS
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
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or f"post-{uuid.uuid4().hex[:6]}"

def content_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

def reading_time_minutes(text: str) -> int:
    words = len(re.findall(r"\w+", text or ""))
    return max(1, round(words / 200))

def excerpt_from_text(text: str, length=170) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    return (clean[:length] + "...") if len(clean) > length else clean

def tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))

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
    seq = SequenceMatcher(None, (a or "")[:1500], (b or "")[:1500]).ratio()
    return seq >= SIMILARITY_SEQ_THRESHOLD

def normalize_keywords(kw) -> List[str]:
    if isinstance(kw, list):
        return [str(x).strip() for x in kw if str(x).strip()]
    if isinstance(kw, str):
        return [x.strip() for x in kw.split(",") if x.strip()]
    return []

def normalize_faq(faq) -> List[dict]:
    if not isinstance(faq, list):
        return []
    out = []
    for x in faq:
        if not isinstance(x, dict):
            continue
        q = x.get("q") or x.get("question")
        a = x.get("a") or x.get("answer")
        if q and a:
            out.append({"q": str(q).strip(), "a": str(a).strip()})
    return out[:5]

def safe_print_excerpt(text: str, max_len=900):
    if not text:
        return
    print(text[:max_len] + ("..." if len(text) > max_len else ""))

def load_existing_articles() -> list:
    d = load_json(ARTICLES_FILE, [])
    return d if isinstance(d, list) else []

def save_articles(articles: list):
    save_json(ARTICLES_FILE, articles[:MAX_ARTICLES_KEEP])

def load_existing_conseils() -> list:
    d = load_json(CONSEILS_FILE, [])
    return d if isinstance(d, list) else []

def save_conseils(conseils: list):
    save_json(CONSEILS_FILE, conseils[:MAX_CONSEILS_KEEP])

def is_duplicate_article(new_slug: str, new_title: str, new_body: str, existing: list) -> bool:
    new_slug = (new_slug or "").strip()
    new_title = (new_title or "").strip().lower()
    new_h = content_hash((new_body or "")[:2500])

    for a in existing:
        if not isinstance(a, dict):
            continue
        if new_slug and (a.get("slug") or "").strip() == new_slug:
            return True
        if new_title and (a.get("title") or "").strip().lower() == new_title:
            return True
        if a.get("content_hash") == new_h:
            return True
        if a.get("title") and new_title and is_similar(new_title, (a.get("title") or "").lower()):
            return True
    return False

def is_duplicate_conseil(new_title: str, new_body: str, existing: list) -> bool:
    new_title = (new_title or "").strip().lower()
    new_h = content_hash((new_body or "")[:2000])

    for c in existing:
        if not isinstance(c, dict):
            continue
        if new_title and (c.get("title") or "").strip().lower() == new_title:
            return True
        if c.get("content_hash") == new_h:
            return True
    return False


# =======================================================
# BOOKMAKERS
# =======================================================

def get_bookmakers_from_data() -> list:
    d = load_json(DATA_FILE, {})
    b = d.get("bookmakers", [])
    if isinstance(b, list) and b:
        out = []
        for x in b:
            if not isinstance(x, dict):
                continue
            out.append({
                "name": x.get("name") or "Bookmaker",
                "url": x.get("url") or BASE_SITE_URL,
                "logo": x.get("logo")
            })
        return out
    return [
        {"name": "1xBet", "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "url": "https://bwredir.com/299Y"},
    ]

def pick_bookmaker() -> dict:
    books = get_bookmakers_from_data()
    return random.choice(books) if books else {"name": "1xBet", "url": BASE_SITE_URL}


# =======================================================
# MATCH DU JOUR
# =======================================================

def pick_match_from_data_json() -> Optional[dict]:
    d = load_json(DATA_FILE, {})
    matches = d.get("matches", [])
    if not isinstance(matches, list) or not matches:
        return None

    today_str = TODAY.isoformat()
    candidates = [m for m in matches if str(m.get("date", "")) == today_str]
    if not candidates:
        return None

    def score(m):
        cat_bonus = 50 if m.get("category") == "vip" else 20 if m.get("category") == "pro" else 0
        return float(m.get("final_score", 0) or 0) + float(m.get("xpronos_score", 0) or 0) + cat_bonus

    best = sorted(candidates, key=score, reverse=True)[0]
    return {
        "id": str(best.get("id") or ""),
        "home_team": best.get("home_team", "Équipe A"),
        "away_team": best.get("away_team", "Équipe B"),
        "league": best.get("league", "Championnat"),
        "event_date": best.get("event_date", ""),
    }

def fetch_allscores_today() -> Optional[dict]:
    if make_request is None:
        return None

    params = {
        "startDate": TODAY.strftime("%d/%m/%Y"),
        "endDate": TODAY.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false",
    }

    try:
        resp = make_request("GET", SPORTDATA_V1_ALLSCORES, params=params, timeout=30)
        if resp is None:
            return None
        return resp.json()
    except Exception:
        return None

def build_popularity_maps(payload: dict) -> Tuple[dict, dict]:
    comp_pop, team_pop = {}, {}

    comps = payload.get("competitions", [])
    if isinstance(comps, list):
        for c in comps:
            cid = c.get("id")
            if cid is None:
                continue
            comp_pop[str(cid)] = c.get("popularityRank", 0) or 0

    teams = payload.get("competitors", [])
    if isinstance(teams, list):
        for t in teams:
            tid = t.get("id")
            if tid is None:
                continue
            team_pop[str(tid)] = t.get("popularityRank", 0) or 0

    return comp_pop, team_pop

def score_game_by_popularity(game: dict, comp_pop: dict, team_pop: dict) -> float:
    comp_id = str(game.get("competitionId") or "")
    home = game.get("homeCompetitor") or {}
    away = game.get("awayCompetitor") or {}
    hid = str(home.get("id") or "")
    aid = str(away.get("id") or "")

    comp_rank = comp_pop.get(comp_id, 0) or 0
    home_rank = team_pop.get(hid, 0) or 0
    away_rank = team_pop.get(aid, 0) or 0

    comp_name = game.get("competitionDisplayName", "") or ""
    boost = 0
    if any(l.lower() in comp_name.lower() for l in POPULAR_LEAGUES):
        boost = 50_000_000

    return float(comp_rank * 2 + home_rank + away_rank + boost)

def pick_best_match_today() -> Optional[dict]:
    by_data = pick_match_from_data_json()
    if by_data:
        print("✅ Match du jour sélectionné depuis data.json")
        return by_data

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
        s = score_game_by_popularity(g, comp_pop, team_pop)
        if s > best_score:
            best_score = s
            best = g

    if not best:
        return None

    home = best.get("homeCompetitor") or {}
    away = best.get("awayCompetitor") or {}

    return {
        "id": str(best.get("id") or ""),
        "home_team": home.get("name", "Équipe A"),
        "away_team": away.get("name", "Équipe B"),
        "league": best.get("competitionDisplayName", "Championnat"),
        "event_date": best.get("startTime") or "",
    }


# =======================================================
# MISTRAL TEXTE
# =======================================================

def call_mistral_text_sdk(prompt: str, temperature=0.6, max_tokens=2800) -> Optional[str]:
    if not mistral_client:
        return None
    try:
        resp = mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content
    except Exception:
        return None

def call_mistral_text_http(prompt: str, temperature=0.6, max_tokens=2800, retries=2) -> Optional[str]:
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
            r = requests.post(url, headers=headers, json=payload, timeout=50)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            if attempt == retries:
                return None
            time.sleep(1)
    return None

def call_mistral_text(prompt: str, label: str = "mistral") -> Optional[str]:
    txt = call_mistral_text_sdk(prompt)
    if txt:
        return txt

    txt = call_mistral_text_http(prompt)
    if txt:
        return txt

    print(f"⚠️ {label}: aucune réponse Mistral")
    return None


# =======================================================
# PARSING TEXTE STRUCTURÉ
# =======================================================

def extract_line_value(text: str, key: str) -> Optional[str]:
    pattern = rf"^{re.escape(key)}\s*:\s*(.+)$"
    m = re.search(pattern, text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None

def extract_faq_json(text: str) -> List[dict]:
    value = extract_line_value(text, "FAQ_JSON")
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return normalize_faq(parsed)
    except Exception:
        return []

def remove_meta_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*(SLUG|META_DESCRIPTION|MOTS_CLES|FAQ_JSON)\s*:", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()

def parse_structured_text(content: str) -> dict:
    if not content:
        return {
            "title": "Article",
            "slug": "",
            "meta_description": "",
            "keywords": [],
            "faq": [],
            "content_markdown": ""
        }

    clean_content = content.strip()

    lines = [line.strip() for line in clean_content.splitlines() if line.strip()]
    title = "Article"
    if lines:
        title = lines[0].lstrip("#").strip() or "Article"

    slug = extract_line_value(clean_content, "SLUG") or slugify(title)
    meta_desc = extract_line_value(clean_content, "META_DESCRIPTION") or ""
    mots_cles = extract_line_value(clean_content, "MOTS_CLES") or ""
    keywords = normalize_keywords(mots_cles)
    faq = extract_faq_json(clean_content)
    content_markdown = remove_meta_lines(clean_content)

    return {
        "title": title,
        "slug": slug,
        "meta_description": meta_desc,
        "keywords": keywords,
        "faq": faq,
        "content_markdown": content_markdown
    }


# =======================================================
# IMAGES
# =======================================================

def ensure_1200x630(path: str) -> Optional[str]:
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)

        target_ratio = OUT_W / OUT_H
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

        img = img.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)

        out = os.path.splitext(path)[0] + "-1200x630.png"
        img.save(out, "PNG", optimize=True)
        return out
    except Exception:
        return path

def generate_image_hf(prompt: str, negative_prompt: str = "", retries: int = 3, folder: str = ARTICLE_IMG_DIR) -> Optional[str]:
    if not HF_TOKEN:
        return None

    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": negative_prompt,
            "width": GEN_W,
            "height": GEN_H,
            "num_inference_steps": 28,
            "guidance_scale": 6.5
        }
    }

    for attempt in range(retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180)

            if r.status_code == 503:
                try:
                    data = r.json()
                    wait = int(data.get("estimated_time", 10))
                except Exception:
                    wait = 10
                time.sleep(min(wait + 2, 25))
                continue

            if r.status_code != 200:
                return None

            if r.headers.get("content-type", "").startswith("application/json"):
                return None

            path = os.path.join(folder, f"hf-{uuid.uuid4().hex[:10]}.png")
            with open(path, "wb") as f:
                f.write(r.content)
            return ensure_1200x630(path)
        except Exception:
            time.sleep(2)

    return None

def generate_image_mistral_sdk(prompt: str, folder: str) -> Optional[str]:
    if not mistral_client or not image_agent_id:
        return None
    try:
        response = mistral_client.beta.conversations.start(
            agent_id=image_agent_id,
            inputs=prompt
        )
        for output in response.outputs:
            if output.type == "message.output":
                for chunk in output.content:
                    if chunk.type == "tool_file" and chunk.tool == "image_generation":
                        file_bytes = mistral_client.files.download(file_id=chunk.file_id).read()
                        path = os.path.join(folder, f"mistral-{uuid.uuid4().hex[:10]}.png")
                        with open(path, "wb") as f:
                            f.write(file_bytes)
                        return ensure_1200x630(path)
    except Exception:
        return None
    return None

def generate_image_pixazo(prompt: str, folder: str) -> Optional[str]:
    if not PIXAZO_API_KEY:
        return None

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Ocp-Apim-Subscription-Key": PIXAZO_API_KEY
    }

    payload = {
        "prompt": prompt,
        "negative_prompt": "text, watermark, logo, ugly, blurry, bad anatomy, extra limbs, cartoon",
        "height": GEN_H,
        "width": GEN_W,
        "num_steps": 22,
        "guidance_scale": 7,
        "seed": random.randint(1, 1000000)
    }

    try:
        resp = requests.post(
            "https://gateway.pixazo.ai/getImage/v1/getSDXLImage",
            json=payload,
            headers=headers,
            timeout=80
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data.get("imageUrl")
        if not image_url:
            return None

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        path = os.path.join(folder, f"pixazo-{uuid.uuid4().hex[:10]}.png")
        with open(path, "wb") as f:
            f.write(img_resp.content)
        return ensure_1200x630(path)
    except Exception:
        return None

def generate_image_with_fallback(prompt: str, folder: str) -> Optional[str]:
    NEG = (
        "text, watermark, logo, signature, ugly, deformed, extra limbs, extra fingers, "
        "bad anatomy, lowres, blurry, cartoon, illustration, 3d render, CGI, oversaturated"
    )

    p = generate_image_hf(prompt, negative_prompt=NEG, retries=3, folder=folder)
    if p:
        return p

    p = generate_image_mistral_sdk(prompt, folder)
    if p:
        return p

    p = generate_image_pixazo(prompt, folder)
    if p:
        return p

    return None


# =======================================================
# TOPICS EVERGREEN
# =======================================================

def load_topics() -> List[dict]:
    payload = load_json(TOPICS_FILE, {})
    if isinstance(payload, dict) and isinstance(payload.get("topics"), list) and payload["topics"]:
        return payload["topics"]
    return [
        {"id": "bankroll-fcfa", "family": "bankroll", "title_template": "Gestion de bankroll en FCFA : méthode simple + exemples", "angle": "discipline + plan"},
        {"id": "bonus-xpvip", "family": "bonus", "title_template": "Bonus + XPVIP : comment utiliser un bonus sans se piéger", "angle": "wagering + prudence"},
    ]

def pick_unused_topic(existing_articles: list, topics: list) -> dict:
    used = set()
    for a in existing_articles:
        if isinstance(a, dict) and a.get("type") == "evergreen" and a.get("topic_id"):
            used.add(a["topic_id"])
    candidates = [t for t in topics if t.get("id") and t["id"] not in used]
    return random.choice(candidates) if candidates else random.choice(topics)

def build_antisim_constraints(existing_articles: list, limit=6) -> str:
    snippets = []
    for a in existing_articles:
        if isinstance(a, dict) and a.get("type") == "evergreen":
            c = re.sub(r"\s+", " ", (a.get("content") or ""))
            snippets.append(c[:220])
    if not snippets:
        return "- Aucun."
    return "\n".join([f"- Ne pas reproduire la formulation: «{s}...»" for s in snippets[:limit]])


# =======================================================
# PROMPTS TEXTE STRUCTURÉ
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

> Les paris comportent des risques. Joue responsablement.
""".strip()

def prompt_match_article(match: dict, bookmaker: dict) -> str:
    ht = match.get("home_team", "Équipe A")
    at = match.get("away_team", "Équipe B")
    league = match.get("league", "Championnat")
    dt = match.get("event_date", "")
    links = internal_links_section(bookmaker)

    return f"""
Tu es journaliste sportif expert pour Mr XPRONOS.

Rédige un article complet en français sur :
Match : {ht} vs {at}
Compétition : {league}
Date : {dt}

Contraintes rédactionnelles :
- Article en Markdown
- Longueur : 850 à 1250 mots
- Style professionnel, moderne, engageant
- Pas de promesse "garanti"
- Inclure :
  1. Un H1 très attractif
  2. Introduction
  3. Analyse des forces en présence
  4. Statistiques utiles
  5. H2H (avec prudence sur ses limites)
  6. Joueurs / dynamiques à suivre
  7. Section "Conseil de pari Mr XPRONOS"
  8. Section "Cotes & value"
  9. Section "Bonus & Bookmakers"
  10. Conclusion
- Ajouter à la fin du contenu :
SLUG: ...
META_DESCRIPTION: ...
MOTS_CLES: mot1, mot2, mot3, mot4, mot5
FAQ_JSON: [{"q":"...","a":"..."},{"q":"...","a":"..."},{"q":"...","a":"..."}]

Ajoute aussi ce bloc dans le contenu :
{links}
""".strip()

def prompt_evergreen(topic: dict, bookmaker: dict, constraints: str) -> str:
    links = internal_links_section(bookmaker)
    topic_id = topic.get("id", "topic")
    title_hint = topic.get("title_template", "Conseils paris sportifs (FCFA)")

    return f"""
Tu es expert paris sportifs et SEO pour Mr XPRONOS.

Rédige un article evergreen en français sur :
- topic_id: {topic_id}
- titre proposé: {title_hint}
- angle: {topic.get("angle","")}

Contraintes :
- Markdown
- 950 à 1400 mots
- Ton premium, concret, orienté FCFA
- Ajouter au moins 1 tableau Markdown
- Ajouter exemples pratiques en FCFA
- Mentionner intelligemment les bonus/bookmakers
- Ajouter une mini-section "Comment utiliser {CODE_PROMO} sur {bookmaker.get("name","un bookmaker")}"
- Ajouter une section "Erreurs à éviter"
- Ajouter une section FAQ
- Ajouter à la fin du contenu :
SLUG: ...
META_DESCRIPTION: ...
MOTS_CLES: mot1, mot2, mot3, mot4, mot5
FAQ_JSON: [{"q":"...","a":"..."},{"q":"...","a":"..."},{"q":"...","a":"..."}]

Anti-similarité :
{constraints}

Ajoute aussi ce bloc dans le contenu :
{links}
""".strip()

def prompt_conseil(topic: str) -> str:
    return f"""
Tu es expert paris sportifs pour Mr XPRONOS.

Rédige un conseil pratique en français sur : "{topic}"

Contraintes :
- Markdown
- 250 à 450 mots
- Très concret
- Style clair, premium, utile
- Si pertinent, utiliser un exemple en FCFA
- Finir par une mini section "Conseil Mr XPRONOS"

Ajouter à la fin du contenu :
MOTS_CLES: mot1, mot2, mot3, mot4
""".strip()


# =======================================================
# FALLBACKS LOCAUX
# =======================================================

def build_local_evergreen_fallback(topic: dict, bookmaker: dict) -> dict:
    title = topic.get("title_template", "Guide paris sportifs FCFA")
    slug = slugify(title)

    content = f"""
# {title}

Les paris sportifs en **FCFA** exigent une approche disciplinée. Beaucoup de joueurs se précipitent, misent trop vite ou choisissent trop de matchs, ce qui finit par casser leur budget.

## Pourquoi ce sujet compte vraiment
Quand ta bankroll est limitée, chaque erreur pèse lourd. Une mauvaise habitude peut effacer plusieurs gains en une seule journée.

## La méthode simple Mr XPRONOS
| Étape | Action |
|---|---|
| 1 | Définir une bankroll claire en FCFA |
| 2 | Choisir un marché compréhensible |
| 3 | Vérifier contexte, forme et cotes |
| 4 | Fixer une mise raisonnable |
| 5 | Accepter qu’un bon pari peut perdre |

## Exemple concret en FCFA
Si ta bankroll est de **20 000 FCFA**, une mise prudente peut être de **500 à 1 000 FCFA**. Cela permet de tenir dans le temps et d’éviter les réactions impulsives.

## Les erreurs à éviter
- Jouer pour se refaire
- Empiler trop de matchs dans un combiné
- Miser gros après une série de gains
- Suivre une cote sans comprendre le contexte

## Bonus & bookmaker
Tu peux regarder **{bookmaker.get("name","1xBet")}** avec le code promo **{CODE_PROMO}** :
{bookmaker.get("url", BASE_SITE_URL)}

## Conseil Mr XPRONOS
Le plus important n’est pas de parier tous les jours, mais de sélectionner les meilleures opportunités avec discipline.
""".strip()

    return {
        "title": title,
        "slug": slug,
        "meta_description": f"{title} : méthode simple, exemples en FCFA, erreurs à éviter et conseil bookmaker.",
        "keywords": ["paris sportifs", "FCFA", "bankroll", "bonus bookmaker", "Mr XPRONOS"],
        "faq": [
            {"q": "Peut-on commencer avec une petite bankroll ?", "a": "Oui, si les mises restent modestes et régulières."},
            {"q": "Faut-il jouer tous les jours ?", "a": "Non, il vaut mieux attendre les bons signaux."},
            {"q": "Les bonus sont-ils toujours intéressants ?", "a": "Il faut lire les conditions avant d’accepter."}
        ],
        "content_markdown": content
    }

def build_local_conseil_fallback(topic: str) -> dict:
    title = f"Conseil pratique : {topic.capitalize()}"
    content = f"""
# {title}

Quand on parle de **{topic}**, beaucoup de parieurs vont trop vite. Pourtant, une bonne décision commence toujours par une méthode claire.

## Ce qu’il faut retenir
- Rester simple
- Éviter les décisions impulsives
- Adapter la mise à ta bankroll
- Penser long terme

## Exemple en FCFA
Avec une bankroll de **10 000 FCFA**, une mise prudente reste modérée. L’idée n’est pas d’accélérer les gains, mais de protéger ton capital.

## Conseil Mr XPRONOS
Prends toujours 2 minutes pour vérifier si le pari est logique, lisible et adapté à ton budget.

MOTS_CLES: conseil, FCFA, paris sportifs, discipline
""".strip()

    return {
        "title": title,
        "content_markdown": content,
        "keywords": ["paris sportifs", "conseil", "FCFA", "Mr XPRONOS"]
    }


# =======================================================
# BUILD OBJECTS
# =======================================================

def build_article_object(parsed: dict, image_path: str, extra: dict) -> dict:
    title = (parsed.get("title") or "Article").strip()
    slug = parsed.get("slug") or slugify(title)
    meta_desc = (parsed.get("meta_description") or "")[:160].strip()
    keywords = normalize_keywords(parsed.get("keywords"))
    faq = normalize_faq(parsed.get("faq"))
    content = parsed.get("content_markdown") or ""

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
        "keywords": ", ".join(keywords) if keywords else "pronostic, football, paris sportifs",
        "faq": faq,
        "content": content,
        "image_url": image_path,
        "og_image": image_path,
        "active": True,
        "content_hash": content_hash(content[:2500]),
        **extra
    }

def build_conseil_object(parsed: dict, image_path: str) -> dict:
    title = (parsed.get("title") or "Conseil").strip()
    content = parsed.get("content_markdown") or ""
    excerpt = excerpt_from_text(content, 140)

    return {
        "title": title,
        "content": content,
        "date": datetime.utcnow().isoformat() + "Z",
        "reading_time": reading_time_minutes(content),
        "excerpt": excerpt,
        "image_url": image_path,
        "active": True,
        "content_hash": content_hash(content[:2000]),
        "keywords": ", ".join(normalize_keywords(parsed.get("keywords")))
    }


# =======================================================
# MAIN
# =======================================================

def main():
    print("=" * 60)
    print("🚀 GÉNÉRATION DE CONTENU IA (parsing texte robuste)")
    print("=" * 60)

    if not MISTRAL_API_KEY:
        print("❌ MISTRAL_API_KEY manquante : impossible de générer le texte.")
        return

    init_mistral_sdk()

    existing_articles = load_existing_articles()
    existing_conseils = load_existing_conseils()

    bookmaker = pick_bookmaker()
    topics = load_topics()

    # ---------------------------------------------------
    # 1) ARTICLE MATCH DU JOUR
    # ---------------------------------------------------
    match = pick_best_match_today()
    if not match:
        print("⚠️ Impossible de récupérer un match. Pas d'article match aujourd'hui.")
    else:
        print(f"⚽ Match du jour: {match['home_team']} vs {match['away_team']} ({match.get('league','')})")
        raw = call_mistral_text(prompt_match_article(match, bookmaker), label="match")
        if not raw:
            print("❌ Échec génération texte match.")
        else:
            parsed = parse_structured_text(raw)
            body = parsed.get("content_markdown", "") or ""

            if is_duplicate_article(parsed["slug"], parsed.get("title", ""), body, existing_articles):
                print("⚠️ Article match doublon -> ignoré.")
            else:
                img_prompt = (
                    f"Ultra realistic football match poster, {match['home_team']} vs {match['away_team']}, "
                    f"packed stadium at night, bright floodlights, cinematic lighting, shallow depth of field, "
                    f"slight motion blur, high detail, HDR, 35mm photo, realistic faces, realistic kits, "
                    f"dramatic atmosphere, 16:9, no text, no watermark, no logos"
                )

                img_path = generate_image_with_fallback(img_prompt, ARTICLE_IMG_DIR)
                if not img_path:
                    print("❌ Image match impossible -> article match ignoré.")
                else:
                    art = build_article_object(parsed, img_path, {
                        "type": "match",
                        "match": f"{match['home_team']} vs {match['away_team']}",
                        "league": match.get("league", ""),
                    })
                    existing_articles.insert(0, art)
                    save_articles(existing_articles)
                    print(f"✅ Article match sauvegardé: {art['title']} (slug={art['slug']})")

    # ---------------------------------------------------
    # 2) ARTICLE EVERGREEN
    # ---------------------------------------------------
    topic = pick_unused_topic(existing_articles, topics)
    constraints = build_antisim_constraints(existing_articles)
    recent_ev = [(a.get("content") or "")[:4500] for a in existing_articles if isinstance(a, dict) and a.get("type") == "evergreen"][:10]

    for attempt in range(MAX_EVERGREEN_RETRIES + 1):
        print(f"🧠 Evergreen: topic={topic.get('id')} tentative {attempt+1}/{MAX_EVERGREEN_RETRIES+1}")

        raw = call_mistral_text(prompt_evergreen(topic, bookmaker, constraints), label="evergreen")
        if not raw:
            print("⚠️ Échec génération evergreen via Mistral -> fallback local.")
            parsed = build_local_evergreen_fallback(topic, bookmaker)
        else:
            parsed = parse_structured_text(raw)

        body = parsed.get("content_markdown", "") or ""

        too_similar = any(is_similar(body, t) for t in recent_ev)
        if too_similar:
            print("⚠️ Evergreen trop similaire -> régénération.")
            constraints += "\n- Change complètement la structure, les sections et le tableau."
            continue

        if is_duplicate_article(parsed.get("slug", ""), parsed.get("title", ""), body, existing_articles):
            print("⚠️ Evergreen doublon -> régénération.")
            continue

        img_prompt = (
            "Photorealistic premium sports betting strategy poster, football themed, dark premium mood with subtle gold accents, "
            "cinematic lighting, high detail, 16:9, no text, no watermark, no logos"
        )
        img_path = generate_image_with_fallback(img_prompt, ARTICLE_IMG_DIR)
        if not img_path:
            print("❌ Image evergreen impossible -> evergreen ignoré.")
            break

        art = build_article_object(parsed, img_path, {
            "type": "evergreen",
            "topic_id": topic.get("id"),
        })
        existing_articles.insert(0, art)
        save_articles(existing_articles)
        print(f"✅ Evergreen sauvegardé: {art['title']} (topic={topic.get('id')})")
        break

    # ---------------------------------------------------
    # 3) CONSEILS (x3)
    # ---------------------------------------------------
    print("\n💡 Génération de 3 conseils...")
    for i in range(3):
        topic_c = random.choice(CONSEIL_TOPICS)
        print(f"   Conseil {i+1}: {topic_c}")

        raw = call_mistral_text(prompt_conseil(topic_c), label=f"conseil-{i+1}")
        if not raw:
            print("   ⚠️ Fallback conseil local")
            parsed = build_local_conseil_fallback(topic_c)
        else:
            parsed = parse_structured_text(raw)
            if not parsed.get("content_markdown"):
                parsed = build_local_conseil_fallback(topic_c)

        body = parsed.get("content_markdown", "") or ""
        if is_duplicate_conseil(parsed.get("title", ""), body, existing_conseils):
            print("   ⚠️ Conseil doublon, ignoré.")
            continue

        img_prompt = (
            f"Photorealistic football coaching / betting advice poster, topic {topic_c}, "
            f"premium dark and gold mood, realistic, no text, no watermark, 16:9"
        )
        img_path = generate_image_with_fallback(img_prompt, CONSEIL_IMG_DIR)
        if not img_path:
            print("   ❌ Image conseil impossible, ignoré.")
            continue

        conseil_obj = build_conseil_object(parsed, img_path)
        existing_conseils.insert(0, conseil_obj)
        save_conseils(existing_conseils)
        print(f"   ✅ Conseil sauvegardé: {conseil_obj['title']}")

    print("\n✅ Génération terminée.")


if __name__ == "__main__":
    main()