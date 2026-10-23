#!/usr/bin/env python3
"""BSD V2 -> Telegram: 20h batch of night coupons plus normal daily windows.

Night coupons: 21h–05h local Togo time (UTC) grouped at 20h.
Neon unique(kind,ref_id,ref_date) prevents resending eligible picks.
"""
import argparse,json,os,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
from bsd_h2h import _utc
from bsd_v2_estimated_odds import valid_standalone_prediction
from bsd_v2_card import render as render_card
from bsd_v2_captions import single_caption,combo_caption,PARSE_MODE
from bsd_v2_combos import combo_ledger_ref
from bsd_v2_night import is_night_match,matches_for_night,batch_date
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"scripts"))
from telegram_rich import post_photo

KIND="bsd_v2_hourly"
COMBO_KIND="bsd_v2_combo_hourly"
URL="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"
BOOKMAKERS_URL="https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html"

def action_buttons():
    return {"inline_keyboard":[
        [{"text":"Voir plus de coupons 🔥","url":URL}],
        [{"text":"S’inscrire ou réinitialiser son compte 🎯","url":BOOKMAKERS_URL}],
    ]}

def partner_pack(now=None):
    """Both image and affiliate buttons use the same UTC day rotation."""
    now=now or datetime.now(timezone.utc)
    return "1xbet_melbet" if now.date().toordinal()%2 == 0 else "1win_betwinner"

def prediction_action_buttons(pack=None):
    """Two colored partner links ONLY for pre-match single/night/combo coupons.

    Use the canonical URLs from config/partners.json to stay in sync with all
    other bookmaker promotions. The old action_buttons() remains unchanged
    for published winning-results messages.
    """
    from urllib.parse import urlsplit
    config_path=Path(__file__).resolve().parent.parent/"config/partners.json"
    try:
        partners=json.loads(config_path.read_text(encoding="utf-8"))["partners"]
        def checked_url(key):
            entry=partners[key]
            url=str(entry["url"]).strip()
            parsed=urlsplit(url)
            if entry.get("enabled") is False or parsed.scheme!="https" or not parsed.netloc:
                raise ValueError(f"Invalid or disabled affiliate partner: {key}")
            return url
        pack=pack or partner_pack()
        keys=("1xbet", "melbet") if pack=="1xbet_melbet" else ("1win", "betwinner") if pack=="1win_betwinner" else None
        if keys is None:raise ValueError("Unknown partner pack")
        first_url,second_url=(checked_url(key) for key in keys)
    except (KeyError,ValueError,OSError,TypeError) as exc:
        raise RuntimeError("Cannot build bookmaker CTA for prediction posts") from exc
    return {"inline_keyboard":[
        [
            {"text":"PARIEZ SUR "+keys[0].upper(),"url":first_url,"style":"primary"},
            {"text":"PARIEZ SUR "+keys[1].upper(),"url":second_url,"style":"primary"},
        ],
        [{"text":"Voir plus de coupons 🔥","url":URL}],
    ]}

def due(matches,now,min_minutes=60,max_minutes=120):
    selected=[]
    for m in matches:
        if not isinstance(m,dict) or m.get("source")!="bsd":continue
        if is_night_match(m):continue
        if str(m.get("status","")).lower() not in ("notstarted","upcoming"):continue
        try:dt=_utc(str(m.get("event_date") or ""))
        except (ValueError,TypeError):continue
        delta=(dt-now).total_seconds()/60
        if m.get("recommendation_eligible") is not True:continue
        picks=[m.get("prediction") or {},*((m.get("predictions") or [])[1:2])]
        valid_price=any(p.get("recommendation_eligible") is True and valid_standalone_prediction(p,False) and p.get("odds",0)>1.50
                        for p in picks if isinstance(p,dict))
        if (min_minutes<=delta<max_minutes and valid_price
                ):
            selected.append(m)
    return sorted(selected,key=lambda m:(m["event_date"],str(m["id"])))


def combos_due(matches,now):
    from bsd_v2_combos import build_combos,due_combos
    return due_combos(build_combos([m for m in matches if not is_night_match(m)]),now)


def expand_tickets(match):
    """Up to two separately tracked market picks for the same BSD fixture."""
    first=match.get("prediction") or {}
    picks=[first]
    for extra in (match.get("predictions") or [])[1:2]:
        if extra.get("selection_key")!=first.get("selection_key"):
            picks.append(extra)
    result=[]
    for idx,p in enumerate(picks):
        odds=p.get("odds")
        if (match.get("recommendation_eligible") is not True or
                p.get("recommendation_eligible") is not True or
                not valid_standalone_prediction(p,False) or p["odds"]<=1.50):
            continue
        variant={**match,"prediction":p}
        if idx:
            variant["_telegram_selection_ref"]=str(match["id"])+":"+str(p["selection_key"])
        result.append(variant)
    return result


def headers(key):
    return {"apikey":key,"Authorization":"Bearer "+key,
            "Content-Type":"application/json",
            "Prefer":"return=representation,resolution=ignore-duplicates"}


def claim(session,base,key,match,chat_id):
    from neon_telegram_ledger import claim as reserve
    event_id=str(match.get("_telegram_selection_ref") or match["id"])
    return bool(reserve(KIND,chat_id+":"+event_id,match["date"]))


def release_failed_claim(session,base,key,match,chat_id):
    from neon_telegram_ledger import release
    event_id=str(match.get("_telegram_selection_ref") or match["id"])
    release(KIND,chat_id+":"+event_id,match["date"])


def send_one(session,token,chat_id,match,*,night=False):
    # Telegram envoie la photo générée depuis le PNG du ballon et des données BSD.
    # Pas de capture de ticket de bookmaker et aucune cote inventée.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        image=render_card(match,Path(directory)/"coupon.png")
        from bsd_v2_telegram_banner import attach_banner
        pack=partner_pack()
        image=attach_banner(image,pack=pack)
        tier=str((match.get("prediction") or {}).get("signal_tier") or match.get("signal_tier") or "QUALIFIE")
        caption=("🏅 " + tier + "\n" + single_caption(match,night=night))
        markup=prediction_action_buttons(pack)
        return post_photo(session,token,chat_id,image,caption,markup,timeout=60)

def combo_ledger_match(combo):
    return {"id":combo["id"],"date":combo["date"]}


def send_combo(session,token,chat,combo,*,night=False):
    from tempfile import TemporaryDirectory
    from bsd_v2_combo_card import render_combo
    with TemporaryDirectory() as directory:
        photo=render_combo(combo,Path(directory)/"combine.png",session=session)
        from bsd_v2_telegram_banner import attach_banner
        pack=partner_pack()
        photo=attach_banner(photo,pack=pack)
        caption=combo_caption(combo,night=night)
        return post_photo(session,token,chat,photo,caption,prediction_action_buttons(pack),timeout=60)

def process(data,now,*,session,token,chat_ids,supabase_url,supabase_key):
    if data.get("source")!="bsd" or data.get("model_version")!="bsd-v2-isolated":
        raise ValueError("Production JSON is not BSD V2")
    night_matches=matches_for_night(data["matches"],now)
    night_mode=batch_date(now) is not None
    selections=[pick for m in due(data["matches"],now) for pick in expand_tickets(m)]
    selections += [pick for m in night_matches for pick in expand_tickets(m)]
    report={"due":len(selections),"sent":0,"already_claimed":0,"errors":0,
            "night_matches":len(night_matches),"night_picks_sent":0,"night_combos_sent":0}
    for match in selections:
        for chat in chat_ids:
            claimed=False
            try:
                claimed=claim(session,supabase_url,supabase_key,match,chat)
                if not claimed:
                    report["already_claimed"]+=1
                    continue
                night=is_night_match(match)
                send_one(session,token,chat,match,night=night)
                report["sent"]+=1
                if night:report["night_picks_sent"]+=1
                time.sleep(.3)
            except Exception as e:
                report["errors"]+=1
                print("TELEGRAM_BSD_ERROR:",match["id"],type(e).__name__,str(e)[:180])
                if claimed:
                    try:
                        release_failed_claim(session,supabase_url,supabase_key,match,chat)
                    except Exception as release_error:
                        print("TELEGRAM_BSD_RELEASE_ERROR:",type(release_error).__name__)
    combo_picks=combos_due(data["matches"],now)
    from bsd_v2_combos import build_combos
    from bsd_v2_night import night_date
    if night_mode:
        combo_picks += [c for c in build_combos(night_matches)
                        if night_date(c["event_date"])==batch_date(now)]
    report["combos_due"]=len(combo_picks)
    report["combos_sent"]=0
    report["combos_claimed"]=0
    for combo in combo_picks:
        for chat in chat_ids:
            # Kind is separate from one-event predictions but uses the
            # existing unique kind+ref_id+date Neon ledger.
            claimed=False
            try:
                combo_ref={"id":combo["id"],"date":combo["date"]}
                ref=combo_ledger_ref(chat,combo)
                from neon_telegram_ledger import claim as reserve
                claimed=bool(reserve(COMBO_KIND,ref,combo_ref["date"]))
                if not claimed:
                    report["combos_claimed"]+=1
                    continue
                night=night_mode and is_night_match(combo["legs"][0])
                send_combo(session,token,chat,combo,night=night)
                report["combos_sent"]+=1
                if night:report["night_combos_sent"]+=1
            except Exception as exc:
                report["errors"]+=1
                print("BSD_COMBO_ERROR",combo["id"],type(exc).__name__,str(exc)[:170])
                if claimed:
                    try:
                        from neon_telegram_ledger import release
                        release(COMBO_KIND,ref,combo["date"])
                    except Exception as secondary:
                        print("BSD_COMBO_RELEASE_ERROR",type(secondary).__name__)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="data.json")
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    data=json.loads(Path(args.data).read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    if data.get('source') != 'bsd' or data.get('model_version') != 'bsd-v2-isolated':
        raise RuntimeError('Le fichier de pronostics du site ne provient pas de BSD V2')
    generated = _utc(str(data.get('generated_at') or ''))
    if now - generated > timedelta(hours=36):
        raise RuntimeError('Pronostics BSD V2 trop anciens: Telegram ne diffuse pas un ancien fichier')
    if args.dry_run:
        print("BSD_TELEGRAM_DRY_RUN:",json.dumps([{"id":m.get("_telegram_selection_ref") or m["id"],"kickoff":m["event_date"]}
          for match in due(data["matches"],now) for m in expand_tickets(match)]))
        print("BSD_COMBO_DRY_RUN:",json.dumps([{"id":x["id"],"kickoff":x["event_date"]}
              for x in combos_due(data["matches"],now)]))
        print("BSD_NIGHT_DRY_RUN:",json.dumps([{"id":m["id"],"kickoff":m["event_date"]}
              for m in matches_for_night(data["matches"],now)]))
        return
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    chat=os.getenv("TELEGRAM_CHAT_ID")
    if not all((token,chat,os.getenv("NEON_DATABASE_URL"))):
        raise RuntimeError("Missing Telegram or Neon credentials")
    report=process(data,now,session=requests.Session(),token=token,
                   chat_ids=[chat],supabase_url="",supabase_key="")
    print("BSD_V2_TELEGRAM:",json.dumps(report))
    if report["errors"]:raise SystemExit("Telegram delivery errors; investigate ledger")


if __name__=="__main__":
    main()
