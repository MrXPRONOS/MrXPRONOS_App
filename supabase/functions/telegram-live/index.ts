// telegram-live/index.ts
// Worker Telegram LIVE ultra-léger.
// Aucun Satori, aucun Resvg, aucune police distante : le PNG est construit
// directement en mémoire avec un petit moteur bitmap pour éviter les 546 CPU.

import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY =
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const CRON_SECRET = Deno.env.get("CRON_SECRET") || "";

import { richPhotoOrLegacy } from "../_shared/telegram_rich.ts";
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
const TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || "";
const TELEGRAM_CHAT_ID_SECONDARY =
  Deno.env.get("TELEGRAM_CHAT_ID_SECONDARY") || "@mrxpronosfr";

const supabase = createClient(
  SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY,
);

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Authorization, x-cron-secret",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
    },
  });
}

function safeNumber(value: unknown, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function nowIso() {
  return new Date().toISOString();
}

function requireAuth(req: Request, url: URL) {
  if (!CRON_SECRET) return;

  const authorization = req.headers.get("authorization") || "";
  const headerSecret = req.headers.get("x-cron-secret") || "";
  const querySecret = url.searchParams.get("key") || "";

  const bearerOk =
    authorization.toLowerCase().startsWith("bearer ") &&
    authorization.slice(7).trim() === CRON_SECRET;

  if (
    !bearerOk &&
    headerSecret !== CRON_SECRET &&
    querySecret !== CRON_SECRET
  ) {
    throw new Error("Unauthorized (CRON_SECRET)");
  }
}

function telegramChatIds() {
  return [
    ...new Set(
      [TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID_SECONDARY]
        .map((x) => String(x || "").trim())
        .filter(Boolean),
    ),
  ];
}

function ascii(value: unknown) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9 .,:;!?+\-/'()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

function fit(value: unknown, max: number) {
  const s = ascii(value);
  if (s.length <= max) return s;
  return s.slice(0, Math.max(1, max - 3)).trimEnd() + "...";
}

function initials(value: unknown) {
  const parts = ascii(value)
    .split(/\s+/)
    .filter(Boolean);

  if (!parts.length) return "MX";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return (parts[0][0] + parts[1][0]).slice(0, 2);
}

function marketLabel(type: unknown) {
  const t = String(type || "");
  if (t === "total_corners") return "CORNERS";
  if (t === "total_shots") return "TIRS";
  if (t === "total_fouls") return "FAUTES";
  return "SIGNAL";
}

function formatThreshold(value: unknown) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ",");
}

function calculatedOdds(pred: any) {
  for (
    const v of [
      pred?.odds,
      pred?.odd,
      pred?.cote,
      pred?.live_odds,
      pred?.bookmaker_odds,
    ]
  ) {
    const n = Number(v);
    if (Number.isFinite(n) && n > 1) {
      return Number(n.toFixed(2));
    }
  }

  const probability = Math.min(
    0.95,
    Math.max(0.2, safeNumber(pred?.probability, 0.78)),
  );

  return Number(
    Math.min(2.35, Math.max(1.08, 0.94 / probability)).toFixed(2),
  );
}

function formatMoney(value: number) {
  return (
    Math.round(value)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " F"
  );
}

// =======================================================
// DB / DELIVERY
// =======================================================

async function releaseStaleClaims() {
  const staleBefore = new Date(
    Date.now() - 5 * 60 * 1000,
  ).toISOString();

  const { error } = await supabase
    .from("live_predictions")
    .update({
      telegram_sent: false,
      telegram_last_error: "Claim Telegram expire",
    })
    .eq("telegram_sent", true)
    .eq("telegram_last_error", "__SENDING__")
    .lt("telegram_last_attempt_at", staleBefore);

  if (error) {
    console.warn("releaseStaleClaims:", error.message);
  }
}

async function getPrediction(predictionId?: string | null) {
  if (predictionId) {
    const { data, error } = await supabase
      .from("live_predictions")
      .select(
        "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, threshold, projected_value, current_value, validated, telegram_sent, telegram_attempts, telegram_last_error, telegram_last_attempt_at, telegram_pending_chat_ids, created_at",
      )
      .eq("id", predictionId)
      .maybeSingle();

    if (error) throw error;
    return data || null;
  }

  // Pas de .lt(telegram_attempts, 5) ici car les anciennes lignes peuvent
  // avoir telegram_attempts = NULL. On filtre proprement côté JS.
  const { data, error } = await supabase
    .from("live_predictions")
    .select(
      "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, threshold, projected_value, current_value, validated, telegram_sent, telegram_attempts, telegram_last_error, telegram_last_attempt_at, telegram_pending_chat_ids, created_at",
    )
    .eq("validated", false)
    .or("telegram_sent.is.null,telegram_sent.eq.false")
    .order("created_at", { ascending: true })
    .limit(30);

  if (error) throw error;

  return (
    (data || []).find(
      (row: any) => safeNumber(row?.telegram_attempts, 0) < 5,
    ) || null
  );
}

async function claimPrediction(id: string) {
  const { data, error } = await supabase
    .from("live_predictions")
    .update({
      telegram_sent: true,
      telegram_last_attempt_at: nowIso(),
      telegram_last_error: "__SENDING__",
    })
    .eq("id", id)
    .or("telegram_sent.is.null,telegram_sent.eq.false")
    .select("id")
    .maybeSingle();

  if (error) throw error;
  return Boolean(data?.id);
}

async function markDelivery(
  row: any,
  ok: boolean,
  failedChatIds: string[],
  errorText: string | null,
) {
  const at = nowIso();

  const values: any = {
    telegram_sent: ok,
    telegram_attempts:
      safeNumber(row?.telegram_attempts, 0) + 1,
    telegram_last_attempt_at: at,
    telegram_last_error:
      ok ? null : errorText || "Echec Telegram",
    telegram_pending_chat_ids:
      ok ? [] : failedChatIds,
  };

  if (ok) {
    values.telegram_sent_at = at;
  }

  const { error } = await supabase
    .from("live_predictions")
    .update(values)
    .eq("id", row.id);

  if (error) {
    console.error("markDelivery:", error.message);
  }
}

async function getMatch(row: any) {
  const { data, error } = await supabase
    .from("matches_live")
    .select(
      "id, home_team, away_team, home_score, away_score, current_minute, league_name",
    )
    .eq("id", String(row.match_id))
    .maybeSingle();

  if (error) {
    console.warn("getMatch:", error.message);
  }

  return {
    id: row.match_id,
    home_team:
      row.home_team ??
      data?.home_team ??
      "EQUIPE A",
    away_team:
      row.away_team ??
      data?.away_team ??
      "EQUIPE B",
    home_score:
      row.home_score ??
      data?.home_score ??
      0,
    away_score:
      row.away_score ??
      data?.away_score ??
      0,
    minute:
      row.minute ??
      data?.current_minute ??
      0,
    league_name:
      row.league_name ??
      data?.league_name ??
      "FOOTBALL",
  };
}

// =======================================================
// MINI MOTEUR RASTER / PNG
// =======================================================

type RGB = [number, number, number];

const WIDTH = 640;
const HEIGHT = 720;
const BPP = 3;

const C = {
  NAVY: [13, 35, 54] as RGB,
  NAVY2: [22, 50, 75] as RGB,
  BLACK: [5, 5, 5] as RGB,
  WHITE: [255, 255, 255] as RGB,
  PAGE: [238, 242, 246] as RGB,
  BORDER: [205, 213, 221] as RGB,
  MUTED: [126, 148, 166] as RGB,
  TEXT: [26, 59, 87] as RGB,
  BLUE: [74, 148, 216] as RGB,
  YELLOW: [241, 207, 54] as RGB,
  GREEN: [88, 169, 92] as RGB,
  RED: [239, 61, 51] as RGB,
  SOFT: [245, 248, 250] as RGB,
};

function imageBuffer(color: RGB = C.PAGE) {
  const data = new Uint8Array(WIDTH * HEIGHT * BPP);

  for (let i = 0; i < data.length; i += BPP) {
    data[i] = color[0];
    data[i + 1] = color[1];
    data[i + 2] = color[2];
  }

  return data;
}

function setPixel(
  data: Uint8Array,
  x: number,
  y: number,
  color: RGB,
) {
  if (
    x < 0 ||
    y < 0 ||
    x >= WIDTH ||
    y >= HEIGHT
  ) return;

  const i = (y * WIDTH + x) * BPP;
  data[i] = color[0];
  data[i + 1] = color[1];
  data[i + 2] = color[2];
}

function fillRect(
  data: Uint8Array,
  x: number,
  y: number,
  w: number,
  h: number,
  color: RGB,
) {
  const x0 = Math.max(0, Math.floor(x));
  const y0 = Math.max(0, Math.floor(y));
  const x1 = Math.min(WIDTH, Math.ceil(x + w));
  const y1 = Math.min(HEIGHT, Math.ceil(y + h));

  for (let yy = y0; yy < y1; yy++) {
    let i = (yy * WIDTH + x0) * BPP;
    for (let xx = x0; xx < x1; xx++) {
      data[i] = color[0];
      data[i + 1] = color[1];
      data[i + 2] = color[2];
      i += BPP;
    }
  }
}

function drawHLine(
  data: Uint8Array,
  x: number,
  y: number,
  w: number,
  color: RGB,
  thickness = 1,
) {
  fillRect(data, x, y, w, thickness, color);
}

function fillCircle(
  data: Uint8Array,
  cx: number,
  cy: number,
  radius: number,
  color: RGB,
) {
  const r2 = radius * radius;
  const x0 = Math.max(0, Math.floor(cx - radius));
  const x1 = Math.min(WIDTH - 1, Math.ceil(cx + radius));
  const y0 = Math.max(0, Math.floor(cy - radius));
  const y1 = Math.min(HEIGHT - 1, Math.ceil(cy + radius));

  for (let y = y0; y <= y1; y++) {
    const dy = y - cy;
    for (let x = x0; x <= x1; x++) {
      const dx = x - cx;
      if (dx * dx + dy * dy <= r2) {
        setPixel(data, x, y, color);
      }
    }
  }
}

function circleOutline(
  data: Uint8Array,
  cx: number,
  cy: number,
  radius: number,
  color: RGB,
  thickness = 3,
) {
  fillCircle(data, cx, cy, radius, color);
  fillCircle(
    data,
    cx,
    cy,
    Math.max(0, radius - thickness),
    C.SOFT,
  );
}

// Police bitmap 5x7.
// Chaque ligne est un masque de 5 bits.
const FONT: Record<string, number[]> = {
  " ": [0,0,0,0,0,0,0],
  "A": [14,17,17,31,17,17,17],
  "B": [30,17,17,30,17,17,30],
  "C": [14,17,16,16,16,17,14],
  "D": [30,17,17,17,17,17,30],
  "E": [31,16,16,30,16,16,31],
  "F": [31,16,16,30,16,16,16],
  "G": [14,17,16,23,17,17,14],
  "H": [17,17,17,31,17,17,17],
  "I": [31,4,4,4,4,4,31],
  "J": [7,2,2,2,18,18,12],
  "K": [17,18,20,24,20,18,17],
  "L": [16,16,16,16,16,16,31],
  "M": [17,27,21,21,17,17,17],
  "N": [17,25,21,19,17,17,17],
  "O": [14,17,17,17,17,17,14],
  "P": [30,17,17,30,16,16,16],
  "Q": [14,17,17,17,21,18,13],
  "R": [30,17,17,30,20,18,17],
  "S": [15,16,16,14,1,1,30],
  "T": [31,4,4,4,4,4,4],
  "U": [17,17,17,17,17,17,14],
  "V": [17,17,17,17,17,10,4],
  "W": [17,17,17,21,21,21,10],
  "X": [17,17,10,4,10,17,17],
  "Y": [17,17,10,4,4,4,4],
  "Z": [31,1,2,4,8,16,31],
  "0": [14,17,19,21,25,17,14],
  "1": [4,12,4,4,4,4,14],
  "2": [14,17,1,2,4,8,31],
  "3": [30,1,1,14,1,1,30],
  "4": [2,6,10,18,31,2,2],
  "5": [31,16,16,30,1,1,30],
  "6": [14,16,16,30,17,17,14],
  "7": [31,1,2,4,8,8,8],
  "8": [14,17,17,14,17,17,14],
  "9": [14,17,17,15,1,1,14],
  ".": [0,0,0,0,0,12,12],
  ",": [0,0,0,0,0,12,8],
  ":": [0,12,12,0,12,12,0],
  ";": [0,12,12,0,12,8,0],
  "!": [4,4,4,4,4,0,4],
  "?": [14,17,1,2,4,0,4],
  "+": [0,4,4,31,4,4,0],
  "-": [0,0,0,31,0,0,0],
  "/": [1,2,2,4,8,8,16],
  "'": [4,4,2,0,0,0,0],
  "(": [2,4,8,8,8,4,2],
  ")": [8,4,2,2,2,4,8],
};

function textWidth(text: string, scale: number) {
  if (!text) return 0;
  return text.length * 6 * scale - scale;
}

function drawText(
  data: Uint8Array,
  textValue: unknown,
  x: number,
  y: number,
  scale: number,
  color: RGB,
  align: "left" | "center" | "right" = "left",
) {
  const text = ascii(textValue);
  let startX = Math.floor(x);
  const width = textWidth(text, scale);

  if (align === "center") {
    startX = Math.floor(x - width / 2);
  } else if (align === "right") {
    startX = Math.floor(x - width);
  }

  let cursor = startX;

  for (const ch of text) {
    const glyph = FONT[ch] || FONT["?"];

    for (let row = 0; row < 7; row++) {
      const mask = glyph[row] || 0;

      for (let col = 0; col < 5; col++) {
        const bit = 1 << (4 - col);

        if (mask & bit) {
          fillRect(
            data,
            cursor + col * scale,
            y + row * scale,
            scale,
            scale,
            color,
          );
        }
      }
    }

    cursor += 6 * scale;
  }
}

async function deflateBytes(input: Uint8Array) {
  const compressedStream = new Blob([input])
    .stream()
    .pipeThrough(new CompressionStream("deflate"));

  return new Uint8Array(
    await new Response(compressedStream).arrayBuffer(),
  );
}

function u32be(value: number) {
  const out = new Uint8Array(4);
  const v = value >>> 0;
  out[0] = (v >>> 24) & 255;
  out[1] = (v >>> 16) & 255;
  out[2] = (v >>> 8) & 255;
  out[3] = v & 255;
  return out;
}

let CRC_TABLE: Uint32Array | null = null;

function crcTable() {
  if (CRC_TABLE) return CRC_TABLE;

  const table = new Uint32Array(256);

  for (let n = 0; n < 256; n++) {
    let c = n;

    for (let k = 0; k < 8; k++) {
      c =
        c & 1
          ? 0xedb88320 ^ (c >>> 1)
          : c >>> 1;
    }

    table[n] = c >>> 0;
  }

  CRC_TABLE = table;
  return table;
}

function crc32(bytes: Uint8Array) {
  const table = crcTable();
  let crc = 0xffffffff;

  for (let i = 0; i < bytes.length; i++) {
    crc =
      table[(crc ^ bytes[i]) & 0xff] ^
      (crc >>> 8);
  }

  return (crc ^ 0xffffffff) >>> 0;
}

function concatBytes(parts: Uint8Array[]) {
  const length = parts.reduce(
    (sum, part) => sum + part.length,
    0,
  );

  const out = new Uint8Array(length);
  let offset = 0;

  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }

  return out;
}

function pngChunk(
  type: string,
  payload = new Uint8Array(),
) {
  const typeBytes = new TextEncoder().encode(type);
  const crcInput = concatBytes([typeBytes, payload]);

  return concatBytes([
    u32be(payload.length),
    typeBytes,
    payload,
    u32be(crc32(crcInput)),
  ]);
}

async function encodePng(rgb: Uint8Array) {
  const stride = WIDTH * BPP;
  const raw = new Uint8Array(
    (stride + 1) * HEIGHT,
  );

  for (let y = 0; y < HEIGHT; y++) {
    const dst = y * (stride + 1);
    raw[dst] = 0;
    raw.set(
      rgb.subarray(y * stride, (y + 1) * stride),
      dst + 1,
    );
  }

  const compressed = await deflateBytes(raw);

  const ihdr = new Uint8Array(13);
  ihdr.set(u32be(WIDTH), 0);
  ihdr.set(u32be(HEIGHT), 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // truecolour RGB
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  return concatBytes([
    new Uint8Array([
      137, 80, 78, 71, 13, 10, 26, 10,
    ]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", compressed),
    pngChunk("IEND"),
  ]);
}

async function renderCoupon(
  match: any,
  pred: any,
) {
  const data = imageBuffer(C.PAGE);

  const minute = Math.max(
    0,
    safeNumber(match?.minute, 0),
  );

  const odds = calculatedOdds(pred);
  const stake = 500_000;
  const potential = Math.round(stake * odds);
  const threshold = formatThreshold(pred?.threshold);
  const market = marketLabel(pred?.prediction_type);

  const home = fit(match?.home_team, 18);
  const away = fit(match?.away_team, 18);
  const league = fit(match?.league_name, 38);

  const currentValue = safeNumber(
    pred?.current_value ??
      pred?.projected_value,
    0,
  );

  const slip = String(pred?.id || "")
    .replace(/[^A-Za-z0-9]/g, "")
    .slice(-8);

  // Barre noire sponsor.
  fillRect(data, 0, 0, WIDTH, 72, C.BLACK);
  drawText(data, "1XBET", 22, 24, 4, C.WHITE);
  drawText(data, "OU", 145, 31, 2, C.WHITE);
  drawText(data, "MELBET", 185, 24, 4, C.WHITE);

  fillRect(data, 420, 17, 200, 40, C.YELLOW);
  drawText(
    data,
    "CODE PROMO XPVIP",
    520,
    30,
    2,
    C.BLACK,
    "center",
  );

  // Carte.
  fillRect(data, 12, 88, 616, 616, C.WHITE);
  drawHLine(data, 12, 180, 616, C.BORDER, 1);
  drawHLine(data, 12, 330, 616, C.BORDER, 1);

  drawText(
    data,
    "NOUVEAU COUPON LIVE",
    30,
    112,
    2,
    C.MUTED,
  );

  drawText(
    data,
    "SIMPLE",
    30,
    142,
    4,
    C.TEXT,
  );

  drawText(
    data,
    "N " + (slip || "LIVE"),
    190,
    149,
    2,
    C.MUTED,
  );

  fillRect(data, 518, 108, 88, 30, C.RED);
  drawText(
    data,
    "LIVE",
    562,
    117,
    2,
    C.WHITE,
    "center",
  );

  // Stats coupon.
  drawText(data, "COTE CALCULEE", 30, 200, 2, C.MUTED);
  drawText(
    data,
    odds.toFixed(2),
    604,
    200,
    3,
    C.TEXT,
    "right",
  );

  drawText(data, "MISE", 30, 232, 2, C.MUTED);
  drawText(
    data,
    "500 000 F",
    604,
    232,
    3,
    C.TEXT,
    "right",
  );

  drawText(data, "GAIN POTENTIEL", 30, 264, 2, C.MUTED);
  drawText(
    data,
    formatMoney(potential),
    604,
    264,
    3,
    C.GREEN,
    "right",
  );

  drawText(data, "STATUT", 30, 296, 2, C.MUTED);
  drawText(
    data,
    "ACCEPTE",
    604,
    296,
    3,
    C.BLUE,
    "right",
  );

  // Ligue / minute.
  drawText(
    data,
    "FOOTBALL - " + league,
    30,
    350,
    2,
    C.MUTED,
  );

  drawText(
    data,
    Math.floor(minute) + " MIN",
    604,
    350,
    2,
    C.RED,
    "right",
  );

  // Equipes.
  circleOutline(data, 105, 430, 38, C.BLUE, 3);
  circleOutline(data, 535, 430, 38, C.BLUE, 3);

  drawText(
    data,
    initials(home),
    105,
    420,
    3,
    C.TEXT,
    "center",
  );

  drawText(
    data,
    initials(away),
    535,
    420,
    3,
    C.TEXT,
    "center",
  );

  drawText(
    data,
    home,
    250,
    410,
    2,
    C.TEXT,
    "right",
  );

  drawText(
    data,
    away,
    390,
    410,
    2,
    C.TEXT,
    "left",
  );

  drawText(
    data,
    safeNumber(match?.home_score) +
      " - " +
      safeNumber(match?.away_score),
    320,
    447,
    4,
    C.TEXT,
    "center",
  );

  // Pronostic.
  fillRect(data, 30, 505, 580, 108, C.SOFT);

  drawText(
    data,
    "PRONOSTIC LIVE",
    48,
    526,
    2,
    C.MUTED,
  );

  drawText(
    data,
    "TOTAL PLUS DE " +
      threshold +
      " " +
      market,
    48,
    558,
    3,
    C.TEXT,
  );

  drawText(
    data,
    "VALEUR ACTUELLE",
    30,
    642,
    2,
    C.MUTED,
  );

  drawText(
    data,
    String(currentValue).replace(".", ","),
    604,
    642,
    3,
    C.TEXT,
    "right",
  );

  drawText(
    data,
    "MR XPRONOS - JOUE RESPONSABLEMENT 18+",
    320,
    680,
    2,
    C.MUTED,
    "center",
  );

  return await encodePng(data);
}

// =======================================================
// TELEGRAM
// =======================================================

async function sendPhoto(
  png: Uint8Array,
  pred: any,
  match: any,
  chatIds: string[],
) {
  const sent: string[] = [];
  const failed: string[] = [];
  const errors: string[] = [];

  const caption =
    "🔥 NOUVEAU COUPON LIVE\n\n" +
    "⚽ " +
    fit(match?.home_team, 30) +
    " vs " +
    fit(match?.away_team, 30) +
    "\n🎯 Total plus de " +
    formatThreshold(pred?.threshold) +
    " " +
    marketLabel(pred?.prediction_type).toLowerCase();

  for (const chatId of chatIds) {
    let success = false;
    let lastError = "";

    for (let attempt = 1; attempt <= 2; attempt++) {
      const form = new FormData();

      form.append("chat_id", chatId);
      form.append("caption", caption);

      form.append(
        "reply_markup",
        JSON.stringify({
          inline_keyboard: [
            [
              {
                text: "Voir plus de coupons 🔥",
                url:
                  "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",
              },
            ],
            [
              {
                text:
                  "S'inscrire ou reinitialiser son compte 🎯",
                url:
                  "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",
              },
            ],
          ],
        }),
      );

      form.append(
        "photo",
        new Blob([png], { type: "image/png" }),
        `coupon-live-${pred.id}.png`,
      );

      try {
        const res = await richPhotoOrLegacy(
          TELEGRAM_BOT_TOKEN,chatId,png,caption,[
            [{text:"Voir plus de coupons 🔥",url:"https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",style:"primary"}],
            [{text:"S'inscrire ou reinitialiser son compte 🎯",url:"https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",style:"success"}]
          ],form,`coupon-live-${pred.id}.png`
        );

        if (res.ok) {
          success = true;
          sent.push(chatId);
          break;
        }

        const body = await res.text().catch(() => "");
        lastError =
          `HTTP ${res.status}: ${body}`;
      } catch (e: any) {
        lastError = e?.message || String(e);
      }

      if (attempt < 2) {
        await new Promise((resolve) =>
          setTimeout(resolve, 400)
        );
      }
    }

    if (!success) {
      failed.push(chatId);
      errors.push(
        `${chatId}: ${lastError || "sendPhoto echoue"}`,
      );
    }
  }

  return {
    ok:
      failed.length === 0 &&
      sent.length === chatIds.length,
    sent,
    failed,
    error:
      errors.length ? errors.join(" | ") : null,
  };
}

async function processOne(
  predictionId?: string | null,
) {
  if (!TELEGRAM_BOT_TOKEN) {
    throw new Error(
      "TELEGRAM_BOT_TOKEN manquant",
    );
  }

  await releaseStaleClaims();

  const row = await getPrediction(
    predictionId || null,
  );

  if (!row) {
    return {
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      error:
        predictionId
          ? "prediction introuvable/non eligible"
          : null,
    };
  }

  if (row.validated === true) {
    return {
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      prediction_id: row.id,
      error: "prediction deja validee",
    };
  }

  if (
    row.telegram_sent === true &&
    row.telegram_last_error !== "__SENDING__"
  ) {
    return {
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_sent: true,
      prediction_id: row.id,
    };
  }

  const claimed = await claimPrediction(
    String(row.id),
  );

  if (!claimed) {
    return {
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_claimed: true,
      prediction_id: row.id,
    };
  }

  const targets =
    Array.isArray(row.telegram_pending_chat_ids) &&
      row.telegram_pending_chat_ids.length
      ? row.telegram_pending_chat_ids
        .map(String)
        .filter(Boolean)
      : telegramChatIds();

  if (!targets.length) {
    await markDelivery(
      row,
      false,
      [],
      "Aucun canal Telegram configure",
    );

    return {
      telegram_retry_processed: 1,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      prediction_id: row.id,
      error: "Aucun canal Telegram configure",
    };
  }

  try {
    const match = await getMatch(row);
    const png = await renderCoupon(
      match,
      row,
    );

    console.log("PNG LIVE genere sans Satori/Resvg", {
      prediction_id: row.id,
      bytes: png.byteLength,
    });

    const delivery = await sendPhoto(
      png,
      row,
      match,
      targets,
    );

    await markDelivery(
      row,
      delivery.ok,
      delivery.failed,
      delivery.error,
    );

    return {
      telegram_retry_processed: 1,
      telegram_retry_sent:
        delivery.ok ? 1 : 0,
      telegram_retry_failed:
        delivery.ok ? 0 : 1,
      telegram_retry_skipped: 0,
      prediction_id: row.id,
      sent_chat_ids: delivery.sent,
      failed_chat_ids: delivery.failed,
      error: delivery.error,
      renderer: "native_bitmap_png",
      png_bytes: png.byteLength,
    };
  } catch (e: any) {
    const errorText =
      e?.stack ||
      e?.message ||
      String(e);

    await markDelivery(
      row,
      false,
      targets,
      errorText,
    );

    return {
      telegram_retry_processed: 1,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      prediction_id: row.id,
      failed_chat_ids: targets,
      error: errorText,
      renderer: "native_bitmap_png",
    };
  }
}

// =======================================================
// SERVER
// =======================================================

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(
      "ok",
      { headers: corsHeaders },
    );
  }

  const url = new URL(req.url);

  try {
    requireAuth(req, url);

    if (
      req.method === "GET" &&
      url.pathname.endsWith("/status")
    ) {
      const { data, error } = await supabase
        .from("live_predictions")
        .select(
          "id, match_name, prediction_type, threshold, telegram_sent, telegram_attempts, telegram_last_attempt_at, telegram_last_error, telegram_pending_chat_ids, created_at",
        )
        .order("created_at", {
          ascending: false,
        })
        .limit(20);

      if (error) throw error;

      return json({
        telegram_configured:
          Boolean(TELEGRAM_BOT_TOKEN) &&
          telegramChatIds().length > 0,
        target_chat_count:
          telegramChatIds().length,
        renderer: "native_bitmap_png",
        predictions: data || [],
      });
    }

    if (req.method !== "POST") {
      return json(
        { error: "POST required" },
        405,
      );
    }

    const body = await req
      .json()
      .catch(() => ({}));

    const predictionId =
      url.searchParams.get("prediction_id") ||
      String(body?.prediction_id || "").trim() ||
      null;

    const result = await processOne(
      predictionId,
    );

    return json({
      success:
        safeNumber(
          result.telegram_retry_failed,
          0,
        ) === 0,
      isolated: true,
      ...result,
    });
  } catch (e: any) {
    console.error(
      "telegram-live error",
      e,
    );

    return json(
      {
        success: false,
        error:
          e?.message ||
          "Erreur serveur",
      },
      500,
    );
  }
});
