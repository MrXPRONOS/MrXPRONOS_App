// supabase/functions/live-scrape-test/index.ts
// =======================================================
// ✅ Système scraping ESPN avec STOCKAGE clone + VALIDATION + NOTIFICATIONS
// Objectifs (suite à tes retours):
// 1) Corriger les faux "LIVE depuis hier" -> purge/filtre stale
// 2) Corners en échelle (8.5 -> 10.5 -> 12.5) et ne JAMAIS proposer un seuil déjà atteint
// 3) ❌ Plus de pronos TIRS (total_shots supprimé)
// 4) Après validation (success), proposer automatiquement le prochain palier corners si possible
// 5) Endpoints compatibles avec live.html (matches/opportunities/today/history/notifications)
//
// ⚠️ Supabase:
// - Ajoute dans supabase/config.toml :
//     [functions.live-scrape-test]
//     verify_jwt = false
// - Variables env requises:
//     SUPABASE_URL
//     SUPABASE_SERVICE_ROLE_KEY
//     CRON_SECRET   (optionnel mais recommandé)
//     TELEGRAM_SCRAPE_CHAT_ID       (nouveau canal Telegram scraping)
//     TELEGRAM_SCRAPE_BOT_TOKEN     (optionnel si tu réutilises TELEGRAM_BOT_TOKEN)
//     TELEGRAM_BOT_TOKEN            (fallback bot si TELEGRAM_SCRAPE_BOT_TOKEN absent)
//
// Tables (clone):
//   matches_live_scrape
//   live_predictions_scrape
//   notifications_scrape
//   cron_runs_scrape
// =======================================================

import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { initWasm, Resvg } from "https://esm.sh/@resvg/resvg-wasm@2.6.2?target=deno";
import satori from "npm:satori@0.12.0";
import { html } from "npm:satori-html@0.3.2";

const ESPN_SCOREBOARD_URL =
  "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard";

const FUNCTION_NAME = "live-scrape-test";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const CRON_SECRET = Deno.env.get("CRON_SECRET") || "";

const SITE_URL = Deno.env.get("SITE_URL") || "https://mrxpronos.github.io/MrXPRONOS_App/";

// Telegram du clone scraping — canal différent de l'ancien système.
// Recommandé : utiliser le même bot, mais un autre CHAT_ID.
const TELEGRAM_SCRAPE_BOT_TOKEN =
  Deno.env.get("TELEGRAM_SCRAPE_BOT_TOKEN") ||
  Deno.env.get("TELEGRAM_BOT_TOKEN") ||
  "";
const TELEGRAM_SCRAPE_CHAT_ID =
  Deno.env.get("TELEGRAM_SCRAPE_CHAT_ID") ||
  Deno.env.get("TELEGRAM_LIVE_SCRAPE_CHAT_ID") ||
  "";
const TELEGRAM_SCRAPE_BUTTON_URL =
  Deno.env.get("TELEGRAM_SCRAPE_BUTTON_URL") ||
  `${SITE_URL.replace(/\/$/, "")}/live-scrape-test.html`;

if (!SUPABASE_URL) console.error("SUPABASE_URL non défini");
if (!SUPABASE_SERVICE_ROLE_KEY) console.error("SUPABASE_SERVICE_ROLE_KEY non défini");
if (!TELEGRAM_SCRAPE_CHAT_ID) console.warn("TELEGRAM_SCRAPE_CHAT_ID non défini: envoi Telegram scraping désactivé");

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// Tables CLONE
const T_MATCHES = "matches_live_scrape";
const T_PREDS = "live_predictions_scrape";
const T_NOTIFS = "notifications_scrape";
const T_CRON = "cron_runs_scrape";

// Stale live cleanup: un match live non mis à jour depuis X minutes est considéré mort
const STALE_LIVE_SECONDS = 20 * 60; // 20 minutes
const staleCutoffIso = () =>
  new Date(Date.now() - STALE_LIVE_SECONDS * 1000).toISOString();

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Authorization, x-cron-secret",
};

function json(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, ...headers, "Content-Type": "application/json" },
  });
}

function safeNumber(value: unknown, fallback = 0): number {
  const n = Number(String(value ?? "").replace("%", "").trim());
  return Number.isFinite(n) ? n : fallback;
}

function nowIso() {
  return new Date().toISOString();
}

function todayYYYYMMDD(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}

function extractPath(url: URL, fnName = FUNCTION_NAME) {
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
    auth.toLowerCase().startsWith("bearer ") &&
    auth.slice(7).trim() === CRON_SECRET;
  const ok = bearerOk || x === CRON_SECRET || q === CRON_SECRET;
  if (!ok) throw new Error("Unauthorized (CRON_SECRET)");
}

function computeFreshness(updatedAt?: string | number | null) {
  if (!updatedAt) return null;
  const ts = typeof updatedAt === "number" ? updatedAt : new Date(updatedAt).getTime();
  if (!Number.isFinite(ts)) return null;
  return Math.max(0, Math.floor((Date.now() - ts) / 1000));
}

function isDuplicateKeyError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return code === "23505" || msg.includes("duplicate key value violates unique constraint");
}

function isUndefinedColumnError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "").toLowerCase();
  return code === "42703" || msg.includes("does not exist");
}

async function setCronRun(name: string, ok: boolean, meta: any = {}) {
  const { error } = await supabase.from(T_CRON).upsert({
    name,
    ok,
    meta: meta || {},
    last_run: nowIso(),
  }, { onConflict: "name" });
  if (error) console.error("cron_runs_scrape upsert failed:", error);
}

function formatLivePredictionType(type: string) {
  if (type === "total_corners") return "Corners";
  if (type === "total_fouls") return "Fautes";
  return "Signal LIVE";
}

function getTotalStats(match: any) {
  const stats = match?.live_stats || match?.raw_data?.live_stats || {};
  const corners = safeNumber(stats?.totals?.corners, 0) ||
    safeNumber(stats?.home?.corner_kicks, 0) + safeNumber(stats?.away?.corner_kicks, 0);
  const fouls = safeNumber(stats?.totals?.fouls, 0) ||
    safeNumber(stats?.home?.fouls, 0) + safeNumber(stats?.away?.fouls, 0);
  return { corners, fouls, shots: 0 };
}

// =======================================================
// TELEGRAM LIVE SCRAPE — canal séparé
// =======================================================
function escapeXml(text: unknown) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function clampText(text: unknown, max = 42) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

function formatThreshold(value: unknown) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
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

async function imageUrlToDataUri(url?: string | null): Promise<string> {
  if (!url) return "";

  try {
    const res = await fetch(String(url), {
      headers: {
        "User-Agent": "Mozilla/5.0 MrXPRONOS-Scrape-Telegram/1.0",
        // Important : on évite webp/avif/svg, qui peuvent casser Satori/resvg.
        "Accept": "image/png,image/jpeg,*/*;q=0.5",
      },
    });

    if (!res.ok) {
      console.warn("Logo impossible à charger:", res.status, url);
      return "";
    }

    const bytes = new Uint8Array(await res.arrayBuffer());

    // Protection simple: on évite de mettre une image énorme dans le rendu Telegram.
    if (bytes.length > 800_000) {
      console.warn("Logo trop lourd, ignoré:", bytes.length, url);
      return "";
    }

    const mime = detectImageMime(bytes);

    if (!mime) {
      const contentType = res.headers.get("content-type") || "unknown";
      console.warn("Logo ignoré: format non supporté par le rendu Telegram", {
        url,
        contentType,
        bytes: bytes.length,
      });
      return "";
    }

    return `data:${mime};base64,${bytesToBase64(bytes)}`;
  } catch (e) {
    console.warn("Logo impossible à convertir en data URI:", url, e);
    return "";
  }
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

  // TrueType: 00010000
  // OpenType CFF: 4f54544f = OTTO
  // TrueType Collection: 74746366 = ttcf
  // Apple TrueType: 74727565 = true
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
      "User-Agent": "Mozilla/5.0 MrXPRONOS-Scrape-Telegram/1.0",
      "Accept": "font/ttf,application/octet-stream,*/*;q=0.8",
    },
  });

  if (!res.ok) {
    throw new Error(`Impossible de télécharger la police fallback ${filename}: HTTP ${res.status}`);
  }

  const bytes = new Uint8Array(await res.arrayBuffer());

  if (!isValidFontFile(bytes)) {
    throw new Error(
      `Police fallback invalide ${filename}: bytes=${bytes.byteLength}, header=${fontHeader(bytes)}. Le fichier téléchargé n'est probablement pas un TTF.`,
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

  console.log("Fonts Telegram chargées:", {
    regular: regular.byteLength,
    bold: bold.byteLength,
    extraBold: extraBold.byteLength,
    regularHeader: fontHeader(regular),
    boldHeader: fontHeader(bold),
    extraBoldHeader: fontHeader(extraBold),
  });

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

function predictionTypeLabel(type: string) {
  if (type === "total_corners") return "Corners";
  if (type === "total_fouls") return "Fautes";
  return "Signal LIVE";
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitText(text: unknown, max = 32): string {
  const s = String(text ?? "").trim();
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


// PATCH SATORI DISPLAY: tous les <div> du template ont display:flex explicite.

async function buildTelegramCouponPng(match: any, pred: any): Promise<Uint8Array> {
  await ensureResvgReady();
  const fonts = await loadFontData();

  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;

  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const typeLabel = predictionTypeLabel(rawType);
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

  const homeLogoData = await imageUrlToDataUri(match?.home_logo || match?.raw_data?.home_logo);
  const awayLogoData = await imageUrlToDataUri(match?.away_logo || match?.raw_data?.away_logo);
  const leagueLogoData = await imageUrlToDataUri(match?.league_logo || match?.raw_data?.league_logo);

  const homeName = fitText(match?.home_team ?? "Équipe A", 22);
  const awayName = fitText(match?.away_team ?? "Équipe B", 22);
  const leagueName = fitText(
    match?.league?.name ?? match?.league_name ?? match?.competition ?? "Football",
    30,
  );

  const couponText =
    rawType === "total_corners"
      ? `Total plus de ${threshold} corners`
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

  const label =
    type === "total_corners"
      ? "corners"
      : type === "total_fouls"
      ? "fautes"
      : "";

  return `🔥 NOUVEAU COUPON LIVE

⚽️ Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}

async function sendTelegramPhoto(pngBytes: Uint8Array, caption: string, buttonUrl?: string) {
  if (!TELEGRAM_SCRAPE_BOT_TOKEN || !TELEGRAM_SCRAPE_CHAT_ID) {
    console.warn("Telegram scraping non configuré: TELEGRAM_SCRAPE_BOT_TOKEN/TELEGRAM_BOT_TOKEN ou TELEGRAM_SCRAPE_CHAT_ID manquant");
    return false;
  }

  const form = new FormData();
  form.append("chat_id", TELEGRAM_SCRAPE_CHAT_ID);
  if (caption && caption.trim()) form.append("caption", caption);
  if (buttonUrl) {
    form.append("reply_markup", JSON.stringify({
      inline_keyboard: [[{ text: "Voir plus d’opportunités 🔥", url: buttonUrl }]],
    }));
  }
  form.append("photo", new Blob([pngBytes], { type: "image/png" }), "coupon-live-scrape.png");

  try {
    const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_SCRAPE_BOT_TOKEN}/sendPhoto`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error("Telegram scrape sendPhoto failed:", res.status, body);
      return false;
    }
    return true;
  } catch (e) {
    console.error("Telegram scrape sendPhoto exception:", e);
    return false;
  }
}

async function sendTelegramMessage(text: string, buttonUrl?: string) {
  if (!TELEGRAM_SCRAPE_BOT_TOKEN || !TELEGRAM_SCRAPE_CHAT_ID) return false;
  const form = new FormData();
  form.append("chat_id", TELEGRAM_SCRAPE_CHAT_ID);
  form.append("text", text);
  if (buttonUrl) {
    form.append("reply_markup", JSON.stringify({
      inline_keyboard: [[{ text: "Voir plus d’opportunités 🔥", url: buttonUrl }]],
    }));
  }

  try {
    const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_SCRAPE_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error("Telegram scrape sendMessage failed:", res.status, body);
    }
    return res.ok;
  } catch (e) {
    console.error("Telegram scrape sendMessage exception:", e);
    return false;
  }
}

async function sendTelegramScrapeCoupon(match: any, pred: any, predictionId?: string | number | null) {
  const buttonUrl = TELEGRAM_SCRAPE_BUTTON_URL;
  const normalizedPred = {
    ...pred,
    type: pred.type ?? pred.prediction_type,
  };

  try {
    const pngBytes = await buildTelegramCouponPng(match, normalizedPred);
    return await sendTelegramPhoto(
      pngBytes,
      buildTelegramText(match, normalizedPred),
      buttonUrl,
    );
  } catch (e) {
    console.error("Génération image Telegram scraping impossible, fallback texte:", e);
    return await sendTelegramMessage(buildTelegramText(match, normalizedPred), buttonUrl);
  }
}

// =======================================================
// Cache mémoire (évite de spam ESPN)
// =======================================================
let memCache: { at: number; date: string; data: any } | null = null;
const CACHE_TTL_MS = 15_000;

async function fetchEspnScoreboard(dateYYYYMMDD: string, force = false) {
  const now = Date.now();
  if (!force && memCache && memCache.date === dateYYYYMMDD &&
    now - memCache.at < CACHE_TTL_MS) {
    return memCache.data;
  }

  const url = new URL(ESPN_SCOREBOARD_URL);
  url.searchParams.set("dates", dateYYYYMMDD);
  url.searchParams.set("limit", "500");

  const res = await fetch(url.toString(), {
    headers: {
      "User-Agent": "Mozilla/5.0 MrXPRONOS-LiveScrape/1.0",
      "Accept": "application/json,text/plain,*/*",
    },
  });
  if (!res.ok) throw new Error(`ESPN HTTP ${res.status}`);
  const data = await res.json();
  memCache = { at: now, date: dateYYYYMMDD, data };
  return data;
}

function extractMinute(status: any): number {
  const displayClock = status?.displayClock || "";
  if (displayClock) {
    const found = String(displayClock).match(/(\d+)/);
    if (found) return safeNumber(found[1], 0);
  }
  const clock = status?.clock; // secondes
  if (clock) return Math.floor(safeNumber(clock, 0) / 60);
  return 0;
}

function getStat(competitor: any, statName: string, fallback = 0): number {
  const stats = competitor?.statistics || [];
  for (const s of stats) {
    if (s?.name === statName) return safeNumber(s?.displayValue ?? s?.value, fallback);
  }
  return fallback;
}

function countCards(details: any[], teamId: string | number | undefined) {
  let yellow = 0;
  let red = 0;
  for (const d of details || []) {
    const tid = String(d?.team?.id || "");
    if (!teamId || tid !== String(teamId)) continue;
    if (d?.yellowCard === true) yellow += 1;
    if (d?.redCard === true) red += 1;
  }
  return { yellow, red };
}

function computeHeatLevelFromStats(totalCorners: number, totalFouls: number): string {
  // Pas de shots (supprimé)
  if (totalCorners >= 9 || totalFouls >= 26) return "hot";
  if (totalCorners >= 6 || totalFouls >= 18) return "warming";
  return "calm";
}

// =======================================================
// Normalisation ESPN -> match stocké
// =======================================================
function normalizeEspnEvent(event: any) {
  const competition = event?.competitions?.[0];
  if (!competition) return null;

  const status = competition?.status || {};
  const statusType = status?.type || {};
  const state = statusType?.state || ""; // "in", "pre", "post"

  const is_live = state === "in";
  const is_finished = Boolean(statusType?.completed);

  const competitors = competition?.competitors || [];
  const home = competitors.find((c: any) => c?.homeAway === "home");
  const away = competitors.find((c: any) => c?.homeAway === "away");
  if (!home || !away) return null;

  const homeTeam = home?.team || {};
  const awayTeam = away?.team || {};
  const details = competition?.details || [];
  const homeCards = countCards(details, homeTeam?.id);
  const awayCards = countCards(details, awayTeam?.id);

  const leagueObj = event?.league || {};
  const seasonObj = event?.season || {};
  const leagueName = leagueObj?.name || leagueObj?.abbreviation || seasonObj?.slug ||
    "Football";
  const leagueId = String(leagueObj?.id || leagueObj?.abbreviation || leagueName);

  const minute = extractMinute(status);

  const homeCorners = getStat(home, "wonCorners");
  const awayCorners = getStat(away, "wonCorners");
  const totalCorners = homeCorners + awayCorners;

  const homeFouls = getStat(home, "foulsCommitted");
  const awayFouls = getStat(away, "foulsCommitted");
  const totalFouls = homeFouls + awayFouls;

  const heat = computeHeatLevelFromStats(totalCorners, totalFouls);

  const eventDate = event?.date ? new Date(event.date).toISOString() : null;

  // logos ESPN (direct)
  const homeLogo = homeTeam?.logo || homeTeam?.logos?.[0]?.href || null;
  const awayLogo = awayTeam?.logo || awayTeam?.logos?.[0]?.href || null;
  const leagueLogo = leagueObj?.logos?.[0]?.href || leagueObj?.logo || null;

  const matchId = String(event?.id || crypto.randomUUID());
  const homeTeamId = String(homeTeam?.id || "");
  const awayTeamId = String(awayTeam?.id || "");

  const raw = {
    source: "espn",
    state,
    status_detail: statusType?.detail || statusType?.description || "",
    display_clock: status?.displayClock || "",
    home_team_obj: { api_id: homeTeamId, id: homeTeamId },
    away_team_obj: { api_id: awayTeamId, id: awayTeamId },
    league: { name: leagueName, api_id: leagueId, id: leagueId },
    live_stats: {
      home: {
        corner_kicks: homeCorners,
        fouls: homeFouls,
        yellow_cards: homeCards.yellow,
        red_cards: homeCards.red,
      },
      away: {
        corner_kicks: awayCorners,
        fouls: awayFouls,
        yellow_cards: awayCards.yellow,
        red_cards: awayCards.red,
      },
      totals: {
        corners: totalCorners,
        fouls: totalFouls,
      },
    },
    heat_level: heat,
  };

  return {
    id: matchId,
    home_team: homeTeam?.displayName || homeTeam?.name || "Home",
    away_team: awayTeam?.displayName || awayTeam?.name || "Away",
    home_score: safeNumber(home?.score, 0),
    away_score: safeNumber(away?.score, 0),
    current_minute: minute,
    league_name: leagueName,
    status: statusType?.name || state || "",
    is_live,
    is_finished,
    event_date: eventDate,
    home_team_id: homeTeamId || null,
    away_team_id: awayTeamId || null,
    league_id: leagueId || null,
    home_logo: homeLogo,
    away_logo: awayLogo,
    league_logo: leagueLogo,
    raw_data: raw,
    updated_at: nowIso(),
  };
}

// =======================================================
// PREDICTIONS (Corners/Fouls) — pas de Shots
// =======================================================

function targetFromThreshold(threshold: number): number {
  // Over 8.5 => target 9
  return Math.floor(threshold) + 1;
}

type CornerRung = {
  threshold: number;
  minMinute: number;
  maxMinute: number;
  minCorners: number;
};

const CORNERS_LADDER: CornerRung[] = [
  { threshold: 8.5, minMinute: 45, maxMinute: 70, minCorners: 7 },
  { threshold: 10.5, minMinute: 55, maxMinute: 82, minCorners: 9 },
  { threshold: 12.5, minMinute: 60, maxMinute: 88, minCorners: 11 },
];

function chooseCornersRung(minute: number, totalCorners: number): CornerRung | null {
  for (const rung of CORNERS_LADDER) {
    const target = targetFromThreshold(rung.threshold);
    const inWindow = minute >= rung.minMinute && minute <= rung.maxMinute;
    const hasPace = totalCorners >= rung.minCorners;
    const notAlreadyWon = totalCorners < target;
    if (inWindow && hasPace && notAlreadyWon) return rung;
  }
  return null;
}

function cornersProbability(minute: number, totalCorners: number, threshold: number) {
  // petit heuristic: plus on est proche du target, plus proba haute
  const target = targetFromThreshold(threshold);
  const gap = Math.max(1, target - totalCorners); // 1..n
  const timeFactor = Math.min(1, Math.max(0, (minute - 40) / 45));
  const base = 0.55 + timeFactor * 0.15;
  const closeness = Math.min(0.25, 0.25 / gap);
  return Math.max(0.55, Math.min(0.92, base + closeness));
}

function foulsCandidate(minute: number, totalFouls: number) {
  // Simple et stable (à ajuster plus tard si tu veux)
  const threshold = 23.5; // target 24
  const target = targetFromThreshold(threshold);
  if (minute < 50 || minute > 85) return null;
  if (totalFouls < 18) return null;
  if (totalFouls >= target) return null; // déjà gagné
  const prob = Math.max(0.55, Math.min(0.9, 0.55 + (totalFouls - 18) * 0.02));
  return { threshold, probability: prob };
}

function predictionMeta(type: string, threshold: number) {
  if (type === "total_corners") return { badge: "Corners", color: "yellow", title: `Over ${threshold} corners` };
  if (type === "total_fouls") return { badge: "Fautes", color: "orange", title: `Over ${threshold} fautes` };
  return { badge: "Signal", color: "gold", title: `Over ${threshold}` };
}

function predictionUiFromRow(row: any, matchRow: any) {
  const type = row.prediction_type;
  const threshold = safeNumber(row.threshold, 0);
  const prob = Number(row.probability || 0);
  const reliability = safeNumber(row.reliability, Math.round(prob * 100));

  let badge = "Signal";
  let color = "gold";
  let title = `Over ${threshold}`;

  if (type === "total_corners") {
    badge = "Corners";
    color = "yellow";
    title = `Over ${threshold} corners`;
  }
  if (type === "total_fouls") {
    badge = "Fautes";
    color = "orange";
    title = `Over ${threshold} fautes`;
  }

  const minute = safeNumber(row.minute, 0);
  const current = safeNumber(row.current_value, 0);
  const signalValue = safeNumber(row.projected_value, current);

  const message = row.message ||
    (type === "total_corners"
      ? `${signalValue} corners à la ${minute}e minute. Prochain palier : ${threshold}.`
      : `${signalValue} fautes à la ${minute}e minute. Palier : ${threshold}.`);

  return {
    id: row.id,
    type,
    badge,
    color,
    title,
    threshold,
    pronostic: threshold,
    probability: prob,
    reliability,
    message,
    // live.html lit ces champs:
    signal_value: signalValue,
    current,
    current_value: current,
    projected: signalValue,
    created_at: row.created_at,
    reasons: ["Système scraping (clone)", `Minute: ${minute}'`],
  };
}

function matchUiFromRow(matchRow: any, predRows: any[]) {
  const raw = matchRow.raw_data || {};
  const league = raw?.league || { name: matchRow.league_name };
  const liveStats = raw?.live_stats || {
    home: {
      corner_kicks: 0,
      fouls: 0,
      yellow_cards: 0,
      red_cards: 0,
    },
    away: {
      corner_kicks: 0,
      fouls: 0,
      yellow_cards: 0,
      red_cards: 0,
    },
  };

  const predsUi = (predRows || []).map((p) => predictionUiFromRow(p, matchRow));
  const bestReliability = predsUi.reduce((m, p) => Math.max(m, p.reliability || 0), 0);

  return {
    id: matchRow.id,
    home_team: matchRow.home_team,
    away_team: matchRow.away_team,
    home_score: matchRow.home_score,
    away_score: matchRow.away_score,
    current_minute: matchRow.current_minute,
    status: matchRow.status,
    status_detail: raw?.status_detail || "",
    is_live: matchRow.is_live,
    is_finished: matchRow.is_finished,
    event_date: matchRow.event_date,

    league,
    league_id: matchRow.league_id,
    home_team_id: matchRow.home_team_id,
    away_team_id: matchRow.away_team_id,
    home_team_obj: raw?.home_team_obj,
    away_team_obj: raw?.away_team_obj,
    home_logo: matchRow.home_logo || raw?.home_logo || null,
    away_logo: matchRow.away_logo || raw?.away_logo || null,
    league_logo: matchRow.league_logo || raw?.league_logo || null,

    live_stats: liveStats,
    heat_level: raw?.heat_level || "calm",
    freshness_seconds: computeFreshness(matchRow.updated_at),

    predictions: predsUi,
    value_score: bestReliability,
    reliability_score: bestReliability,
    ai_score: bestReliability,
    data_quality_score: 70,
  };
}

async function insertNotification(payload: {
  user_id?: string;
  type: string;
  title: string;
  message: string;
  priority?: string;
  read?: boolean;
  related_prediction_id?: string | null;
}) {
  const baseRow: any = {
    user_id: payload.user_id ?? "all",
    type: payload.type,
    title: payload.title,
    message: payload.message,
    created_at: nowIso(),
  };

  const fullRow: any = {
    ...baseRow,
    priority: payload.priority ?? "normal",
    read: payload.read ?? false,
    related_prediction_id: payload.related_prediction_id ?? null,
  };

  const { error } = await supabase.from(T_NOTIFS).insert(fullRow);
  if (!error) return true;

  console.error("notifications_scrape insert failed (full):", error, "row=", fullRow);

  const { error: fallbackError } = await supabase.from(T_NOTIFS).insert(baseRow);
  if (!fallbackError) return true;

  console.error("notifications_scrape insert failed (minimal):", fallbackError, "row=", baseRow);
  return false;
}

async function createNotification(opts: {
  user_id?: string;
  type: string;
  title: string;
  message: string;
  related_prediction_id?: string | null;
  priority?: string;
}) {
  return insertNotification(opts);
}

// =======================================================
// STALE LIVE CLEANUP
// =======================================================
async function cleanupStaleLiveMatches() {
  const cutoff = staleCutoffIso();

  const { data: staleMatches, error } = await supabase
    .from(T_MATCHES)
    .select("id")
    .eq("is_live", true)
    .lt("updated_at", cutoff);

  if (error) throw error;

  if (!staleMatches || staleMatches.length === 0) {
    return { cutoff, cleared: 0 };
  }

  const ids = staleMatches.map((m: any) => m.id);
  const { error: updErr } = await supabase
    .from(T_MATCHES)
    .update({
      is_live: false,
      is_finished: true,
      status: "stale",
      updated_at: nowIso(),
    })
    .in("id", ids);

  if (updErr) throw updErr;
  return { cutoff, cleared: ids.length };
}

// =======================================================
// REFRESH (CRON)
// =======================================================
async function refreshFromEspn(dateYYYYMMDD: string) {
  // 0) purge stale
  const stale = await cleanupStaleLiveMatches();

  // 1) fetch ESPN
  const scoreboard = await fetchEspnScoreboard(dateYYYYMMDD, true);
  const events = scoreboard?.events || [];
  const normalized = events.map(normalizeEspnEvent).filter(Boolean);

  // 2) upsert matches
  if (normalized.length > 0) {
    const { error } = await supabase
      .from(T_MATCHES)
      .upsert(normalized, { onConflict: "id" });
    if (error) throw error;
  }

  // 3) live matches (fresh)
  const cutoff = staleCutoffIso();
  const { data: liveMatches, error: liveErr } = await supabase
    .from(T_MATCHES)
    .select("*")
    .eq("is_live", true)
    .gte("updated_at", cutoff);
  if (liveErr) throw liveErr;

  // 4) existing running preds (for update + avoid duplicates)
  const { data: runningPreds, error: predErr } = await supabase
    .from(T_PREDS)
    .select("*")
    .eq("validated", false);
  if (predErr) throw predErr;

  const runningByMatch = new Map<string, any[]>();
  for (const p of runningPreds || []) {
    const mid = String(p.match_id);
    if (!runningByMatch.has(mid)) runningByMatch.set(mid, []);
    runningByMatch.get(mid)!.push(p);
  }

  let created = 0;
  let updatedRunning = 0;

  for (const m of liveMatches || []) {
    const raw = m.raw_data || {};
    const minute = safeNumber(m.current_minute, 0);
    const totalCorners =
      safeNumber(raw?.live_stats?.totals?.corners, 0) ||
      (safeNumber(raw?.live_stats?.home?.corner_kicks, 0) +
        safeNumber(raw?.live_stats?.away?.corner_kicks, 0));
    const totalFouls =
      safeNumber(raw?.live_stats?.totals?.fouls, 0) ||
      (safeNumber(raw?.live_stats?.home?.fouls, 0) +
        safeNumber(raw?.live_stats?.away?.fouls, 0));

    const running = runningByMatch.get(String(m.id)) || [];

    // 4a) update current_value for running preds
    for (const p of running) {
      let current = 0;
      if (p.prediction_type === "total_corners") current = totalCorners;
      if (p.prediction_type === "total_fouls") current = totalFouls;
      if (current !== safeNumber(p.current_value, -9999)) {
        await supabase
          .from(T_PREDS)
          .update({ current_value: current, minute, updated_at: nowIso() })
          .eq("id", p.id);
        updatedRunning += 1;
      }
    }

    // 4b) create corners rung if none running corners
    const hasRunningCorners = running.some((p) => p.prediction_type === "total_corners");
    if (!hasRunningCorners) {
      const rung = chooseCornersRung(minute, totalCorners);
      if (rung) {
        const prob = cornersProbability(minute, totalCorners, rung.threshold);
        const rel = Math.round(prob * 100);
        const msg =
          `${totalCorners} corners à la ${minute}e minute. ` +
          `Signal pour Over ${rung.threshold} corners.`;

        const { data: ins, error: insErr } = await supabase
          .from(T_PREDS)
          .insert({
            match_id: m.id,
            match_name: `${m.home_team} vs ${m.away_team}`,
            home_team: m.home_team,
            away_team: m.away_team,
            home_score: m.home_score,
            away_score: m.away_score,
            minute,
            league_name: m.league_name,

            prediction_type: "total_corners",
            probability: prob,
            reliability: rel,
            message: msg,

            threshold: rung.threshold,
            projected_value: totalCorners, // "Au signal" (valeur figée)
            current_value: totalCorners,   // "Actuel" (mis à jour)

            confidence: rel >= 85 ? "high" : "medium",
          })
          .select("id")
          .single();

        if (!insErr) {
          created += 1;
          await createNotification({
            type: "live_opportunity",
            title: "Nouveau signal LIVE",
            message: msg,
            related_prediction_id: ins?.id ?? null,
            priority: "high",
          });
          await sendTelegramScrapeCoupon(m, {
            prediction_type: "total_corners",
            type: "total_corners",
            threshold: rung.threshold,
            probability: prob,
            reliability: rel,
          }, ins?.id ?? null);
        }
      }
    }

    // 4c) create fouls if none running fouls
    const hasRunningFouls = running.some((p) => p.prediction_type === "total_fouls");
    if (!hasRunningFouls) {
      const cand = foulsCandidate(minute, totalFouls);
      if (cand) {
        const prob = cand.probability;
        const rel = Math.round(prob * 100);
        const msg =
          `${totalFouls} fautes à la ${minute}e minute. ` +
          `Signal pour Over ${cand.threshold} fautes.`;

        const { data: ins, error: insErr } = await supabase
          .from(T_PREDS)
          .insert({
            match_id: m.id,
            match_name: `${m.home_team} vs ${m.away_team}`,
            home_team: m.home_team,
            away_team: m.away_team,
            home_score: m.home_score,
            away_score: m.away_score,
            minute,
            league_name: m.league_name,
            prediction_type: "total_fouls",
            probability: prob,
            reliability: rel,
            message: msg,
            threshold: cand.threshold,
            projected_value: totalFouls,
            current_value: totalFouls,
            confidence: rel >= 85 ? "high" : "medium",
          })
          .select("id")
          .single();

        if (!insErr) {
          created += 1;
          await createNotification({
            type: "live_opportunity",
            title: "Nouveau signal LIVE",
            message: msg,
            related_prediction_id: ins?.id ?? null,
            priority: "normal",
          });
          await sendTelegramScrapeCoupon(m, {
            prediction_type: "total_fouls",
            type: "total_fouls",
            threshold: cand.threshold,
            probability: prob,
            reliability: rel,
          }, ins?.id ?? null);
        }
      }
    }
  }

  await supabase.from(T_CRON).upsert({
    name: "refresh",
    ok: true,
    last_run: nowIso(),
    meta: { date: dateYYYYMMDD, matches: normalized.length, stale },
  }, { onConflict: "name" });

  return { created, updatedRunning, stale, matches: normalized.length };
}

// =======================================================
// VALIDATE (CRON)
// =======================================================
function currentTotalForType(matchRow: any, type: string): number {
  const raw = matchRow.raw_data || {};
  if (type === "total_corners") {
    return safeNumber(raw?.live_stats?.totals?.corners, 0) ||
      (safeNumber(raw?.live_stats?.home?.corner_kicks, 0) +
        safeNumber(raw?.live_stats?.away?.corner_kicks, 0));
  }
  if (type === "total_fouls") {
    return safeNumber(raw?.live_stats?.totals?.fouls, 0) ||
      (safeNumber(raw?.live_stats?.home?.fouls, 0) +
        safeNumber(raw?.live_stats?.away?.fouls, 0));
  }
  return 0;
}

async function tryCreateNextCornersAfterSuccess(matchRow: any) {
  // Si match toujours live et fresh
  if (!matchRow.is_live) return;
  const freshness = computeFreshness(matchRow.updated_at);
  if (freshness == null || freshness > STALE_LIVE_SECONDS) return;

  // S'il existe déjà un running corners, stop
  const { data: running, error } = await supabase
    .from(T_PREDS)
    .select("id")
    .eq("match_id", matchRow.id)
    .eq("validated", false)
    .eq("prediction_type", "total_corners")
    .limit(1);
  if (error) return;
  if (running && running.length > 0) return;

  const minute = safeNumber(matchRow.current_minute, 0);
  const totalCorners = currentTotalForType(matchRow, "total_corners");
  const rung = chooseCornersRung(minute, totalCorners);
  if (!rung) return;

  const prob = cornersProbability(minute, totalCorners, rung.threshold);
  const rel = Math.round(prob * 100);
  const msg =
    `${totalCorners} corners à la ${minute}e minute. ` +
    `Nouveau palier : Over ${rung.threshold} corners.`;

  const { data: ins, error: insErr } = await supabase
    .from(T_PREDS)
    .insert({
      match_id: matchRow.id,
      match_name: `${matchRow.home_team} vs ${matchRow.away_team}`,
      home_team: matchRow.home_team,
      away_team: matchRow.away_team,
      home_score: matchRow.home_score,
      away_score: matchRow.away_score,
      minute,
      league_name: matchRow.league_name,
      prediction_type: "total_corners",
      probability: prob,
      reliability: rel,
      message: msg,
      threshold: rung.threshold,
      projected_value: totalCorners,
      current_value: totalCorners,
      confidence: rel >= 85 ? "high" : "medium",
    })
    .select("id")
    .single();

  if (!insErr) {
    await createNotification({
      type: "live_opportunity",
      title: "Nouveau signal LIVE",
      message: msg,
      related_prediction_id: ins?.id ?? null,
      priority: "high",
    });
    await sendTelegramScrapeCoupon(matchRow, {
      prediction_type: "total_corners",
      type: "total_corners",
      threshold: rung.threshold,
      probability: prob,
      reliability: rel,
    }, ins?.id ?? null);
  }
}

async function validatePredictions() {
  // purge stale first
  const stale = await cleanupStaleLiveMatches();

  const { data: preds, error } = await supabase
    .from(T_PREDS)
    .select("*")
    .eq("validated", false)
    .in("prediction_type", ["total_corners", "total_fouls"])
    .order("created_at", { ascending: true })
    .limit(500);
  if (error) throw error;

  const matchIds = Array.from(new Set((preds || []).map((p: any) => String(p.match_id))));
  if (matchIds.length === 0) {
    await supabase.from(T_CRON).upsert({
      name: "validate",
      ok: true,
      last_run: nowIso(),
      meta: { validated: 0, stale },
    }, { onConflict: "name" });
    return { validated: 0, reached: 0, failed: 0, stale };
  }

  const { data: matches, error: mErr } = await supabase
    .from(T_MATCHES)
    .select("*")
    .in("id", matchIds);
  if (mErr) throw mErr;
  const matchById = new Map<string, any>((matches || []).map((m: any) => [String(m.id), m]));

  let reached = 0;
  let failed = 0;
  let validated = 0;

  for (const p of preds || []) {
    const mid = String(p.match_id);
    const m = matchById.get(mid);
    if (!m) continue;

    const currentTotal = currentTotalForType(m, p.prediction_type);
    const thr = safeNumber(p.threshold, 0);
    const target = targetFromThreshold(thr);

    // reached instantly
    if (currentTotal >= target) {
      const { error: uErr } = await supabase
        .from(T_PREDS)
        .update({
          validated: true,
          outcome: "success",
          validation_type: "instant",
          validated_at: nowIso(),
          updated_at: nowIso(),
          current_value: currentTotal,
        })
        .eq("id", p.id);
      if (uErr) continue;

      validated += 1;
      reached += 1;

      await createNotification({
        type: "prediction_reached",
        title: "Prono atteint ✅",
        message: `✅ ${p.home_team} vs ${p.away_team} • ${p.prediction_type} • Over ${thr} atteint (${currentTotal}).`,
        related_prediction_id: p.id,
        priority: "high",
      });

      // After success corners -> propose next rung immediately
      if (p.prediction_type === "total_corners") {
        await tryCreateNextCornersAfterSuccess(m);
      }
      continue;
    }

    // final validation when match finished
    if (m.is_finished) {
      const { error: uErr } = await supabase
        .from(T_PREDS)
        .update({
          validated: true,
          outcome: "failure",
          validation_type: "final",
          validated_at: nowIso(),
          updated_at: nowIso(),
          current_value: currentTotal,
        })
        .eq("id", p.id);
      if (uErr) continue;

      validated += 1;
      failed += 1;

      await createNotification({
        type: "prediction_validated",
        title: "Prono échoué ❌",
        message: `❌ ${p.home_team} vs ${p.away_team} • Over ${thr} non atteint (${currentTotal}).`,
        related_prediction_id: p.id,
        priority: "normal",
      });
    }
  }

  await supabase.from(T_CRON).upsert({
    name: "validate",
    ok: true,
    last_run: nowIso(),
    meta: { validated, reached, failed, stale },
  }, { onConflict: "name" });

  return { validated, reached, failed, stale };
}

// =======================================================
// READERS
// =======================================================

async function getLiveMatchesFromDb() {
  const cutoff = staleCutoffIso();
  const { data: matches, error } = await supabase
    .from(T_MATCHES)
    .select("*")
    .eq("is_live", true)
    .gte("updated_at", cutoff)
    .order("updated_at", { ascending: false })
    .limit(200);
  if (error) throw error;

  const ids = (matches || []).map((m: any) => m.id);
  let preds: any[] = [];
  if (ids.length > 0) {
    const { data, error: pErr } = await supabase
      .from(T_PREDS)
      .select("*")
      .eq("validated", false)
      .in("match_id", ids)
      .in("prediction_type", ["total_corners", "total_fouls"])
      .order("reliability", { ascending: false });
    if (pErr) throw pErr;
    preds = data || [];
  }

  const predsByMatch = new Map<string, any[]>();
  for (const p of preds) {
    const mid = String(p.match_id);
    if (!predsByMatch.has(mid)) predsByMatch.set(mid, []);
    predsByMatch.get(mid)!.push(p);
  }

  return (matches || []).map((m: any) => matchUiFromRow(m, predsByMatch.get(String(m.id)) || []));
}

async function getOpportunitiesFromDb() {
  const live = await getLiveMatchesFromDb();
  const withPred = live.filter((m: any) => (m.predictions || []).length > 0);
  withPred.sort((a: any, b: any) => safeNumber(b.value_score, 0) - safeNumber(a.value_score, 0));
  return withPred;
}

async function getTodayPayloadFromDb() {
  const now = nowIso();
  const { data: scheduled, error } = await supabase
    .from(T_MATCHES)
    .select("*")
    .eq("is_live", false)
    .eq("is_finished", false)
    .gt("event_date", now)
    .order("event_date", { ascending: true })
    .limit(150);
  if (error) throw error;

  const ui = (scheduled || []).map((m: any) => matchUiFromRow(m, []));
  return { data: { scheduled: { matches: ui } } };
}

async function getPredictionHistory() {
  const since = new Date(Date.now() - 48 * 3600 * 1000).toISOString();
  const { data, error } = await supabase
    .from(T_PREDS)
    .select("*")
    .in("prediction_type", ["total_corners", "total_fouls"])
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(200);
  if (error) throw error;

  // Enrich shape to what live.html expects
  const matchIds = Array.from(new Set((data || []).map((p: any) => String(p.match_id))));
  const { data: matches, error: mErr } = await supabase
    .from(T_MATCHES)
    .select("*")
    .in("id", matchIds);
  if (mErr) throw mErr;
  const matchById = new Map<string, any>((matches || []).map((m: any) => [String(m.id), m]));

  return (data || []).map((p: any) => {
    const m = matchById.get(String(p.match_id));
    const league = m?.raw_data?.league || { name: p.league_name };
    return {
      id: p.id,
      type: p.prediction_type,
      threshold: p.threshold,
      pronostic: p.threshold,
      probability: Number(p.probability || 0),
      message: p.message,
      signal_value: p.projected_value,
      current: p.current_value,
      projected: p.projected_value,
      current_minute: p.minute,
      minute: p.minute,
      home_team: p.home_team,
      away_team: p.away_team,
      home_score: p.home_score,
      away_score: p.away_score,
      league,
      league_id: m?.league_id,
      home_team_id: m?.home_team_id,
      away_team_id: m?.away_team_id,
      home_team_obj: m?.raw_data?.home_team_obj,
      away_team_obj: m?.raw_data?.away_team_obj,
      validated: p.validated,
      outcome: p.outcome,
      validation_type: p.validation_type,
      timestamp: new Date(p.created_at).getTime(),
    };
  });
}

async function getPredictionById(predId: string) {
  const { data: p, error } = await supabase
    .from(T_PREDS)
    .select("*")
    .eq("id", predId)
    .single();
  if (error) return null;

  const { data: m } = await supabase
    .from(T_MATCHES)
    .select("*")
    .eq("id", p.match_id)
    .single();

  const league = m?.raw_data?.league || { name: p.league_name };
  return {
    id: p.id,
    type: p.prediction_type,
    threshold: p.threshold,
    pronostic: p.threshold,
    probability: Number(p.probability || 0),
    message: p.message,
    signal_value: p.projected_value,
    current: p.current_value,
    projected: p.projected_value,
    current_minute: p.minute,
    minute: p.minute,
    home_team: p.home_team,
    away_team: p.away_team,
    home_score: p.home_score,
    away_score: p.away_score,
    league,
    league_id: m?.league_id,
    home_team_id: m?.home_team_id,
    away_team_id: m?.away_team_id,
    home_team_obj: m?.raw_data?.home_team_obj,
    away_team_obj: m?.raw_data?.away_team_obj,
    validated: p.validated,
    outcome: p.outcome,
    validation_type: p.validation_type,
    timestamp: new Date(p.created_at).getTime(),
  };
}

async function getNotifications(userId: string) {
  const { data, error } = await supabase
    .from(T_NOTIFS)
    .select("*")
    .or(`user_id.eq.${userId},user_id.eq.all`)
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  return data || [];
}

async function markNotificationsRead(ids: number[]) {
  if (!ids.length) return { updated: 0 };
  const { data, error } = await supabase
    .from(T_NOTIFS)
    .update({ read: true })
    .in("id", ids)
    .select("id");
  if (error) throw error;
  return { updated: (data || []).length };
}

// =======================================================
// COMPATIBILITÉ AVEC L'ANCIEN live.ts
// =======================================================
function predictionRowToUi(p: any) {
  return predictionUiFromRow(p, {});
}

async function getCachedLiveStats(matchId: string) {
  const { data, error } = await supabase
    .from(T_MATCHES)
    .select("raw_data")
    .eq("id", String(matchId))
    .maybeSingle();
  if (error || !data) return null;
  return data?.raw_data?.live_stats || null;
}

function computeCurrentValueFromStats(predType: string, stats: any) {
  if (!stats) return null;
  if (predType === "total_corners") {
    return safeNumber(stats?.totals?.corners, 0) ||
      safeNumber(stats?.home?.corner_kicks, 0) + safeNumber(stats?.away?.corner_kicks, 0);
  }
  if (predType === "total_fouls") {
    return safeNumber(stats?.totals?.fouls, 0) ||
      safeNumber(stats?.home?.fouls, 0) + safeNumber(stats?.away?.fouls, 0);
  }
  return null;
}

async function getLiveOpportunitiesFromDb() {
  return getOpportunitiesFromDb();
}

async function refreshLiveDataInDb(dateYYYYMMDD = todayYYYYMMDD()) {
  const meta = await refreshFromEspn(dateYYYYMMDD);
  const count = safeNumber((meta as any)?.matches, 0);
  return { matches: Array.from({ length: count }), meta };
}

async function validatePredictionsNow() {
  return validatePredictions();
}

async function getStoredLogoUrl(type: string, id: string) {
  const cleanId = decodeURIComponent(String(id || ""));
  if (!cleanId) return null;

  if (type === "team") {
    const { data, error } = await supabase
      .from(T_MATCHES)
      .select("home_team_id, away_team_id, home_logo, away_logo, raw_data, updated_at")
      .or(`home_team_id.eq.${cleanId},away_team_id.eq.${cleanId}`)
      .order("updated_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error || !data) return null;
    if (String(data.home_team_id) === cleanId) return data.home_logo || data.raw_data?.home_logo || null;
    if (String(data.away_team_id) === cleanId) return data.away_logo || data.raw_data?.away_logo || null;
    return data.home_logo || data.away_logo || null;
  }

  if (type === "league") {
    const { data, error } = await supabase
      .from(T_MATCHES)
      .select("league_id, league_logo, raw_data, updated_at")
      .eq("league_id", cleanId)
      .order("updated_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error || !data) return null;
    return data.league_logo || data.raw_data?.league_logo || null;
  }

  return null;
}

async function proxyStoredLogo(type: string, id: string) {
  const logoUrl = await getStoredLogoUrl(type, id);
  if (!logoUrl) {
    return new Response("Image not found", {
      status: 404,
      headers: { ...corsHeaders, "Content-Type": "text/plain" },
    });
  }

  const upstream = await fetch(logoUrl);
  if (!upstream.ok) {
    return new Response("Image not found", {
      status: upstream.status,
      headers: { ...corsHeaders, "Content-Type": "text/plain" },
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


// =======================================================
// SERVER
// =======================================================
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const path = extractPath(url);

  try {
    // ===================================================
    // IMG PROXY compatible avec l'ancien live.ts
    // ===================================================
    const imgMatch = path.match(/^\/img\/(team|league|player)\/([^/]+)\/?$/);
    if (imgMatch && req.method === "GET") {
      const type = imgMatch[1];
      const id = imgMatch[2];
      if (type === "player") {
        return new Response("Image not found", {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "text/plain" },
        });
      }
      return proxyStoredLogo(type, id);
    }

    if (path === "/" || path === "") {
      return json({
        ok: true,
        function: FUNCTION_NAME,
        endpoints: [
          "/matches",
          "/opportunities",
          "/today",
          "/predictions/history",
          "/predictions/by-id?id=...",
          "/notifications?user_id=...",
          "/notifications/mark-read",
          "/refresh",
          "/validate",
        ],
      });
    }

    if (path === "/matches" && req.method === "GET") {
      const matches = await getLiveMatchesFromDb();
      return json({ matches });
    }

    if (path === "/opportunities" && req.method === "GET") {
      const opportunities = await getLiveOpportunitiesFromDb();
      return json({ opportunities });
    }

    if (path === "/today" && req.method === "GET") {
      const payload = await getTodayPayloadFromDb();
      return json(payload);
    }

    if (path === "/predictions/history" && req.method === "GET") {
      const history = await getPredictionHistory();
      return json({ history });
    }

    if (path === "/predictions/by-id" && req.method === "GET") {
      const id = url.searchParams.get("id") || "";
      if (!id) return json({ error: "id required" }, 400);
      const prediction = await getPredictionById(id);
      if (!prediction) return json({ error: "not found" }, 404);
      return json({ prediction });
    }

    if (path === "/notifications" && req.method === "GET") {
      const userId = url.searchParams.get("user_id") || "all";
      const notifications = await getNotifications(userId);
      return json({
        notifications: notifications.map((n: any) => ({
          ...n,
          timestamp: new Date(n.created_at).getTime(),
        })),
      });
    }

    if (path === "/notifications/mark-read" && req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      const ids = Array.isArray(body?.notification_ids) ? body.notification_ids : [];
      const result = await markNotificationsRead(ids);
      return json({ success: true, ...result });
    }

    if (path === "/refresh" && req.method === "POST") {
      requireCronAuth(req, url);
      const date = url.searchParams.get("date") || todayYYYYMMDD();
      try {
        const { matches, meta } = await refreshLiveDataInDb(date);
        await setCronRun("live_refresh", true, meta);
        return json({ success: true, count: matches.length, meta });
      } catch (e: any) {
        await setCronRun("live_refresh", false, { error: e?.message || String(e) });
        throw e;
      }
    }

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

    return json({ error: "Not found" }, 404);
  } catch (e) {
    console.error("live-scrape-test.ts error:", e);
    return json({ error: e instanceof Error ? e.message : "Erreur serveur" }, 500);
  }
});
