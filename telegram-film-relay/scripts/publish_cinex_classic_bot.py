"""Publish ONE already-checkpointed licensed CineX classic film using Bot API only.

No Telethon/user session, uploads, archive deletion, publicity, mirrors or ads.
Failure to confirm the exact private rescue invitation prevents ANY publication.
D1 checkpoints make successful posters/videos reusable on a later retry.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

import requests

ROOT=Path(__file__).resolve().parents[1]
TOKEN=re.compile(r"^[A-Za-z0-9_-]{24}$")
INVITE=re.compile(r"^https://t\.me/(?:\+[A-Za-z0-9_-]{12,}|joinchat/[A-Za-z0-9_-]{12,})/?$")
HANDLE="cinexfilms_vf"
PUBLIC="-1003921647496"
RESCUE="-1004357703501"


def api(bot,method,params):
    response=requests.post("https://api.telegram.org/bot"+bot+"/"+method,
                           json=params,timeout=30)
    try:
        obj=response.json()
    except ValueError as e:
        raise RuntimeError("Réponse Telegram indéterminée, aucun réessai automatique") from e
    if not response.ok or not obj.get("ok"):
        # Reapplying an already-current colored keyboard is a successful no-op.
        if method=="editMessageReplyMarkup" and "message is not modified" in str(obj.get("description","")).lower():
            return True
        raise RuntimeError("Telegram "+method+" refusé (code "+str(obj.get("error_code",response.status_code))+")")
    return obj["result"]


def d1(sql,params=None):
    token=os.environ.get("CLOUDFLARE_API_TOKEN","")
    account=os.environ.get("CLOUDFLARE_ACCOUNT_ID","")
    database=os.environ.get("CINERADAR_D1_DATABASE_ID","")
    if not token or not account or not database:
        raise RuntimeError("Configuration D1 absente")
    response=requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query",
        headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},
        json={"sql":sql,"params":params or []},timeout=25)
    if not response.ok:
        raise RuntimeError("Cloudflare D1 indisponible : HTTP "+str(response.status_code))
    obj=response.json()
    if not obj.get("success") or not obj.get("result") or not obj["result"][0].get("success"):
        raise RuntimeError("Cloudflare D1 n'a pas confirmé la requête")
    return obj["result"][0].get("results") or []


def rescue_url(bot):
    channels=json.loads((ROOT/"state/rescue_channels.json").read_text())["channels"]
    expected=channels["@cinexfilms_vf"]
    if str(expected["rescue_channel_id"])!=RESCUE or int(expected["public_id"])!=int(PUBLIC):
        raise RuntimeError("Identité du canal Secours non conforme")
    url=os.getenv("CINEX_RESCUE_INVITE_URL","").strip()
    if not url:
        rows=d1(
            "SELECT rescue_chat_id,invite_url FROM cine_classic_rescue_config WHERE public_handle=?",
            ["@"+HANDLE])
        if rows and str(rows[0].get("rescue_chat_id"))==RESCUE:
            url=str(rows[0].get("invite_url") or "").strip()
    if not url:
        # Bot getChat works only after the bot is actually admitted to Secours.
        try:
            url=str(api(bot,"getChat",{"chat_id":RESCUE}).get("invite_link") or "")
        except RuntimeError:
            url=""
    if not INVITE.fullmatch(url):
        raise RuntimeError("Invitation Secours privée absente : publication refusée avant tout envoi")
    digest=hashlib.sha256(url.encode("utf-8")).hexdigest()
    if digest!=expected["invite_sha256"]:
        raise RuntimeError("Invitation Secours différente du lien vérifié enregistré : refus")
    return url


def source_pair():
    records=json.loads((ROOT/"state/state.json").read_text())["processed"]
    # Use one existing checkpoint (verified paired video + public poster).
    available=[(key,record) for key,record in records.items()
               if isinstance(record,dict) and record.get("private_message_id")
               and record.get("public_message_id")]
    if not available:
        raise RuntimeError("Aucun ancien film vérifié dans le registre, aucun nouvel envoi")
    key,record=available[-1]
    private_video=int(record["private_message_id"])
    public_poster=int(record["public_message_id"])
    if private_video<=0 or public_poster<=0:
        raise RuntimeError("Reçus source invalides")
    return key,private_video,public_poster


def poster_buttons(download,secours,folder):
    """One dedicated native Telegram color per action."""
    return {"inline_keyboard":[
        [{"text":"⬇️ Télécharger","url":download,"style":"success"}],
        [{"text":"🛟 Rejoindre le canal secours","url":secours,"style":"danger"}],
        [{"text":"📁 Rejoindre le dossier","url":folder,"style":"primary"}],
    ]}


def save_buttons(public_video_id):
    url="https://t.me/"+HANDLE+"/"+str(int(public_video_id))
    return {"inline_keyboard":[[{
        "text":"💾 Enregistrer / partager",
        "url":"https://t.me/share/url?url="+quote(url,safe=""),
        "style":"primary",
    }]]}


def previous_classic_publication(state, private_video):
    """A historical GitHub receipt is evidence the media was ALREADY posted.
    Never republish it just because the new D1 ledger is missing.
    """
    for key,row in state.get("processed",{}).items():
        if isinstance(row,dict) and int(row.get("private_message_id") or 0)==int(private_video):
            if int(row.get("public_message_id") or 0)>0:
                return key,int(row["public_message_id"])
    return None


def publish():
    if os.environ.get("CINEX_DOWNLOADS_ENABLED","").lower()!="true":
        raise RuntimeError("GitHub CINEX_DOWNLOADS_ENABLED n'est pas à true")
    bot=os.environ.get("CINEX_BOT_TOKEN","").strip()
    private=os.environ.get("TG_PRIVATE_CHANNEL","")
    if not bot or not re.fullmatch(r"-100\d{5,}",private):
        raise RuntimeError("Identifiants du bot ou vidéothèque classique manquants")
    folder=os.environ.get("CINEX_FILM_FOLDER_URL","").strip()
    if not folder.startswith("https://t.me/addlist/"):
        raise RuntimeError("Lien du dossier CinéX invalide")
    me=api(bot,"getMe",{})
    for cid in (PUBLIC,private):
        chat=api(bot,"getChat",{"chat_id":cid})
        if str(chat.get("id"))!=cid:
            raise RuntimeError("Destination Telegram incompatible avec le registre")
        if cid==PUBLIC and str(chat.get("username","")).lower()!=HANDLE:
            raise RuntimeError("Canal public CineX non conforme")
        membership=api(bot,"getChatMember",{"chat_id":cid,"user_id":me["id"]})
        if membership.get("status") not in ("creator","administrator") or (
            membership.get("status")=="administrator" and not membership.get("can_post_messages",False)):
            raise RuntimeError("Le bot n'est pas autorisé à publier dans le canal "+cid)
    # Cine Radar is a DIFFERENT bot from the publishing account.
    # Block publication until the delivery bot can actually read this library.
    radar=api(bot,"getChat",{"chat_id":"@CineRadarFr_Bot"})
    member=api(bot,"getChatMember",{"chat_id":private,"user_id":radar["id"]})
    if member.get("status") not in ("creator","administrator"):
        raise RuntimeError("BOT_ACCESS_REQUIRED: ajouter @CineRadarFr_Bot en administrateur de la vidéothèque privée CinéX")
    help_link=rescue_url(bot)
    key,video_id,poster_id=source_pair()
    source_id=private
    legacy_state=json.loads((ROOT/"state/state.json").read_text(encoding="utf-8"))
    title="Film CinéX (sélection vérifiée)"
    existing=d1(
        "SELECT token,status,public_poster_message_id,public_video_message_id FROM cine_classic_links WHERE source_chat_id=? AND source_message_id=?",
        [source_id,video_id])
    if existing:
        record=existing[0]
        token=record["token"]
        if record["status"]=="published":
            poster_id_existing=int(record["public_poster_message_id"] or 0)
            video_id_existing=int(record["public_video_message_id"] or 0)
            if poster_id_existing<=0 or video_id_existing<=0:
                raise RuntimeError("Reçu D1 publié incomplet : diagnostic requis, pas de republication")
            # Edit in place: NEVER repost a published film just to change button colors.
            url_download="https://t.me/CineRadarFr_Bot?start=d_"+token
            api(bot,"editMessageReplyMarkup",{
                "chat_id":PUBLIC,"message_id":poster_id_existing,
                "reply_markup":poster_buttons(url_download,help_link,folder),
            })
            api(bot,"editMessageReplyMarkup",{
                "chat_id":PUBLIC,"message_id":video_id_existing,
                "reply_markup":save_buttons(video_id_existing),
            })
            print("ALREADY_PUBLISHED : boutons colorés mis à jour sur les messages existants ; 0 nouvelle publication")
            print("FICHE_TELEGRAM : https://t.me/"+HANDLE+"/"+str(poster_id_existing))
            print("VIDEO_TELEGRAM : https://t.me/"+HANDLE+"/"+str(video_id_existing))
            return
        # A timeout after sending may leave pending with an unknown Telegram ID.
        # Never guess and repost; require manual reconciliation of the receipt.
        raise RuntimeError("PUBLICATION_PENDING_REVIEW : publication partielle ; aucun réessai automatique")
    else:
        previous=previous_classic_publication(legacy_state,video_id)
        if previous:
            print("ALREADY_PUBLISHED_LEGACY : cette vidéo figure déjà dans le registre GitHub : "+str(previous[0]))
            print("PUBLICATION_SKIPPED : aucune nouvelle affiche ni vidéo envoyée")
            return
        token=secrets.token_urlsafe(18)
        if not TOKEN.fullmatch(token):
            raise RuntimeError("Token de livraison invalide")
        d1("INSERT INTO cine_classic_links(token,source_chat_id,source_message_id,title,public_handle,status) VALUES(?,?,?,?,?,'pending')",
           [token,source_id,video_id,title,"@"+HANDLE])
        record={"token":token,"status":"pending","public_poster_message_id":None,"public_video_message_id":None}
    download="https://t.me/CineRadarFr_Bot?start=d_"+token
    rows=poster_buttons(download,help_link,folder)
    poster_new=record["public_poster_message_id"]
    if not poster_new:
        poster_new=api(bot,"copyMessage",{
            "chat_id":PUBLIC,"from_chat_id":PUBLIC,"message_id":poster_id,
            "reply_markup":rows,"disable_notification":True,
        })["message_id"]
        d1("UPDATE cine_classic_links SET public_poster_message_id=?,updated_at=CURRENT_TIMESTAMP WHERE token=? AND status='pending'",
           [poster_new,token])
    video_new=record["public_video_message_id"]
    if not video_new:
        video_new=api(bot,"copyMessage",{
            "chat_id":PUBLIC,"from_chat_id":source_id,"message_id":video_id,
            "disable_notification":True,
        })["message_id"]
        d1("UPDATE cine_classic_links SET public_video_message_id=?,updated_at=CURRENT_TIMESTAMP WHERE token=? AND status='pending'",
           [video_new,token])
    url="https://t.me/"+HANDLE+"/"+str(video_new)
    api(bot,"editMessageReplyMarkup",{
        "chat_id":PUBLIC,"message_id":video_new,
        "reply_markup":save_buttons(video_new),
    })
    d1("UPDATE cine_classic_links SET status='published',updated_at=CURRENT_TIMESTAMP WHERE token=? AND public_poster_message_id=? AND public_video_message_id=?",
       [token,poster_new,video_new])
    print("FICHE_TELEGRAM : https://t.me/"+HANDLE+"/"+str(poster_new))
    print("VIDEO_TELEGRAM : "+url)
    print("TROIS_BOUTONS_AFFICHE : Télécharger, Secours, Dossier")
    print("BOUTON_VIDEO : Enregistrer / partager via Telegram (lien du post)")


if __name__=="__main__":
    try:publish()
    except Exception as e:
        print("CINEX_PUBLISH_BLOCKED : "+str(e),file=sys.stderr)
        raise SystemExit(1)
