// Ciné Radar — moteur de copies Telegram (compte Cloudflare 44).
// Le webhook et les décisions d'autorisation restent sur le compte 52.
// N'expose aucun endpoint public d'envoi sans HMAC valide.
const encoder = new TextEncoder();
const NO_STORE = {'cache-control':'no-store','x-content-type-options':'nosniff'};
const COPY_ROUTE = '/internal/v1/copy';

function json(value, status=200) {
  return Response.json(value, {status, headers:NO_STORE});
}
function positiveId(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0;
}
function validSourceChatId(value) {
  return /^-100[0-9]{5,}$/.test(String(value)) || positiveId(value);
}
export function validIntent(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return false;
  if (!/^(classic|library|franchise|series):[A-Za-z0-9_-]{1,80}$/.test(String(body.request_id || ''))) return false;
  if (body.method !== 'copyMessage') return false;
  if (!/^\d{6,12}:[A-Za-z0-9_-]{20,}$/.test(String(body.bot_token || ''))) return false;
  const p = body.payload;
  if (!p || typeof p !== 'object' || Array.isArray(p)) return false;
  if (!positiveId(p.chat_id) || !validSourceChatId(p.from_chat_id) || !positiveId(p.message_id)) return false;
  if (p.reply_markup !== undefined && (!p.reply_markup || typeof p.reply_markup !== 'object' || JSON.stringify(p.reply_markup).length > 3000)) return false;
  return true;
}
function hexToBytes(hex) {
  if (!/^[a-f0-9]{64}$/i.test(hex || '')) return null;
  return new Uint8Array((hex.match(/.{2}/g) || []).map(x => parseInt(x,16)));
}
export async function signBody(secret, timestamp, text) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), {name:'HMAC',hash:'SHA-256'}, false, ['sign']);
  const bytes = await crypto.subtle.sign('HMAC', key, encoder.encode(timestamp + '.' + text));
  return Array.from(new Uint8Array(bytes), x => x.toString(16).padStart(2,'0')).join('');
}
async function signed(request, secret, body) {
  const t = String(request.headers.get('x-cine-time') || '');
  const signature = hexToBytes(request.headers.get('x-cine-signature'));
  if (!/^\d{13}$/.test(t) || !signature || Math.abs(Date.now() - Number(t)) > 60000) return false;
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), {name:'HMAC',hash:'SHA-256'}, false, ['verify']);
  return crypto.subtle.verify('HMAC', key, signature, encoder.encode(t + '.' + body));
}
const TABLE = `CREATE TABLE IF NOT EXISTS cine_delivery44_receipts (
  request_id TEXT PRIMARY KEY,
  state TEXT NOT NULL CHECK(state IN ('sending','sent','needs_review')),
  sent_message_id INTEGER,
  error_code INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;
async function sendTelegram(intent) {
  const start = Date.now();
  let response, data;
  try {
    response = await fetch('https://api.telegram.org/bot' + intent.bot_token + '/copyMessage', {
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify(intent.payload),
      signal:AbortSignal.timeout(12000)
    });
    data = await response.json();
  } catch {
    return {unknown:true,elapsed_ms:Date.now()-start};
  }
  const code = Number(data?.error_code || response.status);
  if (response.ok && data?.ok === true && positiveId(data?.result?.message_id)) {
    return {ok:true,message_id:Number(data.result.message_id),elapsed_ms:Date.now()-start};
  }
  return {ok:false,error_code:code,retry_after:Number(data?.parameters?.retry_after || 0),elapsed_ms:Date.now()-start};
}
export async function handleRequest(request, env) {
  const path = new URL(request.url).pathname;
  if (path === '/health' && request.method === 'GET') return json({
    service:'cine-radar-delivery-44',status:env?.DB && env?.CINE_BRIDGE_SECRET ? 'ready':'unconfigured',
    webhook:false,handles_media_bytes:false
  });
  if (path !== COPY_ROUTE) return new Response('Not found',{status:404,headers:NO_STORE});
  if (request.method !== 'POST') return json({error:'method_not_allowed'},405);
  if (!env?.DB || !env?.CINE_BRIDGE_SECRET) return json({error:'not_configured'},503);
  if (Number(request.headers.get('content-length') || 0) > 10000) return json({error:'too_large'},413);
  const body = await request.text();
  if (body.length > 10000 || !await signed(request,env.CINE_BRIDGE_SECRET,body)) return json({error:'unauthorized'},403);
  let intent;
  try { intent=JSON.parse(body); } catch { return json({error:'bad_json'},400); }
  if (!validIntent(intent)) return json({error:'bad_request'},400);

  // Le compte 52 déduplique déjà les updates Telegram. Ce second verrou
  // protège contre les replays réseau et interdit tout renvoi ambigu.
  await env.DB.prepare(TABLE).run();
  const claim = await env.DB.prepare(
    "INSERT OR IGNORE INTO cine_delivery44_receipts(request_id,state) VALUES(?,'sending')"
  ).bind(intent.request_id).run();
  if (Number(claim.meta?.changes || 0) !== 1) {
    const old = await env.DB.prepare(
      'SELECT state,sent_message_id FROM cine_delivery44_receipts WHERE request_id=?'
    ).bind(intent.request_id).first();
    if (old?.state === 'sent' && positiveId(old.sent_message_id))
      return json({ok:true,result:{message_id:Number(old.sent_message_id)},replayed:true});
    return json({ok:false,error_code:409,uncertain:true},409);
  }
  const result = await sendTelegram(intent);
  if (result.ok) {
    await env.DB.prepare(
      "UPDATE cine_delivery44_receipts SET state='sent',sent_message_id=?,updated_at=CURRENT_TIMESTAMP WHERE request_id=?"
    ).bind(result.message_id,intent.request_id).run();
    console.log(JSON.stringify({event:'cine_copy_completed',elapsed_ms:result.elapsed_ms}));
    return json({ok:true,result:{message_id:result.message_id},elapsed_ms:result.elapsed_ms});
  }
  // Un refus HTTP 429 explicite garantit que l'envoi n'a pas été accepté.
  // Les autres résultats sont conservés pour examen, sans réessai aveugle.
  if (result.error_code === 429 && !result.unknown) {
    await env.DB.prepare('DELETE FROM cine_delivery44_receipts WHERE request_id=?').bind(intent.request_id).run();
    return json({ok:false,error_code:429,retry_after:result.retry_after},429);
  }
  await env.DB.prepare(
    "UPDATE cine_delivery44_receipts SET state='needs_review',error_code=?,updated_at=CURRENT_TIMESTAMP WHERE request_id=?"
  ).bind(result.error_code || 0,intent.request_id).run();
  console.warn(JSON.stringify({event:'cine_copy_uncertain',elapsed_ms:result.elapsed_ms,error_code:result.error_code || 0}));
  return json({ok:false,error_code:result.error_code || 502,uncertain:true},502);
}
export default {fetch:handleRequest};
