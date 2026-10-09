#!/usr/bin/env python3
"""BSD V2 -> Telegram: 20h batch of night coupons plus normal daily windows.

Night coupons: 21h–05h local Togo time (UTC) grouped at 20h.
Supabase unique(kind,ref_id,ref_date) prevents resending eligible picks.
"""
import argparse,json,os,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
from bsd_h2h import _utc
from bsd_v2_estimated_odds import valid_standalone_prediction
from bsd_v2_card import render as render_card
from bsd_v2_captions import single_caption,combo_caption,PARSE_MODE
from bsd_v2_night import is_night_match,matches_for_night,batch_date
from bsd_v2_telegram_ledger import snapshot

KIND="bsd_v2_hourly"
COMBO_KIND="bsd_v2_combo_hourly"
URL="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"
BOOKMAKERS_URL="https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html"

def action_buttons():
    return {"inline_keyboard":[
        [{"text":"Voir plus de coupons 🔥","url":URL}],
        [{"text":"S’inscrire ou réinitialiser son compte 🎯","url":BOOKMAKERS_URL}],
    ]}

def prediction_action_buttons():
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
        one_xbet=checked_url("1xbet")
        melbet=checked_url("melbet")
    except (KeyError,ValueError,OSError,TypeError) as exc:
        raise RuntimeError("Cannot build bookmaker CTA for prediction posts") from exc
    return {"inline_keyboard":[
        [
            {"text":"PARIEZ SUR 1XBET","url":one_xbet,"style":"primary"},
            {"text":"PARIEZ SUR MELBET","url":melbet,"style":"success"},
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
        picks=[m.get("prediction") or {},*((m.get("predictions") or [])[1:2])]
        valid_price=any(valid_standalone_prediction(p,False) and p.get("odds",0)>1.50
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
        if not valid_standalone_prediction(p,False) or p["odds"]<=1.50:
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
    # One row per channel+match, anchored in the existing unique index.
    # Only the insert winner will send. This is at-most-once for this channel,
    # with a possible missed delivery if the runner crashes after claiming.
    event_id=str(match.get("_telegram_selection_ref") or match["id"])
    ref=chat_id+":"+event_id
    date=match["date"]
    payload={"kind":KIND,"ref_id":ref,"ref_date":date,"validation_sent":False,
             "selection_snapshot":snapshot(match),"delivery_status":"reserved"}
    r=session.post(base.rstrip("/")+"/rest/v1/telegram_sent",
                   params={"on_conflict":"kind,ref_id,ref_date"},
                   headers=headers(key),json=payload,timeout=30)
    r.raise_for_status()
    rows=r.json()
    return isinstance(rows,list) and len(rows)>0


def mark_delivery(session,base,key,match,chat_id,message_id):
    response=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        headers=headers(key),params={"kind":"eq."+KIND,
            "ref_id":"eq."+chat_id+":"+str(match.get("_telegram_selection_ref") or match["id"]),
            "ref_date":"eq."+match["date"]},
        json={"delivery_status":"sent","telegram_message_id":message_id,
              "published_at":datetime.now(timezone.utc).isoformat()},timeout=30)
    response.raise_for_status()


def flag_uncertain_delivery(session,base,key,kind,ref_id,date,reason):
    """Mark uncertain delivery for operator review; never auto-resend."""
    response=session.patch(base.rstrip("/")+"/rest/v1/telegram_sent",
        params={"kind":"eq."+kind,"ref_id":"eq."+ref_id,"ref_date":"eq."+date},
        headers=headers(key),json={"delivery_status":"manual_review",
                                  "validation_details":str(reason)[:180]},timeout=30)
    response.raise_for_status()


def release_failed_claim(session,base,key,match,chat_id):
    # Autorise le réessai lors du prochain cron si Telegram a rejeté l'envoi.
    # Un timeout après acceptation par Telegram reste intrinsèquement ambigu.
    params={"kind":"eq."+KIND,"ref_id":"eq."+chat_id+":"+str(match.get("_telegram_selection_ref") or match["id"]),
            "ref_date":"eq."+match["date"]}
    h=headers(key)
    r=session.delete(base.rstrip("/")+"/rest/v1/telegram_sent",
                     params=params,headers=h,timeout=30)
    r.raise_for_status()


def send_one(session,token,chat_id,match,*,night=False):
    # Telegram envoie la photo générée depuis le PNG du ballon et des données BSD.
    # Pas de capture de ticket de bookmaker et aucune cote inventée.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        image=render_card(match,Path(directory)/"coupon.png")
        from bsd_v2_telegram_banner import attach_banner
        image=attach_banner(image)
        caption=single_caption(match,night=night)
        markup=prediction_action_buttons()
        with open(image,"rb") as pic:
            r=session.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id":chat_id,"caption":caption,
                      "reply_markup":json.dumps(markup),"parse_mode":PARSE_MODE},
                files={"photo":pic},timeout=60)
    r.raise_for_status()
    data=r.json()
    if not data.get("ok"):raise RuntimeError("Telegram photo not accepted")
    return data["result"]["message_id"]

def combo_ledger_match(combo):
    return {"id":combo["id"],"date":combo["date"]}


def send_combo(session,token,chat,combo,*,night=False):
    from tempfile import TemporaryDirectory
    from bsd_v2_combo_card import render_combo
    with TemporaryDirectory() as directory:
        photo=render_combo(combo,Path(directory)/"combine.png",session=session)
        from bsd_v2_telegram_banner import attach_banner
        photo=attach_banner(photo)
        caption=combo_caption(combo,night=night)
        with photo.open("rb") as pic:
            response=session.post("https://api.telegram.org/bot"+token+"/sendPhoto",
                data={"chat_id":chat,"caption":caption,
                      "reply_markup":json.dumps(prediction_action_buttons()),
                      "parse_mode":PARSE_MODE},
                files={"photo":pic},timeout=60)
    response.raise_for_status()
    body=response.json()
    if not body.get("ok"):raise RuntimeError("Telegram combo rejected")
    return body["result"]["message_id"]


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
                message_id=send_one(session,token,chat,match,night=night)
                mark_delivery(session,supabase_url,supabase_key,match,chat,message_id)
                report["sent"]+=1
                if night:report["night_picks_sent"]+=1
                time.sleep(.3)
            except Exception as e:
                report["errors"]+=1
                print("TELEGRAM_BSD_ERROR:",match["id"],type(e).__name__,str(e)[:180])
                if claimed:
                    # Telegram may have accepted a photo despite client failure.
                    # Preserve the claim and put it on an explicit review queue.
                    print("TELEGRAM_BSD_REVIEW_REQUIRED:",match["id"],chat)
                    try:
                        ref=chat+":"+str(match.get("_telegram_selection_ref") or match["id"])
                        flag_uncertain_delivery(session,supabase_url,supabase_key,
                                                KIND,ref,match["date"],e)
                    except Exception as save_error:
                        print("TELEGRAM_BSD_REVIEW_SAVE_ERROR:",type(save_error).__name__)
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
            # existing unique kind+ref_id+date Supabase ledger.
            claimed=False
            try:
                combo_ref={"id":combo["id"],"date":combo["date"]}
                ref=chat+":"+combo_ref["id"]
                response=session.post(supabase_url.rstrip("/")+"/rest/v1/telegram_sent",
                    params={"on_conflict":"kind,ref_id,ref_date"},
                    headers=headers(supabase_key),
                    json={"kind":COMBO_KIND,"ref_id":ref,
                          "ref_date":combo_ref["date"],"validation_sent":False,
                          "selection_snapshot":snapshot(combo,combo=True),
                          "delivery_status":"reserved"},timeout=30)
                response.raise_for_status()
                claimed=isinstance(response.json(),list) and bool(response.json())
                if not claimed:
                    report["combos_claimed"]+=1
                    continue
                night=night_mode and is_night_match(combo["legs"][0])
                message_id=send_combo(session,token,chat,combo,night=night)
                response=session.patch(supabase_url.rstrip("/")+"/rest/v1/telegram_sent",
                    params={"kind":"eq."+COMBO_KIND,"ref_id":"eq."+ref,
                            "ref_date":"eq."+combo["date"]},headers=headers(supabase_key),
                    json={"delivery_status":"sent","telegram_message_id":message_id,
                          "published_at":datetime.now(timezone.utc).isoformat()},timeout=30)
                response.raise_for_status()
                report["combos_sent"]+=1
                if night:report["night_combos_sent"]+=1
            except Exception as exc:
                report["errors"]+=1
                print("BSD_COMBO_ERROR",combo["id"],type(exc).__name__,str(exc)[:170])
                if claimed:
                    print("BSD_COMBO_REVIEW_REQUIRED",combo["id"],chat)
                    try:
                        flag_uncertain_delivery(session,supabase_url,supabase_key,
                                                COMBO_KIND,ref,combo["date"],exc)
                    except Exception as save_error:
                        print("BSD_COMBO_REVIEW_SAVE_ERROR",type(save_error).__name__)
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
    sb_url=os.getenv("SUPABASE_URL")
    sb_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not all((token,chat,sb_url,sb_key)):raise RuntimeError("Missing Telegram or Supabase secrets")
    report=process(data,now,session=requests.Session(),token=token,
                   chat_ids=[chat],supabase_url=sb_url,supabase_key=sb_key)
    print("BSD_V2_TELEGRAM:",json.dumps(report))
    if report["errors"]:raise SystemExit("Telegram delivery errors; investigate ledger")


if __name__=="__main__":
    main()
