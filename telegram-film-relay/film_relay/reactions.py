"""Short optional CineX reactions reminder with persistent anti-duplication."""
import logging

LOG = logging.getLogger("cinex_reactions")
REACTION_TEXT = "❤️ Ne restez pas spectateurs ! Laissez un cœur et réagissez si vous avez aimé le film ! 🍿"
PINNED_TEXT = "🎬 Ne restez pas spectateurs ! Abonnez-vous à CinéX et soutenez nos films avec un ❤️ !"


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
            if (str(getattr(msg, "raw_text", "") or "").strip() == REACTION_TEXT
                    and int(reply_id or 0) == int(anchor_id)):
                receipts[receipt_key] = int(msg.id)
                state.save()
                return False
    except Exception as exc:
        LOG.warning("Vérification anti-doublon impossible (%s): %s", audience, exc)
        return False

    try:
        if audience == "public":
            sent = await bot.send_message(
                channel, REACTION_TEXT, reply_to_message_id=int(anchor_id))
        else:
            sent = await client.send_message(
                channel, REACTION_TEXT, reply_to=int(anchor_id))
        receipts[receipt_key] = int(sent.id)
        state.save()
        return True
    except Exception as exc:
        LOG.warning("Message réactions non envoyé (%s/%s): %s", audience, key, exc)
        return False
