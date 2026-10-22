// Mr XPRONOS: same-refresh Neon -> Cloudflare -> Telegram instant alerts.
// All Telegram credentials are Cloudflare SECRET bindings (never in code).
// Share the existing D1 telegram_sent table with the GitHub legacy sender.
const MODEL = "neon-live-value-v2.3-playability-espn";
const SITE = "https://mrxpronos.github.io/MrXPRONOS_App/live.html";
const KIND = "live_neon_signal";
const json=(o,s=200)=>new Response(JSON.stringify(o),{status:s,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
function asBytes(hex){
 if(!/^[0-9a-f]{64}$/i.test(hex||""))return null;
 return Uint8Array.from(hex.match(/../g),x=>parseInt(x,16));
}
async function verify(req,raw,key){
 const timestamp=req.headers.get("x-mrx-timestamp")||"";
 const signature=req.headers.get("x-mrx-signature")||"";
 if(!/^\d{10,13}$/.test(timestamp)||!key)return false;
 const time=Number(timestamp);
 if(!Number.isSafeInteger(time)||Math.abs(Date.now()-time)>90000)return false;
 const sig=asBytes(signature);
 if(!sig)return false;
 try{
  const k=await crypto.subtle.importKey("raw",new TextEncoder().encode(key),{name:"HMAC",hash:"SHA-256"},false,["verify"]);
  return await crypto.subtle.verify("HMAC",k,sig,new TextEncoder().encode(timestamp+"."+raw));
 }catch{return false}
}
function good(row){
 if(!row||typeof row!=="object")return false;
 if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(row.id||""))return false;
 if(row.model_version!==MODEL||row.pricing_mode!=="model_only")return false;
 if(!["total_shots","total_corners","total_fouls"].includes(row.type))return false;
 if(!["quality","value","high_value"].includes(row.signal_tier))return false;
 if(typeof row.home_team!=="string"||!row.home_team.trim()||row.home_team.length>160||
    typeof row.away_team!=="string"||!row.away_team.trim()||row.away_team.length>160)return false;
 const age=Date.now()-Date.parse(row.created_at);
 if(!Number.isFinite(age)||age < -30000||age>900000)return false;
 const p=Number(row.probability), threshold=Number(row.threshold), current=Number(row.signal_value), reliability=Number(row.reliability),quality=Number(row.data_quality_score);
 return p>=.3&&p<=.95&&Number.isFinite(threshold)&&Number.isFinite(current)&&threshold-current>=2&&reliability>=68&&quality>=67;
}
function clean(str,max=130){return String(str||"").replace(/[<>&]/g,"").slice(0,max)}
function message(row){
 const label={total_shots:"Tirs",total_corners:"Corners",total_fouls:"Fautes"}[row.type];
 const prob=Math.round(Number(row.probability)*100);
 const min=Math.max(0,Math.min(130,Math.trunc(Number(row.minute)||0)));
 return [
  "🔥 NOUVEAU PRONOSTIC LIVE",
  "⚽ "+clean(row.home_team)+" vs "+clean(row.away_team),
  "⏱ Minute : "+min+"'",
  "🎯 "+label+" : Over "+Number(row.threshold),
  "📊 Au signal : "+Number(row.signal_value),
  "🧠 Probabilité estimée (modèle) : "+prob+"%",
  "Cote bookmaker non disponible. Estimation non garantie.",
  "18+ • Joue responsablement."
 ].join("\n");
}

// Original Supabase 640 x 720 bitmap coupon, unchanged pixel geometry and glyphs.
// No screenshots, no invented team badges. Source: supabase/functions/telegram-live/index.ts
function safeNumber(value,fallback=0){const n=Number(value);return Number.isFinite(n)?n:fallback}
function scoreDisplay(match) {
 const h=match?.home_score, a=match?.away_score;
 return h!==null&&h!==undefined&&a!==null&&a!==undefined&&
   Number.isFinite(Number(h))&&Number.isFinite(Number(a))
   ? Math.trunc(Number(h))+" - "+Math.trunc(Number(a)) : " - ";
}
function ascii(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9 .,:;!?+\-/'()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

function fit(value, max) {
  const s = ascii(value);
  if (s.length <= max) return s;
  return s.slice(0, Math.max(1, max - 3)).trimEnd() + "...";
}

function initials(value) {
  const parts = ascii(value)
    .split(/\s+/)
    .filter(Boolean);

  if (!parts.length) return "MX";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return (parts[0][0] + parts[1][0]).slice(0, 2);
}

function marketLabel(type) {
  const t = String(type || "");
  if (t === "total_corners") return "CORNERS";
  if (t === "total_shots") return "TIRS";
  if (t === "total_fouls") return "FAUTES";
  return "SIGNAL";
}

function formatThreshold(value) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ",");
}

function calculatedOdds(pred) {
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

function formatMoney(value) {
  return (
    Math.round(value)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " F"
  );
}


const WIDTH = 640;
const HEIGHT = 720;
const BPP = 3;

const C = {
  NAVY: [13, 35, 54],
  NAVY2: [22, 50, 75],
  BLACK: [5, 5, 5],
  WHITE: [255, 255, 255],
  PAGE: [238, 242, 246],
  BORDER: [205, 213, 221],
  MUTED: [126, 148, 166],
  TEXT: [26, 59, 87],
  BLUE: [74, 148, 216],
  YELLOW: [241, 207, 54],
  GREEN: [88, 169, 92],
  RED: [239, 61, 51],
  SOFT: [245, 248, 250],
};

function imageBuffer(color = C.PAGE) {
  const data = new Uint8Array(WIDTH * HEIGHT * BPP);

  for (let i = 0; i < data.length; i += BPP) {
    data[i] = color[0];
    data[i + 1] = color[1];
    data[i + 2] = color[2];
  }

  return data;
}

function setPixel(
  data,
  x,
  y,
  color,
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
  data,
  x,
  y,
  w,
  h,
  color,
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
  data,
  x,
  y,
  w,
  color,
  thickness = 1,
) {
  fillRect(data, x, y, w, thickness, color);
}

function fillCircle(
  data,
  cx,
  cy,
  radius,
  color,
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
  data,
  cx,
  cy,
  radius,
  color,
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
const FONT = {
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

function textWidth(text, scale) {
  if (!text) return 0;
  return text.length * 6 * scale - scale;
}

function drawText(
  data,
  textValue,
  x,
  y,
  scale,
  color,
  align = "left",
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

async function deflateBytes(input) {
  const compressedStream = new Blob([input])
    .stream()
    .pipeThrough(new CompressionStream("deflate"));

  return new Uint8Array(
    await new Response(compressedStream).arrayBuffer(),
  );
}

function u32be(value) {
  const out = new Uint8Array(4);
  const v = value >>> 0;
  out[0] = (v >>> 24) & 255;
  out[1] = (v >>> 16) & 255;
  out[2] = (v >>> 8) & 255;
  out[3] = v & 255;
  return out;
}

let CRC_TABLE = null;

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

function crc32(bytes) {
  const table = crcTable();
  let crc = 0xffffffff;

  for (let i = 0; i < bytes.length; i++) {
    crc =
      table[(crc ^ bytes[i]) & 0xff] ^
      (crc >>> 8);
  }

  return (crc ^ 0xffffffff) >>> 0;
}

function concatBytes(parts) {
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
  type,
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

async function encodePng(rgb) {
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
  match,
  pred,
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
    scoreDisplay(match),
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

  return data;
}



// Exact source assets and UTC-day alternation from _shared/live_sponsor_banner.ts.
const BANNER_ROOT="https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/assets/images/";
const BANNER_FILES=["telegram-xpvip-banner.png","telegram-xpvip-banner-1win-betwinner.png"];
const pngBannerCache = new Map();
function readU32(buf,idx){return ((buf[idx]*16777216)+(buf[idx+1]<<16)+(buf[idx+2]<<8)+buf[idx+3])>>>0}
async function decodePng(binary){
 const bytes=binary instanceof Uint8Array?binary:new Uint8Array(binary);
 const sig=[137,80,78,71,13,10,26,10];
 if(sig.some((v,i)=>bytes[i]!==v))throw Error("Invalid banner PNG signature");
 let pos=8,width=0,height=0,depth=0,color=0,interlace=0,palette=null,alpha=null;
 const idats=[];
 while(pos+12<=bytes.length){
  const len=readU32(bytes,pos),kind=String.fromCharCode(...bytes.subarray(pos+4,pos+8));
  const start=pos+8,end=start+len;
  if(end+4>bytes.length)throw Error("Truncated banner PNG");
  const part=bytes.subarray(start,end);
  if(kind==="IHDR"){width=readU32(part,0);height=readU32(part,4);depth=part[8];color=part[9];interlace=part[12]}
  if(kind==="PLTE")palette=new Uint8Array(part);
  if(kind==="tRNS")alpha=new Uint8Array(part);
  if(kind==="IDAT")idats.push(part);
  pos=end+4;if(kind==="IEND")break;
 }
 if(depth!==8||interlace!==0||!width||!height||width*height>8000000||![0,2,3,4,6].includes(color))throw Error("Unsupported banner PNG format");
 const bands=({0:1,2:3,3:1,4:2,6:4})[color],stride=width*bands;
 const compressed=new Uint8Array(idats.reduce((n,b)=>n+b.length,0));
 let off=0;for(const b of idats){compressed.set(b,off);off+=b.length}
 const raw=new Uint8Array(await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());
 if(raw.length<(stride+1)*height)throw Error("Incomplete decoded banner");
 const pixels=new Uint8Array(width*height*4),prev=new Uint8Array(stride);
 let cursor=0;
 for(let y=0;y<height;y++){
  const filter=raw[cursor++],line=new Uint8Array(stride);
  for(let x=0;x<stride;x++){
   const a=x>=bands?line[x-bands]:0,b=prev[x],c=x>=bands?prev[x-bands]:0;
   const p=a+b-c,da=Math.abs(p-a),db=Math.abs(p-b),dc=Math.abs(p-c);
   const v=filter===0?0:filter===1?a:filter===2?b:filter===3?Math.floor((a+b)/2):filter===4?(da<=db&&da<=dc?a:db<=dc?b:c):null;
   if(v===null)throw Error("Unsupported PNG filter");
   line[x]=(raw[cursor++]+v)&255;
  }
  for(let x=0;x<width;x++){
   const s=x*bands,d=(y*width+x)*4;
   if(color===6){pixels[d]=line[s];pixels[d+1]=line[s+1];pixels[d+2]=line[s+2];pixels[d+3]=line[s+3]}
   else if(color===2){pixels[d]=line[s];pixels[d+1]=line[s+1];pixels[d+2]=line[s+2];pixels[d+3]=255}
   else if(color===3){
    const i=line[s];if(!palette||i*3+2>=palette.length)throw Error("Invalid indexed banner");
    pixels[d]=palette[i*3];pixels[d+1]=palette[i*3+1];pixels[d+2]=palette[i*3+2];pixels[d+3]=alpha?.[i]??255;
   }else if(color===0){pixels[d]=pixels[d+1]=pixels[d+2]=line[s];pixels[d+3]=255}
   else {pixels[d]=pixels[d+1]=pixels[d+2]=line[s];pixels[d+3]=line[s+1]}
  }
  prev.set(line);
 }
 return {width,height,pixels};
}
async function partnerBanner(dateString){
 const utcDay=Math.floor(Date.parse(dateString+"T00:00:00Z")/86400000);
 if(!Number.isFinite(utcDay))throw Error("Invalid signal date");
 const file=BANNER_FILES[utcDay%2===0?0:1];
 let pending=pngBannerCache.get(file);
 if(!pending){
  pending=(async()=>{
   const r=await fetch(BANNER_ROOT+file,{signal:AbortSignal.timeout(12000)});
   if(!r.ok)throw Error("Banner HTTP "+r.status);
   return decodePng(new Uint8Array(await r.arrayBuffer()));
  })();
  pngBannerCache.set(file,pending);
 }
 try{return await pending}catch(e){pngBannerCache.delete(file);throw e}
}
async function encodeRgb(data,width,height){
 const stride=width*3,raw=new Uint8Array((stride+1)*height);
 for(let y=0;y<height;y++)raw.set(data.subarray(y*stride,(y+1)*stride),y*(stride+1)+1);
 const compressed=await deflateBytes(raw);
 const ihdr=new Uint8Array(13);
 ihdr.set(u32be(width),0);ihdr.set(u32be(height),4);
 ihdr[8]=8;ihdr[9]=2;
 return concatBytes([new Uint8Array([137,80,78,71,13,10,26,10]),pngChunk("IHDR",ihdr),pngChunk("IDAT",compressed),pngChunk("IEND")]);
}
async function renderLegacyImage(row){
 const match={
   home_team:row.home_team,away_team:row.away_team,
   home_score:row.home_score,away_score:row.away_score,
   league_name:row.league_name||"FOOTBALL",minute:row.minute
 };
 const prediction={id:row.id,prediction_type:row.type,threshold:row.threshold,
   current_value:row.signal_value,probability:row.probability};
 const coupon=await renderCoupon(match,prediction);
 const day=new Date(row.created_at).toISOString().slice(0,10);
 const banner=await partnerBanner(day);
 const bannerHeight=Math.max(1,Math.round(banner.height*WIDTH/banner.width));
 if(bannerHeight>WIDTH/3)throw Error("Invalid sponsor banner ratio");
 const result=new Uint8Array(WIDTH*(HEIGHT+bannerHeight)*3);
 const source=banner.pixels;
 for(let y=0;y<bannerHeight;y++){
  const sy=Math.min(banner.height-1,Math.floor((y+0.5)*banner.height/bannerHeight));
  for(let x=0;x<WIDTH;x++){
   const sx=Math.min(banner.width-1,Math.floor((x+0.5)*banner.width/WIDTH));
   const s=(sy*banner.width+sx)*4,d=(y*WIDTH+x)*3,a=source[s+3]/255;
   result[d]=Math.round(source[s]*a+255*(1-a));
   result[d+1]=Math.round(source[s+1]*a+255*(1-a));
   result[d+2]=Math.round(source[s+2]*a+255*(1-a));
  }
 }
 result.set(coupon,bannerHeight*WIDTH*3);
 return encodeRgb(result,WIDTH,HEIGHT+bannerHeight);
}


/** Geometry and copy of the original Supabase LIVE SVG ticket (429x455). */
function liveSvg(row){
 const escapeXml=(v)=>String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&apos;");
 const esc=escapeXml;
 const when=new Date(row.created_at);
 const date=when.toLocaleDateString("fr-FR",{timeZone:"UTC"})+" ("+when.toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit",timeZone:"UTC"})+")";
 const home=String(row.home_team||"Domicile").slice(0,18), away=String(row.away_team||"Extérieur").slice(0,18),league=String(row.league_name||"Football").slice(0,33);
 const minute=Math.max(0,Math.min(130,Math.trunc(Number(row.minute)||0)));
 const homeScore=Number.isFinite(Number(row.home_score))&&row.home_score!==null?Math.trunc(Number(row.home_score)):"—";
 const awayScore=Number.isFinite(Number(row.away_score))&&row.away_score!==null?Math.trunc(Number(row.away_score)):"—";
 const periodText="";
 const odds=Number.isFinite(Number(row.model_fair_odds))&&Number(row.model_fair_odds)>1?Number(row.model_fair_odds):1/Number(row.probability);
 const oddsLabel=row.pricing_mode==="external_live"?"Cote bookmaker":"Cote modèle";
 const stake=500000, potential=Math.round(stake*odds);
 const value=(v)=>Number.isFinite(Number(v))?Number(v).toFixed(2):"—";
 const money=(v)=>Number.isFinite(Number(v))?Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g," ")+" F":"—";
 const slip=String(row.id||"").replace(/[^a-zA-Z0-9]/g,"").slice(-11);
 const threshold=String(row.threshold).replace(".",",");
 const type=({total_corners:"Corners",total_shots:"Tirs",total_fouls:"Fautes"})[row.type]||"";
 const selection="Total. ("+threshold+") Plus de. "+type;
 const receiptStatus="Accepté",slipStatus="Accepté",statusColor="#4f96d7";
 const football=(x,y,sz)=>'<circle cx="'+(x+sz/2)+'" cy="'+(y+sz/2)+'" r="'+(sz*.45)+'" fill="#edf1f4" stroke="#b2bec8"/><text x="'+(x+sz/2)+'" y="'+(y+sz*.67)+'" font-size="'+(sz*.7)+'" text-anchor="middle">⚽</text>';
 const getInitials=(name)=>String(name).split(/\s+/).map(x=>x[0]||"").join("").slice(0,2).toUpperCase();
 const safeLogo=(v)=>/^https:\/\/(?:a\.espncdn\.com|cdn\.espn\.com)\//.test(String(v||""))?String(v):"";
 const circle=(logo,x,name)=>logo?'<image href="'+esc(logo)+'" x="'+x+'" y="282" width="34" height="34" preserveAspectRatio="xMidYMid meet"/>'
 :'<circle cx="'+(x+17)+'" cy="299" r="16" fill="#eff2f4" stroke="#a8b6c2"/><text x="'+(x+17)+'" y="303" font-size="9" font-weight="700" fill="#1e3645" text-anchor="middle">'+esc(getInitials(name))+'</text>';
 const homeLogo=safeLogo(row.home_logo),awayLogo=safeLogo(row.away_logo);
 const tx=(x,y,raw,size,color="#1c3242",weight=700,anchor="start")=>
  '<text x="'+x+'" y="'+y+'" font-size="'+size+'" font-family="Noto Sans,Arial,sans-serif" font-weight="'+weight+'" fill="'+color+'" text-anchor="'+anchor+'">'+esc(raw)+'</text>';
 const formatTelegramClock=(minute)=>String(Math.floor(minute)).padStart(2,"0")+":00";
   const svg='<svg xmlns="http://www.w3.org/2000/svg" width="429" height="455" viewBox="0 0 429 455">'+
    '<rect width="429" height="455" rx="9" fill="#fff" stroke="#dbe0e5"/>'+
    '<circle cx="42" cy="48" r="25" fill="#ecf1f4"/>'+football(29,35,26)+
    '<circle cx="62" cy="69" r="9" fill="#29b36c"/><path d="M58 69l3 3 5-7" fill="none" stroke="white" stroke-width="1.7"/>'+
    tx(80,34,date,12,"#8698a6")+tx(80,55,"Simple",19)+tx(80,72,"N° "+slip,10,"#24313a",600)+
    '<rect x="348" y="24" width="67" height="14" rx="3" fill="#ef4338"/>'+tx(381.5,34,"• En direct",9,"#fff",700,"middle")+
    '<path d="M0 87h429" stroke="#e4e8eb"/>'+
    tx(16,113,oddsLabel+":",15,"#8497a5")+tx(16,141,"Mise:",15,"#8497a5")+
    tx(16,167,"Gains potentiels:",15,"#8497a5")+tx(16,193,"Statut:",15,"#8497a5")+
    tx(414,113,value(odds),15,"#1c3242",700,"end")+tx(414,141,money(stake),15,"#1c3242",700,"end")+
    tx(414,167,money(potential),15,"#4dbb69",700,"end")+tx(414,193,receiptStatus,15,statusColor,700,"end")+
    '<path d="M0 211h429" stroke="#eff3f5" stroke-width="8"/><rect x="7" y="219" width="415" height="234" rx="11" fill="#fbfbfb" stroke="#d9e1e7"/>'+
    football(18,235,24)+tx(52,245,"Football · "+league,12,"#8599a7")+tx(52,262,date,12,"#8599a7")+
    '<rect x="352" y="226" width="67" height="13" rx="3" fill="#ef4338"/>'+tx(385.5,235,"• En direct",9,"#fff",700,"middle")+
    tx(139,304,home,13,"#20323f",700,"end")+circle(homeLogo,150,home)+
    tx(216,305,homeScore+":"+awayScore,19,"#20323f",800,"middle")+circle(awayLogo,249,away)+
    tx(292,304,away,13,"#20323f")+
    tx(216,351,periodText,12,"#879da9",400,"middle")+
    '<path d="M8 363h414" stroke="#dbe1e6"/>'+
    tx(19,383,selection,13,"#24333e",700)+tx(412,383,value(odds),14,"#24333e",700,"end")+
    tx(19,410,"EN DIRECT",13,"#869aa7")+tx(412,410,"temps écoulé : "+formatTelegramClock(minute),13,"#24333e",700,"end")+
    tx(19,439,"Statut:",13,"#869aa7")+tx(412,439,slipStatus,13,statusColor,700,"end")+
    '</svg>';
 return svg;
}
function premiumHtml(row){
 const svg=liveSvg(row);
 // Actual source SVG, not synthetic bitmap letters. BrowserRun renders fonts and images.
 return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=429,initial-scale=1">'+
 '<style>*{box-sizing:border-box}html,body{margin:0;width:429px;height:455px;overflow:hidden;background:#fff}'+
 '@font-face{font-family:"Noto Sans";src:url("https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/supabase/functions/live/_fonts/NotoSans-Regular.ttf") format("truetype");font-style:normal;font-weight:400}'+
 '@font-face{font-family:"Noto Sans";src:url("https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/supabase/functions/live/_fonts/NotoSans-Bold.ttf") format("truetype");font-style:normal;font-weight:700 900}'+
 'svg{width:429px;height:455px;display:block}</style></head><body>'+svg+'</body></html>';
}
async function renderPremiumImage(row,env){
 if(!env.BROWSER?.quickAction)throw Error("browser_binding_missing");
 const response=await env.BROWSER.quickAction("screenshot",{
    html:premiumHtml(row),viewport:{width:429,height:455,deviceScaleFactor:1},
    screenshotOptions:{fullPage:false},waitForSelector:"svg",
    actionTimeout:18000
 });
 if(!response?.ok)throw Error("browser_render_http_"+String(response?.status));
 const bytes=new Uint8Array(await response.arrayBuffer());
 const decoded=await decodePng(bytes);
 if(decoded.width!==429||decoded.height!==455)throw Error("bad_coupon_dimensions");
 const day=new Date(row.created_at).toISOString().slice(0,10);
 const banner=await partnerBanner(day);
 const width=429, couponHeight=455;
 const bannerHeight=Math.max(1,Math.round(banner.height*width/banner.width));
 if(bannerHeight>width/3)throw Error("invalid_banner_dimensions");
 const result=new Uint8Array(width*(couponHeight+bannerHeight)*3);
 const drawImage=(image,x,y,w,h)=>{
  const source=image.pixels;
  for(let dy=0;dy<h;dy++){
   const sy=Math.min(image.height-1,Math.floor((dy+.5)*image.height/h));
   for(let dx=0;dx<w;dx++){
    const sx=Math.min(image.width-1,Math.floor((dx+.5)*image.width/w));
    const s=(sy*image.width+sx)*4,d=((dy+y)*width+x+dx)*3,a=source[s+3]/255;
    result[d]=Math.round(source[s]*a+255*(1-a));
    result[d+1]=Math.round(source[s+1]*a+255*(1-a));
    result[d+2]=Math.round(source[s+2]*a+255*(1-a));
   }
  }
 };
 drawImage(banner,0,0,width,bannerHeight);
 drawImage(decoded,0,bannerHeight,width,couponHeight);
 return encodeRgb(result,width,couponHeight+bannerHeight);
}

async function send(env,chat,row,png){
 const token=env.TELEGRAM_BOT_TOKEN;
 const url="https://api.telegram.org/bot"+token+"/sendPhoto";
 const form=new FormData();
 form.append("chat_id",chat);
 form.append("caption",message(row));
 form.append("reply_markup",JSON.stringify({inline_keyboard:[
   [{text:"🔥 Voir plus de coupons LIVE",url:SITE}],
   [{text:"🎯 S'inscrire / réinitialiser",url:"https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html"}]
 ]}));
 form.append("photo",new Blob([png.buffer.slice(png.byteOffset,png.byteOffset+png.byteLength)],{type:"image/png"}),"coupon-live-"+row.id+".png");
 let resp,body;
 try{
  resp=await fetch(url,{method:"POST",body:form,signal:AbortSignal.timeout(16000)});
  body=await resp.json();
 }catch(e){return {status:"unknown",reason:String(e?.name||"network_error").slice(0,30)}}
 if(!resp.ok||body?.ok!==true)return {status:"rejected",reason:"telegram_http_"+resp.status};
 if(!Number.isSafeInteger(body.result?.message_id))return {status:"unknown",reason:"unconfirmed_message_id"};
 return {status:"sent",message_id:body.result.message_id};
}
async function dispatchOne(env,row){
 const date=new Date(row.created_at).toISOString().slice(0,10);
 const photo=await renderPremiumImage(row,env);
 const destinations=[["primary",env.TELEGRAM_CHAT_ID],["secondary",env.TELEGRAM_CHAT_ID_SECONDARY]]
 .filter(([_,v])=>!!String(v||"").trim());
 const seen=new Set(),res=[];
 for(const [slot,chat] of destinations){
  if(seen.has(String(chat)))continue;
  seen.add(String(chat));
  const ref=row.id+":"+slot;
  // A unique D1 ledger constraint gives cross-run/channel deduplication.
  const claimed=await env.DB.prepare(
   "INSERT OR IGNORE INTO telegram_sent(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,settlement_status,claim_owner) "+
   "VALUES(?,?,?,?,?,0,'reserved','notstarted','neon-instant')"
  ).bind(crypto.randomUUID(),KIND,ref,date,new Date().toISOString()).run();
  if((claimed.meta?.changes||0)!==1){
   const prior=await env.DB.prepare(
    "SELECT delivery_status FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=?"
   ).bind(KIND,ref,date).first();
   res.push({destination:slot,status:prior?.delivery_status==="sent"?"sent":"unresolved"});
   continue;
  }
  const result=await send(env,chat,row,photo);
  if(result.status==="sent"){
   const marked=await env.DB.prepare(
    "UPDATE telegram_sent SET delivery_status='sent',telegram_message_id=?,published_at=? "+
    "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'"
   ).bind(result.message_id,new Date().toISOString(),KIND,ref,date).run();
   res.push({destination:slot,status:marked.meta?.changes===1?"sent":"unresolved"});
  }else if(result.status==="rejected"){
   // Definitive API rejection: safe to retry at next refresh, no message posted.
   await env.DB.prepare(
    "DELETE FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved' AND claim_owner='neon-instant'"
   ).bind(KIND,ref,date).run();
   res.push({destination:slot,status:"rejected"});
  }else{
   // Network ambiguity: retain claim to avoid accidentally double-posting.
   res.push({destination:slot,status:"unresolved"});
  }
 }
 return {prediction_id:row.id,deliveries:res,
  all_sent:res.length===destinations.length&&res.every(x=>x.status==="sent")};
}
export default {
 async fetch(req,env){
  const url=new URL(req.url);
  if(url.pathname==="/health"&&req.method==="GET")return json({
   service:"mrxpronos-neon-live-telegram-instant",
   ready:!!(env.DB&&env.NEON_DELIVERY_HMAC_KEY&&env.TELEGRAM_BOT_TOKEN&&env.TELEGRAM_CHAT_ID&&env.TELEGRAM_CHAT_ID_SECONDARY),
   mode:"post-commit",format:"original-live-svg-browser",sponsor_banner:"daily-utc-alternation",
   live_send:false
  });
  if(url.pathname!=="/deliver")return json({error:"not_found"},404);
  if(req.method!=="POST")return json({error:"method_not_allowed"},405);
  if(!env.DB||!env.NEON_DELIVERY_HMAC_KEY||!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID||!env.TELEGRAM_CHAT_ID_SECONDARY)
   return json({error:"not_configured"},503);
  if(Number(req.headers.get("content-length")||0)>16000)return json({error:"too_large"},413);
  const raw=await req.text();
  if(raw.length>16000)return json({error:"too_large"},413);
  if(!await verify(req,raw,env.NEON_DELIVERY_HMAC_KEY))return json({error:"unauthorized"},401);
  let data;try{data=JSON.parse(raw)}catch{return json({error:"invalid_json"},400)}
  if(!data||!Array.isArray(data.signals)||data.signals.length>4)return json({error:"invalid_payload"},400);
  if(data.signals.some(x=>!good(x)))return json({error:"invalid_signal"},422);
  const result=[];
  for(const s of data.signals)result.push(await dispatchOne(env,s));
  return json({ok:true,results:result,telegram_sent:result.reduce((n,p)=>n+p.deliveries.filter(d=>d.status==="sent").length,0),
   all_sent:result.every(x=>x.all_sent)});
 }
};
