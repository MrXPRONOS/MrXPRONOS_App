// T01 — Atomic, shared send quota for all CineX Telegram delivery families.
// D1 is the ONLY arbiter. No Worker-local counters, user sessions or raw chat IDs.
// On database errors the reservation is denied (never send without a slot).
const WINDOW_MS = 1000;
export const GLOBAL_PER_SECOND = 10;
export const PRIVATE_CHAT_PER_SECOND = 1;
const BUCKET = 'telegram:global';
const SCHEMA = `CREATE TABLE IF NOT EXISTS cine_telegram_send_quota (
  scope TEXT PRIMARY KEY,
  window_start_ms INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  blocked_until_ms INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;
const INSTALLED = new WeakMap();
const enc = new TextEncoder();

async function ensureSchema(db) {
  if (!db || typeof db.prepare !== 'function') throw Error('quota_db_unavailable');
  let pending = INSTALLED.get(db);
  if (!pending) {
    pending = db.prepare(SCHEMA).run();
    INSTALLED.set(db, pending);
  }
  try { await pending; }
  catch (error) { INSTALLED.delete(db); throw error; }
}

async function recipientScope(env, chatId) {
  // HMAC uses a secret held only by the Worker; no subscriber identifiers in D1.
  const key = String(env.TELEGRAM_WEBHOOK_SECRET || env.TELEGRAM_TOKEN || '');
  if (!key) throw Error('quota_secret_missing');
  const hmac = await crypto.subtle.importKey('raw', enc.encode(key),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const digest = new Uint8Array(await crypto.subtle.sign('HMAC', hmac, enc.encode(String(chatId))));
  return 'recipient:' + Array.from(digest.slice(0, 16), byte => byte.toString(16).padStart(2, '0')).join('');
}

async function oneBucket(db, scope, maximum, now) {
  // Single INSERT/UPSERT ... WHERE ... RETURNING is atomic even when all the
  // cron queue workers, webhooks and separate isolates race on the same D1 DB.
  const windowStart = Math.floor(now / WINDOW_MS) * WINDOW_MS;
  const slot = await db.prepare(
    "INSERT INTO cine_telegram_send_quota(scope,window_start_ms,used) VALUES(?,?,1) " +
    "ON CONFLICT(scope) DO UPDATE SET " +
    "window_start_ms=excluded.window_start_ms," +
    "used=CASE WHEN cine_telegram_send_quota.window_start_ms=excluded.window_start_ms " +
    "THEN cine_telegram_send_quota.used+1 ELSE 1 END," +
    "updated_at=CURRENT_TIMESTAMP " +
    "WHERE cine_telegram_send_quota.blocked_until_ms<=? " +
    "AND (cine_telegram_send_quota.window_start_ms<>excluded.window_start_ms OR cine_telegram_send_quota.used<?) " +
    "RETURNING used"
  ).bind(scope, windowStart, now, maximum).first();
  if (slot && Number(slot.used) >= 1) return { allowed: true, retryAfter: 0 };
  const current = await db.prepare(
    'SELECT window_start_ms,blocked_until_ms FROM cine_telegram_send_quota WHERE scope=?'
  ).bind(scope).first();
  const seconds = Math.max(1, Math.ceil(Math.max(
    Number(current?.blocked_until_ms || 0) - now,
    Number(current?.window_start_ms || windowStart) + WINDOW_MS - now
  ) / 1000));
  return { allowed: false, retryAfter: Math.min(3600, seconds), reason: 'quota_busy' };
}

export async function reserveTelegramSend(env, { chatId = null, now = Date.now() } = {}) {
  try {
    if (!Number.isSafeInteger(now) || now < 0) throw Error('quota_clock_invalid');
    await ensureSchema(env?.DB);
    // Per-recipient quota first: an impatient subscriber must not exhaust
    // the GLOBAL bucket while trying to download multiple films concurrently.
    if (chatId !== null && chatId !== undefined) {
      const scope = await recipientScope(env, chatId);
      const perRecipient = await oneBucket(env.DB, scope, PRIVATE_CHAT_PER_SECOND, now);
      if (!perRecipient.allowed) return perRecipient;
    }
    return await oneBucket(env.DB, BUCKET, GLOBAL_PER_SECOND, now);
  } catch {
    return { allowed: false, retryAfter: 60, reason: 'quota_unavailable' };
  }
}

export async function noteTelegramFloodWait(env, retryAfter, { now = Date.now() } = {}) {
  const seconds = Math.max(1, Math.min(3600, Math.ceil(Number(retryAfter) || 0)));
  try {
    await ensureSchema(env?.DB);
    // A real Telegram 429 pauses ALL sending families, not only its origin.
    const until = now + seconds * 1000;
    await env.DB.prepare(
      "INSERT INTO cine_telegram_send_quota(scope,window_start_ms,used,blocked_until_ms) " +
      "VALUES(?,0,0,?) ON CONFLICT(scope) DO UPDATE SET " +
      "blocked_until_ms=MAX(cine_telegram_send_quota.blocked_until_ms,excluded.blocked_until_ms)," +
      "updated_at=CURRENT_TIMESTAMP"
    ).bind(BUCKET, until).run();
    return { recorded: true, retryAfter: seconds };
  } catch {
    return { recorded: false, retryAfter: seconds };
  }
}

export async function pruneTelegramQuota(env) {
  try {
    await ensureSchema(env?.DB);
    const deleted = await env.DB.prepare(
      "DELETE FROM cine_telegram_send_quota WHERE scope<>? AND updated_at<datetime('now','-2 days')"
    ).bind(BUCKET).run();
    return { removed: Number(deleted.meta?.changes || 0) };
  } catch { return { removed: 0, unavailable: true }; }
}
