"""Four daily French RSS posts to the explicit public Fast Deal Telegram channel."""
from datetime import datetime, timezone
import os
from crypto import news_multichannel_v1 as net
from crypto import news_digest_v1 as digest
from crypto import news_media_v1 as media
from crypto import news_translation_v1 as translator
from crypto import production_live_v1 as live

CHANNEL = "@fastdealexchange"

def publish():
    if os.environ.get("CRYPTO_FASTDEAL_ONLY") != "1":
        raise RuntimeError("Fast Deal dispatch must be explicitly selected")
    db = net.Supabase()
    client = net.Telegram()
    bot = client.get("getMe")
    if bot.get("username", "").lower() != net.EXPECTED_BOT or bot.get("is_bot") is not True:
        raise RuntimeError("Unexpected Telegram bot")
    chat = client.get("getChat", {"chat_id": CHANNEL})
    if chat.get("type") != "channel" or str(chat.get("username", "")).lower() != CHANNEL[1:]:
        raise RuntimeError("Fast Deal public channel identity not verified")
    channel_id = int(chat["id"])
    member = client.get("getChatMember", {"chat_id": CHANNEL, "user_id": bot["id"]})
    if member.get("status") not in ("creator", "administrator") or (
        member.get("status") == "administrator" and member.get("can_post_messages") is not True
    ):
        raise RuntimeError("Bot is not authorized to post to Fast Deal")
    receipts = db.rpc("mrx_fastdeal_rss_receipts")
    if not isinstance(receipts, list):
        raise RuntimeError("Fast Deal receipts unavailable")
    today = datetime.now(timezone.utc).date()
    used = 0
    for r in receipts:
        if r.get("status") not in ("reserved", "confirmed"):
            continue
        try:
            day = datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")).astimezone(timezone.utc).date()
        except (KeyError, ValueError, TypeError):
            raise RuntimeError("Invalid Fast Deal receipt timestamp") from None
        if day == today:
            used += 1
    if used >= 4:
        print("FASTDEAL_DAILY_CAP_REACHED")
        return
    candidates = digest.collect({"sent": {}}, datetime.now(timezone.utc))[:net.MAX_CANDIDATES]
    translation = translator.FrenchTranslator()
    for cand in candidates:
        if any(isinstance(r.get("story"), dict) and digest.same_event(cand["main"], r["story"])
               for r in receipts):
            continue
        k = net.article_key(cand)
        photo = media.photo_for(cand, dest=media.OUTPUT.parent / ("fastdeal_" + k + ".jpg"))
        if not photo:
            continue
        image, source = photo
        try:
            french = translation.translate(cand["main"])
            caption = media.caption(cand, image_source=source, translated=french, require_french=True)
        except (translator.TranslationHold, ValueError):
            continue
        result = db.rpc("mrx_fastdeal_rss_claim", {
            "p_article": k, "p_story": net.story_data(cand)
        })
        if result == "daily_cap":
            print("FASTDEAL_DAILY_CAP_REACHED")
            return
        if result != "claimed":
            continue
        # The reservation remains if Telegram's result is uncertain, preventing blind retries.
        message_id = live.record_send({"id": channel_id, "destination": CHANNEL},
                                      caption, image, parse_mode="HTML")
        if db.rpc("mrx_fastdeal_rss_confirm", {
            "p_article": k, "p_message_id": message_id
        }) is not True:
            raise RuntimeError("Fast Deal Telegram confirmation not recorded")
        print("FASTDEAL_RSS_PUBLISHED confirmed=1")
        return
    print("FASTDEAL_NO_VERIFIED_NEW_RSS_NEWS")

if __name__ == "__main__":
    publish()
