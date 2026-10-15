#!/usr/bin/env python3
"""Mr XPRONOS — cinéma Telegram, lot 2/3, five distinct formats.

Uses free TMDB metadata, existing Telegram Rich Messages and native polls.
No film downloads, no paid LLM, no production publication by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import tempfile
from datetime import date, datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
import cinema_telegram as base

ROOT = Path(__file__).resolve().parents[1]
FORMATS = ('series', 'notes', 'pepites', 'acteur', 'sondage')
TMDB = 'https://api.themoviedb.org/3'
POSTER_URL = 'https://image.tmdb.org/t/p/w500'
MOCK_MOVIES = [
    {'id': 501, 'title': 'Le mystère du phare', 'overview': 'Un récit imaginaire au bord de la mer.', 'vote_average': 8.1, 'vote_count': 1200, 'release_date': '2023-01-10', 'poster_path': None},
    {'id': 502, 'title': 'La traversée', 'overview': 'Une aventure inventée pour les tests.', 'vote_average': 7.8, 'vote_count': 900, 'release_date': '2022-03-12', 'poster_path': None},
    {'id': 503, 'title': 'Demain les étoiles', 'overview': 'Un voyage fictif vers les étoiles.', 'vote_average': 8.4, 'vote_count': 2100, 'release_date': '2021-08-21', 'poster_path': None},
    {'id': 504, 'title': 'Un dernier été', 'overview': 'Une fiction romantique.', 'vote_average': 7.7, 'vote_count': 760, 'release_date': '2020-01-02', 'poster_path': None},
    {'id': 505, 'title': 'La porte bleue', 'overview': 'Une énigme fictive.', 'vote_average': 7.9, 'vote_count': 1300, 'release_date': '2019-09-13', 'poster_path': None},
]
MOCK_SERIES = [{'id': 600+i, 'title': v['title'] + ' (série)', 'overview': v['overview'],
                'vote_average': v['vote_average'], 'vote_count': v['vote_count'],
                'release_date': '2024-01-01', 'poster_path': None, 'media_type': 'tv'}
               for i, v in enumerate(MOCK_MOVIES)]
MOCK_ACTOR = {'id': 700, 'name': 'Actrice ou acteur de démonstration',
              'known_for': MOCK_MOVIES[:4], 'profile_path': None}


def compact(value, max_chars=200):
    words = ' '.join(str(value or '').split())
    if len(words) <= max_chars:
        return words
    return words[:max_chars-1].rsplit(' ', 1)[0] + '…'


def safe(value, limit=200):
    return escape(compact(value, limit), quote=False)


def movie_url(item, default='movie', demo=False):
    if demo:
        return 'https://www.themoviedb.org/'
    media = item.get('media_type') or default
    if media not in ('movie', 'tv', 'person'):
        raise ValueError('Unsupported TMDB media type')
    return f"https://www.themoviedb.org/{media}/{int(item['id'])}"


def rating(item):
    r = float(item.get('vote_average') or 0)
    return f'{r:.1f}/10' if r else 'Non noté'


def year(item):
    return (str(item.get('release_date') or '—'))[:4]


def key_seed(kind, when):
    return int(hashlib.sha256(f'{kind}:{when.isoformat()}'.encode()).hexdigest()[:8], 16)


def button(item, demo=False, label='🎬 Découvrir la fiche', media='movie'):
    return [[{'text': label, 'url': movie_url(item, default=media, demo=demo), 'style': 'primary'}]]


def caption(kind, items, when, demo=False):
    """Rich HTML and full-row buttons. HTML-escape every external field."""
    if kind == 'sondage':
        raise ValueError('Native polls have their own layout')
    subject = items[0]
    if kind == 'series':
        names = ''.join(f'<p><b>{i}. {safe(x["title"], 62)}</b> · ⭐ {rating(x)}</p>' for i, x in enumerate(items[:5], 1))
        html = ('<h3>📺 LES SÉRIES DU MOMENT</h3><p><i>La sélection TV de la semaine.</i></p>' + names
                + '<blockquote>📺 Quelle série te tente le plus ?</blockquote>')
        controls = button(subject, demo, '📺 Découvrir la série n° 1', 'tv')
    elif kind == 'notes':
        names = ''.join(f'<p><b>{i}. {safe(x["title"], 62)}</b> — ⭐ {rating(x)} '
                        f'<i>({int(x.get("vote_count") or 0)} avis)</i></p>' for i, x in enumerate(items[:5], 1))
        html = ('<h3>⭐ LES FILMS LES MIEUX NOTÉS</h3>'
                '<p><i>Classement filtré pour éviter les notes sur trop peu de votes.</i></p>'
                + names + '<blockquote>🎥 Lequel mérite sa place dans ton top personnel ?</blockquote>')
        controls = button(subject, demo, '🥇 Découvrir le film n° 1')
    elif kind == 'pepites':
        names = ''.join(f'<p>💎 <b>{safe(x["title"], 62)}</b> · {year(x)} · ⭐ {rating(x)}</p>' for x in items[:3])
        html = ('<h3>💎 PÉPITES CINÉMA À DÉCOUVRIR</h3>'
                '<p><i>Des films appréciés, sélectionnés hors des très gros succès.</i></p>'
                + names + '<blockquote>Parfois, les meilleures découvertes sont les moins évidentes.</blockquote>')
        controls = button(subject, demo, '💎 Voir la première pépite')
    elif kind == 'acteur':
        movies = subject.get('known_for') or []
        names = ''.join(f'<p>🎞 <b>{safe(x.get("title"), 65)}</b> · {year(x)}</p>' for x in movies[:4])
        html = ('<h3>🎭 ACTEUR OU ACTRICE DU JOUR</h3>'
                f'<p>🌟 <b>{safe(subject.get("name"), 100)}</b></p>'
                '<p><i>Quelques films à découvrir dans sa filmographie :</i></p>' + names
                + '<blockquote>Tu l’as découvert dans quel film ?</blockquote>')
        controls = button(subject, demo, '🎭 Explorer la filmographie', 'person')
    else:
        raise ValueError('Unknown cinema format ' + kind)
    html += base.footer(demo)
    return html, controls


class API:
    def __init__(self, token, session=None):
        if not token:
            raise ValueError('TMDB_API_KEY est obligatoire pour les publications réelles')
        self.token = token
        self.session = session or requests.Session()

    def call(self, endpoint, **params):
        r = self.session.get(TMDB + endpoint, params={'api_key': self.token, 'language': 'fr-FR', **params}, timeout=25)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def normalize(items, media='movie'):
        result = []
        for item in items:
            if not item.get('id') or item.get('adult'):
                continue
            title = item.get('title') if media == 'movie' else item.get('name')
            if not title:
                continue
            result.append({'id': item['id'], 'title': title, 'overview': item.get('overview') or '',
                           'vote_average': item.get('vote_average') or 0,
                           'vote_count': item.get('vote_count') or 0,
                           'release_date': item.get('release_date') or item.get('first_air_date') or '',
                           'poster_path': item.get('poster_path'), 'media_type': media,
                           'popularity': item.get('popularity') or 0})
        return result

    def pick(self, kind, when, history=None):
        if kind == 'series':
            pool = self.normalize(self.call('/trending/tv/week').get('results', []), 'tv')
            pool = sorted(pool, key=lambda m: (m['vote_count'] >= 100, m['popularity']), reverse=True)
            count = 5
        elif kind == 'notes':
            pool = self.normalize(self.call('/movie/top_rated').get('results', []))
            pool = [x for x in pool if x['vote_count'] >= 500]
            pool.sort(key=lambda m: (m['vote_average'], m['vote_count']), reverse=True)
            count = 5
        elif kind == 'pepites':
            data = self.call('/discover/movie', **{'sort_by': 'vote_average.desc',
                'vote_count.gte': 200, 'vote_count.lte': 3500, 'vote_average.gte': 7.2,
                'primary_release_date.lte': when.isoformat(), 'include_adult': 'false'})
            pool = self.normalize(data.get('results', []))
            pool = [x for x in pool if 200 <= x['vote_count'] <= 3500]
            count = 3
        elif kind == 'sondage':
            pool = self.normalize(self.call('/trending/movie/week').get('results', []))
            count = 4
        elif kind == 'acteur':
            actors = [a for a in self.call('/person/popular').get('results', [])
                      if a.get('id') and a.get('name') and not a.get('adult')
                      and a.get('known_for_department') == 'Acting']
            if not actors:
                raise RuntimeError('Aucun acteur retourné par TMDB')
            actor = actors[key_seed(kind, when) % len(actors)]
            credits = self.call(f"/person/{actor['id']}/movie_credits").get('cast', [])
            credits = self.normalize(credits)
            credits = [x for x in credits if x['vote_count'] >= 80]
            credits.sort(key=lambda x: (x['vote_count'], x['vote_average']), reverse=True)
            return [{'id': actor['id'], 'name': actor['name'], 'known_for': credits[:4],
                     'profile_path': actor.get('profile_path'), 'media_type': 'person'}]
        else:
            raise ValueError(kind)
        if len(pool) < count:
            raise RuntimeError(f'Pas assez de résultats pour {kind} : {len(pool)}/{count}')
        # Avoid past picks for the same format when possible, never select a film twice in one post.
        recently = set((history or {}).get(kind, []))
        fresh = [x for x in pool if x['id'] not in recently]
        if len(fresh) >= count:
            pool = fresh
        if kind in ('notes',):
            return pool[:count]
        return random.Random(key_seed(kind, when)).sample(pool, count)


def draw_card(kind, items, directory, session, demo=False):
    """Create image locally with Pillow. Optional TMDB posters are used only as visual references."""
    w, h = 960, 640
    canvas = Image.new('RGB', (w, h), '#0c172c')
    artwork = items[0].get('profile_path' if kind == 'acteur' else 'poster_path')
    if artwork and not demo:
        try:
            result = session.get(POSTER_URL + artwork, timeout=15)
            result.raise_for_status()
            poster = Image.open(BytesIO(result.content)).convert('RGB')
            canvas.paste(ImageOps.fit(poster, (470, 640)), (490, 0))
        except (requests.RequestException, OSError, ValueError):
            pass
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    painter = ImageDraw.Draw(layer)
    painter.rectangle((0, 0, 675, h), fill=(11, 25, 48, 250))
    painter.rounded_rectangle((36, 35, w-36, h-35), radius=25, outline=(71, 157, 218, 210), width=4)
    painter.rectangle((43, 42, 910, 122), fill=(17, 48, 80, 240))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), layer).convert('RGB')
    d = ImageDraw.Draw(canvas)
    normal = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    f1 = ImageFont.truetype(bold, 43) if Path(bold).exists() else ImageFont.load_default()
    f2 = ImageFont.truetype(normal, 26) if Path(normal).exists() else ImageFont.load_default()
    headings = {'series': 'LES SÉRIES DU MOMENT', 'notes': 'FILMS LES MIEUX NOTÉS',
                'pepites': 'PÉPITES CINÉMA', 'acteur': 'ACTEUR DU JOUR'}
    d.text((73, 65), 'CINÉMA • MR XPRONOS', font=f2, fill='#77c5ec')
    d.text((73, 156), headings[kind], font=f1, fill='#f5d477')
    labels = [items[0]['name']] if kind == 'acteur' else [m['title'] for m in items[:5]]
    for i, label in enumerate(labels):
        d.text((73, 270 + i*58), compact(label, 26), font=f2, fill='#f3f7ff')
    d.text((73, 553), 'TEST • FICTION' if demo else 'SÉLECTION CINÉMA', font=f2, fill='#77c5ec')
    output = directory / f'{kind}.jpg'
    canvas.save(output, 'JPEG', quality=89)
    return output


def poll_payload(items, chat):
    if len(items) < 2:
        raise ValueError('Two movies required for a Telegram poll')
    options = [{'text': compact(x['title'], 90)} for x in items[:4]]
    return {'chat_id': chat, 'question': '🗳️ CINÉMA : Quel film préfères-tu ?',
            'options': options, 'type': 'regular', 'is_anonymous': True,
            'allows_multiple_answers': False}


def publish(kind, items, chat, token, session, when, demo=False, dry_run=False):
    if kind == 'sondage':
        data = poll_payload(items, chat)
        if dry_run:
            print(json.dumps({'format': kind, 'method': 'sendPoll', 'payload': data}, ensure_ascii=False))
            return None
        return base.call_telegram(session, token, 'sendPoll', data)['message_id']
    html, buttons = caption(kind, items, when, demo)
    if dry_run:
        print(json.dumps({'format': kind, 'html': html, 'buttons': buttons}, ensure_ascii=False))
        return None
    with tempfile.TemporaryDirectory() as directory:
        image = draw_card(kind, items, Path(directory), session, demo)
        return base.post_photo(session, token, chat, image, html, {'inline_keyboard': buttons}, mime='image/jpeg')


def run(argv=None):
    p = argparse.ArgumentParser(description='Cinéma Telegram : formats 6 à 10')
    p.add_argument('--mode', choices=['test', 'production'], default='test')
    p.add_argument('--format', choices=(*FORMATS, 'all'), default='all')
    p.add_argument('--demo', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--date', default=date.today().isoformat())
    p.add_argument('--force', action='store_true')
    a = p.parse_args(argv)
    now = date.fromisoformat(a.date)
    if a.mode == 'production' and a.demo:
        p.error('Démonstrations fictives interdites en production')
    if a.mode == 'production' and not a.dry_run and os.getenv('CINEMA_PRODUCTION_ENABLED') != 'true':
        p.error('Production inactive, CINEMA_PRODUCTION_ENABLED doit valoir true')
    chat = base.target_chat(a.mode)
    token = os.getenv('CINEMA_TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    if not a.dry_run and (not token or not chat):
        p.error('Token/canal manquant, envoi annulé')
    if not a.dry_run:
        sports = {x for x in [os.getenv('TELEGRAM_CHAT_ID'), os.getenv('TELEGRAM_CHAT_ID_SECONDARY')] if x}
        if chat in sports:
            p.error('Canal cinéma égal à un canal de pronostics: interdit')
    if not a.demo and not os.getenv('TMDB_API_KEY'):
        p.error('TMDB_API_KEY requis (ou --demo --dry-run)')
    state_file = ROOT / 'cinema' / ('sent_test_batch2.json' if a.mode == 'test' else 'sent_production_batch2.json')
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        records = json.loads(state_file.read_text('utf-8')) if state_file.exists() else {}
    except (ValueError, OSError) as exc:
        raise RuntimeError('Historique illisible ; ne rien publier avant réparation') from exc
    session = requests.Session()
    if a.mode == 'test' and not a.dry_run:
        base.verify_test_bot(session, token, chat)
    api = None if a.demo else API(os.getenv('TMDB_API_KEY'), session)
    kinds = FORMATS if a.format == 'all' else (a.format,)
    for kind in kinds:
        state_key = f'{now}:{kind}'
        if not a.force and not a.dry_run and state_key in records:
            print('SKIP_DUPLICATE', state_key)
            continue
        if a.demo:
            items = [MOCK_ACTOR] if kind == 'acteur' else (MOCK_SERIES if kind == 'series' else MOCK_MOVIES)
        else:
            recent = {}
            for k, record in records.items():
                if k.endswith(':' + kind) and isinstance(record, dict):
                    recent.setdefault(kind, []).extend(record.get('ids', []))
            items = api.pick(kind, now, recent)
        if kind == 'sondage' and len(items) < 2:
            raise RuntimeError('Not enough poll options')
        mid = publish(kind, items, chat, token, session, now, a.demo, a.dry_run)
        if not a.dry_run:
            records[state_key] = {'message_id': mid, 'chat_id': chat,
                                  'ids': [int(x['id']) for x in items],
                                  'utc': datetime.now(timezone.utc).isoformat()}
            temp = state_file.with_suffix('.tmp')
            temp.write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
            os.replace(temp, state_file)
            print('POSTED', kind, mid)
    return 0


if __name__ == '__main__':
    sys.exit(run())