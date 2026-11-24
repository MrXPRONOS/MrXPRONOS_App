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


# Keep educational text, remove external promotions and Telegram handles.
# Telegram hidden URL entities are not copied: all outgoing text is plain.
URL = re.compile(r"(?i)(?:\b(?:https?|ftp|tg|ton|mailto):(?:/{0,2})[^\s<>\"'«»]+|\bwww\.[^\s<>\"'«»]+|\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|me|fr|tg|co|be|info|biz|xyz|app|link|site|online|store|edu|gov|africa|dev|ly|to|tv|cc|ai|uk|de|ru|ng|ci|sn|bj|cm|gh|us|ca|cloud|tech|live|pro|shop|page|academy|training)(?![\w.-])(?:[/?#][^\s<>\"'«»]*)?)")
HANDLE = re.compile(r"(?<![\w@])@[a-zA-Z0-9_]{1,32}\b")
MARKDOWN_LINK = re.compile(r"\[([^\]\n]+)\]\((?:https?://|tg:|www\.|t\.me/)[^)\n]+\)",re.I)

def clean_text(text):
    text=MARKDOWN_LINK.sub(r"\1",text or "")
    text=URL.sub("",text)
    text=HANDLE.sub("",text)
    text=re.sub(r"\[\s*\]|\(\s*\)|<\s*>","",text)
    lines=[re.sub(r"[ \t]+"," ",line).strip() for line in text.splitlines()]
    # Drop orphaned advertising labels, but preserve substantive text.
    lines=[line for line in lines if not re.fullmatch(r"(?i)(?:lien|link|telegram|contact|whatsapp|rejoignez[- ]nous|abonnez[- ]vous|suivez[- ]nous|canal|channel)\s*[:\-–—]?\s*",line)]
    return re.sub(r"\n{3,}","\n\n","\n".join(lines)).strip()

def clean_message(message):
    # Telegram URL and mention entities use UTF-16 offsets, not Python indices.
    # A hidden text URL is neutralized by not passing its entity to Bot API.
    raw=message.raw_text or ""
    data=raw.encode("utf-16-le")
    spans=[]
    for entity in message.entities or []:
        if type(entity).__name__ in {"MessageEntityUrl","MessageEntityMention"}:
            spans.append((entity.offset*2,(entity.offset+entity.length)*2))
    for start,end in sorted(set(spans),reverse=True):
        if 0<=start<end<=len(data):
            data=data[:start]+data[end:]
    return clean_text(data.decode("utf-16-le"))


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

def channel_ref(value):
    """Canonical config reference, not an authorization to join a channel."""
    if isinstance(value,bool) or not isinstance(value,(str,int)):
        raise ValueError("Invalid channel reference")
    value=str(value).strip()
    if re.fullmatch(r"-100[0-9]+",value):
        return int(value)
    match=re.fullmatch(r"(?:(?:https?://)?(?:t\.me|telegram\.me)/|@)?([a-zA-Z][a-zA-Z0-9_]{3,31})/?",value,re.I)
    if match:
        return "@"+match[1].lower()
    raise ValueError("Invalid channel reference: expected public username or -100 ID")

def read_config_json(name, expected_type):
    raw=os.environ.get(name, "").strip()
    if not raw:
        raise RuntimeError(name+" is missing or empty")
    try:
        value=json.loads(raw)
    except json.JSONDecodeError:
        # Repair ONLY bare @username tokens outside JSON strings. Never eval
        # config, infer missing rights flags, or change quoted author text.
        pattern=r'"(?:\\.|[^"\\])*"|(?<![\w@])@[A-Za-z][A-Za-z0-9_]{3,31}(?=\s*[,}\]])'
        repaired=re.sub(pattern,lambda m: json.dumps(m[0]) if m[0].startswith("@") else m[0],raw)
        try:
            value=json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name}: invalid JSON at line {exc.lineno}, column {exc.colno}") from None
    if not isinstance(value,expected_type):
        raise RuntimeError(name+" has the wrong JSON structure")
    return value

def config():
    sources=read_config_json("FORMATION_SOURCES_JSON",list)
    dest=read_config_json("FORMATION_DESTINATIONS_JSON",dict)
    stage=channel_ref(os.environ["FORMATION_STAGE_CHAT"])
    key=os.environ["FORMATION_STATE_KEY"]
    if len(key)<32 or set(dest)!=set(CATS)|{"general"} or not sources: raise ValueError("Invalid config")
    dest={k:channel_ref(v) for k,v in dest.items()}
    if not isinstance(stage,int): raise RuntimeError("FORMATION_STAGE_CHAT must identify the private staging channel by -100 ID")
    for source in sources:
        if not isinstance(source,dict) or source.get("authorized") is not True or not str(source.get("credit","")).strip():
            raise ValueError("Missing source permission or credit")
        source["chat"]=channel_ref(source["chat"])
        if not clean_text(str(source["credit"])): raise ValueError("Credit must contain a plain author or source name")
        if source.get("category","auto") not in (*CATS,"general","auto"): raise ValueError("Invalid source category")
    refs=[stage,*dest.values(),*[s["chat"] for s in sources]]
    if len(set(refs))!=len(refs): raise ValueError("Overlapping channel references")
    return sources,dest,stage,key

async def run(publish):
    from telethon import TelegramClient, errors, utils
    from telethon.sessions import StringSession
    sources,dest,stage,key=config()
    state=load_state()
    if state.get("cooldown",0)>time.time(): raise RuntimeError("Personal Telegram cooldown active")
    bot=Bot(os.environ["FORMATION_BOT_TOKEN"])
    me=bot.call("getMe")["id"]
    resolved_dest={}
    for cat,chat in [*dest.items(),("stage",stage)]:
        info=bot.call("getChat",chat_id=chat)
        if info["type"]!="channel" or bool(info.get("username"))!=(cat=="general") or (cat=="stage" and info.get("has_protected_content")):
            raise RuntimeError("Wrong destination type/visibility: "+cat)
        chat_id=info["id"]
        if cat!="stage": resolved_dest[cat]=chat_id
        elif chat_id!=stage: raise RuntimeError("Staging channel identity mismatch")
        member=bot.call("getChatMember",chat_id=chat_id,user_id=me)
        if member["status"] not in ("creator","administrator") or (cat!="stage" and member["status"]!="creator" and not member.get("can_post_messages")):
            raise RuntimeError("Bot permissions missing: "+cat)
    dest=resolved_dest
    if len(set([stage,*dest.values()]))!=6: raise RuntimeError("Overlapping destination IDs")
    print("Destination channels validated:",len(dest))
    client=TelegramClient(StringSession(os.environ["TG_STRING_SESSION"]),int(os.environ["TG_API_ID"]),os.environ["TG_API_HASH"],flood_sleep_threshold=0,request_retries=0)
    try:
        await client.connect()
        if not await client.is_user_authorized(): raise RuntimeError("Personal session unauthorized")
        entities={d.id:d.entity async for d in client.iter_dialogs()}
        if any(i not in entities for i in [stage,*dest.values()]):
            raise RuntimeError("Personal account must already belong to all destination and staging channels")
        # Resolve public sources once to canonical peer IDs. Numeric private
        # references must already be accessible via the personal account.
        seen={stage,*dest.values()}
        for index,source in enumerate(sources,1):
            ref=source["chat"]
            if isinstance(ref,int):
                entity=entities.get(ref)
            else:
                try:
                    entity=await client.get_entity(ref)
                except (ValueError,errors.UsernameInvalidError,errors.UsernameNotOccupiedError):
                    raise RuntimeError(f"Source #{index}: public username not found") from None
            if entity is None or not getattr(entity,"broadcast",False):
                raise RuntimeError(f"Source #{index}: inaccessible or not a broadcast channel")
            peer=utils.get_peer_id(entity)
            if peer in seen: raise RuntimeError("Overlapping canonical source/destination IDs")
            seen.add(peer)
            entities[peer]=entity
            source["chat"]=peer
        print("Source channels validated:",len(sources))
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
                kind="poster" if m.photo or family=="poster" else "file" if family else "text" if (not m.media or getattr(m,"web_preview",None)) and m.raw_text else "other"
                records.append({"id":m.id,"kind":kind,"family":family,"album":m.grouped_id,"text":m.raw_text or "","clean_text":clean_message(m),"name":name,"size":size,"media":str(m.document.id) if m.document else "","protected":bool(getattr(m,"noforwards",False))})
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
            credit="Source / crédit : "+clean_text(str(source["credit"]))
            destchat=dest[cat]
            # Validate entire course before sending any item.
            plan=[]
            for n,m in enumerate(group):
                marker="Réf. F-"+digest(key,cid+":"+str(n))[:18]
                body=m.get("clean_text",clean_text(m["text"]))
                if m["kind"]=="text" and not body:
                    plan.append((m,marker,None)); continue
                if m["kind"]=="poster": body=(body+"\n\n"+credit).strip()
                if m["kind"]=="file" and not body: body=clean_text(m["name"]) or "Document de formation"
                body=(body+"\n\n"+marker).strip()
                if len(body.encode("utf-16-le"))//2 > (4096 if m["kind"]=="text" else 1024): raise RuntimeError("Caption too long; manual review required")
                plan.append((m,marker,body))
            # Forward media to a private technical channel WITH original attribution.
            # Do not use drop_author, or bypass Telegram's forwarding restrictions.
            for i in range(active["next"],len(plan)):
                m,marker,body=plan[i]
                if body is None:
                    active["next"]=i+1; checkpoint(state); continue
                if m["kind"]=="text":
                    method="sendMessage"; params={"chat_id":destchat,"text":body,"link_preview_options":{"is_disabled":True}}
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
