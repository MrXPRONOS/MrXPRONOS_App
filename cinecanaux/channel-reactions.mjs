import {reserveTelegramSend,noteTelegramFloodWait} from './telegram-global-quota.mjs';
/**
 * Channel-post reactions from two owner-controlled Telegram bots.
 *
 * All Telegram channel_post publishers are covered by the SAME authenticated
 * Cine Radar webhook. Never react to private messages, replies, test events,
 * edited posts or historical posts. No user Telegram session is used.
 *
 * Both bot credentials MUST be configured; otherwise deliveries remain queued.
 * D1 deduplicates channel messages and retains failed reactions for Cron retries.
 */
const ROLE_RADAR = "radar";
const ROLE_CANAL = "canal";
const TOKEN_NAMES = {
  [ROLE_RADAR]: "TELEGRAM_TOKEN",
  [ROLE_CANAL]: "CANAL_BOT_TOKEN",
};
const EXPECTED_BOT_NAMES = {
  [ROLE_RADAR]: "cineradarfr_bot",
  [ROLE_CANAL]: "mrxpronos_canal_bot",
};
const MAX_PENDING = 25;
const MAX_DELAY_SECONDS = 6 * 3600;
const idsVerified = new Map();

export function isNewChannelPublication(post) {
  return post?.chat?.type === "channel"
    && Number.isSafeInteger(post.chat.id)
    && post.chat.id < 0
    && Number.isSafeInteger(post.message_id)
    && post.message_id > 0
    && !post?.is_automatic_forward;
}

export function reactionFor(sequence, role) {
  if (!Number.isSafeInteger(sequence) || sequence <= 0) throw Error("Invalid sequence");
  if (role !== ROLE_RADAR && role !== ROLE_CANAL) throw Error("Invalid bot role");
  return (sequence % 2 === 1) === (role === ROLE_RADAR) ? "❤️" : "👍";
}

export async function enqueueChannelReactions(env, post) {
  if (!isNewChannelPublication(post)) return { queued: false };
  const chat = String(post.chat.id);
  const mediaGroup = post.media_group_id ? String(post.media_group_id) : null;
  // A single Telegram album receives just one pair of reactions.
  await env.DB.prepare(
    "INSERT OR IGNORE INTO channel_reaction_posts(chat_id,message_id,media_group_id) VALUES(?,?,?)"
  ).bind(chat, post.message_id, mediaGroup).run();
  const record = await env.DB.prepare(
    "SELECT seq,message_id FROM channel_reaction_posts WHERE chat_id=? AND (message_id=? OR (media_group_id IS NOT NULL AND media_group_id=?)) ORDER BY seq LIMIT 1"
  ).bind(chat, post.message_id, mediaGroup).first();
  if (!record?.seq) throw Error("reaction_queue_missing_post");
  const seq = Number(record.seq);
  await env.DB.batch([
    env.DB.prepare(
      "INSERT OR IGNORE INTO channel_reaction_jobs(post_seq,bot_role,emoji) VALUES(?,?,?)"
    ).bind(seq, ROLE_RADAR, reactionFor(seq, ROLE_RADAR)),
    env.DB.prepare(
      "INSERT OR IGNORE INTO channel_reaction_jobs(post_seq,bot_role,emoji) VALUES(?,?,?)"
    ).bind(seq, ROLE_CANAL, reactionFor(seq, ROLE_CANAL)),
  ]);
  return { queued: true, postSequence: seq };
}

function nextTryDate(seconds) {
  return new Date(Date.now() + seconds * 1000).toISOString().slice(0, 19).replace("T", " ");
}

async function callTelegram(token, method, data, request) {
  let response;
  try {
    response = await request("https://api.telegram.org/bot" + token + "/" + method, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(data),
      signal: AbortSignal.timeout(8500),
    });
  } catch {
    return { ok: false, error: "transport_unavailable", retryAfter: 0, status: 0 };
  }
  let payload;
  try { payload = await response.json(); }
  catch { return { ok: false, error: "bad_response", retryAfter: 0, status: response.status }; }
  return {
    ok: response.ok && payload?.ok === true,
    result: payload?.result,
    error: String(payload?.description || "telegram_rejected").slice(0, 150),
    retryAfter: Number(payload?.parameters?.retry_after || 0),
    status: response.status,
  };
}

async function confirmBotRole(role, token, request) {
  // This lookup is safe to cache within the Worker isolate.
  const prior = idsVerified.get(role);
  if (prior?.token === token && prior.expires > Date.now()) return prior.ok;
  const who = await callTelegram(token, "getMe", {}, request);
  const ok = who.ok
    && String(who.result?.username || "").toLowerCase() === EXPECTED_BOT_NAMES[role];
  idsVerified.set(role, { token, ok, expires: Date.now() + (ok ? 3600000 : 60000) });
  return ok;
}

async function deliverReaction(token, chatId, messageId, emoji, request) {
  return callTelegram(token, "setMessageReaction", {
    chat_id: chatId,
    message_id: messageId,
    reaction: [{ type: "emoji", emoji }],
    is_big: false,
  }, request);
}

/**
 * Trigger after channel_post and from the 1-minute Cron.
 * The first role is always completed before the second starts on that post.
 */
export async function processReactionQueue(env, { limit = MAX_PENDING, request = fetch } = {}) {
  const enabled = env?.TELEGRAM_TOKEN && env?.CANAL_BOT_TOKEN && env?.DB;
  if (!enabled) return { skipped: "missing_bot_credentials_or_database" };
  const rows = await env.DB.prepare(
    "SELECT j.post_seq,j.bot_role,j.emoji,j.attempts,p.chat_id,p.message_id " +
    "FROM channel_reaction_jobs j JOIN channel_reaction_posts p ON p.seq=j.post_seq " +
    "WHERE NOT EXISTS (SELECT 1 FROM channel_reaction_terminal_posts t WHERE t.post_seq=j.post_seq) " +
    "AND ((j.state IN ('pending','retry') AND datetime(j.next_try_at)<=CURRENT_TIMESTAMP) " +
    "OR (j.state='sending' AND datetime(j.updated_at)<=datetime('now','-2 minutes'))) " +
    "ORDER BY j.post_seq ASC,CASE j.bot_role WHEN 'radar' THEN 0 ELSE 1 END LIMIT ?"
  ).bind(Math.min(MAX_PENDING, Math.max(1, Math.trunc(limit) || 1))).all();
  let sent = 0, failed = 0, deferred = 0;
  for (const row of rows.results || []) {
    const role = row.bot_role;
    if (role !== ROLE_RADAR && role !== ROLE_CANAL) continue;
    if (role === ROLE_CANAL) {
      const preceding = await env.DB.prepare(
        "SELECT state FROM channel_reaction_jobs WHERE post_seq=? AND bot_role='radar'"
      ).bind(row.post_seq).first();
      if (preceding?.state !== "sent") { deferred++; continue; }
    }
    // Reaction updates also share the global quota, but do not count as new chat messages.
    const quota=await reserveTelegramSend(env);
    if(!quota.allowed){deferred++;continue;}
    const claim = await env.DB.prepare(
      "UPDATE channel_reaction_jobs SET state='sending',attempts=attempts+1,updated_at=CURRENT_TIMESTAMP " +
      "WHERE post_seq=? AND bot_role=? AND " +
      "((state IN ('pending','retry') AND datetime(next_try_at)<=CURRENT_TIMESTAMP) " +
      "OR (state='sending' AND datetime(updated_at)<=datetime('now','-2 minutes')))"
    ).bind(row.post_seq, role).run();
    if (Number(claim?.meta?.changes || 0) !== 1) continue;

    const token = env[TOKEN_NAMES[role]];
    let answer;
    if (!(await confirmBotRole(role, token, request))) {
      answer = { ok: false, error: "bot_username_mismatch_or_unreachable", status: 0 };
    } else {
      answer = await deliverReaction(token, row.chat_id, Number(row.message_id), row.emoji, request);
    }
    if(Number(answer.status)===429)await noteTelegramFloodWait(env,answer.retryAfter||30);
    // A channel message that Telegram can no longer find will not become
    // reactable through retries. Quarantine the entire post (both bot roles),
    // without deleting it from the audit ledger or blocking newer posts.
    if (Number(answer.status) === 400 && /message to react not found/i.test(String(answer.error || ""))) {
      await env.DB.prepare(
        "INSERT OR IGNORE INTO channel_reaction_terminal_posts(post_seq,reason) VALUES(?,?)"
      ).bind(row.post_seq, "telegram_message_not_found").run();
      await env.DB.prepare(
        "UPDATE channel_reaction_jobs SET state='retry',next_try_at='9999-12-31 23:59:59'," +
        "last_error='terminal:message_not_found',updated_at=CURRENT_TIMESTAMP " +
        "WHERE post_seq=? AND bot_role=?"
      ).bind(row.post_seq, role).run();
      console.warn("channel_reaction_terminal_post", Number(row.post_seq));
      failed++;
      continue;
    }
    if (answer.ok) {
      await env.DB.prepare(
        "UPDATE channel_reaction_jobs SET state='sent',sent_at=CURRENT_TIMESTAMP,last_error='',updated_at=CURRENT_TIMESTAMP WHERE post_seq=? AND bot_role=?"
      ).bind(row.post_seq, role).run();
      sent++;
    } else {
      // No blind resend of the channel publication; only re-apply the reaction.
      // Telegram reaction setting is idempotent for one bot and one emoji.
      const delay = Math.max(
        30,
        Math.min(MAX_DELAY_SECONDS,
          Math.max(Number(answer.retryAfter || 0), 30 * (2 ** Math.min(8, Number(row.attempts || 0))))
        )
      );
      await env.DB.prepare(
        "UPDATE channel_reaction_jobs SET state='retry',next_try_at=?,last_error=?,updated_at=CURRENT_TIMESTAMP WHERE post_seq=? AND bot_role=?"
      ).bind(nextTryDate(delay), String(answer.error || "telegram_rejected").slice(0, 150), row.post_seq, role).run();
      console.warn("channel_reaction_retry", role, Number(answer.status || 0), "after", delay);
      failed++;
    }
  }
  return { sent, failed, deferred };
}
