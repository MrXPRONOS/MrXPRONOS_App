#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
content_generator.py - Générateur de contenu IA pour Mr XPRONOS (V2 SEO)
- 1 article match du jour (choisi via allscores + popularité)
- 1 article evergreen (unique, non similaire)
- Images 1200x630 (Mistral -> Pixazo fallback) + post-traitement
- SEO: slug, meta_description, keywords, FAQ JSON
- Maillage interne + section Bonus/Bookmaker
"""

import os
import json
import re
import uuid
import time
import random
import hashlib
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any, Tuple
from difflib import SequenceMatcher

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

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
PIXAZO_API_KEY = os.environ.get("PIXAZO_API_KEY")

DATA_FILE = "data.json"
ARTICLES_FILE = "articles.json"

ASSET_IMG_DIR = "assets/images"
ARTICLE_IMG_DIR = os.path.join(ASSET_IMG_DIR, "articles")
os.makedirs(ARTICLE_IMG_DIR, exist_ok=True)

BASE_SITE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/"
CODE_PROMO = "XPVIP"

SPORTDATA_V1_ALLSCORES = "https://v1.football.sportsapipro.com/games/allscores"

POPULAR_LEAGUES = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Super Lig", "Russian Premier League",
    "MLS", "Brasileirão", "Liga Profesional", "Jupiler Pro League",
    "Super League", "Championship", "Liga Portugal", "Trendyol Super Lig"
]

# Evergreen: on ne répète pas le même topic_id
EVERGREEN_TOPICS = [
    {
        "id": "bankroll-gestion-1",
        "title_template": "Gestion de bankroll : la méthode simple pour durer (avec exemples en FCFA)",
        "angle": "pédagogie + règles + exemples + erreurs à éviter"
    },
    {
        "id": "double-chance-guide-1",
        "title_template": "Double chance (1X / X2) : stratégie, pièges et comment bien la choisir",
        "angle": "cas concrets + quand éviter + optimisation"
    },
    {
        "id": "value-bet-1",
        "title_template": "Value Bet : comment repérer une cote rentable (même sans être expert)",
        "angle": "méthode + mini-calcul + erreurs fréquentes"
    },
    {
        "id": "over-under-25-1",
        "title_template": "Over/Under 2.5 : l’analyse qui évite les faux bons matchs",
        "angle": "stats utiles + contexte + gestion risque"
    },
    {
        "id": "btts-1",
        "title_template": "BTTS (Les deux équipes marquent) : critères fiables et check-list rapide",
        "angle": "signaux + exemples + pièges"
    },
    {
        "id": "bonus-xpvip-1xbet-1",
        "title_template": "Bonus 1xBet avec XPVIP : comment l’utiliser intelligemment (sans perdre ton bonus)",
        "angle": "conditions générales + rollover + stratégie prudente"
    },
    {
        "id": "bonus-xpvip-1win-1",
        "title_template": "Bonus 1win + code XPVIP : maximiser l’offre et sécuriser tes mises",
        "angle": "conversion + gestion mise + erreurs"
    },
    {
        "id": "comparatif-bookmakers-1",
        "title_template": "Comparatif Bookmakers : 1xBet, 1win, Betwinner — lequel choisir selon ton style ?",
        "angle": "tableau avantages/inconvénients + recommandations"
    },
    {
        "id": "analyse-match-1",
        "title_template": "Comment analyser un match (méthode rapide) : forme, H2H, motivation, cotes",
        "angle": "framework simple + exemple"
    },
    {
        "id": "piege-bookmaker-1",
        "title_template": "Pièges bookmakers : 7 signaux qui doivent te faire éviter un match",
        "angle": "liste + explications + exemples"
    },
]

# Anti similarité evergreen
SIMILARITY_JACCARD_THRESHOLD = 0.62
SIMILARITY_SEQ_THRESHOLD = 0.86
MAX_EVERGREEN_RETRIES = 2

# Image output
TARGET_W, TARGET_H = 1200, 630


# =======================================================
# MISTRAL (texte + image)
# =======================================================

mistral_client = None
IMAGE_AGENT_ID = None

def init_mistral() -> bool:
    global mistral_client, IMAGE_AGENT_ID
    if not MISTRAL_API_KEY:
        print("⚠️ MISTRAL_API_KEY non définie - texte/images Mistral désactivés")
        return False
    try:
        from mistralai import Mistral
        mistral_client = Mistral(api_key=MISTRAL_API_KEY)
        print("✅ Client Mistral initialisé")
        IMAGE_AGENT_ID = create_image_agent()
        return True
    except ImportError as e:
        print(f"⚠️ Module mistralai non installé: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Erreur init Mistral: {e}")
        return False

def create_image_agent():
    if not mistral_client:
        return None
    try:
        agent = mistral_client.beta.agents.create(
            model="mistral-medium-2505",
            name="Image Generation Agent",
            description="Agent used to generate images.",
            instructions="Use the image generation tool when you have to create images.",
            tools=[{"type": "image_generation"}],
            completion_args={"temperature": 0.3, "top_p": 0.95}
        )
        print("✅ Agent image Mistral créé")
        return agent.id
    except Exception as e:
        print(f"❌ Erreur création agent image: {e}")
        return None

def call_mistral_text(prompt: str, temperature=0.7, max_tokens=2200, retries=2) -> Optional[str]:
    if not mistral_client:
        return None
    for attempt in range(retries + 1):
        try:
            resp = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Mistral texte tentative {attempt+1}/{retries+1} échouée: {e}")
            if attempt == retries:
                return None
            time.sleep(1)
    return None

def call_mistral_json(prompt: str, retries=2) -> Optional[dict]:
    """
    Demande à Mistral de répondre en JSON strict.
    """
    txt = call_mistral_text(prompt, temperature=0.55, max_tokens=2400, retries=retries)
    if not txt:
        return None
    # essayer parse direct
    try:
        return json.loads(txt)
    except Exception:
        pass
    # extraire bloc JSON
    m = re.search(r"\{[\s\S]*\}\s*$", txt.strip())
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

def generate_image_mistral(prompt: str) -> Optional[str]:
    if not mistral_client or not IMAGE_AGENT_ID:
        return None
    try:
        response = mistral_client.beta.conversations.start(
            agent_id=IMAGE_AGENT_ID,
            inputs=prompt
        )
        for output in response.outputs:
            if output.type == "message.output":
                for chunk in output.content:
                    if chunk.type == "tool_file" and chunk.tool == "image_generation":
                        file_id = chunk.file_id
                        file_bytes = mistral_client.files.download(file_id=file_id).read()
                        filename = os.path.join(ARTICLE_IMG_DIR, f"img-{uuid.uuid4().hex[:10]}.png")
                        with open(filename, "wb") as f:
                            f.write(file_bytes)
                        return filename
        return None
    except Exception as e:
        print(f"❌ Mistral image error: {e}")
        return None


# =======================================================
# PIXAZO (fallback image)
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

        filename = os.path.join(ARTICLE_IMG_DIR, f"img-{uuid.uuid4().hex[:10]}.png")
        with open(filename, "wb") as f:
            f.write(img_resp.content)
        return filename
    except Exception as e:
        print(f"❌ Pixazo image error: {e}")
        return None


# =======================================================
# IMAGE POST-PROCESS (1200x630)
# =======================================================

def ensure_1200x630(path: str) -> Optional[str]:
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        # Crop center to target ratio
        target_ratio = TARGET_W / TARGET_H
        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            # too wide -> crop width
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif current_ratio < target_ratio:
            # too tall -> crop height
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


def generate_image_1200x630(prompt: str, mistral_ok: bool) -> Optional[str]:
    img_path = None
    if mistral_ok:
        img_path = generate_image_mistral(prompt)

    if not img_path:
        img_path = generate_image_pixazo(prompt)

    if not img_path:
        return None

    return ensure_1200x630(img_path)


# =======================================================
# DATA / BOOKMAKERS
# =======================================================

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            c = f.read().strip()
            if not c:
                return default
            return json.loads(c)
    except Exception:
        return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_existing_articles() -> list:
    d = load_json(ARTICLES_FILE, [])
    return d if isinstance(d, list) else []

def get_bookmakers_from_data() -> list:
    d = load_json(DATA_FILE, {})
    b = d.get("bookmakers", [])
    if isinstance(b, list) and b:
        return b
    # fallback minimal
    return [
        {"name": "1xBet", "url": "https://refpa58144.com/L?tag=d_2054511m_1599c_&site=2054511&ad=1599"},
        {"name": "1win", "url": "https://1wrbgb.com/?open=register&p=qqcw"},
        {"name": "Betwinner", "url": "https://bwredir.com/299Y"},
    ]

def pick_bookmaker() -> dict:
    books = get_bookmakers_from_data()
    return random.choice(books) if books else {"name": "1xBet", "url": BASE_SITE_URL}

def slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or f"post-{uuid.uuid4().hex[:6]}"

def reading_time_minutes(text: str) -> int:
    words = len(re.findall(r"\w+", text or ""))
    return max(1, round(words / 200))

def excerpt_from_text(text: str, length=160) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()
    return (t[:length] + "...") if len(t) > length else t

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
    jac = jaccard(ta, tb)
    if jac >= SIMILARITY_JACCARD_THRESHOLD:
        return True
    seq = SequenceMatcher(None, (a or "")[:1200], (b or "")[:1200]).ratio()
    return seq >= SIMILARITY_SEQ_THRESHOLD

def is_duplicate_article(new_slug: str, new_title: str, new_body: str, existing: list) -> bool:
    new_slug = (new_slug or "").strip()
    new_title = (new_title or "").strip().lower()
    new_h = content_hash(new_body[:2000])

    for a in existing:
        if not isinstance(a, dict):
            continue
        if (a.get("slug") or "").strip() == new_slug and new_slug:
            return True
        if (a.get("title") or "").strip().lower() == new_title and new_title:
            return True
        if a.get("content_hash") == new_h:
            return True

        # similar title check
        if new_title and a.get("title"):
            if is_similar(new_title, a["title"].lower()):
                return True
    return False


# =======================================================
# SPORTDATA: Match sélection par popularité (allscores)
# =======================================================

def fetch_allscores_today() -> Optional[dict]:
    if make_request is None:
        return None

    params = {
        "startDate": today.strftime("%d/%m/%Y"),
        "endDate": today.strftime("%d/%m/%Y"),
        "sports": 1,
        "showOdds": "false",
        "onlyMajorGames": "false"
    }

    resp = make_request("GET", SPORTDATA_V1_ALLSCORES, params=params, timeout=30)
    if resp is None or resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None

def build_popularity_maps(payload: dict) -> Tuple[dict, dict]:
    comp_pop = {}
    team_pop = {}
    if not isinstance(payload, dict):
        return comp_pop, team_pop

    comps = payload.get("competitions", [])
    for c in comps if isinstance(comps, list) else []:
        cid = c.get("id")
        if cid is None:
            continue
        comp_pop[str(cid)] = {
            "popularityRank": c.get("popularityRank", 0) or 0,
            "imageVersion": c.get("imageVersion"),
            "name": c.get("name")
        }

    teams = payload.get("competitors", [])
    for t in teams if isinstance(teams, list) else []:
        tid = t.get("id")
        if tid is None:
            continue
        team_pop[str(tid)] = {
            "popularityRank": t.get("popularityRank", 0) or 0,
            "imageVersion": t.get("imageVersion"),
            "name": t.get("name")
        }

    return comp_pop, team_pop

def score_game(game: dict, comp_pop: dict, team_pop: dict) -> float:
    """
    Score simple: compétition (x2) + home + away + boost ligue populaire.
    popularityRank semble "plus grand = plus populaire" dans tes data.
    """
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
    if any(x.lower() in comp_name.lower() for x in [l.lower() for l in POPULAR_LEAGUES]):
        boost = 50_000_000  # gros boost pour ligues majeures

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
        "event_date": best.get("startTime") or best.get("start_time") or "",
    }


# =======================================================
# PROMPTS
# =======================================================

def build_internal_links_section(bookmaker: dict) -> str:
    bm_name = bookmaker.get("name", "Bookmaker")
    bm_url = bookmaker.get("url", BASE_SITE_URL)
    return f"""
## Liens utiles
- Pronostics du jour : {BASE_SITE_URL}pronos.html
- Bonus & promotions : {BASE_SITE_URL}bonus.html
- Accès LIVE VIP : {BASE_SITE_URL}live.html

## Bonus recommandé
Si tu veux profiter des offres, tu peux tester **{bm_name}** avec le code promo **{CODE_PROMO}** :
{bm_url}

> Les paris comportent des risques. Joue responsablement.
""".strip()

def prompt_match_article(match: dict, bookmaker: dict) -> str:
    ht = match.get("home_team", "Équipe A")
    at = match.get("away_team", "Équipe B")
    league = match.get("league", "Championnat")
    dt = match.get("event_date", "")

    links = build_internal_links_section(bookmaker)

    return f"""
Tu es un journaliste sportif + expert paris sportifs pour le site Mr XPRONOS.

Génère un JSON STRICT (sans texte autour) avec les clés :
- title (string) : Titre SEO clair contenant "Pronostic", les 2 équipes et la compétition.
- slug (string) : slug URL en minuscules avec tirets, unique.
- meta_description (string) : <= 160 caractères.
- keywords (array de 5 à 8 strings)
- faq (array de 3 objets {{q,a}})
- content_markdown (string) : article complet en Markdown (800 à 1200 mots)

Sujet :
Match : {ht} vs {at}
Compétition : {league}
Date : {dt}

Contraintes rédactionnelles :
- Structure H2/H3, style professionnel, moderne, sans promesses "garanti".
- Ajouter une section "Conseil de pari Mr XPRONOS" avec une recommandation (double chance ou prudente).
- Mentionner une estimation "mise conseillée" en FCFA (ex: 1 000 à 5 000 FCFA) et gestion bankroll.
- Ajouter une mini-section "Cotes & value" (même si tu restes qualitatif).
- Ajouter {links} à la fin du markdown.
- Langue : français.

Réponds UNIQUEMENT en JSON valide.
""".strip()

def prompt_evergreen(topic: dict, bookmaker: dict, constraints: str) -> str:
    links = build_internal_links_section(bookmaker)
    return f"""
Tu es un expert paris sportifs et SEO pour Mr XPRONOS.

Génère un JSON STRICT (sans texte autour) avec :
- title (string) : titre SEO très clair, différent des autres articles.
- slug (string)
- meta_description (string) <=160 caractères
- keywords (array 6 à 10 strings)
- faq (array de 3 objets {{q,a}})
- content_markdown (string) : article evergreen 900-1400 mots, très utile, actionnable.

Thème evergreen (unique) :
- topic_id: {topic["id"]}
- angle: {topic["angle"]}
- titre proposé: {topic["title_template"]}

Contraintes très importantes :
- NE PAS répéter une structure trop similaire à d’autres articles.
- Ajouter au moins 1 tableau (Markdown) comparatif ou checklist.
- Ajouter des exemples concrets en FCFA.
- Parler intelligemment des BONUS et du choix bookmaker (sans exagération).
- Ajouter un mini paragraphe "Comment utiliser {CODE_PROMO} sur {bookmaker.get("name","un bookmaker")}".
- Ajouter {links} à la fin du markdown.
- Style: unique, concret, non répétitif.

Contraintes anti-similarité supplémentaires :
{constraints}

Réponds UNIQUEMENT en JSON valide.
""".strip()


# =======================================================
# ARTICLE BUILD / SAVE
# =======================================================

def save_articles(articles: list):
    # on limite pour éviter repo énorme (tu peux augmenter)
    articles = articles[:80]
    save_json(ARTICLES_FILE, articles)

def build_article_object(js: dict, image_url: str, author="Mr XPRONOS", extra: dict = None) -> dict:
    title = js.get("title", "Article").strip()
    slug = js.get("slug") or slugify(title)
    meta_desc = (js.get("meta_description") or "")[:160].strip()
    keywords = js.get("keywords") or []
    faq = js.get("faq") or []
    content = js.get("content_markdown") or ""

    # excerpt & reading time
    excerpt = excerpt_from_text(content, 170)
    rt = reading_time_minutes(content)

    return {
        "slug": slug,
        "title": title,
        "date": datetime.utcnow().isoformat() + "Z",
        "author": author,
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
        **(extra or {})
    }


# =======================================================
# MAIN GENERATION
# =======================================================

def pick_unused_evergreen_topic(existing: list) -> Optional[dict]:
    used = set()
    for a in existing:
        if isinstance(a, dict) and a.get("type") == "evergreen" and a.get("topic_id"):
            used.add(a["topic_id"])

    candidates = [t for t in EVERGREEN_TOPICS if t["id"] not in used]
    if not candidates:
        # si tout est utilisé, on recycle mais avec contrainte forte
        return random.choice(EVERGREEN_TOPICS)
    return random.choice(candidates)

def recent_evergreen_texts(existing: list, limit=12) -> List[str]:
    texts = []
    for a in existing:
        if isinstance(a, dict) and a.get("type") == "evergreen":
            texts.append((a.get("content") or "")[:4000])
    return texts[:limit]

def build_antisim_constraints(existing_evergreen: List[str]) -> str:
    # On passe à Mistral des "interdits" simples
    snippets = []
    for t in existing_evergreen[:6]:
        snippet = re.sub(r"\s+", " ", t)
        snippets.append(snippet[:220])
    if not snippets:
        return "- Aucun."

    return "\n".join([f"- Ne pas reproduire ce type de formulation: «{s}...»" for s in snippets])

def main():
    print("=" * 60)
    print("🚀 GÉNÉRATION CONTENU IA (Match du jour + Evergreen, SEO + images 1200x630)")
    print("=" * 60)

    mistral_ok = init_mistral()

    existing_articles = load_existing_articles()

    # -------------------------------------------------------
    # 1) MATCH DU JOUR (via allscores + popularité)
    # -------------------------------------------------------
    bookmaker = pick_bookmaker()
    match = pick_best_match_today()

    if not match:
        print("⚠️ Impossible de récupérer un match via allscores. Pas d'article match aujourd'hui.")
    else:
        print(f"⚽ Match du jour sélectionné: {match['home_team']} vs {match['away_team']} ({match.get('league','')})")

        prompt = prompt_match_article(match, bookmaker)
        js = call_mistral_json(prompt) if mistral_ok else None
        if not js:
            print("❌ Échec génération JSON match (Mistral indisponible ou erreur).")
        else:
            # sécuriser slug
            js["slug"] = js.get("slug") or slugify(js.get("title", "pronostic"))
            # dédup
            if is_duplicate_article(js["slug"], js.get("title",""), js.get("content_markdown",""), existing_articles):
                print("⚠️ Article match détecté comme doublon (slug/titre/similarité). Ignoré.")
            else:
                img_prompt = (
                    f"Football match poster, realistic, dynamic stadium atmosphere, "
                    f"{match['home_team']} vs {match['away_team']}, {match.get('league','League')}, "
                    f"no text, no watermark, cinematic lighting, high quality, 1200x630"
                )

                image_path = generate_image_1200x630(img_prompt, mistral_ok)
                if not image_path:
                    print("❌ Image match impossible -> article match ignoré (conformément à ta règle).")
                else:
                    new_article = build_article_object(js, image_path, extra={
                        "type": "match",
                        "match": f"{match['home_team']} vs {match['away_team']}",
                        "league": match.get("league", ""),
                    })
                    existing_articles.insert(0, new_article)
                    save_articles(existing_articles)
                    print(f"✅ Article match sauvegardé: {new_article['title']} (slug={new_article['slug']})")

    # -------------------------------------------------------
    # 2) EVERGREEN (unique + anti similarité)
    # -------------------------------------------------------
    topic = pick_unused_evergreen_topic(existing_articles)
    if not topic:
        print("⚠️ Aucun topic evergreen disponible.")
        return

    existing_ev_texts = recent_evergreen_texts(existing_articles, limit=12)
    constraints = build_antisim_constraints(existing_ev_texts)

    for attempt in range(MAX_EVERGREEN_RETRIES + 1):
        print(f"🧠 Evergreen: topic={topic['id']} tentative {attempt+1}/{MAX_EVERGREEN_RETRIES+1}")

        prompt = prompt_evergreen(topic, bookmaker, constraints)
        js = call_mistral_json(prompt) if mistral_ok else None
        if not js:
            print("❌ Échec génération JSON evergreen.")
            break

        js["slug"] = js.get("slug") or slugify(js.get("title", f"evergreen-{topic['id']}"))

        body = js.get("content_markdown", "") or ""

        # anti-similarité (contenu vs evergreen récents)
        too_similar = False
        for t in existing_ev_texts[:10]:
            if is_similar(body, t):
                too_similar = True
                break

        if too_similar:
            print("⚠️ Evergreen trop similaire à un article existant -> régénération.")
            constraints += "\n- Le prochain article doit changer COMPLETEMENT la structure (différentes sections, différent tableau, différent exemple)."
            continue

        if is_duplicate_article(js["slug"], js.get("title",""), body, existing_articles):
            print("⚠️ Evergreen doublon détecté -> régénération.")
            continue

        img_prompt = (
            f"Sports betting strategy illustration, modern premium style, realistic, "
            f"football themed, dark and gold color palette, no text, no watermark, 1200x630"
        )
        image_path = generate_image_1200x630(img_prompt, mistral_ok)
        if not image_path:
            print("❌ Image evergreen impossible -> evergreen ignoré (conformément à ta règle).")
            break

        new_article = build_article_object(js, image_path, extra={
            "type": "evergreen",
            "topic_id": topic["id"]
        })

        existing_articles.insert(0, new_article)
        save_articles(existing_articles)
        print(f"✅ Evergreen sauvegardé: {new_article['title']} (topic={topic['id']})")
        break

    print("✅ Génération terminée.")


if __name__ == "__main__":
    main()