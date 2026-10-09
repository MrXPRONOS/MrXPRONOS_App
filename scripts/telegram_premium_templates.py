"""Five distinct editorial layouts for Telegram's structured Rich Messages.

HTML is emitted as discrete paragraph, heading, quote and footer blocks.
All user/provider strings are escaped by callers or by these builders.
"""
from html import escape
import re

_BLOCK=re.compile(r"(<blockquote(?:\s[^>]*)?>.*?</blockquote>)",re.S|re.I)

def _paras(chunk):
    return "".join(
        "<p>"+part.strip().replace("\n","<br/>")+"</p>"
        for part in re.split(r"\n\s*\n",chunk.strip())
        if part.strip()
    )

def premium_sections(html):
    """Preserve blockquotes, and make blank-line separated HTML into real blocks."""
    if str(html or "").lstrip().startswith(("<h3>","<p>","<h2>")):
        return str(html).strip()
    sections=_BLOCK.split(str(html or "").strip())
    return "".join(section if section.lstrip().startswith("<blockquote")
                   else _paras(section) for section in sections if section.strip())

def cta_note(label="Choisis ton bookmaker"):
    return f"<p><b>👇 {escape(label)}</b></p>"

def bonus(name,title,offer,pitch,code="XPVIP",conditions=""):
    e=lambda x:escape(str(x),quote=False)
    return (
        f"<h3>🔥 {e(name).upper()} — {e(title).upper()}</h3>"
        f"<p>Découvre l’offre du moment et vérifie ses conditions avant de t’inscrire.</p>"
        f"<blockquote><b>🎁 OFFRE</b><br/>{e(offer)}<br/>"
        f"<b>🏷 CODE PROMO : <code>{e(code)}</code></b></blockquote>"
        f"<p><i>{e(pitch)}</i></p>"
        "<p><b>✨ Comment en profiter</b></p>"
        "<p>1. Ouvre le lien partenaire ci-dessous.<br/>"
        "2. Crée ton compte si tu remplis les conditions.<br/>"
        f"3. Renseigne <b>{e(code)}</b> si le champ est proposé.<br/>"
        "4. Consulte les conditions avant tout dépôt.</p>"
        f"<p><b>⚠️ À vérifier</b><br/><i>{e(conditions or 'L’offre et son éligibilité peuvent varier selon le pays et le compte.')}</i></p>"
        "<p><i>🔞 18+ · Parie uniquement si tu le souhaites et de manière responsable.</i></p>"
        +cta_note("Accéder à l’offre")
    )

def guide(name,code="XPVIP"):
    e=lambda x:escape(str(x),quote=False)
    return (
        f"<h3>📲 GUIDE — OUVRIR UN COMPTE {e(name).upper()}</h3>"
        "<p>Les étapes essentielles pour accéder au partenaire présenté sur l’image.</p>"
        "<p><b>🧭 Les étapes</b><br/>"
        "1. Ouvre le lien ci-dessous.<br/>"
        "2. Renseigne les informations demandées.<br/>"
        f"3. Vérifie le champ <b>code promo</b> : <b>{e(code)}</b>.<br/>"
        "4. Lis les conditions avant de finaliser.</p>"
        f"<blockquote><b>🏷 CODE PROMO : <code>{e(code)}</code></b><br/>"
        "<i>Vérifie qu’il est appliqué si un champ promo est proposé.</i></blockquote>"
        "<p><i>🔞 18+ · Les conditions varient selon le pays et le compte. Jeu responsable.</i></p>"
        +cta_note("Ouvrir la page d’inscription")
    )

def partners(code="XPVIP"):
    e=lambda x:escape(str(x),quote=False)
    return (
        "<h3>🔥 XPVIP — PARTENAIRES MR XPRONOS</h3>"
        "<p>Retrouve les plateformes partenaires et leurs liens d’inscription ci-dessous.</p>"
        f"<blockquote><b>🏷 CODE PROMO : <code>{e(code)}</code></b><br/>"
        "<i>Vérifie sa prise en compte lorsque le formulaire le propose.</i></blockquote>"
        "<p><b>✨ Un seul code, plusieurs partenaires.</b><br/>"
        "Choisis librement la plateforme qui te convient.</p>"
        "<p><i>⚠️ Les conditions diffèrent selon le pays, le bookmaker et le compte.</i></p>"
        "<p><i>🔞 18+ · Jeu responsable.</i></p>"
        +cta_note("Choisis une plateforme ci-dessous")
    )

def daily_promo(title,intro,offer,code="XPVIP"):
    e=lambda x:escape(str(x),quote=False)
    return (
        f"<h3>{title}</h3>"
        f"<p>{intro}</p>"
        f"<blockquote><b>🎁 OFFRE</b><br/>{e(offer)}<br/>"
        f"<b>🏷 CODE PROMO : <code>{e(code)}</code></b></blockquote>"
        "<p><b>ℹ️ Avant de t’inscrire</b><br/>"
        f"Vérifie l’éligibilité et la présence du code <b>{e(code)}</b> "
        "lorsqu’un champ promo est disponible.</p>"
        "<p><i>🔞 18+ · Offre soumise à conditions ; joue de façon responsable.</i></p>"
        +cta_note("Consulter l’offre")
    )

def coupon(existing_html):
    """Preserve exact predictions and prices; improve block-level hierarchy only."""
    return premium_sections(existing_html)

def live(text):
    e=escape(str(text or ""),quote=False)
    lines=[line.strip() for line in e.splitlines() if line.strip()]
    if not lines:return ""
    return ("<h3>"+lines[0]+"</h3>"
            +"".join(f"<p>{line}</p>" for line in lines[1:])
            +"<p><i>🔞 18+ · Parier responsablement.</i></p>")
