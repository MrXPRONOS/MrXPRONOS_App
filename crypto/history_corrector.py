"""One-time repair of wrong Telegram images, not a new market-data post.

Tries Telegram editMessageMedia on original messages; if Bot API explicitly
refuses to edit them, posts a dated photo reply so the correction is visible.
The fallback is labeled correctly; never claims that the old photo was edited.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from crypto import production_seed_v1 as seed

MANIFEST = Path("crypto/history_corrections_2026_10_18.json")
REGISTER = Path("crypto/history_corrections_applied.json")
ROOT = Path("crypto/generated/test")

def caption(d):
    if d["kind"] == "global_units":
        cap = d["market_cap_usd"]/1e9
        volume = d["volume_24h_usd"]/1e9
        note = (f"Capitalisation réelle de l’instantané : {cap:,.2f} Md USD\n"
                f"Volume global 24 h : {volume:,.2f} Md USD\n\n"
                "L’ancienne image multipliait les valeurs mondiales par 1 milliard.")
    else:
        note = ("Cet article CoinDesk concernait la SEC et les actions tokenisées, "
                "et ne prouvait pas un changement de frais d’OKX. "
                "Il avait été classé à tort dans la rubrique Exchanges.")
    return (f"⚠️ RECTIFICATIF ACTU CRYPTO — N°{d['number']:02d}\n"
            f"Publication historique du {d['date_utc']}\n\n"
            + note + "\n\n"
            "Ce rectificatif porte sur les anciennes données ou leur classification ; "
            "ce n’est pas une cotation actualisée.\nSource initiale : " + d["source"])


def response_json(resp):
    try:
        resp.raise_for_status()
        parsed=resp.json()
    except requests.RequestException:
        raise RuntimeError("Telegram response uncertain; manual intervention required") from None
    except ValueError:
        raise RuntimeError("Telegram returned unparseable reply") from None
    if not isinstance(parsed,dict) or parsed.get("ok") is not True:
        raise RuntimeError("Telegram rejected correction")
    m=parsed.get("result")
    if not isinstance(m,dict) or not isinstance(m.get("message_id"),int):
        raise RuntimeError("Telegram did not confirm message id")
    return m


def edit_or_reply(d,chat):
    png=ROOT/("rectification_"+str(d["number"]).zfill(2)+".png")
    seed.validate_image(png)
    msg_id=d["message_id"]
    data={"chat_id":chat["id"],"message_id":msg_id,
          "media":json.dumps({"type":"photo","media":"attach://photo","caption":caption(d)},
                             ensure_ascii=False)}
    with png.open("rb") as pic:
        try:
            resp=requests.post("https://api.telegram.org/bot"+seed.TOKEN+"/editMessageMedia",
                               data=data,files={"photo":(png.name,pic,"image/png")},timeout=(10,90))
        except requests.RequestException:
            raise RuntimeError("Telegram edit result unknown — do not retry automatically") from None
    if resp.status_code==200:
        result=response_json(resp)
        if result["message_id"]!=msg_id or not result.get("photo"):
            raise RuntimeError("Original photo edit not confirmed")
        return {"mode":"edited_original","message_id":msg_id}
    # Fallback ONLY for explicit non-editability, never for connection uncertainty.
    try:
        failure=resp.json()
        reason=str(failure.get("description") or "").lower()
    except ValueError:
        raise RuntimeError("Telegram edit failed without usable error") from None
    if resp.status_code != 400 or not any(x in reason for x in (
            "message can't be edited","message to edit not found",
            "message is not modified","message can't be found")):
        raise RuntimeError("Telegram edit rejected; not retrying: "+reason[:130])
    # An added reply is fully transparent if the old picture cannot be edited.
    with png.open("rb") as pic:
        try:
            reply=requests.post(
                "https://api.telegram.org/bot"+seed.TOKEN+"/sendPhoto",
                data={"chat_id":chat["id"],"caption":caption(d),
                      "reply_parameters":json.dumps({"message_id":msg_id,
                          "allow_sending_without_reply":False})},
                files={"photo":(png.name,pic,"image/png")},timeout=(10,90))
        except requests.RequestException:
            raise RuntimeError("Telegram reply result unknown — manual investigation needed") from None
    posted=response_json(reply)
    if (posted.get("chat",{}).get("id")!=chat["id"] or not posted.get("photo")
            or posted.get("reply_to_message",{}).get("message_id")!=msg_id):
        raise RuntimeError("Rectification reply linkage not confirmed")
    return {"mode":"replied_correction","message_id":posted["message_id"],
            "original_message_id":msg_id}


def run():
    chat=seed.verify_production_route()
    records=json.loads(MANIFEST.read_text(encoding="utf-8"))["corrections"]
    state=json.loads(REGISTER.read_text(encoding="utf-8"))
    history=seed.read_state()["sent"]
    if not isinstance(state.get("corrected"),dict):
        raise ValueError("Invalid historic correction register")
    for d in records:
        n=d["number"]
        key=str(n)
        if key in state["corrected"]:
            print("HISTORY_CORRECTION_ALREADY_RECORDED",n,state["corrected"][key]["mode"])
            continue
        old=history.get("initial_history_"+str(n).zfill(2))
        if not old or old["message_id"]!=d["message_id"]:
            raise ValueError("Original historical Telegram message identity mismatch")
        result=edit_or_reply(d,chat)
        state["corrected"][key]={**result,"applied_at":datetime.now(timezone.utc).isoformat()}
        REGISTER.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("HISTORY_CORRECTION_CONFIRMED",n,result["mode"],result["message_id"])


if __name__=="__main__":
    run()
