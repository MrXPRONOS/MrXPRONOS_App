#!/usr/bin/env python3
"""Cinema Telegram: 5 formats, free TMDB data, rich Telegram, test-first."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

import requests
try:
    from telegram_rich import post_photo, post_text
except ModuleNotFoundError:
    from scripts.telegram_rich import post_photo, post_text

ROOT = Path(__file__).resolve().parents[1]
FORMATS = ('film', 'top5', 'sorties', 'soir', 'quiz')
# Canal de test explicitement désigné; aucun fallback vers un canal des pronostics.
TEST_CHANNEL = '@predict_mrxp'
TMDB = 'https://api.themoviedb.org/3'
IMG = 'https://image.tmdb.org/t/p/w780'
# Only use unaltered official TMDB image files; never render a new illustration.
ATTRIBUTION = 'This product uses the TMDB API but is not endorsed or certified by TMDB.'
QUIZZES = [
    ('Dans quel film apparaît le personnage Jack Dawson ?', ['Titanic', 'Avatar', 'Inception', 'Gladiator'], 0,
     'Jack Dawson est un personnage du film Titanic (1997).'),
    ('Qui a réalisé le film Inception (2010) ?', ['Steven Spielberg', 'Christopher Nolan', 'James Cameron', 'Ridley Scott'], 1,
     'Inception est réalisé par Christopher Nolan.'),
    ('Quel film met en scène le personnage de Simba ?', ['Madagascar', 'Le Roi lion', 'Shrek', 'Toy Story'], 1,
     'Simba est le personnage principal du Roi lion.'),
    ('Dans quelle saga trouve-t-on Dark Vador ?', ['Star Wars', 'Matrix', 'Harry Potter', 'Avatar'], 0,
     'Dark Vador est un personnage de Star Wars.'),
    ('Quel acteur interprète Forrest Gump ?', ['Tom Hanks', 'Tom Cruise', 'Brad Pitt', 'Will Smith'], 0,
     'Tom Hanks joue Forrest Gump dans le film de 1994.'),
]
DEMO = [
    {'id': 1001, 'title': 'Film de démonstration Alpha', 'overview': 'Synopsis fictif pour tester la mise en page Telegram.', 'release_date': '2025-01-01', 'vote_average': 7.9, 'vote_count': 440, 'poster_path': None},
    {'id': 1002, 'title': 'Film de démonstration Bravo', 'overview': 'Un deuxième exemple sans données externes.', 'release_date': '2025-05-03', 'vote_average': 7.2, 'vote_count': 230, 'poster_path': None},
    {'id': 1003, 'title': 'Film de démonstration Charlie', 'overview': 'Une aventure imaginaire réservée aux tests.', 'release_date': '2026-11-02', 'vote_average': 8.1, 'vote_count': 510, 'poster_path': None},
    {'id': 1004, 'title': 'Film de démonstration Delta', 'overview': 'Un scénario fictif.', 'release_date': '2026-11-15', 'vote_average': 7.4, 'vote_count': 140, 'poster_path': None},
    {'id': 1005, 'title': 'Film de démonstration Echo', 'overview': 'Une cinquième fiche fictive.', 'release_date': '2026-12-01', 'vote_average': 8.0, 'vote_count': 280, 'poster_path': None},
]


def short(value, limit=280):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= limit else value[:limit - 1].rsplit(' ', 1)[0] + '…'


def title(movie):
    return escape(short(movie.get('title') or 'Film sans titre', 100))


def link(movie, demo=False):
    return 'https://www.themoviedb.org/' if demo else f"https://www.themoviedb.org/movie/{int(movie['id'])}"


def score(movie):
    n = float(movie.get('vote_average') or 0)
    return f'{n:.1f}/10' if n else 'Non noté'


def year(movie):
    return str(movie.get('release_date') or '—')[:4]


def description(movie):
    return escape(short(movie.get('overview') or 'Synopsis indisponible pour le moment.', 350))


def footer(demo):
    return '<p><i>' + ('🧪 DÉMONSTRATION — données fictives.' if demo else escape(ATTRIBUTION)) + '</i></p>'


def button(url, label='🎬 Voir la fiche du film'):
    return [[{'text': label, 'url': url, 'style': 'primary'}]]


def render(kind, movies, today, demo=False):
    """Return (HTML body, one-button-per-row keyboard, featured movie)."""
    if kind == 'quiz':
        raise ValueError('Quiz is sent with native sendPoll, not a fake callback button')
    first = movies[0]
    name = title(first)
    if kind == 'film':
        body = (f'<h3>🎬 LE FILM DU JOUR</h3><p><b>{name}</b> · {year(first)}</p>'
                f'<p>⭐ <b>{score(first)}</b></p><blockquote>{description(first)}</blockquote>'
                '<p><i>🍿 Une découverte à ajouter à ta liste de films.</i></p>')
        keyboard = button(link(first, demo))
    elif kind == 'top5':
        ranking = ''.join(f'<p><b>{i}.</b> {title(m)} ({year(m)}) · ⭐ {score(m)}</p>'
                          for i, m in enumerate(movies[:5], 1))
        body = ('<h3>🔥 TOP 5 DES FILMS À DÉCOUVRIR</h3>'
                '<p><i>Notre sélection de cinq films parmi les tendances.</i></p>'
                + ranking + '<blockquote>Lequel veux-tu regarder en premier ?</blockquote>')
        keyboard = button(link(first, demo), '🥇 Découvrir le numéro 1')
    elif kind == 'sorties':
        rows = ''.join(f'<p>🗓 <b>{escape(str(m.get("release_date") or "Date à confirmer"))}</b> — {title(m)}</p>'
                       for m in movies[:5])
        body = ('<h3>🆕 LES PROCHAINES SORTIES CINÉMA</h3>'
                '<p><i>Dates indicatives, variables selon les pays.</i></p>'
                + rows + '<blockquote>Quel film attends-tu le plus ?</blockquote>')
        keyboard = button(link(first, demo), '🎞 Explorer la première sortie')
    elif kind == 'soir':
        body = (f'<h3>🍿 TON FILM POUR CE SOIR</h3><p><b>{name}</b> · {year(first)}</p>'
                f'<p>⭐ Note du public : <b>{score(first)}</b></p>'
                f'<blockquote>{description(first)}</blockquote>'
                '<p><i>Prends une pause et profite de ta soirée cinéma !</i></p>')
        keyboard = button(link(first, demo), '🌙 Consulter ce film')
    else:
        raise ValueError('Format inconnu : ' + kind)
    body += footer(demo)
    return body, keyboard, first


class TMDBClient:
    def __init__(self, api_key, session=None):
        if not api_key:
            raise ValueError('TMDB_API_KEY absent. Utiliser --demo seulement pour les tests.')
        self.api_key = api_key
        self.session = session or requests.Session()

    def get(self, endpoint, **params):
        response = self.session.get(TMDB + endpoint, params={'api_key': self.api_key,
                                     'language': 'fr-FR', **params}, timeout=25)
        response.raise_for_status()
        data = response.json()
        return [m for m in data.get('results', []) if m.get('id') and m.get('title')]

    def choose(self, kind, today):
        if kind in ('film', 'top5', 'soir'):
            films = self.get('/trending/movie/week')
            if kind == 'soir':
                filtered = [m for m in films if float(m.get('vote_average') or 0) >= 6.5 and
                            int(m.get('vote_count') or 0) >= 100]
                films = filtered or films
        elif kind == 'sorties':
            films = self.get('/movie/upcoming', region='FR')
            films = [m for m in films if str(m.get('release_date') or '') >= today.isoformat()]
            films.sort(key=lambda m: m.get('release_date') or '9999')
        else:
            raise ValueError(kind)
        if kind != 'quiz':
            films = [m for m in films if valid_tmdb_path(m.get('poster_path'))]
        if not films:
            raise RuntimeError(f'Aucun film exploitable pour {kind}; publication ignorée.')
        seed = int(hashlib.sha256(f'{kind}:{today.isoformat()}'.encode()).hexdigest()[:8], 16)
        if kind in ('film', 'soir'):
            return [films[seed % len(films)]]
        if kind == 'top5':
            return random.Random(seed).sample(films, min(5, len(films)))
        return films[:5]


def valid_tmdb_path(path):
    """Only accept a path from TMDB, never an arbitrary external URL."""
    return bool(isinstance(path, str) and re.fullmatch(r"/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png)", path, re.I))


def download_source_image(items, session, folder, *, person=False):
    """Download official TMDB image bytes as-is; no drawing, cropping or overlays.

    Return (file_path, mime_type), or (None, None) when TMDB provides no image.
    For rankings the image is the official poster of the first available title.
    """
    field = 'profile_path' if person else 'poster_path'
    source = next((item[field] for item in items if valid_tmdb_path(item.get(field))), None)
    if not source:
        print('SOURCE_IMAGE_MISSING', field)
        return None, None
    response = session.get(IMG + source, timeout=25)
    response.raise_for_status()
    data = response.content
    if data.startswith(b'\xff\xd8\xff'):
        ext, mime = '.jpg', 'image/jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        ext, mime = '.png', 'image/png'
    else:
        raise ValueError('TMDB image is not a supported original JPEG/PNG')
    if not 100 < len(data) <= 9_000_000:
        raise ValueError('TMDB image size is invalid or too large')
    path = folder / ('tmdb_original' + ext)
    path.write_bytes(data)  # Exact bytes received from the image provider.
    print('SOURCE_IMAGE_TMDB', source, len(data), mime)
    return path, mime


def call_telegram(session, token, method, payload):
    resp = session.post(f'https://api.telegram.org/bot{token}/{method}', json=payload, timeout=40)
    resp.raise_for_status()
    body = resp.json()
    if not body.get('ok'):
        raise RuntimeError('Réponse Telegram non valide : ' + method)
    return body['result']


def target_chat(mode):
    return TEST_CHANNEL if mode == 'test' else os.getenv('CINEMA_PRODUCTION_CHAT_ID')


def verify_test_bot(session, token, chat):
    """Ne rien envoyer si le bot ne peut pas publier dans le canal dédié."""
    if chat != TEST_CHANNEL:
        raise RuntimeError('Canal de test inattendu : envoi refusé')
    me = call_telegram(session, token, 'getMe', {})
    user_id = me.get('id')
    if not user_id:
        raise RuntimeError('Impossible de vérifier le bot Telegram')
    member = call_telegram(session, token, 'getChatMember',
                           {'chat_id': chat, 'user_id': user_id})
    if member.get('status') not in ('administrator', 'creator'):
        raise RuntimeError('Le bot doit être administrateur de ' + TEST_CHANNEL)
    if member.get('can_post_messages') is False:
        raise RuntimeError('Le bot ne possède pas le droit de publier dans ' + TEST_CHANNEL)
    print('TEST_CHANNEL_VERIFIED', TEST_CHANNEL)


def publish(kind, movies, token, chat, today, session, demo=False, dry_run=False):
    if kind == 'quiz':
        index = int(hashlib.sha256(today.isoformat().encode()).hexdigest()[:8], 16) % len(QUIZZES)
        question, options, correct, explanation = QUIZZES[index]
        data = {'chat_id': chat, 'type': 'quiz', 'question': '🧠 QUIZ CINÉMA — ' + question,
                'options': [{'text': option} for option in options], 'correct_option_id': correct, 'explanation': explanation,
                'is_anonymous': True}
        if dry_run:
            print(json.dumps({'type': kind, 'method': 'sendPoll', 'preview': data}, ensure_ascii=False))
            return None
        return call_telegram(session, token, 'sendPoll', data)['message_id']
    body, keyboard, _ = render(kind, movies, today, demo)
    if dry_run:
        print(json.dumps({'type': kind, 'html': body, 'buttons': keyboard}, ensure_ascii=False))
        return None
    if demo:
        # Fictional demonstrations do not have real posters: text-only, never invented images.
        return post_text(session, token, chat, body, {'inline_keyboard': keyboard}, html=True)
    with tempfile.TemporaryDirectory() as tmp:
        image, mime = download_source_image(movies, session, Path(tmp))
        if image is None:
            return post_text(session, token, chat, body, {'inline_keyboard': keyboard}, html=True)
        return post_photo(session, token, chat, image, body, {'inline_keyboard': keyboard}, mime=mime)


def main(argv=None):
    p = argparse.ArgumentParser(description='5 publications cinéma Telegram — série 1/3')
    p.add_argument('--mode', choices=['test', 'production'], default='test')
    p.add_argument('--format', choices=[*FORMATS, 'all'], default='all')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--demo', action='store_true', help='Données fictives, tests uniquement')
    p.add_argument('--date', default=date.today().isoformat())
    p.add_argument('--force', action='store_true', help='Republier volontairement le même format du jour')
    args = p.parse_args(argv)
    today = date.fromisoformat(args.date)
    if args.mode == 'production' and args.demo:
        p.error('Mode --demo interdit en production')
    if args.mode == 'production' and os.getenv('CINEMA_PRODUCTION_ENABLED') != 'true' and not args.dry_run:
        p.error('Production désactivée : CINEMA_PRODUCTION_ENABLED doit valoir true')
    token = os.getenv('CINEMA_TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    # Canal de test dédié et fixe: le workflow et les secrets ne peuvent pas le rediriger.
    chat = target_chat(args.mode)
    if not args.dry_run and (not token or not chat):
        p.error('Bot token ou chat ID dédié manquant; aucun envoi effectué')
    if args.mode == 'test' and not args.dry_run:
        prohibited = {os.getenv('TELEGRAM_CHAT_ID'), os.getenv('TELEGRAM_CHAT_ID_SECONDARY')}
        if chat in {x for x in prohibited if x}:
            p.error('Le canal de test correspond à un canal de pronostics : envoi BLOQUÉ')
    if args.mode == 'production' and not args.dry_run and chat == os.getenv('TELEGRAM_CHAT_ID'):
        p.error('Le canal cinéma correspond au canal principal de pronostics : envoi BLOQUÉ')
    if args.demo is False and args.format != 'quiz' and not os.getenv('TMDB_API_KEY'):
        p.error('TMDB_API_KEY manquant ; pour un aperçu sans clé, ajouter --demo --dry-run')
    tmdb = None if args.demo or args.format == 'quiz' else TMDBClient(os.getenv('TMDB_API_KEY'))
    state_path = ROOT / 'cinema' / ('sent_test.json' if args.mode == 'test' else 'sent_production.json')
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(state_path.read_text('utf-8')) if state_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        raise RuntimeError('Historique invalide : correction manuelle nécessaire avant publication')
    kinds = FORMATS if args.format == 'all' else (args.format,)
    session = requests.Session()
    if args.mode == 'test' and not args.dry_run:
        verify_test_bot(session, token, chat)
    for kind in kinds:
        key = f'{today.isoformat()}:{kind}'
        if not args.dry_run and not args.force and key in state:
            print('SKIP_DOUBLON', key)
            continue
        films = [] if kind == 'quiz' else (([m for m in DEMO if (m.get('release_date') or '') >= today.isoformat()] or DEMO[-3:]
                                          if kind == 'sorties' else DEMO) if args.demo else tmdb.choose(kind, today))
        print('FORMAT', kind, 'MODE', args.mode, 'DEMO', args.demo, 'DATE', today)
        mid = publish(kind, films, token, chat, today, session, args.demo, args.dry_run)
        if not args.dry_run:
            state[key] = {'message_id': mid, 'chat_id': chat, 'utc': datetime.now(timezone.utc).isoformat()}
            temp = state_path.with_suffix('.tmp')
            temp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            os.replace(temp, state_path)
            print('SENT', kind, mid)
    return 0


if __name__ == '__main__':
    sys.exit(main())