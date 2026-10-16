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
    # Telethon resolves KeyboardInlineButton.url through MessageButton.url;
    # raw reply_markup.buttons may be keyboard wrappers with no .url field.
    for row in getattr(msg,"buttons",[]) or []:
        for wrapper in row:
            url=getattr(wrapper,"url",None)
            if url and str(url) not in found:
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
            markup=getattr(msg,"reply_markup",None)
            wrapped=getattr(msg,"buttons",None)
            print(f"{name}: message={msgid}, boutons={len(urls)}, destination={urls[:1]}")
            print(f"{name}: markup={type(markup).__name__}, "
                  f"button_wrapper={type(wrapped).__name__}, "
                  f"sender={getattr(msg,'sender_id',None)}, "
                  f"media={type(getattr(msg,'media',None)).__name__}, "
                  f"caption={repr(str(getattr(msg,'raw_text','') or '')[:95])}")
            if markup is not None:
                print(f"{name}: markup_sample={repr(markup)[:550]}")
                for row in getattr(markup,"rows",[]) or []:
                    for button in getattr(row,"buttons",[]) or []:
                        print(f"{name}: button_type={type(button).__name__}, "
                              f"url={getattr(button,'url',None)!r}, "
                              f"text={getattr(button,'text',None)!r}")
            for row in wrapped or []:
                for button in row:
                    print(f"{name}: wrapper_type={type(button).__name__}, "
                          f"wrapper_url={getattr(button,'url',None)!r}")
        return 0
    finally:
        await client.disconnect()


if __name__=="__main__":
    raise SystemExit(asyncio.run(execute()))
