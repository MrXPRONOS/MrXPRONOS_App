"""Mr XPRONOS Coupons - bot Telegram avec récompenses XP et coupons cote >= 4.00.

Aucun argent, aucun retrait, aucun pari placé. Coupons fournis par les admins.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from db import Store
from odds import format_coupon

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('couponbot')

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_IDS = {int(v.strip()) for v in os.getenv('ADMIN_IDS', '').split(',') if v.strip().isdigit()}
BOT_NAME = os.getenv('BOT_TITLE', 'Mr XPRONOS Coupons')[:80]
DB_PATH = os.getenv('DB_PATH', './data/coupons_v4.db')
REFERRAL_POINTS = int(os.getenv('REFERRAL_POINTS', '30'))
BONUS_POINTS = int(os.getenv('BONUS_POINTS', '5'))
BONUS_COOLDOWN = int(os.getenv('BONUS_COOLDOWN_HOURS', '2')) * 3600
BONUS_DAILY_CAP = int(os.getenv('BONUS_DAILY_CAP_POINTS', '10'))
SITE_URL = os.getenv('SITE_URL', 'https://mrxpronos.github.io/MrXPRONOS_App/').strip()

try:
    REQUIRED = json.loads(os.getenv('REQUIRED_CHANNELS_JSON', '[]'))
    if not isinstance(REQUIRED, list) or not all(
        isinstance(x, dict) and str(x.get('id', '')).strip() and
        str(x.get('url', '')).startswith('https://t.me/') for x in REQUIRED
    ):
        raise ValueError()
except ValueError as exc:
    raise RuntimeError('REQUIRED_CHANNELS_JSON doit contenir des objets {"id":"@canal", "url":"https://t.me/canal"}') from exc
if not (0 <= REFERRAL_POINTS <= 100000 and 0 < BONUS_POINTS <= BONUS_DAILY_CAP <= 100000
        and BONUS_COOLDOWN > 0):
    raise RuntimeError('Configuration des points invalide')

store = Store(DB_PATH)
MENU = ReplyKeyboardMarkup([
    ['🎟️ Coupons cote 4+', '🎫 Mes coupons'],
    ['🚩 Tâche', '🎁 Bonus'],
    ['⭐ Mes XP', '↗️ Partager'],
    ['✅ Vérifier', '📋 Procédure']
], resize_keyboard=True)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def send(update, message, **kwargs):
    if update.effective_message:
        await update.effective_message.reply_text(message, **kwargs)


async def check_member(bot, channel, uid):
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=uid)
        if member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.OWNER,
                             ChatMemberStatus.ADMINISTRATOR):
            return True
        if member.status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, 'is_member', False))
        return False
    except TelegramError as exc:
        log.warning('Impossible de vérifier le canal %s: %s', channel, exc)
        return None


def required_keyboard():
    rows = [[InlineKeyboardButton(f'📲 Canal {i + 1}', url=c['url'])]
            for i, c in enumerate(REQUIRED)]
    rows.append([InlineKeyboardButton('✅ Vérifier mes abonnements', callback_data='verify')])
    return InlineKeyboardMarkup(rows)


async def gate(update, ctx):
    user = store.user(update.effective_user.id)
    if not user:
        await send(update, 'Commence par /start pour créer ton profil.')
        return False
    if not user['adult_confirmed']:
        await send(update, '🔞 Ces coupons concernent les paris sportifs. Accès réservé aux adultes (18+).\n'
                   'Confirme ton âge uniquement si tu as 18 ans ou plus.',
                   reply_markup=InlineKeyboardMarkup([
                       [InlineKeyboardButton('✅ Je confirme avoir 18 ans ou plus', callback_data='adult_yes')],
                       [InlineKeyboardButton('🚫 Je suis mineur', callback_data='adult_no')]
                   ]))
        return False
    if REQUIRED:
        result = [await check_member(ctx.bot, item['id'], user['id']) for item in REQUIRED]
        if any(r is None for r in result):
            await send(update, '⚠️ Vérification temporairement impossible. Le bot doit être administrateur '
                       'de chaque canal requis.', reply_markup=required_keyboard())
            return False
        if not all(result):
            await send(update, '📲 Rejoins les canaux requis, puis clique sur Vérifier.',
                       reply_markup=required_keyboard())
            return False
    # S'il n'y a aucun canal obligatoire, aucune prime de parrainage n'est versée.
    result = store.verify_requirements(user['id'], REFERRAL_POINTS,
                                       referrals_enabled=bool(REQUIRED))
    if result == 'referral_rewarded':
        await send(update, '✅ Vérification confirmée. Ton parrain a reçu ses XP.')
    return True


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    u = update.effective_user
    referrer = None
    if ctx.args and re.fullmatch(r'ref_\d{1,20}', ctx.args[0]):
        referrer = int(ctx.args[0][4:])
    store.ensure_user(u.id, u.first_name or 'Membre', referrer)
    await send(update,
               f'⚽ Bienvenue sur {BOT_NAME} !\n\n'
               '🎟️ Débloque des coupons de pronostics avec une cote totale de 4.00 ou plus.\n'
               '⭐ Acquiers des XP grâce aux missions, aux bonus et au parrainage vérifié.\n'
               '🎫 Échange tes XP contre des coupons Simple, Pro ou VIP.\n\n'
               '🔞 18+ • Cotes indicatives, susceptibles de changer. Aucun gain garanti.\n'
               'L’utilisation de XP n’est pas un dépôt ni une promesse de revenus.',
               reply_markup=MENU)
    await gate(update, ctx)


async def verify(update, ctx):
    if await gate(update, ctx):
        await send(update, '✅ Accès vérifié ! Tu peux recevoir des XP et accéder aux coupons.', reply_markup=MENU)


async def balance(update, ctx):
    if not await gate(update, ctx):
        return
    u = store.user(update.effective_user.id)
    await send(update, f'⭐ {u["name"]}\n'
               f'Solde : {u["points"]} XP\n'
               f'👥 Filleuls validés : {store.referral_count(u["id"])}\n'
               f'🎫 Coupons débloqués : {len(store.my_coupons(u["id"], limit=1000))}\n\n'
               'Les XP sont des points virtuels, non convertibles en argent.')


async def share(update, ctx):
    if not await gate(update, ctx):
        return
    bot_user = await ctx.bot.get_me()
    uid = update.effective_user.id
    link = f'https://t.me/{bot_user.username}?start=ref_{uid}'
    note = (f'⭐ {REFERRAL_POINTS} XP pour chaque ami qui rejoint tous les canaux requis et '
            'termine la vérification.' if REQUIRED else
            'ℹ️ Parrainage non récompensé actuellement : aucun canal obligatoire configuré.')
    await send(update, f'↗️ Ton lien unique :\n{link}\n\n{note}\n'
               f'👥 Filleuls validés : {store.referral_count(uid)}',
               disable_web_page_preview=True)


async def show_tasks(update, ctx):
    if not await gate(update, ctx):
        return
    all_tasks = store.tasks()
    claimed = store.claimed_task_ids(update.effective_user.id)
    if not all_tasks:
        await send(update, '🚩 Aucune mission disponible actuellement.')
        return
    rows = []
    for task in all_tasks:
        finished = task['id'] in claimed
        rows.append([InlineKeyboardButton(
            f'{"✅" if finished else "📲"} Mission #{task["id"]} : +{task["points"]} XP',
            url=task['url'])])
        if not finished:
            rows.append([InlineKeyboardButton('✔️ Check mission #'+str(task['id']),
                                              callback_data=f'task:{task["id"]}')])
    await send(update, '🚩 Rejoins les canaux ci-dessous, puis clique sur Check pour obtenir des XP.\n'
               f'Terminées : {len(claimed & {t["id"] for t in all_tasks})}/{len(all_tasks)}',
               reply_markup=InlineKeyboardMarkup(rows))


async def task_claim(update, ctx, task_id):
    if not await gate(update, ctx):
        return
    task = store.task(task_id)
    if task is None:
        await send(update, 'Mission indisponible.')
        return
    member = await check_member(ctx.bot, task['chat_id'], update.effective_user.id)
    if member is None:
        await send(update, '⚠️ Impossible de vérifier. Le bot doit être administrateur du canal.')
    elif not member:
        await send(update, '❌ Abonnement non confirmé. Rejoins le canal, puis réessaie.')
    else:
        result = store.claim_task(update.effective_user.id, task_id)
        await send(update, {
            'ok': f'✅ Mission validée : +{task["points"]} XP.',
            'already': '✅ Mission déjà récompensée.',
            'locked': '🔒 Accès non vérifié.',
            'missing': 'Mission indisponible.'
        }[result])


async def bonus(update, ctx):
    if not await gate(update, ctx):
        return
    result, remaining = store.claim_bonus(update.effective_user.id, BONUS_POINTS,
                                          BONUS_COOLDOWN, BONUS_DAILY_CAP)
    if result == 'cooldown':
        hours, rem = divmod(remaining, 3600)
        mins, secs = divmod(rem, 60)
        await send(update, f'⏳ Bonus déjà obtenu. Reviens dans {hours} h {mins} min {secs} s.')
    else:
        await send(update, {
            'ok': f'🎁 Bonus reçu : +{BONUS_POINTS} XP !',
            'daily_cap': '⏸️ Plafond de bonus quotidien atteint (UTC).',
            'locked': '🔒 Vérifie ton accès avant de récupérer un bonus.'
        }[result])


def coupon_list_keyboard(category='ALL', uid=None):
    available = store.available_coupons()
    if category != 'ALL':
        available = [c for c in available if c['category'] == category]
    redeemed = store.redeemed_ids(uid) if uid is not None else set()
    buttons = [[InlineKeyboardButton(f'{"✅" if c["id"] in redeemed else "🎟️"} '
                                     f'#{c["id"]} • {c["category"]} • cote {c["total_odds"]} • {c["cost"]} XP',
                                     callback_data=f'view:{c["id"]}')]
               for c in available[:30]]
    return available, InlineKeyboardMarkup(buttons) if buttons else None


async def coupons(update, ctx, category='ALL'):
    if not await gate(update, ctx):
        return
    available, keyboard = coupon_list_keyboard(category, update.effective_user.id)
    if not available:
        await send(update, '🎟️ Aucun coupon de cote 4.00 ou plus disponible actuellement. '
                   'Les coupons sont publiés par un administrateur.')
        return
    await send(update, f'🎟️ {len(available)} coupon(s) disponibles (cote totale ≥ 4.00)\n'
               'Appuie sur un coupon pour consulter son coût et le débloquer.', reply_markup=keyboard)


async def view_coupon(update, ctx, coupon_id):
    if not await gate(update, ctx):
        return
    uid = update.effective_user.id
    owned = store.owned_coupon(uid, coupon_id)
    if owned:
        await send(update, format_coupon({
            'title': owned['title_snapshot'], 'category': owned['category_snapshot'],
            'total_odds': owned['total_odds_snapshot'],
            'selections_json': owned['selections_snapshot']}))
        return
    c = store.coupon(coupon_id)
    if not c or not c['active'] or c['expires_at'] <= int(datetime.now(timezone.utc).timestamp()) or c['stock'] == 0:
        await send(update, 'Coupon indisponible ou expiré.')
        return
    expiry = datetime.fromtimestamp(c['expires_at'], timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    await send(update, f'🎟️ Coupon #{c["id"]} : {c["title"]}\n'
               f'🏷️ {c["category"]}\n📈 Cote totale indicative : {c["total_odds"]}\n'
               f'⚽ {len(json.loads(c["selections_json"]))} sélection(s)\n'
               f'⭐ Coût : {c["cost"]} XP\n⌛ Disponible jusqu’au {expiry}\n\n'
               'Les cotes varient selon le bookmaker. 18+ • Aucun gain garanti.',
               reply_markup=InlineKeyboardMarkup([
                   [InlineKeyboardButton(f'🔓 Débloquer • {c["cost"]} XP', callback_data=f'redeem:{coupon_id}')]
               ]))


async def redeem(update, ctx, coupon_id):
    if not await gate(update, ctx):
        return
    uid = update.effective_user.id
    result, coupon = store.redeem_coupon(uid, coupon_id)
    if result == 'ok':
        await send(update, f'✅ Coupon #{coupon_id} débloqué !\n\n'+format_coupon(coupon))
    elif result == 'already':
        await view_coupon(update, ctx, coupon_id)
    else:
        await send(update, {
            'insufficient': '⭐ Pas assez de XP. Réalise des missions ou demande ton bonus.',
            'unavailable': 'Coupon expiré, désactivé ou épuisé.',
            'missing': 'Coupon introuvable.',
            'locked': '🔒 Vérification requise.'
        }[result])


async def my_coupons(update, ctx):
    if not await gate(update, ctx):
        return
    items = store.my_coupons(update.effective_user.id)
    if not items:
        await send(update, '🎫 Tu n’as pas encore débloqué de coupon. Ouvre « 🎟️ Coupons cote 4+ ».')
        return
    rows = [[InlineKeyboardButton(f'🎫 #{c["coupon_id"]} • {c["category_snapshot"]} • '
                                  f'cote {c["total_odds_snapshot"]}',
                                  callback_data=f'view:{c["coupon_id"]}')]
            for c in items]
    await send(update, '🎫 Tes coupons (historique). Les anciennes cotes ne sont pas garanties :',
               reply_markup=InlineKeyboardMarkup(rows))


async def info(update, ctx):
    await send(update, '📋 COMMENT ÇA MARCHE ?\n'
               '1️⃣ /start, puis confirme avoir au moins 18 ans.\n'
               '2️⃣ Rejoins les canaux obligatoires et appuie sur ✅ Vérifier.\n'
               '3️⃣ 🚩 Tâche : participe à des missions pour obtenir des XP.\n'
               f'4️⃣ 🎁 Bonus : {BONUS_POINTS} XP toutes les {BONUS_COOLDOWN // 3600} h '
               f'(maximum {BONUS_DAILY_CAP} XP/jour).\n'
               f'5️⃣ ↗️ Partager : {REFERRAL_POINTS} XP par filleul vérifié '
               '(si des canaux obligatoires sont activés).\n'
               '6️⃣ 🎟️ Coupons cote 4+ : utilise les XP pour débloquer un coupon '
               'de cote totale minimale 4.00.\n'
               '7️⃣ 🎫 Mes coupons : retrouve ceux que tu as débloqués.\n\n'
               'Les XP n’ont aucune valeur monétaire et ne sont pas retirables. '
               'Les cotes annoncées sont indicatives et peuvent changer. '
               'Les paris entraînent un risque de perte. 18+ • Joue responsablement.')


async def cancel(update, ctx):
    ctx.user_data.pop('expecting', None)
    await send(update, 'Annulé.', reply_markup=MENU)


async def on_text(update, ctx):
    if update.effective_chat.type != 'private':
        return
    u = update.effective_user
    store.ensure_user(u.id, u.first_name or 'Membre')
    key = (update.effective_message.text or '').strip()
    actions = {
        '🎟️ Coupons cote 4+': coupons, '🎫 Mes coupons': my_coupons,
        '🚩 Tâche': show_tasks, '🎁 Bonus': bonus, '⭐ Mes XP': balance,
        '↗️ Partager': share, '✅ Vérifier': verify, '📋 Procédure': info,
    }
    if key in actions:
        await actions[key](update, ctx)
    else:
        await send(update, 'Commande inconnue. Utilise le menu ou /start.', reply_markup=MENU)


async def on_callback(update, ctx):
    q = update.callback_query
    await q.answer()
    if update.effective_chat.type != 'private':
        return
    if q.data == 'adult_yes':
        if not store.user(update.effective_user.id):
            await send(update, 'Envoie /start d’abord.')
            return
        store.confirm_adult(update.effective_user.id)
        await verify(update, ctx)
    elif q.data == 'adult_no':
        await send(update, '🚫 Accès aux coupons de paris sportifs refusé aux mineurs.')
    elif q.data == 'verify':
        await verify(update, ctx)
    elif q.data.startswith('task:') and q.data[5:].isdigit():
        await task_claim(update, ctx, int(q.data[5:]))
    elif q.data.startswith('view:') and q.data[5:].isdigit():
        await view_coupon(update, ctx, int(q.data[5:]))
    elif q.data.startswith('redeem:') and q.data[7:].isdigit():
        await redeem(update, ctx, int(q.data[7:]))


async def admin_command(update, ctx):
    if update.effective_chat.type != 'private':
        return
    if not is_admin(update.effective_user.id):
        await send(update, 'Accès administrateur réservé.')
        return
    command = update.effective_message.text.split()[0].split('@')[0].lower()
    raw = update.effective_message.text.partition(' ')[2].strip()
    args = ctx.args
    try:
        if command == '/addcoupon':
            # Format: CAT | XP | FIN_UTC | STOCK | TITRE | MATCH ; MARCHE ; COTE [ | ...]
            parts = [x.strip() for x in raw.split('|')]
            if len(parts) < 6:
                raise ValueError('Format : /addcoupon PRO | 50 | 2026-10-30T18:00 | -1 | '
                                 'Coupon soir | Arsenal - Chelsea ; Plus de 1,5 buts ; 1.70 | '
                                 'Milan - Napoli ; Double chance 1X ; 2.40')
            cat, cost_raw, expiry_raw, stock_raw, title, *selection_parts = parts
            if not cost_raw.isdecimal() or not re.fullmatch(r'-1|\d+', stock_raw):
                raise ValueError('XP doit être positif ou nul, stock entier positif ou -1 (illimité).')
            try:
                expiry = int(datetime.strptime(expiry_raw, '%Y-%m-%dT%H:%M')
                             .replace(tzinfo=timezone.utc).timestamp())
            except ValueError as exc:
                raise ValueError('Date UTC au format 2026-10-30T18:00.') from exc
            selections = []
            for part in selection_parts:
                cols = [x.strip() for x in part.split(';')]
                if len(cols) != 3:
                    raise ValueError('Chaque sélection doit être : Match ; Marché ; Cote')
                selections.append({'match': cols[0], 'market': cols[1], 'odd': cols[2]})
            coupon_id = store.add_coupon(cat, title, selections, int(cost_raw), expiry, int(stock_raw))
            c = store.coupon(coupon_id)
            out = (f'✅ Coupon #{coupon_id} ajouté !\nCote combinée : {c["total_odds"]} '
                   f'(≥ 4.00)\nCatégorie : {cat.upper()}\nCoût : {cost_raw} XP\n'
                   f'Sélections : {len(selections)}')
        elif command == '/listcoupons':
            coupons_list = store.all_coupons()
            out = '\n'.join(f'#{c["id"]} {c["category"]} cote {c["total_odds"]} '
                            f'{c["cost"]}XP actif={bool(c["active"])} stock={c["stock"]}'
                            for c in coupons_list) or 'Aucun coupon.'
        elif command in ('/delcoupon', '/activatecoupon'):
            if len(args) != 1 or not args[0].isdecimal():
                raise ValueError('Usage : /delcoupon 1 ou /activatecoupon 1')
            activate = command == '/activatecoupon'
            exists = store.set_coupon_active(int(args[0]), activate)
            out = ('✅ Coupon activé.' if activate else '✅ Coupon désactivé.') if exists else 'Coupon inconnu.'
        elif command == '/addtask':
            if len(args) != 3 or not args[2].isdecimal():
                raise ValueError('Usage : /addtask @canal https://t.me/canal 15')
            chat_id, url, points = args[0], args[1], int(args[2])
            if not url.startswith('https://t.me/'):
                raise ValueError('Lien Telegram requis.')
            myself = await ctx.bot.get_me()
            role = await ctx.bot.get_chat_member(chat_id, myself.id)
            if role.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                raise ValueError('Le bot doit être admin du canal.')
            id_ = store.add_task(chat_id, url, points)
            out = f'✅ Mission #{id_} créée : {points} XP.'
        elif command == '/deltask':
            if len(args) != 1 or not args[0].isdecimal():
                raise ValueError('Usage : /deltask 1')
            out = '✅ Mission désactivée.' if store.disable_task(int(args[0])) else 'Mission inconnue.'
        elif command == '/listtasks':
            out = ('\n'.join(f'#{t["id"]} {t["chat_id"]} {t["points"]} XP' for t in store.tasks())
                   or 'Aucune mission.')
        elif command == '/grantxp':
            if len(args) != 2 or not all(x.isdecimal() for x in args):
                raise ValueError('Usage : /grantxp 123456789 30')
            ok = store.grant_points(int(args[0]), int(args[1]), update.effective_user.id)
            out = '✅ XP ajoutés.' if ok else 'Utilisateur introuvable.'
        elif command == '/stats':
            s = store.stats()
            out = ('📊 Statistiques\n'
                   f'Comptes : {s["users"]}\nAdultes vérifiés : {s["verified"]}\n'
                   f'Parrainages validés : {s["referrals"]}\n'
                   f'Missions validées : {s["tasks"]}\nCoupons créés : {s["coupons"]}\n'
                   f'Coupons débloqués : {s["redeemed"]}\nXP distribués : {s["points_earned"]}\n'
                   f'XP utilisés : {s["points_spent"]}\nXP restants : {s["points_available"]}')
        else:
            out = ('📋 ADMIN\n/addcoupon /listcoupons /delcoupon /activatecoupon\n'
                   '/addtask /deltask /listtasks /grantxp /stats')
    except (ValueError, IndexError, TelegramError) as exc:
        out = f'⚠️ {exc}'
    await send(update, out)


async def on_error(update, ctx):
    log.error('Erreur Telegram (détails journalisés côté serveur)', exc_info=ctx.error)


def main():
    if not BOT_TOKEN or BOT_TOKEN == 'METTRE_ICI_LE_TOKEN':
        raise RuntimeError('Renseigne BOT_TOKEN dans ton fichier .env')
    if not ADMIN_IDS:
        raise RuntimeError('Renseigne ADMIN_IDS dans ton fichier .env')
    log.info('Démarrage %s, minimum des cotes 4.00, canaux obligatoires=%s',
             BOT_NAME, len(REQUIRED))
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', info))
    app.add_handler(CommandHandler('annuler', cancel))
    app.add_handler(CommandHandler('coupons', coupons))
    app.add_handler(CommandHandler('mescoupons', my_coupons))
    for command in ('admin', 'addcoupon', 'listcoupons', 'delcoupon', 'activatecoupon',
                    'addtask', 'deltask', 'listtasks', 'grantxp', 'stats'):
        app.add_handler(CommandHandler(command, admin_command))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
