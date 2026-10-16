"""Read-only check that native Telegram URL buttons survived primary->mirror forwarding."""
from __future__ import annotations
import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from film_relay.state import State
from film_relay.runner import config_from


def button_urls(msg):
    found=[]
    markup=getattr(msg,"reply_markup",None)
    for row in getattr(markup,"rows",[]) or []:
        for button in getattr(row,"buttons",[]) or []:
            url=getattr(button,"url",None)
            if url:
                found.append(str(url))
    return found


async def execute():
    config=config_from(os.getenv("CHANNELS_CONFIG","config/channels.json"))
    state=State(os.getenv("STATE_PATH","state/state.json"))
    client=TelegramClient(StringSession(os.environ["TG_STRING_SESSION"]),
                          int(os.environ["TG_API_ID"]),os.environ["TG_API_HASH"])
    await client.connect()
    try:
        public=await client.get_entity(config["public_channel"])
        mirror=await client.get_entity(config["mirror_channel"])
        private=await client.get_entity(int(config["private_channel"]))
        ids=[
            ("principal",str(getattr(public,"id",0))),
            ("secondaire",str(getattr(mirror,"id",0))),
            ("privé",str(getattr(private,"id",0))),
        ]
        for name,id_text in ids:
            key="-100"+id_text
            entry=state.data.get("promotions",{}).get(key,{})
            sent=entry.get("sent",{})
            if not sent:
                print(f"{name}: AUCUNE PUBLICITÉ enregistrée.")
                continue
            msgid=int(sent[sorted(sent,key=lambda x:int(x))[-1]])
            channel={"principal":public,"secondaire":mirror,"privé":private}[name]
            msgs=await client.get_messages(channel,ids=msgid)
            msg=msgs if not isinstance(msgs,list) else (msgs[0] if msgs else None)
            if msg is None:
                print(f"{name}: message manquant (id={msgid})")
                continue
            urls=button_urls(msg)
            print(f"{name}: message={msgid}, boutons={len(urls)}, destination={urls[:1]}")
        return 0
    finally:
        await client.disconnect()


if __name__=="__main__":
    raise SystemExit(asyncio.run(execute()))
