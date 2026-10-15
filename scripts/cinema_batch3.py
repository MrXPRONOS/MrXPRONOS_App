#!/usr/bin/env python3
"""Formats cinéma 11-15 pour Telegram, données et médias TMDB authentiques.

Aucune image générée, composée, recadrée ou retouchée. Les visuels restent
les octets fournis par TMDB. Les votes utilisent l'API de sondage native.
"""
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
import cinema_telegram as base

ROOT = Path(__file__).resolve().parents[1]
FORMATS = ('duel', 'anecdote', 'boxoffice', 'bandeannonce', 'weekend')
GENRES = ((28, 'Action'), (35, 'Comédie'), (18, 'Drame'),
          (878, 'Science-fiction'), (53, 'Thriller'), (10749, 'Romance'))
DEMO_MOVIES = [
    {'id': 1001, 'title': 'Film test Alpha', 'poster_path': None, 'release_date': '2025-01-01', 'vote_average': 8.0, 'genre_ids': [28]},
    {'id': 1002, 'title': 'Film test Bravo', 'poster_path': None, 'release_date': '2025-03-03', 'vote_average': 7.8, 'genre_ids': [35]},
    {'id': 1003, 'title': 'Film test Charlie', 'poster_path': None, 'release_date': '2025-06-09', 'vote_average': 7.5, 'genre_ids': [18]},
    {'id': 1004, 'title': 'Film test Delta', 'poster_path': None, 'release_date': '2025-08-12', 'vote_average': 7.1, 'genre_ids': [878]},
]


def safe(value, limit=130):
    """All strings from metadata must be HTML escaped before markup creation."""
    return escape(base.short(value, limit), quote=False)


def stable_seed(kind, when):
    return int(hashlib.sha256(f'{kind}:{when.isoformat()}'.encode()).hexdigest()[:8], 16)


def movie_link(movie, demo=False):
    return 'https://www.themoviedb.org/' if demo else f"https://www.themoviedb.org/movie/{int(movie['id'])}"


def action(label, url, style='primary'):
    if not re.fullmatch(r'https://[^\s]+', url):
        raise ValueError('Lien du bouton non sécurisé')
    return [{'text': label, 'url': url, 'style': style}]


def source_buttons(movies, *, demo=False, labels=None):
    # One button per row, so Telegram can use its available horizontal space.
    return [action((labels[i] if labels else f'🎬 Voir le film {i+1}'), movie_link(m, demo))
            for i, m in enumerate(movies)]


def attribution(demo):
    return base.footer(demo)


def dollars(value):
    number = int(value)
    if number <= 0:
        raise ValueError('Montant des recettes non disponible')
    return f'{number:,}'.replace(',', ' ') + ' $'


class TMDB:
    def __init__(self, api_key, session=None):
        if not api_key:
            raise ValueError('TMDB_API_KEY absent ; aucune donnée cinéma réelle disponible')
        self.api_key = api_key
        self.session = session or requests.Session()

    def get(self, endpoint, **params):
        if not endpoint.startswith('/') or '://' in endpoint:
            raise ValueError('Chemin TMDB invalide')
        response = self.session.get(base.TMDB + endpoint,
                                    params={'api_key': self.api_key, 'language': 'fr-FR', **params},
                                    timeout=25)
        response.raise_for_status()
        return response.json()

    def trending(self):
        results = self.get('/trending/movie/week').get('results', [])
        return [m for m in results if m.get('id') and m.get('title') and not m.get('adult')
                and base.valid_tmdb_path(m.get('poster_path'))]

    def pick(self, kind, when, history=None):
        history = set(history or ())
        if kind in ('duel', 'anecdote', 'bandeannonce', 'weekend'):
            pool = self.trending()
            fresh = [m for m in pool if m['id'] not in history]
            if len(fresh) >= 4:
                pool = fresh
            if not pool:
                raise RuntimeError('TMDB n’a retourné aucun film avec affiche source')
            pool = random.Random(stable_seed(kind, when)).sample(pool, len(pool))
            if kind == 'duel':
                if len(pool) < 2:
                    raise RuntimeError('Deux films avec affiche source sont nécessaires au duel')
                return {'items': pool[:2]}
            if kind == 'anecdote':
                # A verifiable cinema fact, derived from credited crew; never invent a story.
                for movie in pool[:12]:
                    details = self.get(f"/movie/{int(movie['id'])}/credits")
                    directors = [p.get('name') for p in details.get('crew', [])
                                 if p.get('job') == 'Director' and p.get('name')]
                    if directors:
                        return {'items': [movie], 'directors': directors[:3]}
                raise RuntimeError('Aucun réalisateur vérifiable dans les crédits TMDB')
            if kind == 'bandeannonce':
                for movie in pool[:15]:
                    # Trailer official flag is provider metadata; don't infer official status.
                    clips = self.get(f"/movie/{int(movie['id'])}/videos").get('results', [])
                    clips += self.get(f"/movie/{int(movie['id'])}/videos", language='en-US').get('results', [])
                    videos = [v for v in clips if v.get('site') == 'YouTube'
                              and v.get('type') == 'Trailer' and v.get('official') is True
                              and re.fullmatch(r'[a-zA-Z0-9_-]{11}', str(v.get('key') or ''))]
                    if videos:
                        video = videos[0]
                        return {'items': [movie], 'video_url': 'https://www.youtube.com/watch?v=' + video['key'],
                                'video_name': video.get('name') or ''}
                raise RuntimeError('Aucune bande-annonce officielle YouTube vérifiée par TMDB')
            # weekend: one different genre per recommendation, with source posters.
            selected = []
            seen = set()
            for genre_id, genre_name in GENRES:
                choice = next((m for m in pool if genre_id in (m.get('genre_ids') or [])
                               and m['id'] not in seen), None)
                if choice:
                    selected.append(dict(choice, editorial_genre=genre_name))
                    seen.add(choice['id'])
                if len(selected) == 4:
                    break
            if len(selected) < 3:
                raise RuntimeError('Pas assez de genres différents pour le week-end')
            return {'items': selected}
        if kind == 'boxoffice':
            # This is NOT a weekly box-office chart. TMDB movie detail 'revenue'
            # supplies cumulative global receipts, when populated by providers.
            pool = self.get('/movie/now_playing', region='FR', page=1).get('results', [])
            pool += self.get('/movie/now_playing', region='FR', page=2).get('results', [])
            eligible = [m for m in pool if m.get('id') and m.get('title') and
                        base.valid_tmdb_path(m.get('poster_path')) and not m.get('adult')]
            unique = {int(m['id']): m for m in eligible}
            receipts = []
            for movie in list(unique.values())[:35]:
                details = self.get(f"/movie/{int(movie['id'])}")
                value = details.get('revenue')
                if isinstance(value, int) and value > 0:
                    receipts.append(dict(movie, revenue=value))
            receipts.sort(key=lambda m: m['revenue'], reverse=True)
            if not receipts:
                raise RuntimeError('Aucune recette cumulée valide déclarée dans TMDB')
            return {'items': receipts[:5]}
        raise ValueError(f'Format non reconnu : {kind}')


def demo_selection(kind):
    if kind == 'anecdote':
        return {'items': DEMO_MOVIES[:1], 'directors': ['Réalisateur fictif']}
    if kind == 'bandeannonce':
        return {'items': DEMO_MOVIES[:1], 'video_url': 'https://www.themoviedb.org/',
                'video_name': 'Aperçu fictif (aucune bande-annonce réelle)'}
    if kind == 'boxoffice':
        return {'items': [dict(m, revenue=(5-i)*10_000_000) for i, m in enumerate(DEMO_MOVIES)]}
    return {'items': DEMO_MOVIES[:2] if kind == 'duel' else DEMO_MOVIES}


def render(kind, selection, when, demo=False):
    """Return HTML and vertical one-button-per-row rich keyboard."""
    items = selection['items']
    if not items:
        raise ValueError('Aucun contenu à publier')
    if kind == 'duel':
        if len(items) != 2:
            raise ValueError('Le duel nécessite exactement deux films')
        html = ('<h3>⚔️ DUEL CINÉMA</h3><p><i>Deux films, un seul favori !</i></p>'
                f'<p>🎬 <b>A — {safe(items[0]["title"])}</b></p>'
                f'<p>🎞 <b>B — {safe(items[1]["title"])}</b></p>'
                '<blockquote>Vote dans le sondage qui accompagne cette publication.</blockquote>')
        buttons = source_buttons(items, demo=demo, labels=['🎬 Découvrir le film A', '🎬 Découvrir le film B'])
    elif kind == 'anecdote':
        movie = items[0]
        names = ', '.join(safe(n, 100) for n in selection['directors'])
        html = ('<h3>🎥 LE SAVAIS-TU ?</h3><p><b>' + safe(movie['title']) + '</b></p>'
                '<blockquote>🎬 Ce film est crédité à la réalisation de <b>' + names + '</b>.</blockquote>'
                '<p><i>Une information issue des crédits du film, pas une anecdote inventée.</i></p>')
        buttons = source_buttons(items, demo=demo, labels=['🔍 Vérifier la fiche du film'])
    elif kind == 'boxoffice':
        lines = ''.join(f'<p><b>{i}. {safe(m["title"], 75)}</b> — {dollars(m["revenue"])}</p>'
                        for i, m in enumerate(items[:5], 1))
        html = ('<h3>🏆 BOX-OFFICE — RECETTES CUMULÉES</h3>'
                '<p><i>Sélection de films à l’affiche en France, classés selon les recettes mondiales cumulées indiquées dans TMDB. '
                'Ce n’est pas un classement hebdomadaire des entrées.</i></p>' + lines
                + '<blockquote>💵 Données indicatives et parfois incomplètes. Devise : USD.</blockquote>')
        buttons = source_buttons(items[:1], demo=demo, labels=['🏆 Voir le film en tête de cette sélection'])
    elif kind == 'bandeannonce':
        movie = items[0]
        html = ('<h3>🎞️ BANDE-ANNONCE OFFICIELLE</h3><p><b>' + safe(movie['title']) + '</b>'
                ' · ' + safe(base.year(movie)) + '</p>'
                '<blockquote>📺 Regarde la bande-annonce officielle référencée par TMDB sur YouTube.</blockquote>'
                '<p><i>La vidéo est consultée sur sa plateforme d’origine.</i></p>')
        buttons = [action('▶️ Regarder la bande-annonce', selection['video_url']),
                   action('🎬 Fiche du film', movie_link(movie, demo))]
    elif kind == 'weekend':
        choices = ''.join(f'<p>🍿 <b>{safe(m["editorial_genre"] if "editorial_genre" in m else "Sélection")}</b> : '
                          f'{safe(m["title"])}</p>' for m in items[:4])
        html = ('<h3>🍿 SÉLECTION CINÉMA DU WEEK-END</h3>'
                '<p><i>Quatre ambiances pour choisir ta prochaine séance.</i></p>' + choices
                + '<blockquote>Quel genre te tente ce week-end ?</blockquote>')
        buttons = source_buttons(items[:4], demo=demo)
    else:
        raise ValueError(f'Format non reconnu : {kind}')
    return html + attribution(demo), buttons


def poll_payload(items, chat):
    if len(items) != 2:
        raise ValueError('Le duel doit proposer deux films')
    return {'chat_id': chat, 'type': 'regular', 'is_anonymous': True,
            'question': '⚔️ Quel film remporte ce duel cinéma ?',
            'options': [{'text': base.short(m['title'], 80)} for m in items]}


def publish(kind, selection, chat, token, session, when, *, demo=False,
            dry_run=False, previous=None, on_progress=None):
    """For duel, persist each step to recover safely after a partial Telegram send."""
    html, buttons = render(kind, selection, when, demo)
    prev = dict(previous or {})
    if dry_run:
        print(json.dumps({'format': kind, 'html': html, 'buttons': buttons,
                          'poll': poll_payload(selection['items'], chat) if kind == 'duel' else None,
                          'photo': 'TMDB source only; demo has no image'}, ensure_ascii=False))
        return None
    photo_id = prev.get('photo_message_id')
    if photo_id is None:
        if demo:
            # No invented movie image for fictitious demo data.
            photo_id = base.post_text(session, token, chat, html, {'inline_keyboard': buttons}, html=True)
        else:
            with tempfile.TemporaryDirectory() as temp:
                image, mime = base.download_source_image(selection['items'], session, Path(temp))
                if image is None:
                    raise RuntimeError('Publication annulée : aucune affiche TMDB disponible')
                photo_id = base.post_photo(session, token, chat, image, html,
                                           {'inline_keyboard': buttons}, mime=mime)
        prev['photo_message_id'] = photo_id
        if on_progress:
            on_progress(prev)
    if kind == 'duel':
        if prev.get('poll_message_id') is None:
            poll = base.call_telegram(session, token, 'sendPoll', poll_payload(selection['items'], chat))
            prev['poll_message_id'] = poll['message_id']
            if on_progress:
                on_progress(prev)
    return prev


def run(argv=None):
    parser = argparse.ArgumentParser(description='Cinéma Telegram — troisième série de cinq formats')
    parser.add_argument('--mode', choices=['test', 'production'], default='test')
    parser.add_argument('--format', choices=(*FORMATS, 'all'), default='all')
    parser.add_argument('--demo', action='store_true', help='Données fictives (texte seul), jamais en production')
    parser.add_argument('--dry-run', action='store_true', help='Aucun message envoyé')
    parser.add_argument('--force', action='store_true', help='Rejoue volontairement une publication')
    parser.add_argument('--date', default=date.today().isoformat())
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.date)
    if args.mode == 'production' and args.demo:
        parser.error('Interdit : démonstration fictive en production')
    if args.mode == 'production' and not args.dry_run and os.getenv('CINEMA_PRODUCTION_ENABLED') != 'true':
        parser.error('Production non activée : CINEMA_PRODUCTION_ENABLED=true requis')
    chat = base.target_chat(args.mode)
    token = os.getenv('CINEMA_TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    if not args.dry_run and (not token or not chat):
        parser.error('Bot token ou canal Telegram manquant')
    if not args.dry_run:
        other_chats = {x for x in [os.getenv('TELEGRAM_CHAT_ID'), os.getenv('TELEGRAM_CHAT_ID_SECONDARY')] if x}
        if chat in other_chats:
            parser.error('Ce canal appartient au système de pronostics : envoi bloqué')
    if not args.demo and not os.getenv('TMDB_API_KEY'):
        parser.error('TMDB_API_KEY requis ; utiliser --demo --dry-run pour aperçu hors connexion')
    state_file = ROOT / 'cinema' / ('sent_test_batch3.json' if args.mode == 'test' else 'sent_production_batch3.json')
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
    session = requests.Session()
    if args.mode == 'test' and not args.dry_run:
        base.verify_test_bot(session, token, chat)
    api = None if args.demo else TMDB(os.getenv('TMDB_API_KEY'), session)
    kinds = FORMATS if args.format == 'all' else (args.format,)
    for kind in kinds:
        key = f'{today.isoformat()}:{kind}'
        previous = state.get(key, {})
        if previous.get('done') and not args.dry_run and not args.force:
            print('SKIP_DUPLICATE', key)
            continue
        if args.force:
            previous = {}
        # Preserve the original selection after an interrupted two-step duel.
        if previous.get('selection'):
            selection = previous['selection']
        else:
            recent_ids = {int(identifier) for record in state.values() if isinstance(record, dict)
                          for identifier in record.get('ids', []) if str(identifier).isdigit()}
            selection = demo_selection(kind) if args.demo else api.pick(kind, today, recent_ids)
        print('CINEMA_BATCH3', kind, args.mode, 'demo', args.demo)
        if not args.dry_run and not previous.get('selection'):
            previous['selection'] = selection
            previous['ids'] = [m['id'] for m in selection['items']]
            state[key] = previous
        def save_progress(snapshot):
            state[key] = {**previous, **snapshot, 'chat_id': chat, 'timestamp': datetime.now(timezone.utc).isoformat()}
            temp = state_file.with_suffix('.tmp')
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.replace(temp, state_file)
        result = publish(kind, selection, chat, token, session, today, demo=args.demo,
                         dry_run=args.dry_run, previous=previous, on_progress=save_progress)
        if not args.dry_run:
            save_progress({**(result or {}), 'done': True})
            print('POSTED', kind, result)
    return 0


if __name__ == '__main__':
    sys.exit(run())