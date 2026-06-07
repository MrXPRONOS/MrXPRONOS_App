// live.ts (Supabase Edge Function / Deno)
// =======================================================
// PATCHES inclus :
// 1) Règle pronostic: on ne propose un seuil que si (seuil >= actuel + 2)
// 2) LIVE UI: /matches et /opportunities lisent la DB (matches_live + live_predictions)
// 3) Historique: INSERT only (pas d'écrasement)
// 4) "Projection" => "Au signal" stocké dans projected_value
// 5) Validation in-play: update current_value + success instant si current_value > threshold
// 6) Notifications: insertNotification() robuste (fallback minimal) + related_prediction_id
// 7) Anti-crash duplicate key (23505): savePrediction idempotent + tolérance message sans code
// 8) History + detail endpoints enrichis avec logos (via matches_live.raw_data)
//    - GET /predictions/history
//    - GET /predictions/by-id?id=...
//
// IMPORTANT (DB) :
// - Le meilleur schéma est un UNIQUE INDEX PARTIEL sur (match_id,prediction_type,threshold) WHERE validated=false.
// - Si ton index unique inclut validated ou n'est pas partiel, les UPDATE validated=true peuvent aussi déclencher 23505.
// Ce fichier contient un "self-heal" (merge + delete) si ça arrive.
// =======================================================

import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { initWasm, Resvg } from "https://esm.sh/@resvg/resvg-wasm@2.6.2?target=deno";
import satori from "npm:satori@0.12.0";
import { html } from "npm:satori-html@0.3.2";

// =======================================================
// ENV
// =======================================================
const BSD_API_TOKEN = Deno.env.get("BSD_API_TOKEN") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const DEFAULT_TZ = Deno.env.get("BSD_TZ") || "Europe/Paris";

const CRON_SECRET = Deno.env.get("CRON_SECRET") || "";
const DEBUG_KEY = Deno.env.get("DEBUG_KEY") || "";

const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
const TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || "";
const SITE_URL = Deno.env.get("SITE_URL") || "https://mrxpronos.github.io/MrXPRONOS_App/";

const BSD_API_BASE = "https://sports.bzzoiro.com/api";
const BSD_IMG_BASE = "https://sports.bzzoiro.com/img";

if (!BSD_API_TOKEN) console.error("BSD_API_TOKEN non défini");
if (!SUPABASE_URL) console.error("SUPABASE_URL non défini");
if (!SUPABASE_SERVICE_ROLE_KEY) console.error("SUPABASE_SERVICE_ROLE_KEY non défini");

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// =======================================================
// CORS
// =======================================================
const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-cron-secret",
};

// =======================================================
// HELPERS
// =======================================================
function json(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, ...headers, "Content-Type": "application/json" },
  });
}

function safeNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function computeFreshness(updatedAt?: string | number | null) {
  if (!updatedAt) return null;
  const ts = typeof updatedAt === "number" ? updatedAt : new Date(updatedAt).getTime();
  if (!Number.isFinite(ts)) return null;
  return Math.max(0, Math.floor((Date.now() - ts) / 1000));
}

function extractPath(url: URL, fnName = "live") {
  const p = url.pathname;
  const needle = `/${fnName}`;
  const i = p.lastIndexOf(needle);
  if (i >= 0) {
    const rest = p.slice(i + needle.length);
    return rest === "" ? "/" : rest;
  }
  return p || "/";
}

function requireCronAuth(req: Request, url: URL) {
  if (!CRON_SECRET) return; // public si non défini
  const auth = req.headers.get("authorization") || "";
  const x = req.headers.get("x-cron-secret") || "";
  const q = url.searchParams.get("key") || "";

  const bearerOk =
    auth.toLowerCase().startsWith("bearer ") && auth.slice(7).trim() === CRON_SECRET;

  const ok = bearerOk || x === CRON_SECRET || q === CRON_SECRET;
  if (!ok) throw new Error("Unauthorized (CRON_SECRET)");
}

function requireDebugAuth(url: URL) {
  if (!DEBUG_KEY) return; // public si non défini
  const key = url.searchParams.get("key") || "";
  if (key !== DEBUG_KEY) throw new Error("Unauthorized (DEBUG_KEY)");
}

async function fetchBSD(endpoint: string, params?: Record<string, string>) {
  if (!BSD_API_TOKEN) throw new Error("BSD_API_TOKEN missing");

  const url = new URL(`${BSD_API_BASE}${endpoint}`);
  const finalParams: Record<string, string> = { ...(params || {}) };

  if (!finalParams.tz) finalParams.tz = DEFAULT_TZ;
  for (const [k, v] of Object.entries(finalParams)) {
    if (v != null && v !== "") url.searchParams.set(k, v);
  }

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Token ${BSD_API_TOKEN}` },
  });

  if (!res.ok) {
    const error = await res.text().catch(() => "");
    throw new Error(`BSD API error (${res.status}): ${error || res.statusText}`);
  }

  return res.json();
}

function isFinishedEvent(ev: any) {
  const status = String(ev?.status || "").toLowerCase();
  const period = String(ev?.period || "").toUpperCase();
  return status === "finished" || period === "FT";
}

function isDuplicateKeyError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return (
    code === "23505" ||
    msg.includes("duplicate key value violates unique constraint") ||
    msg.includes("live_predictions_unique_idx")
  );
}

function isUndefinedColumnError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return code === "42703" || msg.toLowerCase().includes("does not exist");
}

// =======================================================
// ✅ Notifications insertion robuste + logs + fallback
// =======================================================
async function insertNotification(payload: {
  user_id?: string;
  type: string;
  title: string;
  message: string;
  priority?: string;
  read?: boolean;
  related_prediction_id?: string | number | null;
}) {
  const baseRow: any = {
    user_id: payload.user_id ?? "all",
    type: payload.type,
    title: payload.title,
    message: payload.message,
    created_at: new Date().toISOString(),
  };

  const fullRow: any = {
    ...baseRow,
    priority: payload.priority ?? "normal",
    read: payload.read ?? false,
    related_prediction_id:
      payload.related_prediction_id == null ? null : String(payload.related_prediction_id),
  };

  // 1) tentative "full"
  {
    const { error } = await supabase.from("notifications").insert(fullRow);
    if (!error) return true;

    console.error("❌ notifications insert failed (full):", error, "row=", fullRow);

    // 2) fallback minimal
    const { error: e2 } = await supabase.from("notifications").insert(baseRow);
    if (!e2) return true;

    console.error("❌ notifications insert failed (minimal):", e2, "row=", baseRow);
    return false;
  }
}


// =======================================================
// ✅ TELEGRAM LIVE COUPONS — IMAGE SATORI + LOGOS + TEXTE DANS L'IMAGE
// =======================================================
function formatLivePredictionType(type: string) {
  if (type === "total_corners") return "Corners";
  if (type === "total_shots") return "Tirs";
  if (type === "total_fouls") return "Fautes";
  return "Signal LIVE";
}

function formatThreshold(value: unknown) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

function predictionLabelForCaption(type: string) {
  if (type === "total_corners") return "corners";
  if (type === "total_shots") return "tirs";
  if (type === "total_fouls") return "fautes";
  return "";
}

function getTeamInitials(name: unknown) {
  const clean = String(name ?? "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!clean) return "MX";

  const parts = clean.split(" ").filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = "";
  const chunkSize = 0x8000;

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

function detectImageMime(bytes: Uint8Array): string {
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return "image/png";
  }

  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return "image/jpeg";
  }

  return "";
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitText(text: unknown, max = 32): string {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)).trim() + "…";
}

function confidenceFromPrediction(pred: any): number {
  const probability = safeNumber(pred?.probability, 0);
  if (probability > 0 && probability <= 1) return Math.round(probability * 100);

  const reliability = safeNumber(pred?.reliability, 0);
  if (reliability > 0) return Math.round(reliability);

  const confidence = safeNumber(pred?.confidence, 0);
  if (confidence > 0 && confidence <= 1) return Math.round(confidence * 100);
  if (confidence > 0) return Math.round(confidence);

  return 0;
}

function pickLogoId(match: any, type: "home" | "away" | "league") {
  const raw = match?.raw_data || match || {};

  if (type === "home") {
    return (
      match?.home_team_id ??
      raw?.home_team_id ??
      raw?.home_team_obj?.id ??
      raw?.home_team_obj?.api_id ??
      raw?.home?.id ??
      raw?.home?.team?.id ??
      null
    );
  }

  if (type === "away") {
    return (
      match?.away_team_id ??
      raw?.away_team_id ??
      raw?.away_team_obj?.id ??
      raw?.away_team_obj?.api_id ??
      raw?.away?.id ??
      raw?.away?.team?.id ??
      null
    );
  }

  return (
    match?.league_id ??
    raw?.league_id ??
    raw?.league?.id ??
    raw?.competition?.id ??
    null
  );
}

function pickLogoUrl(match: any, type: "home" | "away" | "league") {
  const raw = match?.raw_data || match || {};

  if (type === "home") {
    return (
      match?.home_logo ??
      raw?.home_logo ??
      raw?.home_team_obj?.logo ??
      raw?.home_team_obj?.image ??
      raw?.home?.logo ??
      raw?.home?.team?.logo ??
      null
    );
  }

  if (type === "away") {
    return (
      match?.away_logo ??
      raw?.away_logo ??
      raw?.away_team_obj?.logo ??
      raw?.away_team_obj?.image ??
      raw?.away?.logo ??
      raw?.away?.team?.logo ??
      null
    );
  }

  return (
    match?.league_logo ??
    raw?.league_logo ??
    raw?.league?.logo ??
    raw?.competition?.logo ??
    null
  );
}

async function bytesToSupportedDataUri(bytes: Uint8Array, sourceLabel = "image") {
  if (bytes.length > 800_000) {
    console.warn("Logo trop lourd, ignoré:", sourceLabel, bytes.length);
    return "";
  }

  const mime = detectImageMime(bytes);
  if (!mime) {
    console.warn("Logo ignoré: format non supporté par le rendu Telegram:", sourceLabel, {
      bytes: bytes.length,
      header: Array.from(bytes.slice(0, 12)).map((b) => b.toString(16).padStart(2, "0")).join(" "),
    });
    return "";
  }

  return `data:${mime};base64,${bytesToBase64(bytes)}`;
}

async function imageUrlToDataUri(url?: string | null): Promise<string> {
  if (!url) return "";

  try {
    const res = await fetch(String(url), {
      headers: {
        "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
        "Accept": "image/png,image/jpeg,*/*;q=0.5",
      },
    });

    if (!res.ok) {
      console.warn("Logo impossible à charger:", res.status, url);
      return "";
    }

    return await bytesToSupportedDataUri(new Uint8Array(await res.arrayBuffer()), String(url));
  } catch (e) {
    console.warn("Logo impossible à convertir en data URI:", url, e);
    return "";
  }
}

async function bsdImageToDataUri(type: "team" | "league", id?: string | number | null) {
  if (!id || !BSD_API_TOKEN) return "";

  try {
    const url = `${BSD_IMG_BASE}/${type}/${encodeURIComponent(String(id))}/`;
    const res = await fetch(url, {
      headers: {
        Authorization: `Token ${BSD_API_TOKEN}`,
        "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
        "Accept": "image/png,image/jpeg,*/*;q=0.5",
      },
    });

    if (!res.ok) {
      console.warn("Logo BSD impossible à charger:", res.status, type, id);
      return "";
    }

    return await bytesToSupportedDataUri(new Uint8Array(await res.arrayBuffer()), `${type}:${id}`);
  } catch (e) {
    console.warn("Logo BSD impossible à convertir:", type, id, e);
    return "";
  }
}

async function getTelegramLogoData(match: any, kind: "home" | "away" | "league") {
  const directUrl = pickLogoUrl(match, kind);
  if (directUrl) {
    const direct = await imageUrlToDataUri(directUrl);
    if (direct) return direct;
  }

  const id = pickLogoId(match, kind);
  if (!id) return "";

  return await bsdImageToDataUri(kind === "league" ? "league" : "team", id);
}

let resvgReady: Promise<void> | null = null;

type TelegramFonts = {
  regular: ArrayBuffer;
  bold: ArrayBuffer;
  extraBold: ArrayBuffer;
};

let cachedFontData: TelegramFonts | null = null;

const REMOTE_FONT_URLS: Record<string, string> = {
  "NotoSans-Regular.ttf":
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
  "NotoSans-Bold.ttf":
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
  "NotoSans-ExtraBold.ttf":
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-ExtraBold.ttf",
};

function isValidFontFile(bytes: Uint8Array): boolean {
  if (bytes.length < 20_000) return false;

  const head = Array.from(bytes.slice(0, 4))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return head === "00010000" || head === "4f54544f" || head === "74746366" || head === "74727565";
}

function fontHeader(bytes: Uint8Array): string {
  return Array.from(bytes.slice(0, 16))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join(" ");
}

async function readLocalFont(filename: string): Promise<Uint8Array | null> {
  const candidates: Array<string | URL> = [
    `./_fonts/${filename}`,
    new URL(`./_fonts/${filename}`, import.meta.url),
  ];

  for (const candidate of candidates) {
    try {
      const bytes = await Deno.readFile(candidate);
      if (isValidFontFile(bytes)) return bytes;

      console.warn("Police locale invalide, fallback remote:", {
        filename,
        candidate: String(candidate),
        bytes: bytes.byteLength,
        header: fontHeader(bytes),
      });
    } catch (e: any) {
      console.warn("Police locale non lisible:", {
        filename,
        candidate: String(candidate),
        error: e?.message || String(e),
      });
    }
  }

  return null;
}

async function fetchRemoteFont(filename: string): Promise<Uint8Array> {
  const url = REMOTE_FONT_URLS[filename];
  if (!url) throw new Error(`Aucune URL fallback pour la police ${filename}`);

  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
      "Accept": "font/ttf,application/octet-stream,*/*;q=0.8",
    },
  });

  if (!res.ok) {
    throw new Error(`Impossible de télécharger la police fallback ${filename}: HTTP ${res.status}`);
  }

  const bytes = new Uint8Array(await res.arrayBuffer());

  if (!isValidFontFile(bytes)) {
    throw new Error(
      `Police fallback invalide ${filename}: bytes=${bytes.byteLength}, header=${fontHeader(bytes)}.`,
    );
  }

  return bytes;
}

async function readFontFile(filename: string): Promise<Uint8Array> {
  const local = await readLocalFont(filename);
  if (local) return local;

  const remote = await fetchRemoteFont(filename);
  console.log("Police chargée depuis fallback remote:", {
    filename,
    bytes: remote.byteLength,
    header: fontHeader(remote),
  });
  return remote;
}

function toExactArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function loadFontData(): Promise<TelegramFonts> {
  if (cachedFontData) return cachedFontData;

  const regular = await readFontFile("NotoSans-Regular.ttf");
  const bold = await readFontFile("NotoSans-Bold.ttf");
  const extraBold = await readFontFile("NotoSans-ExtraBold.ttf");

  cachedFontData = {
    regular: toExactArrayBuffer(regular),
    bold: toExactArrayBuffer(bold),
    extraBold: toExactArrayBuffer(extraBold),
  };

  return cachedFontData;
}

async function ensureResvgReady() {
  if (!resvgReady) {
    resvgReady = (async () => {
      const wasmUrl = "https://cdn.jsdelivr.net/npm/@resvg/resvg-wasm@2.6.2/index_bg.wasm";
      const wasm = await fetch(wasmUrl);
      if (!wasm.ok) throw new Error(`Impossible de charger resvg wasm: ${wasm.status}`);
      await initWasm(await wasm.arrayBuffer());
    })();
  }
  await resvgReady;
}

async function buildTelegramCouponPng(match: any, pred: any): Promise<Uint8Array> {
  await ensureResvgReady();
  const fonts = await loadFontData();

  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;

  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const typeLabel = formatLivePredictionType(rawType);
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const confidence = confidenceFromPrediction(pred);

  const currentValue =
    pred?.current_value ??
    pred?.current ??
    pred?.signal_value ??
    pred?.value_at_signal ??
    0;

  const [homeLogoData, awayLogoData, leagueLogoData] = await Promise.all([
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
    getTelegramLogoData(match, "league"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 22);
  const awayName = fitText(match?.away_team ?? "Équipe B", 22);
  const leagueName = fitText(
    match?.league?.name ?? match?.league_name ?? match?.competition ?? "Football",
    30,
  );

  const couponText =
    rawType === "total_corners"
      ? `Total plus de ${threshold} corners`
      : rawType === "total_shots"
      ? `Total plus de ${threshold} tirs`
      : rawType === "total_fouls"
      ? `Total plus de ${threshold} fautes`
      : `Total plus de ${threshold}`;

  const reason = fitText(
    pred?.message ??
      pred?.reason ??
      `${currentValue} ${typeLabel.toLowerCase()} à la ${minute}e minute`,
    78,
  );

  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));

  const markup = html(`
    <div style="width:1080px;height:1080px;display:flex;flex-direction:column;background:#050505;color:#ffffff;font-family:'Noto Sans';padding:52px;box-sizing:border-box;">
      <div style="width:976px;height:976px;display:flex;flex-direction:column;border:3px solid #D4AF37;border-radius:46px;padding:38px;box-sizing:border-box;background:#0d0d0d;">

        <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-bottom:26px;">
          <div style="display:flex;flex-direction:column;">
            <div style="display:flex;font-size:25px;color:#D4AF37;font-weight:900;letter-spacing:2px;">MR XPRONOS</div>
            <div style="display:flex;margin-top:10px;font-size:50px;font-weight:900;color:#ffffff;line-height:1;">NOUVEAU COUPON LIVE</div>
          </div>
          <div style="display:flex;background:#2563EB;color:#ffffff;padding:15px 28px;border-radius:999px;font-size:27px;font-weight:900;">LIVE ${minute}'</div>
        </div>

        <div style="display:flex;flex-direction:column;background:#171717;border:1px solid #2b2b2b;border-radius:34px;padding:30px;margin-bottom:26px;box-sizing:border-box;">
          <div style="display:flex;flex-direction:row;align-items:center;margin-bottom:26px;">
            ${
              leagueLogoData
                ? `<img src="${leagueLogoData}" width="44" height="44" style="border-radius:999px;margin-right:16px;" />`
                : `<div style="display:flex;width:44px;height:44px;border-radius:999px;border:2px solid #D4AF37;margin-right:16px;"></div>`
            }
            <div style="display:flex;font-size:27px;font-weight:800;color:#D4AF37;">${escapeHtml(leagueName)}</div>
          </div>

          <div style="display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
            <div style="width:255px;display:flex;flex-direction:column;align-items:center;">
              ${
                homeLogoData
                  ? `<img src="${homeLogoData}" width="92" height="92" style="object-fit:contain;border-radius:18px;" />`
                  : `<div style="width:92px;height:92px;border-radius:999px;border:3px solid #D4AF37;color:#D4AF37;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;">${homeInitials}</div>`
              }
              <div style="display:flex;margin-top:16px;font-size:29px;font-weight:900;text-align:center;color:#ffffff;line-height:1.12;">${escapeHtml(homeName)}</div>
            </div>

            <div style="width:310px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
              <div style="display:flex;font-size:76px;font-weight:900;color:#ffffff;line-height:1;">${score}</div>
              <div style="display:flex;margin-top:12px;font-size:22px;color:#A3A3A3;font-weight:800;">En direct</div>
            </div>

            <div style="width:255px;display:flex;flex-direction:column;align-items:center;">
              ${
                awayLogoData
                  ? `<img src="${awayLogoData}" width="92" height="92" style="object-fit:contain;border-radius:18px;" />`
                  : `<div style="width:92px;height:92px;border-radius:999px;border:3px solid #D4AF37;color:#D4AF37;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;">${awayInitials}</div>`
              }
              <div style="display:flex;margin-top:16px;font-size:29px;font-weight:900;text-align:center;color:#ffffff;line-height:1.12;">${escapeHtml(awayName)}</div>
            </div>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;background:#2a230b;border:2px solid #D4AF37;border-radius:34px;padding:36px;box-sizing:border-box;">
          <div style="display:flex;font-size:24px;font-weight:900;color:#D4AF37;text-transform:uppercase;letter-spacing:1px;">Pronostic live</div>

          <div style="margin-top:18px;width:820px;font-size:50px;font-weight:900;color:#ffffff;line-height:1.12;display:flex;flex-direction:column;">
            ${escapeHtml(couponText)}
          </div>

          <div style="margin-top:26px;display:flex;flex-direction:row;">
            <div style="display:flex;background:#050505;border:1px solid #3a3a3a;border-radius:18px;padding:16px 20px;font-size:25px;font-weight:900;color:#ffffff;margin-right:16px;">Type : ${escapeHtml(typeLabel)}</div>
            <div style="display:flex;background:#050505;border:1px solid #3a3a3a;border-radius:18px;padding:16px 20px;font-size:25px;font-weight:900;color:#ffffff;">Fiabilité : ${confidence}%</div>
          </div>

          <div style="display:flex;margin-top:26px;font-size:28px;font-weight:800;color:#ffffff;">Au signal : ${escapeHtml(currentValue)} • Pronostic : ${escapeHtml(threshold)}</div>
          <div style="display:flex;margin-top:22px;font-size:25px;line-height:1.35;font-weight:700;color:#E5E7EB;">${escapeHtml(reason)}</div>
        </div>

        <div style="margin-top:auto;text-align:center;font-size:21px;color:#A3A3A3;font-weight:700;display:flex;align-items:center;justify-content:center;">
          18+ • Joue responsablement
        </div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 1080,
    fonts: [
      { name: "Noto Sans", data: fonts.regular, weight: 400, style: "normal" },
      { name: "Noto Sans", data: fonts.bold, weight: 700, style: "normal" },
      { name: "Noto Sans", data: fonts.extraBold, weight: 900, style: "normal" },
    ],
    embedFont: true,
  });

  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      loadSystemFonts: false,
    },
  });

  return resvg.render().asPng();
}

function buildTelegramText(match: any, pred: any) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const label = predictionLabelForCaption(type);
  return `🔥 NOUVEAU COUPON LIVE

⚽️ Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}

async function sendTelegramPhoto(pngBytes: Uint8Array, caption: string, buttonUrl?: string) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    console.warn("Telegram non configuré: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant");
    return false;
  }

  const form = new FormData();
  form.append("chat_id", TELEGRAM_CHAT_ID);
  if (caption && caption.trim()) form.append("caption", caption);

  if (buttonUrl) {
    form.append(
      "reply_markup",
      JSON.stringify({
        inline_keyboard: [
          [
            {
              text: "Voir plus d’opportunités 🔥",
              url: buttonUrl,
            },
          ],
        ],
      })
    );
  }

  form.append("photo", new Blob([pngBytes], { type: "image/png" }), "coupon-live.png");

  try {
    const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error("❌ Telegram sendPhoto failed:", res.status, body);
      return false;
    }

    console.log("✅ Coupon LIVE envoyé en image Telegram");
    return true;
  } catch (e) {
    console.error("❌ Telegram sendPhoto exception:", e);
    return false;
  }
}

async function sendTelegramMessage(text: string, buttonUrl?: string) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return false;

  const form = new FormData();
  form.append("chat_id", TELEGRAM_CHAT_ID);
  form.append("text", text);

  if (buttonUrl) {
    form.append(
      "reply_markup",
      JSON.stringify({
        inline_keyboard: [[{ text: "Voir plus d’opportunités 🔥", url: buttonUrl }]],
      })
    );
  }

  try {
    const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error("❌ Telegram sendMessage failed:", res.status, body);
    }

    return res.ok;
  } catch (e) {
    console.error("❌ Telegram sendMessage exception:", e);
    return false;
  }
}

async function sendTelegramLiveCoupon(match: any, pred: any, predictionId?: string | number | null) {
  const liveUrl = `${SITE_URL.replace(/\/$/, "")}/live.html`;

  try {
    const pngBytes = await buildTelegramCouponPng(match, pred);
    return await sendTelegramPhoto(
      pngBytes,
      buildTelegramText(match, pred),
      liveUrl,
    );
  } catch (e) {
    console.error("❌ Génération image LIVE impossible, fallback texte:", e);
    return await sendTelegramMessage(buildTelegramText(match, pred), liveUrl);
  }
}


function validationStatusMeta(outcome: "success" | "failure") {
  if (outcome === "success") {
    return {
      emoji: "✅",
      header: "COUPON VALIDÉ",
      status: "RÉUSSI",
      color: "#22C55E",
      bg: "#0f2a18",
      border: "#22C55E",
    };
  }

  return {
    emoji: "❌",
    header: "COUPON PERDU",
    status: "ÉCHOUÉ",
    color: "#EF4444",
    bg: "#2a1111",
    border: "#EF4444",
  };
}

function buildValidationCouponText(pred: any) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const label = predictionLabelForCaption(type);
  return `Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}

function splitMatchName(matchName?: string | null) {
  const text = String(matchName ?? "").trim();
  if (!text) return { home: "Équipe A", away: "Équipe B" };

  const parts = text.split(/\s+vs\s+/i);
  if (parts.length >= 2) {
    return {
      home: parts[0].trim() || "Équipe A",
      away: parts.slice(1).join(" vs ").trim() || "Équipe B",
    };
  }

  return { home: text, away: "Équipe B" };
}

async function getTelegramMatchFromCache(pred: any, ev?: any | null) {
  const { data } = await supabase
    .from("matches_live")
    .select("*")
    .eq("id", String(pred.match_id))
    .limit(1)
    .maybeSingle();

  if (data) {
    return {
      id: data.id,
      home_team: data.home_team,
      away_team: data.away_team,
      home_score: data.home_score ?? 0,
      away_score: data.away_score ?? 0,
      current_minute: data.current_minute ?? 90,
      league_name: data.league_name ?? pred.league_name ?? null,
      league: { name: data.league_name ?? pred.league_name ?? "Football" },
      raw_data: data.raw_data || {},
      home_logo: data.raw_data?.home_logo ?? null,
      away_logo: data.raw_data?.away_logo ?? null,
      league_logo: data.raw_data?.league_logo ?? null,
    };
  }

  const names = splitMatchName(pred?.match_name);

  return {
    id: pred.match_id,
    home_team: names.home,
    away_team: names.away,
    home_score: ev?.home_score ?? ev?.home?.score ?? 0,
    away_score: ev?.away_score ?? ev?.away?.score ?? 0,
    current_minute: 90,
    league_name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football",
    league: { name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football" },
    raw_data: ev || {},
  };
}

async function buildTelegramValidationPng(
  match: any,
  pred: any,
  outcome: "success" | "failure",
  currentValue: number,
  validationType: "instant" | "final",
): Promise<Uint8Array> {
  await ensureResvgReady();
  const fonts = await loadFontData();

  const meta = validationStatusMeta(outcome);
  const minute = safeNumber(match?.current_minute ?? match?.minute, validationType === "final" ? 90 : 0);
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;

  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const typeLabel = formatLivePredictionType(rawType);
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const [homeLogoData, awayLogoData, leagueLogoData] = await Promise.all([
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
    getTelegramLogoData(match, "league"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 22);
  const awayName = fitText(match?.away_team ?? "Équipe B", 22);
  const leagueName = fitText(
    match?.league?.name ?? match?.league_name ?? match?.competition ?? "Football",
    30,
  );

  const couponText = buildValidationCouponText(pred);
  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));
  const resultLabel = validationType === "instant" ? "Validé en live" : "Validé fin de match";
  const resultSentence =
    outcome === "success"
      ? "Le seuil a été dépassé. Coupon validé."
      : "Le seuil n'a pas été dépassé. Coupon perdu.";

  const markup = html(`
    <div style="width:1080px;height:1080px;display:flex;flex-direction:column;background:#050505;color:#ffffff;font-family:'Noto Sans';padding:52px;box-sizing:border-box;">
      <div style="width:976px;height:976px;display:flex;flex-direction:column;border:3px solid ${meta.border};border-radius:46px;padding:38px;box-sizing:border-box;background:#0d0d0d;">

        <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-bottom:26px;">
          <div style="display:flex;flex-direction:column;">
            <div style="display:flex;font-size:25px;color:#D4AF37;font-weight:900;letter-spacing:2px;">MR XPRONOS</div>
            <div style="display:flex;margin-top:10px;font-size:50px;font-weight:900;color:#ffffff;line-height:1;">${escapeHtml(meta.header)}</div>
          </div>
          <div style="display:flex;background:${meta.color};color:#050505;padding:15px 28px;border-radius:999px;font-size:27px;font-weight:900;">${escapeHtml(meta.status)}</div>
        </div>

        <div style="display:flex;flex-direction:column;background:#171717;border:1px solid #2b2b2b;border-radius:34px;padding:30px;margin-bottom:26px;box-sizing:border-box;">
          <div style="display:flex;flex-direction:row;align-items:center;margin-bottom:26px;">
            ${
              leagueLogoData
                ? `<img src="${leagueLogoData}" width="44" height="44" style="border-radius:999px;margin-right:16px;" />`
                : `<div style="display:flex;width:44px;height:44px;border-radius:999px;border:2px solid #D4AF37;margin-right:16px;"></div>`
            }
            <div style="display:flex;font-size:27px;font-weight:800;color:#D4AF37;">${escapeHtml(leagueName)}</div>
          </div>

          <div style="display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
            <div style="width:255px;display:flex;flex-direction:column;align-items:center;">
              ${
                homeLogoData
                  ? `<img src="${homeLogoData}" width="92" height="92" style="object-fit:contain;border-radius:18px;" />`
                  : `<div style="width:92px;height:92px;border-radius:999px;border:3px solid #D4AF37;color:#D4AF37;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;">${homeInitials}</div>`
              }
              <div style="display:flex;margin-top:16px;font-size:29px;font-weight:900;text-align:center;color:#ffffff;line-height:1.12;">${escapeHtml(homeName)}</div>
            </div>

            <div style="width:310px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
              <div style="display:flex;font-size:76px;font-weight:900;color:#ffffff;line-height:1;">${score}</div>
              <div style="display:flex;margin-top:12px;font-size:22px;color:#A3A3A3;font-weight:800;">${escapeHtml(resultLabel)}</div>
            </div>

            <div style="width:255px;display:flex;flex-direction:column;align-items:center;">
              ${
                awayLogoData
                  ? `<img src="${awayLogoData}" width="92" height="92" style="object-fit:contain;border-radius:18px;" />`
                  : `<div style="width:92px;height:92px;border-radius:999px;border:3px solid #D4AF37;color:#D4AF37;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900;">${awayInitials}</div>`
              }
              <div style="display:flex;margin-top:16px;font-size:29px;font-weight:900;text-align:center;color:#ffffff;line-height:1.12;">${escapeHtml(awayName)}</div>
            </div>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;background:${meta.bg};border:2px solid ${meta.border};border-radius:34px;padding:36px;box-sizing:border-box;">
          <div style="display:flex;font-size:24px;font-weight:900;color:${meta.color};text-transform:uppercase;letter-spacing:1px;">Résultat du coupon</div>

          <div style="margin-top:18px;width:820px;font-size:50px;font-weight:900;color:#ffffff;line-height:1.12;display:flex;flex-direction:column;">
            ${escapeHtml(couponText)}
          </div>

          <div style="margin-top:26px;display:flex;flex-direction:row;">
            <div style="display:flex;background:#050505;border:1px solid #3a3a3a;border-radius:18px;padding:16px 20px;font-size:25px;font-weight:900;color:#ffffff;margin-right:16px;">Type : ${escapeHtml(typeLabel)}</div>
            <div style="display:flex;background:#050505;border:1px solid #3a3a3a;border-radius:18px;padding:16px 20px;font-size:25px;font-weight:900;color:#ffffff;">Statut : ${escapeHtml(meta.status)}</div>
          </div>

          <div style="display:flex;margin-top:26px;font-size:28px;font-weight:800;color:#ffffff;">Final : ${escapeHtml(currentValue)} • Seuil : ${escapeHtml(threshold)}</div>
          <div style="display:flex;margin-top:22px;font-size:25px;line-height:1.35;font-weight:700;color:#E5E7EB;">${escapeHtml(resultSentence)}</div>
        </div>

        <div style="margin-top:auto;text-align:center;font-size:21px;color:#A3A3A3;font-weight:700;display:flex;align-items:center;justify-content:center;">
          18+ • Joue responsablement
        </div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 1080,
    fonts: [
      { name: "Noto Sans", data: fonts.regular, weight: 400, style: "normal" },
      { name: "Noto Sans", data: fonts.bold, weight: 700, style: "normal" },
      { name: "Noto Sans", data: fonts.extraBold, weight: 900, style: "normal" },
    ],
    embedFont: true,
  });

  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      loadSystemFonts: false,
    },
  });

  return resvg.render().asPng();
}

function buildTelegramValidationText(pred: any, outcome: "success" | "failure", currentValue: number) {
  const meta = validationStatusMeta(outcome);
  const couponText = buildValidationCouponText(pred);

  return `${meta.emoji} ${outcome === "success" ? "COUPON VALIDÉ" : "COUPON PERDU"}

⚽️ ${couponText}
📊 Résultat : ${currentValue}`;
}

async function sendTelegramValidationResult(
  match: any,
  pred: any,
  outcome: "success" | "failure",
  currentValue: number,
  validationType: "instant" | "final",
  predictionId?: string | number | null,
) {
  const liveUrl = `${SITE_URL.replace(/\/$/, "")}/live.html`;

  try {
    const pngBytes = await buildTelegramValidationPng(match, pred, outcome, currentValue, validationType);
    return await sendTelegramPhoto(
      pngBytes,
      buildTelegramValidationText(pred, outcome, currentValue),
      liveUrl,
    );
  } catch (e) {
    console.error("❌ Génération image VALIDATION impossible, fallback texte:", e);
    return await sendTelegramMessage(
      buildTelegramValidationText(pred, outcome, currentValue),
      liveUrl,
    );
  }
}


// =======================================================
// ✅ CRON HEALTH (cron_runs)
// =======================================================
async function setCronRun(name: string, ok: boolean, meta: any = {}) {
  try {
    await supabase.from("cron_runs").upsert({
      name,
      last_run_at: new Date().toISOString(),
      last_ok: ok,
      meta: meta ?? {},
    });
  } catch (e) {
    console.error("cron_runs upsert failed:", e);
  }
}

// =======================================================
// LIVE ENGINE
// =======================================================
function computeMomentum(stats: any) {
  const h = stats?.home || {};
  const a = stats?.away || {};

  const hm =
    safeNumber(h.total_shots) * 2 +
    safeNumber(h.shots_on_target) * 3 +
    safeNumber(h.corner_kicks) * 1.5 +
    safeNumber(h.ball_possession) * 0.15;

  const am =
    safeNumber(a.total_shots) * 2 +
    safeNumber(a.shots_on_target) * 3 +
    safeNumber(a.corner_kicks) * 1.5 +
    safeNumber(a.ball_possession) * 0.15;

  const total = hm + am;
  const homeRatio = total > 0 ? hm / total : 0.5;
  const awayRatio = 1 - homeRatio;

  let dominant = "balanced";
  if (homeRatio >= 0.58) dominant = "home";
  else if (awayRatio >= 0.58) dominant = "away";

  return {
    total: Math.round(total),
    home_ratio: Math.round(homeRatio * 100),
    away_ratio: Math.round(awayRatio * 100),
    dominant_side: dominant,
  };
}

function getTotalStats(stats: any) {
  return {
    shots: safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots),
    shotsOnTarget:
      safeNumber(stats?.home?.shots_on_target) + safeNumber(stats?.away?.shots_on_target),
    corners: safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks),
    fouls: safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls),
    possessionHome: safeNumber(stats?.home?.ball_possession),
    possessionAway: safeNumber(stats?.away?.ball_possession),
  };
}

function getMatchFlow(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);

  const globalShotsRate = totals.shots / Math.max(minute, 1);
  const globalCornersRate = totals.corners / Math.max(minute, 1);
  const globalFoulsRate = totals.fouls / Math.max(minute, 1);

  const attackingPressure =
    totals.shotsOnTarget * 2 +
    totals.corners * 1.4 +
    Math.abs(totals.possessionHome - totals.possessionAway) * 0.08 +
    safeNumber(momentum?.total) * 0.12;

  let flow: "offensive" | "neutral" | "defensive" = "neutral";

  if (attackingPressure >= 18 || globalShotsRate >= 0.22 || globalCornersRate >= 0.09) {
    flow = "offensive";
  }

  if (
    minute >= 65 &&
    attackingPressure < 12 &&
    globalShotsRate < 0.18 &&
    globalCornersRate < 0.07
  ) {
    flow = "defensive";
  }

  return { flow, attackingPressure, globalShotsRate, globalCornersRate, globalFoulsRate };
}

function conservativeProjection(params: {
  current: number;
  minute: number;
  type: "shots" | "corners" | "fouls";
  flow: "offensive" | "neutral" | "defensive";
}) {
  const { current, minute, type, flow } = params;

  const elapsed = Math.max(1, minute);
  const remaining = Math.max(0, 90 - elapsed);
  const baseRate = current / elapsed;

  let multiplier = 0.72;
  if (flow === "offensive") multiplier = 0.82;
  if (flow === "neutral") multiplier = 0.7;
  if (flow === "defensive") multiplier = 0.52;

  if (minute >= 70) multiplier -= 0.08;
  if (minute >= 78) multiplier -= 0.1;

  multiplier = Math.max(0.35, multiplier);

  let projected = current + baseRate * remaining * multiplier;

  const maxExtra = type === "corners" ? 4 : type === "shots" ? 8 : 8;
  projected = Math.min(projected, current + maxExtra);

  return Number(projected.toFixed(1));
}

/**
 * ✅ Règle :
 * prediction seulement si seuil >= actuel + 2
 */
function getSafeThreshold(
  type: "shots" | "corners" | "fouls",
  current: number,
  projected: number,
  minGap = 2,
) {
  const thresholds =
    type === "corners"
      ? [7.5, 8.5, 9.5, 10.5, 11.5]
      : type === "shots"
        ? [17.5, 19.5, 21.5, 23.5, 25.5, 27.5, 29.5]
        : [19.5, 21.5, 23.5, 24.5, 25.5, 27.5];

  for (const t of thresholds) {
    const gapOk = (t - current) >= minGap;
    if (current < t && projected >= t + 0.5 && gapOk) return t;
  }
  return null;
}

function computeHeatLevel(match: any) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const totals = getTotalStats(stats);

  let score = 0;
  score += totals.shots * 1.2;
  score += totals.shotsOnTarget * 2;
  score += totals.corners * 1.2;
  score += totals.fouls * 0.35;
  score += minute >= 55 ? 6 : 0;
  score += minute >= 70 ? 5 : 0;

  if (score >= 38) return "explosive";
  if (score >= 26) return "hot";
  if (score >= 14) return "warming";
  return "calm";
}

function predictTotalCorners(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.corners;

  if (minute < 18 || minute > 82) return null;
  if (current < 3) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "corners",
    flow: flowData.flow,
  });

  const threshold = getSafeThreshold("corners", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.58;
  let reliability = 52;
  const reasons: string[] = [];

  if (current >= 4) { probability += 0.06; reliability += 6; reasons.push(`${current} corners déjà obtenus`); }
  if (totals.shots >= 10) { probability += 0.06; reliability += 5; reasons.push(`${totals.shots} tirs cumulés`); }
  if (totals.shotsOnTarget >= 4) { probability += 0.04; reliability += 4; reasons.push(`${totals.shotsOnTarget} tirs cadrés`); }
  if (flowData.flow === "offensive") { probability += 0.07; reliability += 7; reasons.push(`Match offensif`); }
  if (flowData.flow === "defensive") { probability -= 0.08; reliability -= 8; reasons.push(`Rythme défensif`); }
  if (minute >= 25 && minute <= 70) { probability += 0.05; reliability += 6; reasons.push(`Fenêtre (${minute}')`); }

  probability = Math.min(0.90, Math.max(0.50, probability));
  reliability = Math.min(92, Math.max(40, reliability));

  if (probability < 0.76 || reliability < 63) return null;

  return {
    type: "total_corners",
    title: `Over ${threshold} corners`,
    badge: "Corners",
    color: "yellow",
    probability,
    message: `${current} corners actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function predictTotalShots(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.shots;

  if (minute < 15 || minute > 83) return null;
  if (current < 6) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({ current, minute, type: "shots", flow: flowData.flow });

  const threshold = getSafeThreshold("shots", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.60;
  let reliability = 55;
  const reasons: string[] = [];

  if (current >= 8) { probability += 0.06; reliability += 6; reasons.push(`${current} tirs déjà enregistrés`); }
  if (totals.shotsOnTarget >= 3) { probability += 0.06; reliability += 5; reasons.push(`${totals.shotsOnTarget} tirs cadrés`); }
  if (flowData.flow === "offensive") { probability += 0.08; reliability += 7; reasons.push(`Match offensif`); }
  if (flowData.flow === "defensive") { probability -= 0.10; reliability -= 8; reasons.push(`Rythme baisse`); }
  if (minute >= 20 && minute <= 72) { probability += 0.05; reliability += 5; reasons.push(`Minute (${minute}')`); }

  probability = Math.min(0.91, Math.max(0.50, probability));
  reliability = Math.min(93, Math.max(40, reliability));

  if (probability < 0.77 || reliability < 64) return null;

  return {
    type: "total_shots",
    title: `Over ${threshold} tirs`,
    badge: "Tirs",
    color: "green",
    probability,
    message: `${current} tirs actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function predictTotalFouls(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.fouls;

  if (minute < 18 || minute > 84) return null;
  if (current < 6) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "fouls",
    flow: flowData.flow === "offensive" ? "neutral" : flowData.flow,
  });

  const threshold = getSafeThreshold("fouls", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.57;
  let reliability = 54;
  const reasons: string[] = [];

  if (current >= 8) { probability += 0.05; reliability += 6; reasons.push(`${current} fautes déjà sifflées`); }
  if (minute >= 25 && minute <= 75) { probability += 0.05; reliability += 5; reasons.push(`Période exploitable`); }
  if (flowData.flow === "defensive") { probability += 0.03; reliability += 3; reasons.push(`Match fermé`); }
  if (flowData.flow === "offensive") { probability -= 0.03; reliability -= 2; }

  probability = Math.min(0.88, Math.max(0.50, probability));
  reliability = Math.min(90, Math.max(40, reliability));

  if (probability < 0.75 || reliability < 62) return null;

  return {
    type: "total_fouls",
    title: `Over ${threshold} fautes`,
    badge: "Fautes",
    color: "orange",
    probability,
    message: `${current} fautes actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function computeAiScore(match: any, predictions: any[]) {
  const best = predictions?.[0];
  if (!best) return 0;

  const momentum = computeMomentum(match?.live_stats || {});
  let score = 0;
  score += Math.round((best.probability || 0) * 50);
  score += Math.round((best.reliability || 0) * 0.35);
  score += Math.round((momentum.total || 0) * 0.2);

  return Math.min(99, score);
}

function computeValueScore(match: any, predictions: any[]) {
  const best = predictions?.[0];
  if (!best) return 0;

  const minute = safeNumber(match?.current_minute, 0);
  let score = 0;
  score += Math.round((best.probability || 0) * 40);
  score += Math.round((best.reliability || 0) * 0.25);
  score += minute >= 25 ? 10 : 0;
  score += minute >= 45 ? 10 : 0;
  score += minute >= 60 ? 8 : 0;

  return Math.min(99, score);
}

function normalizeMatch(match: any, updatedAt?: string) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const momentum = computeMomentum(stats);

  const allPredictions = [
    predictTotalShots(stats, minute, momentum),
    predictTotalCorners(stats, minute, momentum),
    predictTotalFouls(stats, minute, momentum),
  ].filter(Boolean);

  allPredictions.sort((a: any, b: any) => {
    if ((b.probability || 0) !== (a.probability || 0)) return (b.probability || 0) - (a.probability || 0);
    return (b.reliability || 0) - (a.reliability || 0);
  });

  const predictions = allPredictions.filter((p: any) => (p.probability || 0) >= 0.80);

  return {
    ...match,
    momentum_index: momentum,
    pressure_index: momentum,
    predictions,
    all_predictions: allPredictions,
    ai_score: computeAiScore(match, allPredictions),
    value_score: computeValueScore(match, allPredictions),
    reliability_score: allPredictions?.[0]?.reliability || 0,
    data_quality_score: 90,
    heat_level: computeHeatLevel(match),
    freshness_seconds: computeFreshness(updatedAt || new Date().toISOString()),
  };
}

// =======================================================
// DB - matches cache
// =======================================================
async function cacheLiveMatches(rawMatches: any[]) {
  for (const m of rawMatches) {
    const normalized = normalizeMatch(m);

    const payload: any = {
      id: String(m.id),
      home_team: m.home_team ?? null,
      away_team: m.away_team ?? null,
      home_score: m.home_score ?? 0,
      away_score: m.away_score ?? 0,
      current_minute: m.current_minute ?? 0,
      league_name: m.league?.name ?? null,
      status: m.status ?? null,
      raw_data: normalized,
      momentum: normalized.momentum_index ?? null,
      updated_at: new Date().toISOString(),
    };

    const { error } = await supabase.from("matches_live").upsert(payload);
    if (error) throw error;
  }
}

// =======================================================
// DB - predictions helpers (idempotence)
// =======================================================
async function findExistingPredictionId(params: {
  match_id: string;
  prediction_type: string;
  threshold: number;
  validated?: boolean | null; // null => ignore filter
}) {
  let q = supabase
    .from("live_predictions")
    .select("id")
    .eq("match_id", params.match_id)
    .eq("prediction_type", params.prediction_type)
    .eq("threshold", params.threshold)
    .order("created_at", { ascending: false })
    .limit(1);

  if (params.validated === true || params.validated === false) {
    q = q.eq("validated", params.validated);
  }

  const { data, error } = await q.maybeSingle();
  if (error) throw error;
  return data?.id ?? null;
}

/**
 * ✅ savePrediction :
 * - INSERT only
 * - idempotent (catch duplicate key)
 */
async function savePrediction(match: any, pred: any) {
  const matchId = String(match.id);
  const thresholdNum = Number(safeNumber(pred.threshold, 0).toFixed(1));
  const signalValue = safeNumber(pred.signal_value ?? pred.current, 0);

  const payload: any = {
    match_id: matchId,
    match_name: `${match.home_team} vs ${match.away_team}`,
    home_team: match.home_team ?? null,
    away_team: match.away_team ?? null,
    home_score: match.home_score ?? 0,
    away_score: match.away_score ?? 0,

    minute: match.current_minute ?? 0,
    league_name: match.league?.name ?? null,

    prediction_type: pred.type,
    probability: pred.probability,
    message: pred.message,

    threshold: thresholdNum,
    projected_value: signalValue,
    current_value: signalValue,

    confidence: pred.probability >= 0.84 ? "high" : "medium",
    validated: false,
    outcome: null,
    updated_at: new Date().toISOString(),
  };

  // pré-check : d'abord validated=false (si index partiel), sinon fallback sans filtre
  const existingRunning = await findExistingPredictionId({
    match_id: matchId,
    prediction_type: pred.type,
    threshold: thresholdNum,
    validated: false,
  });
  if (existingRunning) return { created: false, id: existingRunning };

  // INSERT
  const { data, error } = await supabase
    .from("live_predictions")
    .insert({ ...payload, created_at: new Date().toISOString() })
    .select("id")
    .single();

  if (error) {
    if (isDuplicateKeyError(error)) {
      // race condition: quelqu’un a insert entre temps
      const id2 =
        (await findExistingPredictionId({
          match_id: matchId,
          prediction_type: pred.type,
          threshold: thresholdNum,
          validated: false,
        })) ??
        (await findExistingPredictionId({
          match_id: matchId,
          prediction_type: pred.type,
          threshold: thresholdNum,
          validated: null,
        }));
      return { created: false, id: id2 };
    }
    throw error;
  }

  await insertNotification({
    user_id: "all",
    type: "live_prediction",
    title: "Nouvelle opportunité LIVE",
    message:
`${payload.match_name}
Pronostic: ${pred.title}
Minute du signal: ${payload.minute}'
Pronostic (seuil): ${payload.threshold}
Au signal: ${signalValue}`,
    priority: pred.probability >= 0.86 ? "urgent" : "normal",
    read: false,
    related_prediction_id: data.id,
  });

  // ✅ Envoi du nouveau coupon LIVE dans Telegram uniquement quand il est nouvellement créé.
  // Si le coupon existe déjà, la fonction retourne created:false avant cette partie, donc pas de doublon Telegram.
  await sendTelegramLiveCoupon(match, pred, data.id);

  return { created: true, id: data.id };
}

async function getCachedLiveStats(matchId: string) {
  const { data, error } = await supabase
    .from("matches_live")
    .select("raw_data")
    .eq("id", String(matchId))
    .limit(1)
    .maybeSingle();

  if (error || !data) return null;
  return data?.raw_data?.live_stats || null;
}

// =======================================================
// ✅ Safe update helper (tolerates missing columns like validation_type)
// =======================================================
async function updatePredictionSafe(predId: string, values: any) {
  const { error } = await supabase.from("live_predictions").update(values).eq("id", predId);
  if (!error) return true;

  // if schema doesn't have some columns, retry without them
  if (isUndefinedColumnError(error)) {
    const cleaned = { ...values };
    delete cleaned.validation_type;
    delete cleaned.validated_at; // if missing
    const { error: e2 } = await supabase.from("live_predictions").update(cleaned).eq("id", predId);
    if (!e2) return true;
    throw e2;
  }

  throw error;
}

// =======================================================
// ✅ Validation "merge" self-heal on duplicate unique index
// If UPDATE validated=true fails with 23505:
// - find existing validated=true row with same key
// - update that row with finalValue/outcome
// - delete the current row
// returns the "kept" prediction id
// =======================================================
async function validatePredictionWithMerge(params: {
  predRow: any; // must contain id, match_id, prediction_type, threshold
  outcome: "success" | "failure";
  currentValue: number;
  validation_type: "instant" | "final";
}) {
  const predId = String(params.predRow.id);
  const matchId = String(params.predRow.match_id);
  const pType = String(params.predRow.prediction_type);
  const threshold = Number(safeNumber(params.predRow.threshold, 0).toFixed(1));

  try {
    await updatePredictionSafe(predId, {
      validated: true,
      outcome: params.outcome,
      current_value: params.currentValue,
      validated_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      validation_type: params.validation_type,
    });
    return predId;
  } catch (e: any) {
    // If it's not a duplicate key issue, rethrow
    if (!isDuplicateKeyError(e)) throw e;

    // Duplicate means another row already exists for this "validated=true" key (depending on your index)
    const existingValidatedId = await findExistingPredictionId({
      match_id: matchId,
      prediction_type: pType,
      threshold,
      validated: true,
    });

    if (existingValidatedId) {
      // update the validated row with the newest final state
      await updatePredictionSafe(String(existingValidatedId), {
        validated: true,
        outcome: params.outcome,
        current_value: params.currentValue,
        validated_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        validation_type: params.validation_type,
      });

      // delete the current conflicting row (validated=false or trying to validate)
      const { error: delErr } = await supabase.from("live_predictions").delete().eq("id", predId);
      if (delErr) console.error("⚠️ delete duplicate pending pred failed:", delErr);

      return String(existingValidatedId);
    }

    // If we couldn't find an existing validated row, fallback: keep current row as-is (avoid crash)
    console.error("⚠️ duplicate on validate but no existing validated row found. predId=", predId);
    return predId;
  }
}

// =======================================================
// ✅ IN-PLAY VALIDATION
// =======================================================
function computeCurrentValueFromStats(predType: string, stats: any) {
  if (!stats) return null;

  if (predType === "total_shots") {
    return safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
  }
  if (predType === "total_corners") {
    return safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
  }
  if (predType === "total_fouls") {
    return safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
  }
  return null;
}

async function validatePredictionsInPlay(liveMatchesNormalized: any[]) {
  const liveMap = new Map<string, any>();
  for (const m of liveMatchesNormalized || []) liveMap.set(String(m.id), m);

  const { data: pending, error } = await supabase
    .from("live_predictions")
    .select("id, match_id, match_name, prediction_type, threshold, validated")
    .eq("validated", false);

  if (error) throw error;
  if (!pending?.length) return { instant_validated: 0, updated_running: 0, skipped: 0 };

  let instantValidated = 0;
  let updatedRunning = 0;
  let skipped = 0;

  for (const pred of pending) {
    const match = liveMap.get(String(pred.match_id));
    if (!match) { skipped++; continue; } // pas/plus live

    const stats = match?.live_stats || null;
    const currentValue = computeCurrentValueFromStats(pred.prediction_type, stats);
    if (currentValue == null) { skipped++; continue; }

    // update running : current_value uniquement
    await updatePredictionSafe(String(pred.id), {
      current_value: currentValue,
      updated_at: new Date().toISOString(),
    });
    updatedRunning++;

    // success instant
    const threshold = safeNumber(pred.threshold, 0);
    const reached = currentValue > threshold;

    if (reached) {
      const keptId = await validatePredictionWithMerge({
        predRow: pred,
        outcome: "success",
        currentValue,
        validation_type: "instant",
      });

      await insertNotification({
        user_id: "all",
        type: "prediction_reached",
        title: "Pronostic atteint en LIVE",
        message:
`${match.home_team} vs ${match.away_team}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Actuel: ${currentValue}
Minute: ${match.current_minute ?? "-"}'`,
        priority: "normal",
        read: false,
        related_prediction_id: keptId,
      });

      // ✅ Envoi Telegram résultat : coupon validé en live.
      await sendTelegramValidationResult(match, pred, "success", currentValue, "instant", keptId);

      instantValidated++;
    }
  }

  return { instant_validated: instantValidated, updated_running: updatedRunning, skipped };
}

// =======================================================
// ✅ LIVE (DB) : /matches + /opportunities depuis Supabase
// =======================================================
function predictionMeta(type: string, threshold: number) {
  if (type === "total_corners") return { badge: "Corners", color: "yellow", title: `Over ${threshold} corners` };
  if (type === "total_shots") return { badge: "Tirs", color: "green", title: `Over ${threshold} tirs` };
  if (type === "total_fouls") return { badge: "Fautes", color: "orange", title: `Over ${threshold} fautes` };
  return { badge: "Signal", color: "gold", title: `Over ${threshold}` };
}

function predictionRowToUi(p: any) {
  const threshold = safeNumber(p.threshold, 0);
  const meta = predictionMeta(p.prediction_type, threshold);

  const signalValue = p.projected_value ?? null;
  const reliability = Math.round((Number(p.probability) || 0) * 100);

  return {
    id: p.id,
    type: p.prediction_type,
    title: meta.title,
    badge: meta.badge,
    color: meta.color,
    probability: Number(p.probability) || 0,
    message: p.message,

    threshold,
    pronostic: threshold,

    current: p.current_value ?? null,

    signal_value: signalValue,
    projected: signalValue, // compat UI

    reliability,
    reasons: [],

    confidence: p.confidence ?? null,
    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,

    created_at: p.created_at ?? null,
  };
}

async function getLiveMatchesFromDb(maxAgeSeconds = 240) {
  const since = new Date(Date.now() - maxAgeSeconds * 1000).toISOString();

  const { data: rows, error } = await supabase
    .from("matches_live")
    .select("id, raw_data, updated_at")
    .gte("updated_at", since)
    .order("updated_at", { ascending: false });

  if (error) throw error;

  const matchesRows = rows || [];
  const ids = matchesRows.map((r: any) => String(r.id));
  if (!ids.length) return [];

  const { data: preds, error: predErr } = await supabase
    .from("live_predictions")
    .select("id, match_id, prediction_type, probability, message, threshold, current_value, projected_value, confidence, validated, outcome, validation_type, created_at")
    .in("match_id", ids)
    .eq("validated", false)
    .order("created_at", { ascending: false });

  if (predErr) throw predErr;

  const byMatch = new Map<string, any[]>();
  for (const p of preds || []) {
    const k = String(p.match_id);
    if (!byMatch.has(k)) byMatch.set(k, []);
    byMatch.get(k)!.push(p);
  }

  const out = matchesRows.map((r: any) => {
    const base = r.raw_data || {};
    const pRows = byMatch.get(String(r.id)) || [];
    const uiPreds = pRows.map(predictionRowToUi);

    uiPreds.sort((a: any, b: any) => safeNumber(b.probability) - safeNumber(a.probability));

    return {
      ...base,
      predictions: uiPreds,
      all_predictions: uiPreds,
      freshness_seconds: computeFreshness(r.updated_at),
      updated_at: r.updated_at,
    };
  });

  out.sort((a: any, b: any) => safeNumber(b.value_score) - safeNumber(a.value_score));
  return out;
}

async function getLiveOpportunitiesFromDb() {
  const matches = await getLiveMatchesFromDb();
  const withPred = matches.filter((m: any) => Array.isArray(m.predictions) && m.predictions.length > 0);

  withPred.sort((a: any, b: any) => {
    const ap = safeNumber(a?.predictions?.[0]?.probability, 0);
    const bp = safeNumber(b?.predictions?.[0]?.probability, 0);
    if (bp !== ap) return bp - ap;
    return safeNumber(b.value_score) - safeNumber(a.value_score);
  });

  return withPred.slice(0, 12);
}

// =======================================================
// ROUTES CORE
// =======================================================
async function refreshLiveDataInDb() {
  const liveData = await fetchBSD("/live/");
  const rawMatches = liveData.results || [];
  const nowIso = new Date().toISOString();

  const normalizedMatches = rawMatches.map((m: any) => normalizeMatch(m, nowIso));

  // cache matches
  await cacheLiveMatches(rawMatches);

  // save predictions (tolérant)
  let createdPreds = 0;
  let existingPreds = 0;
  let failedPreds = 0;

  for (const m of normalizedMatches) {
    for (const pred of m.predictions || []) {
      try {
        const res = await savePrediction(m, pred);
        if (res.created) createdPreds++;
        else existingPreds++;
      } catch (e) {
        failedPreds++;
        console.error("savePrediction failed (ignored):", e);
      }
    }
  }

  // validate in play
  const instant = await validatePredictionsInPlay(normalizedMatches);

  return {
    matches: normalizedMatches,
    meta: {
      matches_live: rawMatches.length,
      predictions_created: createdPreds,
      predictions_existing: existingPreds,
      predictions_failed: failedPreds,
      ...instant,
    },
  };
}

async function validatePredictionsNow() {
  const { data: pending, error: pendingError } = await supabase
    .from("live_predictions")
    .select("id, match_id, match_name, prediction_type, threshold, league_name, validated, created_at")
    .eq("validated", false)
    .order("created_at", { ascending: false });

  if (pendingError) throw pendingError;
  if (!pending?.length) return { validated: 0, skipped: 0, failed: 0 };

  let validated = 0;
  let skipped = 0;
  let failed = 0;

  for (const pred of pending) {
    let ev: any = null;
    try {
      ev = await fetchBSD(`/events/${pred.match_id}/`);
    } catch {
      skipped++;
      continue;
    }

    if (!isFinishedEvent(ev)) continue;

    let stats = ev.live_stats || null;
    if (!stats) stats = await getCachedLiveStats(String(pred.match_id));
    if (!stats) { skipped++; continue; }

    const threshold = safeNumber(pred.threshold, 0);
    let finalValue = 0;
    let ok = false;

    if (pred.prediction_type === "total_shots") {
      finalValue = safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_corners") {
      finalValue = safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_fouls") {
      finalValue = safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
      ok = finalValue > threshold;
    } else {
      skipped++;
      continue;
    }

    try {
      const keptId = await validatePredictionWithMerge({
        predRow: pred,
        outcome: ok ? "success" : "failure",
        currentValue: finalValue,
        validation_type: "final",
      });

      await insertNotification({
        user_id: "all",
        type: "prediction_validated",
        title: "Prédiction validée",
        message:
`${pred.match_name}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Valeur finale: ${finalValue}
Résultat: ${ok ? "✅ réussi" : "❌ échoué"}`,
        priority: "normal",
        read: false,
        related_prediction_id: keptId,
      });

      // ✅ Envoi Telegram résultat final : coupon validé ou perdu.
      const telegramMatch = await getTelegramMatchFromCache(pred, ev);
      await sendTelegramValidationResult(
        telegramMatch,
        pred,
        ok ? "success" : "failure",
        finalValue,
        "final",
        keptId,
      );

      validated++;
    } catch (e) {
      failed++;
      console.error("validatePredictionsNow failed (ignored):", e);
    }
  }

  return { validated, skipped, failed };
}

// =======================================================
// ✅ Helpers UI history/detail (logos via matches_live.raw_data)
// =======================================================
async function getRawMatchMap(matchIds: string[]) {
  const ids = [...new Set((matchIds || []).map(String).filter(Boolean))];
  const matchMap = new Map<string, any>();
  if (!ids.length) return matchMap;

  const { data: mrows, error: mErr } = await supabase
    .from("matches_live")
    .select("id, raw_data")
    .in("id", ids);

  if (mErr) {
    console.error("matches_live fetch failed:", mErr);
    return matchMap;
  }

  for (const r of mrows || []) matchMap.set(String(r.id), r.raw_data || {});
  return matchMap;
}

function enrichPredictionForUi(p: any, raw: any) {
  return {
    id: p.id,
    match_id: String(p.match_id),

    home_team: p.home_team ?? raw.home_team ?? null,
    away_team: p.away_team ?? raw.away_team ?? null,
    home_score: p.home_score ?? raw.home_score ?? 0,
    away_score: p.away_score ?? raw.away_score ?? 0,
    current_minute: p.minute ?? null, // minute du signal (fixe historique)

    league: raw.league ?? { name: p.league_name ?? null },
    league_id: raw.league_id ?? null,
    home_team_id: raw.home_team_id ?? null,
    away_team_id: raw.away_team_id ?? null,
    home_team_obj: raw.home_team_obj ?? null,
    away_team_obj: raw.away_team_obj ?? null,

    match: p.match_name,
    type: p.prediction_type,
    probability: Number(p.probability),

    message: p.message,

    pronostic: p.threshold,
    threshold: p.threshold,

    signal_value: p.projected_value,
    projected: p.projected_value,
    current: p.current_value,

    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,
    validated_at: p.validated_at ?? null,

    timestamp: new Date(p.created_at).getTime(),
  };
}

// =======================================================
// SERVER
// =======================================================
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const path = extractPath(url, "live");

  try {
    // ===================================================
    // IMG PROXY
    // ===================================================
    const imgMatch = path.match(/^\/img\/(team|league|player)\/(\d+)\/?$/);
    if (imgMatch && req.method === "GET") {
      const type = imgMatch[1];
      const apiId = imgMatch[2];

      const upstream = await fetch(`${BSD_IMG_BASE}/${type}/${apiId}/`, {
        headers: { Authorization: `Token ${BSD_API_TOKEN}` },
      });

      if (!upstream.ok) {
        const t = await upstream.text().catch(() => "");
        return new Response(t || "Image not found", {
          status: upstream.status,
          headers: { ...corsHeaders, "Content-Type": upstream.headers.get("content-type") || "text/plain" },
        });
      }

      return new Response(upstream.body, {
        status: 200,
        headers: {
          ...corsHeaders,
          "Content-Type": upstream.headers.get("content-type") || "image/png",
          "Cache-Control": "public, max-age=31536000",
        },
      });
    }

    // ===================================================
    // DEBUG finished events
    // ===================================================
    if (path === "/debug/events-finished" && req.method === "GET") {
      requireDebugAuth(url);

      const date = url.searchParams.get("date") || "2026-03-29";
      const tz = url.searchParams.get("tz") || DEFAULT_TZ;
      const raw = url.searchParams.get("raw") === "1";

      const data = await fetchBSD("/events/", {
        status: "finished",
        date_from: date,
        date_to: date,
        tz,
      });

      if (raw) return json(data);

      const compact = (data?.results || []).map((m: any) => ({
        id: m.id,
        event_date: m.event_date,
        status: m.status,
        period: m.period ?? null,
        home_team: m.home_team,
        away_team: m.away_team,
        score: `${m.home_score ?? "-"}-${m.away_score ?? "-"}`,
        has_live_stats: !!m.live_stats,
      }));

      return json({
        query: { status: "finished", date_from: date, date_to: date, tz },
        count: data?.count ?? compact.length,
        results: compact,
      });
    }

    // ===================================================
    // CRON: refresh
    // ===================================================
    if (path === "/refresh" && req.method === "POST") {
      requireCronAuth(req, url);

      try {
        const { matches, meta } = await refreshLiveDataInDb();
        await setCronRun("live_refresh", true, meta);
        return json({ success: true, count: matches.length, meta });
      } catch (e: any) {
        await setCronRun("live_refresh", false, { error: e?.message || String(e) });
        throw e;
      }
    }

    // ===================================================
    // CRON: validate (final)
    // ===================================================
    if (path === "/validate" && req.method === "POST") {
      requireCronAuth(req, url);

      try {
        const result = await validatePredictionsNow();
        await setCronRun("live_validate", true, result);
        return json({ success: true, ...result });
      } catch (e: any) {
        await setCronRun("live_validate", false, { error: e?.message || String(e) });
        throw e;
      }
    }

    // ===================================================
    // UI: matches (DB)
    // ===================================================
    if (path === "/matches" && req.method === "GET") {
      const matches = await getLiveMatchesFromDb();
      return json({ matches });
    }

    // ===================================================
    // UI: opportunities (DB)
    // ===================================================
    if (path === "/opportunities" && req.method === "GET") {
      const opportunities = await getLiveOpportunitiesFromDb();
      return json({ opportunities });
    }

    // ===================================================
    // UI: today (BSD direct)
    // ===================================================
    if (path === "/today" && req.method === "GET") {
      const today = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);

      const liveData = await fetchBSD("/live/");
      const liveMatches = liveData.results || [];

      const eventsData = await fetchBSD("/events/", { date_from: today, date_to: today });
      const allEvents = eventsData.results || [];

      const scheduled: any[] = [];
      const finished: any[] = [];

      allEvents.forEach((ev: any) => {
        if (isFinishedEvent(ev)) finished.push(ev);
        else {
          const isLive = liveMatches.some((l: any) => String(l.id) === String(ev.id));
          if (!isLive) scheduled.push(ev);
        }
      });

      return json({
        data: {
          live: { count: liveMatches.length, matches: liveMatches },
          scheduled: { count: scheduled.length, matches: scheduled },
          finished: { count: finished.length, matches: finished.slice(0, 10) },
        },
      });
    }

    // ===================================================
    // UI: history (48h) + logos
    // ===================================================
    if (path === "/predictions/history" && req.method === "GET") {
      const since = new Date(Date.now() - 48 * 3600 * 1000).toISOString();

      const { data, error } = await supabase
        .from("live_predictions")
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at")
        .gte("created_at", since)
        .order("created_at", { ascending: false });

      if (error) throw error;

      const preds = data || [];
      const rawMap = await getRawMatchMap(preds.map((p: any) => String(p.match_id)));

      return json({
        history: preds.map((p: any) =>
          enrichPredictionForUi(p, rawMap.get(String(p.match_id)) || {})
        ),
      });
    }

    // ===================================================
    // UI: prediction detail by id (pour clic notif)
    // ===================================================
    if (path === "/predictions/by-id" && req.method === "GET") {
      const id = url.searchParams.get("id") || "";
      if (!id) return json({ error: "id required" }, 400);

      const { data: p, error } = await supabase
        .from("live_predictions")
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at")
        .eq("id", id)
        .maybeSingle();

      if (error) throw error;
      if (!p) return json({ error: "not found" }, 404);

      const { data: mrow, error: mErr } = await supabase
        .from("matches_live")
        .select("raw_data")
        .eq("id", String(p.match_id))
        .maybeSingle();

      if (mErr) console.error("matches_live by-id failed:", mErr);

      return json({ prediction: enrichPredictionForUi(p, mrow?.raw_data || {}) });
    }

    // ===================================================
    // UI: notifications
    // ===================================================
    if (path === "/notifications" && req.method === "GET") {
      const userId = url.searchParams.get("user_id") || "all";
      const ids = userId === "all" ? ["all"] : ["all", userId];

      const { data, error } = await supabase
        .from("notifications")
        .select("*")
        .in("user_id", ids)
        .order("created_at", { ascending: false })
        .limit(50);

      if (error) throw error;

      return json({
        notifications: (data || []).map((n: any) => ({
          ...n,
          timestamp: new Date(n.created_at).getTime(),
        })),
      });
    }

    if (path === "/notifications/mark-read" && req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      const ids = Array.isArray(body.notification_ids) ? body.notification_ids : [];

      if (!ids.length) return json({ success: true, updated: 0 });

      const { error } = await supabase
        .from("notifications")
        .update({ read: true })
        .in("id", ids);

      if (error) throw error;

      return json({ success: true, updated: ids.length });
    }

    return json({ error: "Not found" }, 404);
  } catch (e: any) {
    console.error("live.ts error:", e);
    return json({ error: e?.message || "Erreur serveur" }, 500);
  }
});