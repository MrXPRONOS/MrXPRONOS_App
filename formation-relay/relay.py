"""Formation relay: conservative grouping, authorized sources, durable receipts."""
import asyncio
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from course_formats import attachment_family, groups

CATS = ("business", "finance", "digitale", "mindset")
WORDS = {
    "business": ("entrepreneuriat","business","marketing","ecommerce","e commerce","vente","dropshipping","affiliation","entreprise"),
    "finance": ("finance","trading","crypto","bitcoin","bourse","investissement","forex","immobilier","blockchain"),
    "digitale": ("informatique","programmation","python","javascript","intelligence artificielle","chatgpt","developpement web","montage video","graphisme","automatisation","excel"),
    "mindset": ("mindset","leadership","developpement personnel","productivite","psychologie","discipline","communication","motivation"),
}
STATE = Path("formation-relay/state.json")

def norm(s):
    s = unicodedata.normalize("NFKD", s.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in s if not unicodedata.combining(c))))

def classify(text):
    text = " " + norm(text) + " "
    scores = {k: sum(" "+w+" " in text for w in ws) for k,ws in WORDS.items()}
    best = max(scores.values())
    winners = [k for k,v in scores.items() if v == best and v > 0]
    return winners[0] if len(winners)==1 else "general"

def digest(key, s):
    return hmac.new(key.encode(),s.encode(),hashlib.sha256).hexdigest()

def fingerprints(key, group):
    files=[m for m in group if m["kind"]=="file"]
    text=" ".join(m["text"] for m in group if m["kind"]!="file")
    title=norm(text.split("\n")[0])[:240]
    media=[digest(key,"media:"+m["media"]) for m in files]
    names=[digest(key,"file:"+norm(m["name"])+":"+str(m["size"])) for m in files if m["name"] and m["size"]]
    marks=sorted(set(media+names+([digest(key,"title:"+title)] if len(title)>=12 else [])))
    cid=digest(key,"course:"+":".join(media))
    return cid,marks

def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"done":{},"active":None,"cooldown":0}

def checkpoint(state):
    STATE.parent.mkdir(exist_ok=True)
    temp=STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state,sort_keys=True,indent=2)+"\n")
    temp.replace(STATE)
    def git(*args):
        subprocess.run(["git",*args],check=True,stdout=subprocess.DEVNULL)
    git("add",str(STATE))
    if subprocess.run(["git","diff","--cached","--quiet"]).returncode==0: return
    git("commit","-m","state: formation receipts [skip ci]")
    for _ in range(4):
        if subprocess.run(["git","push","origin","HEAD:main"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0: return
        # No other formation runner can write concurrently. Rebase unrelated changes.
        git("pull","--rebase","origin","main")
        time.sleep(3)
    raise RuntimeError("Durable checkpoint unavailable")

class Bot:
    def __init__(self, token):
        self.token=token
    def call(self, method, **params):
        import requests
        # Never print response bodies, URLs, or tokens. No automatic retry on writes.
        try:
            r=requests.post("https://api.telegram.org/bot"+self.token+"/"+method,json=params,timeout=60)
            j=r.json()
        except Exception:
            raise RuntimeError("Bot API response uncertain") from None
        if not j.get("ok"):
            raise RuntimeError("Bot API rejected request: "+str(j.get("error_code",0)))
        return j["result"]

def config():
    sources=json.loads(os.environ["FORMATION_SOURCES_JSON"])
    dest=json.loads(os.environ["FORMATION_DESTINATIONS_JSON"])
    stage=int(os.environ["FORMATION_STAGE_CHAT"])
    key=os.environ["FORMATION_STATE_KEY"]
    if len(key)<32 or set(dest)!=set(CATS)|{"general"} or not sources: raise ValueError("Invalid config")
    dest={k:int(v) for k,v in dest.items()}
    ids=[stage,*dest.values(),*[int(s["chat"]) for s in sources]]
    if len(set(ids))!=len(ids) or any(not str(i).startswith("-100") for i in ids): raise ValueError("Invalid or overlapping channel IDs")
    for s in sources:
        if s.get("authorized") is not True or not str(s.get("credit","")).strip(): raise ValueError("Missing source permission or credit")
        if s.get("category","auto") not in (*CATS,"general","auto"): raise ValueError("Invalid source category")
    return sources,dest,stage,key

async def run(publish):
    from telethon import TelegramClient, errors, utils
    from telethon.sessions import StringSession
    sources,dest,stage,key=config()
    state=load_state()
    if state.get("cooldown",0)>time.time(): raise RuntimeError("Personal Telegram cooldown active")
    bot=Bot(os.environ["FORMATION_BOT_TOKEN"])
    me=bot.call("getMe")["id"]
    for cat,chat in [*dest.items(),("stage",stage)]:
        info=bot.call("getChat",chat_id=chat)
        if info["type"]!="channel" or bool(info.get("username"))!=(cat=="general"):
            raise RuntimeError("Wrong destination type/visibility: "+cat)
        member=bot.call("getChatMember",chat_id=chat,user_id=me)
        if member["status"] not in ("creator","administrator") or (cat!="stage" and member["status"]!="creator" and not member.get("can_post_messages")):
            raise RuntimeError("Bot permissions missing: "+cat)
    client=TelegramClient(StringSession(os.environ["TG_STRING_SESSION"]),int(os.environ["TG_API_ID"]),os.environ["TG_API_HASH"],flood_sleep_threshold=0,request_retries=0)
    try:
        await client.connect()
        if not await client.is_user_authorized(): raise RuntimeError("Personal session unauthorized")
        entities={d.id:d.entity async for d in client.iter_dialogs()}
        if any(i not in entities for i in [stage,*dest.values(),*[int(s["chat"]) for s in sources]]):
            raise RuntimeError("Personal account must already belong to all configured channels")
        candidates=[]
        for source in sources:
            entity=entities[int(source["chat"])]
            if getattr(entity,"noforwards",False): continue
            records=[]
            async for m in client.iter_messages(entity,limit=600,wait_time=3):
                if not m or not m.id: continue
                name=getattr(m.file,"name",None) or "" if m.file else ""
                size=getattr(m.file,"size",0) or 0 if m.file else 0
                mime=getattr(m.file,"mime_type","") or "" if m.file else ""
                family=attachment_family(name,mime) if m.document else None
                kind="poster" if m.photo or family=="poster" else "file" if family else "text" if not m.media and m.raw_text else "other"
                records.append({"id":m.id,"kind":kind,"family":family,"album":m.grouped_id,"text":m.raw_text or "","name":name,"size":size,"media":str(m.document.id) if m.document else "","protected":bool(getattr(m,"noforwards",False))})
            for group in groups(list(reversed(records))):
                cid,marks=fingerprints(key,group)
                cat=source.get("category","auto")
                if cat=="auto": cat=classify(" ".join(m["text"]+" "+m["name"] for m in group))
                candidates.append((source,group,cid,marks,cat))
        print("Complete candidate groups:",len(candidates))
        if not publish: return
        if os.environ.get("FORMATION_RIGHTS_ATTESTED")!="true" or os.environ.get("FORMATION_DURABLE_STATE")!="true":
            raise RuntimeError("Publication not authorized or durable state disabled")
        active=state.get("active")
        if active and active.get("pending") is not None:
            # A lost API response is not evidence of failure. Check the marker
            # in destination history before advancing. Never automatically resend.
            marker=active["pending"]
            async for msg in client.iter_messages(entities[dest[active["cat"]]],limit=200,wait_time=3):
                if (msg.raw_text or "").endswith(marker):
                    active["next"]+=1; active["pending"]=None; checkpoint(state); break
            else: raise RuntimeError("Uncertain previous delivery; manual reconciliation required")
        if active and not any(c[2]==active["cid"] for c in candidates): raise RuntimeError("Incomplete delivery source no longer available")
        used=set()
        if active:
            candidates.sort(key=lambda c:c[2]!=active["cid"])
        for source,group,cid,marks,cat in candidates:
            active=state.get("active")
            if active and cid!=active["cid"]: continue
            if active and marks!=active["marks"]: raise RuntimeError("Source changed during delivery")
            if not active:
                if cid in state["done"] or any(set(marks)&set(v) for v in state["done"].values()): continue
                # General receives a separate eligible course, never the same
                # course sent to a specialty in this or a previous cycle.
                if cat in used:
                    if "general" in used: continue
                    cat="general"
                if cat in used: continue
                active={"cid":cid,"marks":marks,"cat":cat,"next":0,"pending":None}
                state["active"]=active; checkpoint(state)
            cat=active["cat"]
            credit="Source / crédit : "+str(source["credit"]).strip()
            destchat=dest[cat]
            # Validate entire course before sending any item.
            plan=[]
            for n,m in enumerate(group):
                marker="Réf. F-"+digest(key,cid+":"+str(n))[:18]
                body=m["text"]
                if m["kind"]=="poster": body=(body+"\n\n"+credit).strip()
                if m["kind"]=="file" and not body: body=m["name"] or "Document de formation"
                body=(body+"\n\n"+marker).strip()
                if len(body.encode("utf-16-le"))//2 > (4096 if m["kind"]=="text" else 1024): raise RuntimeError("Caption too long; manual review required")
                plan.append((m,marker,body))
            # Forward media to a private technical channel WITH original attribution.
            # Do not use drop_author, or bypass Telegram's forwarding restrictions.
            for i in range(active["next"],len(plan)):
                m,marker,body=plan[i]
                if m["kind"]=="text":
                    method="sendMessage"; params={"chat_id":destchat,"text":body}
                else:
                    forwarded=await client.forward_messages(entities[stage],m["id"],from_peer=entities[int(source["chat"])])
                    if not forwarded: raise RuntimeError("Staging failed")
                    method="copyMessage"; params={"chat_id":destchat,"from_chat_id":stage,"message_id":forwarded.id,"caption":body}
                    await asyncio.sleep(3)
                active["pending"]=marker; checkpoint(state)
                bot.call(method,**params)
                active["next"]=i+1; active["pending"]=None; checkpoint(state)
                await asyncio.sleep(3)
            state["done"][cid]=marks
            state["active"]=None; checkpoint(state); used.add(cat)
            print("Course delivered:",cat,"files:",sum(m["kind"]=="file" for m in group))
            if len(used)==5: break
    except errors.FloodWaitError as exc:
        if os.environ.get("FORMATION_DURABLE_STATE")=="true":
            state["cooldown"]=int(time.time())+int(exc.seconds)+60
            checkpoint(state)
        print("Personal FloodWait seconds:",int(exc.seconds))
        raise RuntimeError("Stop: Telegram requested cooldown") from None
    finally:
        await client.disconnect()

if __name__=="__main__":
    try: asyncio.run(run("--publish" in sys.argv))
    except Exception as exc:
        # Only our own controlled RuntimeError messages may be exposed.
        print("Formation stopped:",str(exc) if type(exc) is RuntimeError else type(exc).__name__,file=sys.stderr)
        sys.exit(1)
