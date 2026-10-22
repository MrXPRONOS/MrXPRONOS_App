
import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ========================
// ENV
// ========================
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
const TELEGRAM_SECRET_TOKEN = Deno.env.get("TELEGRAM_SECRET_TOKEN") || "";
const MISTRAL_API_KEY = Deno.env.get("MISTRAL_API_KEY") || "";
const HF_TOKEN = Deno.env.get("HF_TOKEN") || "";
const HF_MODEL = Deno.env.get("HF_MODEL") || "Qwen/Qwen2.5-7B-Instruct";

if (!SUPABASE_URL) throw new Error("Missing SUPABASE_URL");
if (!SUPABASE_SERVICE_KEY) throw new Error("Missing SUPABASE_SERVICE_ROLE_KEY");
if (!TELEGRAM_BOT_TOKEN) throw new Error("Missing TELEGRAM_BOT_TOKEN");

const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// ========================
// LINKS
// ========================
const SITE = {
  pronos: "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html",
  bonus: "https://mrxpronos.github.io/MrXPRONOS_App/bonus.html",
  contact: "https://mrxpronos.github.io/MrXPRONOS_App/contact.html",
  live: "https://mrxpronos.github.io/MrXPRONOS_App/live.html",
  historique: "https://mrxpronos.github.io/MrXPRONOS_App/historique.html",
};

const OFFICIAL_CONTACTS = {
  whatsapp: "https://wa.me/22899201444",
  telegram: "https://t.me/mr_xpronos",
};

const TG_MAX_MATCHES = 8;
const TG_MAX_CHARS = 1900;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, X-Telegram-Bot-Api-Secret-Token",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

// ========================
// Helpers
// ========================
function normalizeQuestion(input: string): string {
  return String(input || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, ""); // enlève accents
}

function stripTags(input: string) {
  return String(input || "").replace(/<[^>]+>/g, "");
}

function escapeTextKeepEntities(s: string) {
  const ents: string[] = [];
  let idx = 0;
  const protectedText = String(s || "").replace(
    /&[a-zA-Z0-9#]+;/g,
    (m) => {
      const token = `__ENT_${idx++}__`;
      ents.push(m);
      return token;
    },
  );

  let out = protectedText.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(
    />/g,
    "&gt;",
  );
  ents.forEach((e, i) => (out = out.replaceAll(`__ENT_${i}__`, e)));
  return out;
}

function clampTelegram(html: string) {
  let s = String(html || "");
  if (s.length > TG_MAX_CHARS) s = s.slice(0, TG_MAX_CHARS - 1) + "...";
  return s;
}

function safeUrl(url: string) {
  const u = String(url || "").trim();
  if (!u) return "";
  return encodeURI(u);
}

function tgLinkBlock(label: string, url: string) {
  const u = safeUrl(url);
  if (!u.startsWith("http")) return "";
  return `<i>${escapeTextKeepEntities(label)}</i>\n${escapeTextKeepEntities(
    u,
  )}`;
}

function tgQuote(text: string) {
  const t = escapeTextKeepEntities(String(text || "").trim());
  if (!t) return "";
  return `<pre>${t}</pre>`;
}

function markdownLiteToTelegramHtml(s: string): string {
  let out = String(s || "");
  out = out.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  out = out.replace(/__(.+?)__/g, "<b>$1</b>");
  out = out.replace(
    /(^|[^*])\*(?!\*)([^*\n]+)\*(?!\*)/g,
    "$1<i>$2</i>",
  );
  out = out.replace(
    /(^|[^_])_([^_\n]+)_/g,
    "$1<i>$2</i>",
  );
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  return out;
}

function cleanFences(s: string) {
  let out = String(s || "").trim();
  out = out.replace(/^```html\s*/i, "");
  out = out.replace(/^```\s*/i, "");
  out = out.replace(/\s*```$/i, "");
  out = out.replace(/^`+|`+$/g, "").trim();
  return out.trim();
}

function sanitizeTelegramHtml(html: string): string {
  let s = cleanFences(html);
  s = markdownLiteToTelegramHtml(s);

  const allowed = new Set(["b", "i", "u", "s", "code", "pre"]);
  const tagTokens: Array<{ token: string; tag: string }> = [];
  let tagIndex = 0;

  for (const t of Array.from(allowed)) {
    s = s.replace(new RegExp(`<${t}>`, "gi"), () => {
      const token = `__TAG_${tagIndex++}__`;
      tagTokens.push({ token, tag: `<${t}>` });
      return token;
    });
    s = s.replace(new RegExp(`</${t}>`, "gi"), () => {
      const token = `__TAG_${tagIndex++}__`;
      tagTokens.push({ token, tag: `</${t}>` });
      return token;
    });
  }

  s = s.replace(/<[^>]+>/g, "");
  s = escapeTextKeepEntities(s);

  for (const x of tagTokens) s = s.replaceAll(x.token, x.tag);

  s = s.replace(/\n{3,}/g, "\n\n").trim();
  return s || "...";
}

function pickOne<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ========================
// Telegram API
// ========================
async function tgApi(method: string, payload: any) {
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/${method}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data?.ok === false) {
    throw new Error(`Telegram API error: ${JSON.stringify(data)}`);
  }
  return data;
}

function splitTelegramHtml(html: string, maxLen = 3800) {
  const parts = String(html || "").split("\n\n");
  const chunks: string[] = [];
  let current = "";
  const flush = () => {
    if (current.trim()) chunks.push(current.trim());
    current = "";
  };

  for (const p of parts) {
    const candidate = current ? current + "\n\n" + p : p;
    if (candidate.length <= maxLen) {
      current = candidate;
      continue;
    }
    if (current) flush();
    let s = p;
    while (s.length > maxLen) {
      chunks.push(s.slice(0, maxLen));
      s = s.slice(maxLen);
    }
    if (s.trim()) chunks.push(s.trim());
  }
  flush();
  return chunks.length ? chunks : [String(html || "")];
}

async function sendTelegramHtml(chatId: number, html: string) {
  const chunks = splitTelegramHtml(html, 3800);
  for (const chunk of chunks) {
    try {
      await tgApi("sendMessage", {
        chat_id: chatId,
        text: chunk,
        parse_mode: "HTML",
        disable_web_page_preview: true,
      });
    } catch (e) {
      console.error("sendMessage failed, fallback:", e);
      await tgApi("sendMessage", {
        chat_id: chatId,
        text: stripTags(chunk) || "Erreur d'affichage.",
        disable_web_page_preview: true,
      });
    }
  }
}

// ========================
// Anti-spam
// ========================
async function checkRateLimit(userId: string) {
  const MIN_INTERVAL_MS = 2500;
  const WINDOW_MS = 60_000;
  const MAX_PER_WINDOW = 12;

  const now = new Date();
  const nowIso = now.toISOString();

  const { data: row } = await sb
    .from("assistant_rate_limits")
    .select("user_id,last_message_at,window_start,window_count")
    .eq("user_id", userId)
    .maybeSingle();

  const last = row?.last_message_at ? new Date(row.last_message_at) : null;
  const ws = row?.window_start ? new Date(row.window_start) : null;

  if (last && now.getTime() - last.getTime() < MIN_INTERVAL_MS) {
    const wait = Math.ceil(
      (MIN_INTERVAL_MS - (now.getTime() - last.getTime())) / 1000,
    );
    return { allowed: false, waitSeconds: wait };
  }

  let windowStart = ws;
  let count = Number(row?.window_count || 0);

  if (!windowStart || now.getTime() - windowStart.getTime() > WINDOW_MS) {
    windowStart = now;
    count = 1;
  } else {
    count += 1;
  }

  if (count > MAX_PER_WINDOW) return { allowed: false, waitSeconds: 20 };

  await sb.from("assistant_rate_limits").upsert({
    user_id: userId,
    last_message_at: nowIso,
    window_start: windowStart.toISOString(),
    window_count: count,
    updated_at: nowIso,
  });

  return { allowed: true, waitSeconds: 0 };
}

// ========================
// Sessions
// ========================
async function getSession(userId: string) {
  const { data } = await sb
    .from("telegram_sessions")
    .select("pending_action,pending_payload,updated_at")
    .eq("user_id", userId)
    .maybeSingle();

  if (!data) return null;
  const updatedAt = data.updated_at ? new Date(data.updated_at) : null;
  if (updatedAt && (Date.now() - updatedAt.getTime()) > 15 * 60 * 1000) {
    await clearSession(userId);
    return null;
  }
  return data;
}

async function setSession(
  userId: string,
  pending_action: string,
  pending_payload: any,
) {
  await sb.from("telegram_sessions").upsert({
    user_id: userId,
    pending_action,
    pending_payload,
    updated_at: new Date().toISOString(),
  });
}

async function clearSession(userId: string) {
  await sb.from("telegram_sessions").delete().eq("user_id", userId);
}

// ========================
// Telegram cache
// ========================
async function tgGetCache(cacheKey: string) {
  try {
    const { data } = await sb
      .from("telegram_cache")
      .select("answer, expires_at")
      .eq("cache_key", cacheKey)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (!data) return null;
    if (
      data.expires_at &&
      new Date(data.expires_at).getTime() < Date.now()
    ) return null;
    return String(data.answer || "");
  } catch {
    return null;
  }
}

async function tgSetCache(
  cacheKey: string,
  question: string,
  answer: string,
  hours = 4,
) {
  try {
    const expiresAt = new Date(
      Date.now() + hours * 60 * 60 * 1000,
    ).toISOString();
    const { error } = await sb.from("telegram_cache").insert({
      cache_key: cacheKey,
      question,
      answer,
      created_at: new Date().toISOString(),
      expires_at: expiresAt,
    });
    if (error) console.error("telegram_cache insert error:", error);
  } catch (e) {
    console.error("telegram_cache insert exception:", e);
  }
}

// ========================
// Historique conversations
// ========================
async function getHistoryFromConversations(
  userId: string,
  limitPairs = 5,
) {
  try {
    const { data, error } = await sb
      .from("conversations")
      .select("question,reponse,created_at")
      .eq("user_id", userId)
      .order("created_at", { ascending: false })
      .limit(limitPairs);

    if (error || !data) return [];
    const rows = [...data].reverse();

    const history: { role: "user" | "assistant"; content: string }[] = [];
    for (const r of rows) {
      if (r?.question) {
        history.push({ role: "user", content: String(r.question) });
      }
      if (r?.reponse) {
        history.push({
          role: "assistant",
          content: stripTags(String(r.reponse)),
        });
      }
    }
    return history.slice(-10);
  } catch {
    return [];
  }
}

// ========================
// DB
// ========================
async function getPronosticsToday(): Promise<any[]> {
  const now = new Date();
  const today = now.toISOString().split("T")[0];
  let dateCible = today;
  if (now.getHours() >= 22) {
    const d = new Date(now);
    d.setDate(d.getDate() + 1);
    dateCible = d.toISOString().split("T")[0];
  }

  const { data, error } = await sb.from("pronostics").select("*").eq(
    "date",
    dateCible,
  );
  if (error) throw error;
  const rows = data || [];
  rows.sort(
    (a: any, b: any) =>
      Number(b.final_score || 0) - Number(a.final_score || 0),
  );
  return rows;
}

async function getBookmakersList(): Promise<
  { nom: string; lien_affiliation?: string }[]
> {
  const { data, error } = await sb
    .from("bookmakers")
    .select("nom, lien_affiliation")
    .eq("active", true)
    .order("nom", { ascending: true });
  if (error) return [];
  return (data || []).map((x: any) => ({
    nom: String(x.nom || ""),
    lien_affiliation: x.lien_affiliation || "",
  }));
}

function extractBookmakerName(
  text: string,
  candidates: string[],
): string | null {
  const q = normalizeQuestion(text);
  for (const name of candidates) {
    const n = normalizeQuestion(name);
    if (n && q.includes(n)) return name;
  }
  if (q.includes("1xbet") || q.includes("1x bet")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("1xbet")
    ) || null;
  }
  if (q.includes("1win")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("1win")
    ) || null;
  }
  if (q.includes("betwinner")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("betwinner")
    ) || null;
  }
  if (q.includes("melbet")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("melbet")
    ) || null;
  }
  if (q.includes("linebet")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("linebet")
    ) || null;
  }
  if (q.includes("betclic")) {
    return candidates.find((x) =>
      normalizeQuestion(x).includes("betclic")
    ) || null;
  }
  return null;
}

function detectPlatform(text: string): "android" | "ios" | "web" | "unknown" {
  const q = normalizeQuestion(text);
  if (q.includes("android")) return "android";
  if (q.includes("iphone") || q.includes("ios")) return "ios";
  if (
    q.includes("pc") || q.includes("web") ||
    q.includes("navigateur")
  ) return "web";
  return "unknown";
}

// ========================
// Logging
// ========================
async function logConversation(
  userId: string,
  question: string,
  answer: string,
  fromCache = false,
) {
  try {
    const { error } = await sb.from("conversations").insert({
      user_id: userId,
      question,
      reponse: answer,
      from_cache: fromCache,
      created_at: new Date().toISOString(),
    });
    if (error) console.error("conversations insert error:", error);
  } catch (e) {
    console.error("conversations insert exception:", e);
  }
}

// ========================
// Intent detection (SANS accents)
// ========================
function detectIntent(q: string) {
  const s = normalizeQuestion(q); // sans accents
  const trimmed = s.trim();

  const isJust = (words: string[]) =>
    words.some((w) =>
      trimmed === w ||
      trimmed === w + " !" ||
      trimmed === w + " ?" ||
      trimmed === w + "." ||
      trimmed === "merci beaucoup" // petit bonus
    );

  // PRIORITE 1: Stop session
  if (
    s.includes("laisse tomber") ||
    s.includes("laisser tomber") ||
    s.includes("stop") ||
    s.includes("arrete") ||
    s.includes("autre chose") ||
    s.includes("annule") ||
    s.includes("non merci") ||
    s.includes("pas besoin") ||
    isJust([
      "merci",
      "ok",
      "c bon",
      "cest bon",
      "c'est bon",
      "ca va",
      "daccord",
      "d'accord",
    ])
  ) {
    return "stop_session";
  }

  // PRIORITE 2: Problemes
  if (
    s.includes("authentification") ||
    s.includes("google") ||
    s.includes("2fa") ||
    s.includes("bloque") ||
    s.includes("bloqu") ||
    s.includes("retir") ||
    s.includes("argent") ||
    s.includes("kyc") ||
    s.includes("verif") ||
    s.includes("document") ||
    s.includes("plante") ||
    s.includes("crash") ||
    s.includes("panne") ||
    s.includes("limite") ||
    s.includes("banni") ||
    s.includes("rollover") ||
    s.includes("wager") ||
    s.includes("mot de passe") ||
    s.includes("mdp")
  ) {
    return "problem";
  }

  // PRIORITE 3: Deja un compte
  if (
    s.includes("deja un compte") ||
    s.includes("j ai un compte") ||
    s.includes("jai un compte") ||
    s.includes("compte existe") ||
    s.includes("already have")
  ) {
    return "already_account";
  }

  // PRIORITE 4: Cote elevee
  if (
    s.includes("cote 100") ||
    s.includes("cote 50") ||
    s.includes("cote 20") ||
    s.includes("grosse cote") ||
    s.includes("grande cote") ||
    s.includes("cote eleve")
  ) {
    return "high_odds";
  }

  // PRIORITE 5: Guide pari (debutant)
  if (
    s.includes("debutant") ||
    s.includes("debuter") ||
    s.includes("premiere fois") ||
    s.includes("1ere fois") ||
    s.includes("premier pari") ||
    s.includes("je ne sais pas comment parier") ||
    (s.includes("ne sais pas") && s.includes("parier")) ||
    s.includes("apprendre a parier") ||
    s.includes("comment utiliser") ||
    s.includes("comment miser") ||
    s.includes("comment joue") ||
    s.includes("comment jouer") ||
    s.includes("guide") ||
    (s.includes("comment") && s.includes("parier")) ||
    (s.includes("comment") && s.includes("trouver") &&
      (s.includes("match") || s.includes("coupon") || s.includes("prono")))
  ) {
    return "guide_betting";
  }

  // PRIORITE 6: Autres intents
  if (s.includes("vip") || s.includes("code vip") || s.includes("abonnement vip")) {
    return "vip";
  }

  if (s.includes("live") || s.includes("direct") || s.includes("temps reel")) {
    return "live";
  }

  if (
    s.includes("bonus") ||
    s.includes("promo") ||
    s.includes("promotion") ||
    s.includes("code") ||
    s.includes("xpvip") ||
    s.includes("inscrire") ||
    s.includes("inscription") ||
    s.includes("compte") ||
    s.includes("bookmaker") ||
    s.includes("1xbet") ||
    s.includes("1win") ||
    s.includes("betwinner") ||
    s.includes("melbet") ||
    s.includes("linebet") ||
    s.includes("betclic") ||
    s.includes("freebet") ||
    s.includes("offre de bienvenue") ||
    s.includes("bonus de bienvenue")
  ) {
    return "bonus";
  }

  // SUPPORT: on enlève "aide" pour ne pas voler guide_betting
  if (
    s.includes("support") ||
    s.includes("contact") ||
    s.includes("bug") ||
    s.includes("ne marche pas")
  ) {
    return "support";
  }

  if (
    s.includes("hier") ||
    s.includes("resultat") ||
    s.includes("valide") ||
    s.includes("gagne") ||
    s.includes("perdu") ||
    s.includes("echoue")
  ) {
    return "results";
  }

  if (
    s.includes("pronostic") ||
    s.includes("pronos") ||
    s.includes("prono") ||
    s.includes("match") ||
    s.includes("coupon") ||
    s.includes("paris") ||
    s.includes("pari") ||
    s.includes("ticket") ||
    s.includes("grille") ||
    s.includes("cote du jour") ||
    s.includes("bet du jour")
  ) {
    return "prono";
  }

  return "generic";
}

// Fallback "intelligent" pour l'intent avec LLM
async function detectIntentSmart(text: string): Promise<string> {
  const base = detectIntent(text);
  if (base !== "generic") return base;

  if (!HF_TOKEN && !MISTRAL_API_KEY) return "generic";

  const system = `
Tu es un routeur d'intentions pour un bot Telegram de paris sportifs.
Tu dois classer le message utilisateur dans UNE SEULE categorie.

Definitions (resume):
- "prono" : il veut les pronostics, coupons, matchs a jouer.
- "bonus" : il veut un bonus, code promo, offre de bienvenue, inscription bookmaker.
- "vip" : il parle du VIP, abonnement VIP, code VIP.
- "live" : il parle des pronos en direct, live, temps reel.
- "guide_betting" : il ne sait pas comment parier, il est debutant ou demande qu'on lui montre comment utiliser les coupons ou un bookmaker.
- "problem" : probleme avec un bookmaker (compte bloque, retrait impossible, authentification, Google Authenticator, KYC, documents, limites, etc.).
- "support" : il veut juste parler au support de Mr XPRONOS (WhatsApp / Telegram), sans detail technique precis.
- "results" : il demande des resultats, historique, si un prono est gagne ou perdu.
- "high_odds" : il demande des grosses cotes (cote 50, cote 100, grosse cote).
- "already_account" : il dit qu'il a deja un compte sur un bookmaker.
- "stop_session" : il dit d'arreter, laisse tomber, c'est bon, merci, etc.
- "generic" : discussion generale, blague, small talk ou tout ce qui ne rentre pas clairement dans les autres.

Renvoie UNIQUEMENT un mot parmi :
{prono, bonus, vip, live, support, problem, results, guide_betting, high_odds, already_account, stop_session, generic}.
Pas de phrase, pas d'explication, juste le label.
`.trim();

  const messages = [
    { role: "system", content: system },
    { role: "user", content: text },
  ];

  let raw = "";
  try {
    if (HF_TOKEN) raw = await callHFModel(messages);
    else raw = await callMistralLLM(messages);
  } catch {
    return "generic";
  }

  const first = normalizeQuestion(raw).split(/\s+/)[0] || "generic";
  const allowed = new Set([
    "prono",
    "bonus",
    "vip",
    "live",
    "support",
    "problem",
    "results",
    "guide_betting",
    "high_odds",
    "already_account",
    "stop_session",
    "generic",
  ]);
  if (!allowed.has(first)) return "generic";
  return first as string;
}

// ========================
// VIP helpers
// ========================
function extractVipId(text: string): string | null {
  const m = String(text || "").match(
    /(MX-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i,
  );
  return m ? m[1].toUpperCase() : null;
}

function buildWhatsAppPrefillUrl(vipId: string) {
  const msg = `Bonjour, je veux m'abonner au VIP.\nMon ID VIP est: ${vipId}`;
  return `https://wa.me/22899201444?text=${encodeURIComponent(msg)}`;
}

// ========================
// Controlled responses
// ========================
function couponsResponse(pronos: any[]) {
  const items = (pronos || []).slice(0, TG_MAX_MATCHES).map((p: any) => {
    const match = String(p.match || "").trim() ||
      `${p.home_team || ""} vs ${p.away_team || ""}`.trim();
    const pred = String(p.prediction || p.type || "").trim();
    if (!match || !pred) return null;
    return `- ${escapeTextKeepEntities(match)} : <b>${
      escapeTextKeepEntities(
        pred,
      )
    }</b>`;
  }).filter(Boolean) as string[];

  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Voici les coupons du jour :</b>\n` +
        `${
          items.length
            ? items.join("\n")
            : "Aucun coupon dispo pour le moment."
        }\n\n` +
        `${tgLinkBlock("Voir tous les pronostics", SITE.pronos)}`,
    ),
  );
}

function vipAskIdResponse() {
  const variants = [
    `<b>OK pour le VIP.</b>\nEnvoie-moi ton <b>ID VIP</b> (format MX-...).\nTu le trouves dans l'appli Mr XPRONOS.`,
    `<b>On part sur le VIP alors.</b>\nJ'ai besoin de ton <b>ID VIP</b> (MX-...).\nRegarde dans l'appli Mr XPRONOS.`,
    `<b>Parfait pour le VIP.</b>\nEnvoie ton <b>ID VIP</b> (MX-...).\nIl est affiché dans l'appli Mr XPRONOS.`,
  ];

  const core = pickOne(variants);

  return sanitizeTelegramHtml(
    clampTelegram(
      `${core}\n\n${tgLinkBlock("Ouvrir LIVE VIP", SITE.live)}`,
    ),
  );
}

function vipActivationResponse(vipId: string) {
  const wa = buildWhatsAppPrefillUrl(vipId);
  const messageToCopy =
    `Bonjour, je veux m'abonner au VIP.\nMon ID VIP est: ${vipId}`;

  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>ID recu : ${escapeTextKeepEntities(vipId)}</b>\n\n` +
        `Pour t'abonner (5 000 F CFA/mois), contacte-moi directement :\n\n` +
        `${tgLinkBlock("WhatsApp (message pret)", wa)}\n\n` +
        `${tgLinkBlock("Telegram", OFFICIAL_CONTACTS.telegram)}\n\n` +
        `<b>Message a copier :</b>\n<pre>${
          escapeTextKeepEntities(
            messageToCopy,
          )
        }</pre>\n` +
        `${tgQuote("Des que c'est active, tu auras acces au LIVE VIP.")}`,
    ),
  );
}

function askWhichBookmakerResponse(bookmakers: string[]) {
  const top = bookmakers.slice(0, 6).map((b) =>
    `- <b>${escapeTextKeepEntities(b)}</b>`
  ).join("\n");
  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Tu veux quel bookmaker ?</b>\n${top}\n\n` +
        `${tgQuote("Reponds juste avec le nom (ex: 1xBet).")}`,
    ),
  );
}

function affiliateIntroResponse(bookmakerName: string, affiliateUrl: string) {
  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>${escapeTextKeepEntities(bookmakerName)}</b>\n` +
        `Voici ton lien. Tu es sur <b>Android</b>, <b>iPhone</b> ou <b>Web</b> ?\n\n` +
        `${tgLinkBlock("Lien d'inscription", affiliateUrl)}`,
    ),
  );
}

function signupStepsResponse(
  bookmakerName: string,
  affiliateUrl: string,
  platform: "android" | "ios" | "web",
) {
  let steps = "";
  if (platform === "android") {
    steps =
      `<b>Etapes Android :</b>\n` +
      `1. Ouvre le lien ci-dessous\n` +
      `2. Cree ton compte (nom / tel / mail)\n` +
      `3. Verifie ton numero si demande\n` +
      `4. Fais un premier depot\n` +
      `5. Ajoute le code <b>XPVIP</b> si le champ existe\n` +
      `6. Fais le KYC tot (piece + selfie)\n`;
  } else if (platform === "ios") {
    steps =
      `<b>Etapes iPhone :</b>\n` +
      `1. Ouvre le lien dans Safari\n` +
      `2. Cree ton compte\n` +
      `3. Si ca bloque, desactive VPN ou bloqueur\n` +
      `4. Depot, puis KYC (piece + selfie)\n` +
      `5. Ajoute <b>XPVIP</b> si possible\n`;
  } else {
    steps =
      `<b>Etapes Web/PC :</b>\n` +
      `1. Ouvre le lien dans ton navigateur\n` +
      `2. Cree ton compte\n` +
      `3. Verifie email/tel\n` +
      `4. Depot, puis KYC\n` +
      `5. <b>XPVIP</b> si possible\n`;
  }

  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Inscription ${escapeTextKeepEntities(bookmakerName)}</b>\n\n` +
        `${tgLinkBlock("Lien d'inscription", affiliateUrl)}\n\n` +
        `${steps}\n` +
        `${tgQuote("Si tu bloques a une etape, dis-moi l'ecran exact.")}`,
    ),
  );
}

function alreadyAccountResponse(bookmakerName: string) {
  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Tu as deja un compte ${
        escapeTextKeepEntities(
          bookmakerName,
        )
      } ?</b>\n` +
        `Pas de souci ! Dis-moi ce qui te bloque :\n` +
        `- Connexion\n` +
        `- Retrait\n` +
        `- Bonus\n` +
        `- Comment parier\n\n` +
        `${tgQuote("Je suis la pour t'aider.")}`,
    ),
  );
}

function guideBettingResponse(bookmakerName?: string) {
  const bm = bookmakerName
    ? ` sur ${escapeTextKeepEntities(bookmakerName)}`
    : "";
  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Guide pour debutant${bm} :</b>\n\n` +
        `1. Connecte-toi a ton compte\n` +
        `2. Va dans "Sports" ou "En direct"\n` +
        `3. Choisis un match des coupons\n` +
        `4. Clique sur la cote (ex: 1X)\n` +
        `5. Entre ta mise dans le coupon\n` +
        `6. Valide le pari\n\n` +
        `Conseil : commence avec de petites mises.\n\n` +
        `${tgQuote("Tu veux que je t'explique un pari en detail ?")}`,
    ),
  );
}

function guideFindMatchesResponse(bookmakerName: string) {
  const bm = escapeTextKeepEntities(bookmakerName);
  return sanitizeTelegramHtml(
    clampTelegram(
      `<b>Comment trouver les matchs sur ${bm} :</b>\n\n` +
        `1. Ouvre ${bm} et connecte-toi a ton compte.\n` +
        `2. Va dans <b>Sports</b> puis <b>Football</b>.\n` +
        `3. Utilise la loupe (recherche) et tape le nom d'une equipe du match (ex: "Al Shorta" ou "Quwa Al Jawiya").\n` +
        `4. Quand tu vois le match, ouvre-le et clique sur la cote correspondante (1X, X2, etc.).\n` +
        `5. Repete pour chaque match du coupon.\n\n` +
        `${tgQuote("Si tu veux, dis-moi le nom exact d'un match et je te dis quoi chercher sur " + bm + ".")}`,
    ),
  );
}

function highOddsResponse() {
  const variants = [
    `<b>Une grosse cote, c'est tres risque.</b>\nMise petit, combine peu de matchs, et ne mise jamais l'argent dont tu as besoin.`,
    `<b>Cote elevee = risque eleve.</b>\nC'est tentant, mais concentre-toi surtout sur des tickets plus raisonnables.`,
  ];
  const core = pickOne(variants);

  return sanitizeTelegramHtml(
    clampTelegram(
      `${core}\n\n` +
        `${tgLinkBlock("Voir les coupons du jour", SITE.pronos)}\n` +
        `${tgQuote("La discipline bat la chance sur le long terme.")}`,
    ),
  );
}

function troubleshootResponse(issue: string, bookmaker?: string) {
  const contact = tgLinkBlock("Support", SITE.contact);
  const bm = bookmaker ? ` sur ${escapeTextKeepEntities(bookmaker)}` : "";

  const map: Record<string, string> = {
    auth: sanitizeTelegramHtml(
      clampTelegram(
        `<b>Probleme authentification${bm} :</b>\n` +
          `- Verifie l'heure de ton telephone (doit etre automatique)\n` +
          `- Desactive puis reactive Google Authenticator\n` +
          `- Contacte le support du bookmaker avec ton ID\n\n` +
          `${contact}\n${
            tgQuote(
              "Tu as encore tes codes de recuperation ?",
            )
          }`,
      ),
    ),
    withdraw: sanitizeTelegramHtml(
      clampTelegram(
        `<b>Retrait bloque${bm} :</b>\n` +
          `- Verifie KYC valide\n` +
          `- Retire par la meme methode que le depot\n` +
          `- Verifie conditions bonus (wagering)\n\n` +
          `${contact}\n${tgQuote("Tu utilises un bonus ou non ?")}`,
      ),
    ),
    kyc: sanitizeTelegramHtml(
      clampTelegram(
        `<b>KYC / verification${bm} :</b>\n` +
          `- Envoie piece + selfie + preuve d'adresse\n` +
          `- Les infos doivent correspondre au compte\n` +
          `- Ne donne JAMAIS le CVC de ta carte\n\n` +
          `${contact}\n${tgQuote("Quel message d'erreur tu vois ?")}`,
      ),
    ),
    crash: sanitizeTelegramHtml(
      clampTelegram(
        `<b>Si l'appli plante${bm} :</b>\n` +
          `- Ferme et relance l'appli\n` +
          `- Passe en 4G/5G (ou Wi-Fi stable)\n` +
          `- Essaye la version navigateur\n\n` +
          `${contact}\n${tgQuote("Tu es sur Android ou iPhone ?")}`,
      ),
    ),
    limited: sanitizeTelegramHtml(
      clampTelegram(
        `<b>Compte limite${bm} :</b>\n` +
          `- Ca arrive si tu gagnes souvent\n` +
          `- Solution: varier les marches, mises normales\n` +
          `- Avoir 2-3 bookmakers aide\n\n` +
          `${tgQuote("Tu veux une strategie bankroll simple ?")}`,
      ),
    ),
  };

  return map[issue] ||
    sanitizeTelegramHtml(
      clampTelegram(
        `<b>OK.</b>\nDis-moi le probleme exact en 1 phrase.\n${contact}\n${
          tgQuote(
            "Quel bookmaker ? Quel message ?",
          )
        }`,
      ),
    );
}

function detectIssueType(text: string) {
  const q = normalizeQuestion(text);
  if (
    q.includes("authentification") || q.includes("google") ||
    q.includes("2fa")
  ) return "auth";
  if (
    q.includes("retrait") || q.includes("withdraw") ||
    q.includes("argent") || q.includes("bloque")
  ) return "withdraw";
  if (
    q.includes("kyc") || q.includes("verif") ||
    q.includes("document")
  ) return "kyc";
  if (
    q.includes("plante") || q.includes("crash") ||
    q.includes("panne")
  ) return "crash";
  if (
    q.includes("limite") || q.includes("limit") ||
    q.includes("banni")
  ) return "limited";
  return "unknown";
}

// ========================
// LLM "humain" + garde-fous
// ========================
function buildHumanSystemPrompt(currentIntent?: string) {
  return `
Tu es "Mr XPRONOS", assistant Telegram expert en paris sportifs.

ROLE GENERAL:
- Tu discutes comme un parieur experimente: tu expliques, tu conseilles, tu donnes des exemples.
- Tu peux parler de paris simples, combines, value bet, bankroll, tilt, erreurs a eviter, etc.
- Tu adaptes ta reponse au message et au contexte, sans faire de menu numerote.

CONTRAINTES IMPORTANTES (A RESPECTER STRICTEMENT):
1) PAS DE COUPONS INVENTES
   - Tu NE CREES JAMAIS de pronostics precis, tickets ou coupons personnalises.
   - Tu n'inventes pas de matchs (pas de "Equipe A vs Equipe B : 1X").
   - Tu ne donnes pas de liste detaillee de bets comme si c'etait des pronos officiels.
   - Si l'utilisateur demande des "coupons", "tickets", "pronos du jour", explique-lui que les coupons officiels sont sur le site Mr XPRONOS et/ou dans l'application, sans inventer de matchs.
   - Tu peux expliquer COMMENT utiliser un coupon (comment le jouer sur un bookmaker), mais pas quel coupon exact jouer.

2) PAS DE LIENS OU CODES PROMOS INVENTES
   - Tu NE CREES JAMAIS de nouveaux liens, URL raccourcies ou codes promos.
   - Tu peux UNIQUEMENT utiliser ces liens officiels, et les afficher en clair (sans balise <a>) :
     - Pronostics : ${SITE.pronos}
     - Bonus / bookmakers : ${SITE.bonus}
     - LIVE VIP : ${SITE.live}
     - Contact : ${SITE.contact}
     - WhatsApp : ${OFFICIAL_CONTACTS.whatsapp}
     - Telegram : ${OFFICIAL_CONTACTS.telegram}
   - Tu ne donnes pas de lien direct generique vers les sites de bookmakers (ex: pas de "https://1xbet.com").
   - Code promo autorise: XPVIP (uniquement cite, pas invente).

3) PAS DE PROMESSES DE GAIN
   - Tu ne promets jamais "garanti", "100% sur", "impossible de perdre", "sans risque".
   - Tu rappelles que les paris sportifs comportent des risques et qu'il faut jouer de maniere responsable.

COMPORTEMENT:
- Tutoiement, ton d'ami.
- Reponses courtes (2 a 8 lignes).
- Tu peux repondre au small talk ("salut", "ca va", "merci", etc.) et faire une petite blague legere si c'est naturel.
- Tu poses au maximum 1 question de relance, pas plus.
- Tu evites de repeter mot pour mot toujours la meme phrase.

CONTEXTE:
${currentIntent ? `- Le message courant a ete route vers l'intention "${currentIntent}". Adapte ta reponse a ce contexte.\n` : ""}

FORMAT:
- HTML Telegram uniquement : <b>, <i>, <u>, <s>, <code>, <pre>.
- Pas de <a>, pas de listes HTML, pas de markdown.
- Si tu donnes un lien officiel ci-dessus, mets juste l'URL en texte brut.
`.trim();
}

async function callMistralLLM(messages: any[]) {
  if (!MISTRAL_API_KEY) throw new Error("MISTRAL_API_KEY missing");
  const res = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${MISTRAL_API_KEY}`,
    },
    body: JSON.stringify({
      model: "mistral-small-latest",
      messages,
      temperature: 0.55,
      max_tokens: 700,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return String(data?.choices?.[0]?.message?.content || "");
}

async function callHFModel(messages: any[]) {
  if (!HF_TOKEN) throw new Error("HF_TOKEN missing");
  const res = await fetch(
    "https://router.huggingface.co/v1/chat/completions",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${HF_TOKEN}`,
      },
      body: JSON.stringify({
        model: HF_MODEL,
        messages,
        temperature: 0.55,
        max_tokens: 700,
      }),
    },
  );
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return String(data?.choices?.[0]?.message?.content || "");
}

function applyLLMGuards(raw: string): string {
  let s = String(raw || "");

  // 1) Bloquer les liens non autorisés (remplacer par texte neutre)
  const allowedLinks = [
    SITE.pronos,
    SITE.bonus,
    SITE.live,
    SITE.contact,
    OFFICIAL_CONTACTS.whatsapp,
    OFFICIAL_CONTACTS.telegram,
  ];

  s = s.replace(/https?:\/\/[^\s<]+/gi, (url) => {
    const ok = allowedLinks.some((a) => url.startsWith(a));
    return ok ? url : "le site du bookmaker";
  });

  // 2) Eviter un pattern typique de coupon "- Team vs Team : pari"
  s = s.replace(
    /^- [^:\n]+ vs [^:\n]+ : [^\n]+$/gim,
    "- [exemple de pari non detaille ici]",
  );

  return s;
}

async function callGenericLLM(
  question: string,
  history: { role: string; content: string }[],
  intent: string,
) {
  if (!MISTRAL_API_KEY && !HF_TOKEN) {
    return sanitizeTelegramHtml(
      clampTelegram(
        `Bonne question ! Pour une aide rapide :\n${OFFICIAL_CONTACTS.whatsapp}`,
      ),
    );
  }

  const system = buildHumanSystemPrompt(intent);
  const messages: any[] = [{ role: "system", content: system }];

  for (const h of (history || []).slice(-8)) {
    if (h?.role && h?.content) {
      messages.push({ role: h.role, content: String(h.content) });
    }
  }

  messages.push({ role: "user", content: question });

  let raw = "";
  if (HF_TOKEN) {
    try {
      raw = await callHFModel(messages);
    } catch {
      raw = await callMistralLLM(messages);
    }
  } else {
    raw = await callMistralLLM(messages);
  }

  const guarded = applyLLMGuards(raw);
  return sanitizeTelegramHtml(clampTelegram(guarded));
}

// ========================
// MAIN HANDLER
// ========================
async function handleUpdate(update: any) {
  const msg = update?.message || update?.edited_message;
  if (!msg?.text) return;

  const chat = msg.chat;
  const chatId = chat?.id;
  const chatType = chat?.type;
  const fromId = msg.from?.id;
  const text = String(msg.text || "").trim();

  if (chatType !== "private") return;
  if (!chatId || !fromId || !text) return;

  const userId = `tg:${fromId}`;

  // Commande /start
  if (text === "/start") {
    const ans = sanitizeTelegramHtml(
      clampTelegram(
        `<b>Salut ! Je suis Mr XPRONOS.</b>\n` +
          `Pose-moi ta question : coupons, bonus, inscription, VIP, ou juste pour discuter.\n\n` +
          `${tgLinkBlock("Pronostics", SITE.pronos)}`,
      ),
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // Ignorer autres commandes
  if (text.startsWith("/")) return;

  const rl = await checkRateLimit(userId);
  if (!rl.allowed) {
    const ans = sanitizeTelegramHtml(
      `Attends <b>${rl.waitSeconds}s</b> puis reessaie.`,
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  try {
    await tgApi("sendChatAction", { chat_id: chatId, action: "typing" });
  } catch {
    // ignore
  }

  // ==== ETAPE 1: DETECT INTENT (avec fallback LLM) ====
  const intent = await detectIntentSmart(text);

  // ==== ETAPE 2: STOP SESSION (priorite absolue) ====
  if (intent === "stop_session") {
    await clearSession(userId);
    const ans = sanitizeTelegramHtml(
      clampTelegram(
        `<b>Pas de souci !</b>\n` +
          `On parle de quoi alors ? Foot, paris, ou autre chose ?\n\n` +
          `${tgQuote("Je suis la pour t'aider.")}`,
      ),
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 3: VIP ID direct ====
  const vipId = extractVipId(text);
  if (vipId) {
    const ans = vipActivationResponse(vipId);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 4: PROBLEMES (clear session + reponse adaptee) ====
  if (intent === "problem") {
    await clearSession(userId);
    const issue = detectIssueType(text);
    const books = await getBookmakersList();
    const names = books.map((b) => b.nom).filter(Boolean);
    const bm = extractBookmakerName(text, names);
    const ans = troubleshootResponse(issue, bm || undefined);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 5: DEJA UN COMPTE (clear session) ====
  if (intent === "already_account") {
    await clearSession(userId);
    const books = await getBookmakersList();
    const names = books.map((b) => b.nom).filter(Boolean);
    const bm = extractBookmakerName(text, names) || "ce bookmaker";
    const ans = alreadyAccountResponse(bm);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 6: GUIDE PARI (debutant) ====
  if (intent === "guide_betting") {
    await clearSession(userId);
    const books = await getBookmakersList();
    const names = books.map((b) => b.nom).filter(Boolean);
    const bm = extractBookmakerName(text, names);

    const q = normalizeQuestion(text);
    let ans: string;

    if (
      (q.includes("trouver ces matchs") ||
        (q.includes("trouver") && q.includes("match"))) &&
      bm
    ) {
      ans = guideFindMatchesResponse(bm);
    } else {
      ans = guideBettingResponse(bm || undefined);
    }

    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 7: COTE ELEVEE ====
  if (intent === "high_odds") {
    await clearSession(userId);
    const ans = highOddsResponse();
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 8: SESSION PENDING (seulement si pas de probleme) ====
  const session = await getSession(userId);

  if (session?.pending_action === "await_platform_signup") {
    const platform = detectPlatform(text);
    const bookmakerName = String(
      session.pending_payload?.bookmakerName || "Bookmaker",
    );
    const affiliateUrl = String(
      session.pending_payload?.affiliateUrl || "",
    );

    if (platform === "unknown") {
      const ans = sanitizeTelegramHtml(
        `Tu es sur <b>Android</b>, <b>iPhone</b> ou <b>Web</b> ?`,
      );
      await logConversation(userId, text, ans);
      await sendTelegramHtml(chatId, ans);
      return;
    }

    await clearSession(userId);
    const ans = signupStepsResponse(bookmakerName, affiliateUrl, platform);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (session?.pending_action === "await_bookmaker") {
    const names = (session.pending_payload?.bookmakers || []) as string[];
    const chosen = extractBookmakerName(text, names);

    if (!chosen) {
      const ans = sanitizeTelegramHtml(
        `Je n'ai pas reconnu. Dis juste le nom (ex: <b>1xBet</b>).`,
      );
      await logConversation(userId, text, ans);
      await sendTelegramHtml(chatId, ans);
      return;
    }

    const books = await getBookmakersList();
    const row = books.find((b) =>
      normalizeQuestion(b.nom) === normalizeQuestion(chosen)
    );
    const aff = row?.lien_affiliation || "";
    await clearSession(userId);

    if (!aff || !String(aff).startsWith("http")) {
      const ans = sanitizeTelegramHtml(
        `<b>${
          escapeTextKeepEntities(
            chosen,
          )
        }</b>\nJe n'ai pas de lien pour celui-la.\n\n${
          tgLinkBlock(
            "Voir Bonus",
            SITE.bonus,
          )
        }`,
      );
      await logConversation(userId, text, ans);
      await sendTelegramHtml(chatId, ans);
      return;
    }

    await setSession(userId, "await_platform_signup", {
      bookmakerName: chosen,
      affiliateUrl: aff,
    });
    const ans = affiliateIntroResponse(chosen, aff);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 9: INTENTS SPECIFIQUES ====
  if (intent === "prono") {
    const pronos = await getPronosticsToday();
    const ans = couponsResponse(pronos);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (intent === "vip") {
    const ans = vipAskIdResponse();
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (intent === "live") {
    const ans = sanitizeTelegramHtml(
      clampTelegram(
        `<b>LIVE VIP</b>\nOuvre-le ici :\n\n${
          tgLinkBlock(
            "LIVE VIP",
            SITE.live,
          )
        }`,
      ),
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (intent === "bonus") {
    const books = await getBookmakersList();
    const names = books.map((b) => b.nom).filter(Boolean);
    const chosen = extractBookmakerName(text, names);

    if (chosen) {
      const row = books.find((b) =>
        normalizeQuestion(b.nom) === normalizeQuestion(chosen)
      );
      const aff = row?.lien_affiliation || "";
      if (aff && String(aff).startsWith("http")) {
        await setSession(userId, "await_platform_signup", {
          bookmakerName: chosen,
          affiliateUrl: aff,
        });
        const ans = affiliateIntroResponse(chosen, aff);
        await logConversation(userId, text, ans);
        await sendTelegramHtml(chatId, ans);
        return;
      }
    }

    await setSession(userId, "await_bookmaker", {
      bookmakers: names.slice(0, 12),
    });
    const ans = askWhichBookmakerResponse(names);
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (intent === "support") {
    const ans = sanitizeTelegramHtml(
      clampTelegram(
        `<b>OK.</b>\nDis-moi ce qui bloque, ou ecris-nous :\n\n` +
          `${tgLinkBlock("WhatsApp", OFFICIAL_CONTACTS.whatsapp)}\n\n` +
          `${tgLinkBlock("Telegram", OFFICIAL_CONTACTS.telegram)}`,
      ),
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  if (intent === "results") {
    const ans = sanitizeTelegramHtml(
      clampTelegram(
        `<b>Historique & resultats :</b>\n\n` +
          `${tgLinkBlock(
            "Voir l'historique sur le site",
            SITE.historique,
          )}\n\n` +
          `${tgQuote("Si tu veux, dis-moi le match et je te dis si c'est passe ou pas.")}`,
      ),
    );
    await logConversation(userId, text, ans);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  // ==== ETAPE 10: TOUT LE RESTE -> LLM HUMAIN (general, sans coupons/liens inventes) ====
  const cacheKey = `tg:generic:${normalizeQuestion(text)}`;
  const cached = await tgGetCache(cacheKey);
  if (cached) {
    const ans = sanitizeTelegramHtml(cached);
    await logConversation(userId, text, ans, true);
    await sendTelegramHtml(chatId, ans);
    return;
  }

  const history = await getHistoryFromConversations(userId, 5);
  const ans = await callGenericLLM(text, history, intent);
  await tgSetCache(cacheKey, text, ans, 4);
  await logConversation(userId, text, ans, false);
  await sendTelegramHtml(chatId, ans);
}

// ========================
// SERVE
// ========================
serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  if (TELEGRAM_SECRET_TOKEN) {
    const got =
      req.headers.get("X-Telegram-Bot-Api-Secret-Token") ||
      "";
    if (got !== TELEGRAM_SECRET_TOKEN) {
      return json({ error: "unauthorized" }, 401);
    }
  }

  const update = await req.json().catch(() => null);
  if (!update) return json({ error: "Invalid JSON" }, 400);

  // @ts-ignore
  if (globalThis.EdgeRuntime?.waitUntil) {
    // @ts-ignore
    globalThis.EdgeRuntime.waitUntil(handleUpdate(update));
    return json({ ok: true }, 200);
  }

  await handleUpdate(update);
  return json({ ok: true }, 200);
});
