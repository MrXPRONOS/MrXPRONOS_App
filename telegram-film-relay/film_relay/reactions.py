"""Short optional CineX reactions reminder with persistent anti-duplication."""
import logging

LOG = logging.getLogger("cinex_reactions")
REACTION_PARTS = (
    "❤️ Ne restez pas spectateurs !",
    "🍿 Laissez un cœur et réagissez si vous avez aimé ce film !",
    "💬 Votre avis compte !",
)
# Telegram stores formatted messages as plain raw_text, without HTML tags.
REACTION_TEXT = "\n".join(REACTION_PARTS)
REACTION_HTML = (
    f"<b>{REACTION_PARTS[0]}</b>\n"
    f"<b><i>{REACTION_PARTS[1]}</i></b>\n"
    f"<blockquote>{REACTION_PARTS[2]}</blockquote>"
)
LEGACY_REACTION_TEXT = (
    "❤️ Ne restez pas spectateurs ! Laissez un cœur et réagissez si vous avez aimé le film ! 🍿"
)

PINNED_PARTS = (
    "🎬 Ne restez pas spectateurs !",
    "❤️ Abonnez-vous à CinéX et soutenez nos films !",
    "🍿 Vos réactions font vivre la communauté.",
)
# Copy-friendly one-line text; the actual formatted version has three short lines
# because Telegram renders a blockquote on a separate line.
PINNED_TEXT = " ".join(PINNED_PARTS)
PINNED_HTML = (
    f"<b>{PINNED_PARTS[0]}</b>\n"
    f"<b><i>{PINNED_PARTS[1]}</i></b>\n"
    f"<blockquote>{PINNED_PARTS[2]}</blockquote>"
)


def reaction_entities():
    """Explicit MTProto entities guarantee a real Telegram blockquote.

    Telethon's HTML parser and Telegram Bot API do not necessarily support
    the same tags. Telegram offsets use UTF-16 code units, not Python indices.
    """
    from telethon.tl.types import (
        MessageEntityBold, MessageEntityItalic, MessageEntityBlockquote,
    )

    def units(value):
        return len(value.encode("utf-16-le")) // 2

    a, b, quote = REACTION_PARTS
    second = units(a + "\n")
    third = units(a + "\n" + b + "\n")
    return [
        MessageEntityBold(offset=0, length=units(a)),
        MessageEntityBold(offset=second, length=units(b)),
        MessageEntityItalic(offset=second, length=units(b)),
        MessageEntityBlockquote(offset=third, length=units(quote), collapsed=False),
    ]


async def send_after_film(client, bot, channel, anchor_id, state, key, *, audience):
    if audience not in ("private", "public"):
        raise ValueError("Audience invalide")
    receipts = state.data.setdefault("reaction_prompts", {})
    receipt_key = f"{audience}:{key}"
    if receipt_key in receipts:
        return False
    try:
        async for msg in client.iter_messages(channel, limit=70):
            reply_id = getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None)
            if (
                " ".join(str(getattr(msg, "raw_text", "") or "").split()) in {
                    " ".join(REACTION_TEXT.split()),
                    " ".join(LEGACY_REACTION_TEXT.split()),
                }
                and int(reply_id or 0) == int(anchor_id)
            ):
                receipts[receipt_key] = int(msg.id)
                state.save()
                return False
    except Exception as exc:
        LOG.warning("Vérification anti-doublon impossible (%s): %s", audience, exc)
        return False

    try:
        if audience == "public":
            sent = await bot.send_message(
                channel, REACTION_HTML, parse_mode="html",
                reply_to_message_id=int(anchor_id))
        else:
            sent = await client.send_message(
                channel, REACTION_TEXT, formatting_entities=reaction_entities(),
                reply_to=int(anchor_id))
        receipts[receipt_key] = int(sent.id)
        state.save()
        return True
    except Exception as exc:
        LOG.warning("Message réactions non envoyé (%s/%s): %s", audience, key, exc)
        return False
