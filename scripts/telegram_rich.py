"""Telegram Bot API 10.3 rich messages: photo, caption and embedded CTA rows.

A request explicitly rejected by Telegram (HTTP 400/404) can fall back to
legacy sendPhoto without losing the publication. Ambiguous network errors
must not trigger a second send.
"""
import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from telegram_premium_templates import premium_sections

class RichFormatUnavailable(Exception): pass

def rich_buttons(markup):
    if not isinstance(markup,dict):return ""
    result=[]
    for row in markup.get("inline_keyboard",[]):
        entries=[]
        for item in row:
            if not isinstance(item,dict) or not item.get("url"):continue
            url=str(item["url"])
            if urlsplit(url).scheme not in ("https","http"):continue
            style=item.get("style") or "primary"
            if style not in ("danger","success","primary"):style="primary"
            label=escape(str(item.get("text") or ""),quote=False)
            entries.append(f'<tg-button type="url" style="{style}" url="{escape(url,quote=True)}">{label}</tg-button>')
        if entries:
            result.append('<tg-button-row align="center">'+''.join(entries)+'</tg-button-row>')
    return '\n'.join(result)

def rich_markup(caption,keyboard,*,picture=True):
    # Captions already supplied by our publisher are correctly HTML-escaped.
    body=str(caption or "").strip()
    parts=[]
    if picture:parts.append('<img src="tg://photo?id=coupon"/>')
    if body:parts.append(premium_sections(body))
    buttons=rich_buttons(keyboard)
    if buttons:parts.append(buttons)
    return '\n'.join(parts)

def legacy_caption(html):
    """Downgrade rich-only tags without losing Telegram-supported emphasis."""
    plain=re.sub(r"</?(?:h[1-6]|p)>","\n",str(html or ""),flags=re.I)
    plain=re.sub(r"<br\s*/?>","\n",plain,flags=re.I)
    return re.sub(r"\n{3,}","\n\n",plain).strip()


def post_photo(session,token,chat,image,caption,keyboard,*,timeout=120,mime="image/png"):
    p=Path(image)
    url=f"https://api.telegram.org/bot{token}/sendRichMessage"
    rm={"html":rich_markup(caption,keyboard),
        "media":[{"id":"coupon","media":{"type":"photo","media":"attach://coupon_photo"}}]}
    with p.open("rb") as f:
        response=session.post(url,data={"chat_id":chat,"rich_message":json.dumps(rm,ensure_ascii=False)},
            files={"coupon_photo":(p.name,f,mime)},timeout=timeout)
    if response.status_code in (400,404):
        print("TELEGRAM_RICH_UNAVAILABLE:",response.status_code,"using legacy photo")
        with p.open("rb") as f:
            response=session.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id":chat,"caption":legacy_caption(caption),"parse_mode":"HTML",
                      "reply_markup":json.dumps(keyboard,ensure_ascii=False)},
                files={"photo":(p.name,f,mime)},timeout=timeout)
    response.raise_for_status()
    payload=response.json()
    if not payload.get("ok"):raise RuntimeError("Telegram rejected rich/photo message")
    return payload["result"]["message_id"]

def post_text(session,token,chat,text,keyboard=None,*,timeout=60,html=False):
    rm={"html":rich_markup(text if html else escape(str(text)),keyboard,picture=False)}
    resp=session.post(f"https://api.telegram.org/bot{token}/sendRichMessage",
            data={"chat_id":chat,"rich_message":json.dumps(rm,ensure_ascii=False)},timeout=timeout)
    if resp.status_code in (400,404):
        payload={"chat_id":chat,"text":text}
        if html:
            payload["parse_mode"]="HTML"
            payload["text"]=legacy_caption(text)
        if keyboard:payload["reply_markup"]=json.dumps(keyboard,ensure_ascii=False)
        resp=session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data=payload,timeout=timeout)
    resp.raise_for_status()
    body=resp.json()
    if not body.get("ok"):raise RuntimeError("Telegram rejected rich/text message")
    return body["result"]["message_id"]
