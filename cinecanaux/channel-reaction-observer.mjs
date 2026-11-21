/**
 * Lightweight publication observer, not a reaction dispatcher.
 *
 * GitHub Actions owns all Telegram reaction requests and job creation.
 * The existing Cine Radar webhook still receives channel_post events for
 * unrelated features; record only the stable message reference in D1.
 * Do not call Telegram, create reaction jobs, or poll queues here.
 */
export function isChannelPublication(post) {
  return post?.chat?.type === "channel"
    && Number.isSafeInteger(post.chat.id)
    && post.chat.id < 0
    && Number.isSafeInteger(post.message_id)
    && post.message_id > 0
    && !post.is_automatic_forward;
}

export async function observeChannelPublication(env, post) {
  if (!isChannelPublication(post)) return { observed: false };
  if (!env?.DB) throw new Error("channel_publication_db_unavailable");
  const chatId = String(post.chat.id);
  const mediaGroupId = post.media_group_id ? String(post.media_group_id) : null;
  // The unique index on (chat_id,media_group_id) deduplicates albums.
  // One D1 INSERT, no read-back and no reaction jobs on Cloudflare.
  await env.DB.prepare(
    "INSERT OR IGNORE INTO channel_reaction_posts(chat_id,message_id,media_group_id) VALUES(?,?,?)"
  ).bind(chatId, post.message_id, mediaGroupId).run();
  return { observed: true };
}
