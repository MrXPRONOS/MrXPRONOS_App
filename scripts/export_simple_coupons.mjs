import fs from "fs";
import path from "path";
import { chromium } from "playwright";

const OUT_DIR = process.env.OUT_DIR || "telegram_out";
const URL = process.env.EXPORT_URL || "http://127.0.0.1:8000/pronos.html";
const LIMIT = Number(process.env.LIMIT || "5");

fs.mkdirSync(OUT_DIR, { recursive: true });

const POPULAR_LEAGUES = [
  "Premier League","LaLiga","Serie A","Bundesliga","Ligue 1","Eredivisie","Primeira Liga",
  "Super Lig","Russian Premier League","MLS","Brasileirão","Liga Profesional","Jupiler Pro League",
  "Super League","Championship","Liga Portugal","Trendyol Super Lig",
];

function pad(n){ return String(n).padStart(2,"0"); }
function todayUtc(){ return new Date().toISOString().slice(0,10); }

function sortMatchesByLeague(matches){
  return matches.sort((a,b) => {
    const leagueA = a.league || "";
    const leagueB = b.league || "";
    const ia = POPULAR_LEAGUES.findIndex(l => leagueA.includes(l) || leagueA === l);
    const ib = POPULAR_LEAGUES.findIndex(l => leagueB.includes(l) || leagueB === l);
    const ra = ia === -1 ? 999 : ia;
    const rb = ib === -1 ? 999 : ib;
    if (ra !== rb) return ra - rb;
    return new Date(a.event_date || 0) - new Date(b.event_date || 0);
  });
}

function firstNonEmpty(...values){
  for (const value of values){
    if (value !== undefined && value !== null && String(value).trim()) return value;
  }
  return "";
}

function pickLogo(m, side){
  const raw = m?.raw_data || {};
  const obj = side === "home" ? (m?.home_team_obj || raw?.home_team_obj || {}) : (m?.away_team_obj || raw?.away_team_obj || {});
  const nested = side === "home" ? (m?.home || raw?.home || {}) : (m?.away || raw?.away || {});
  return String(firstNonEmpty(
    side === "home" ? m?.home_logo : m?.away_logo,
    side === "home" ? m?.home_team_logo : m?.away_team_logo,
    obj?.logo,
    obj?.image,
    nested?.logo,
    nested?.image,
    nested?.team?.logo,
    nested?.team?.image,
    side === "home" ? m?.home_logo_url : m?.away_logo_url,
    side === "home" ? raw?.home_logo : raw?.away_logo,
    ""
  ) || "");
}

function pickTopSimpleToday(limit){
  const data = JSON.parse(fs.readFileSync("data.json","utf-8"));
  const t = todayUtc();
  const matches = Array.isArray(data?.matches) ? data.matches : [];
  const filtered = matches.filter(m =>
    m?.category === "simple" &&
    (String(m?.event_date || "").slice(0,10) === t || String(m?.date || "").slice(0,10) === t)
  );

  const sorted = sortMatchesByLeague(filtered);

  return sorted.slice(0, limit).map(m => ({
    match_id: String(m.id),
    home_team: m.home_team || "Équipe A",
    away_team: m.away_team || "Équipe B",
    league: m.league || m.league_name || "Football",
    event_date: m.event_date || m.date || "",
    prediction: m?.prediction?.double_chance || m?.double_chance || "-",
    confidence: m?.prediction?.confidence || m?.confidence || null,
    home_logo: pickLogo(m, "home"),
    away_logo: pickLogo(m, "away"),
  }));
}

function esc(value){
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function eventDateLabel(value){
  if (!value) return todayUtc();
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return String(value).slice(0,16);
  return new Intl.DateTimeFormat("fr-FR", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d).replace(",", " ·");
}

function predictionLabel(value){
  const p = String(value || "-").trim().toUpperCase();
  if (p === "1X") return "Double chance · 1X";
  if (p === "X2") return "Double chance · X2";
  if (p === "12") return "Double chance · 12";
  return String(value || "Pronostic");
}

function asAssetUrl(value){
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^(https?:|data:|blob:)/i.test(raw)) return raw;
  try { return new URL(raw.replace(/^\.\//, ""), URL).href; }
  catch { return raw; }
}

function initials(name){
  const words = String(name || "").replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "MX";
  if (words.length === 1) return words[0].slice(0,2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function couponHtml(match){
  const homeLogo = asAssetUrl(match.home_logo);
  const awayLogo = asAssetUrl(match.away_logo);
  const oneXbetLogo = new URL("assets/images/1xbet.png", URL).href;

  const homeVisual = homeLogo
    ? `<img class="team-logo" src="${esc(homeLogo)}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="team-fallback" style="display:none">${esc(initials(match.home_team))}</div>`
    : `<div class="team-fallback">${esc(initials(match.home_team))}</div>`;

  const awayVisual = awayLogo
    ? `<img class="team-logo" src="${esc(awayLogo)}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="team-fallback" style="display:none">${esc(initials(match.away_team))}</div>`
    : `<div class="team-fallback">${esc(initials(match.away_team))}</div>`;

  return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<base href="${esc(URL)}">
<style>
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;background:#0f2639;font-family:Arial,Helvetica,sans-serif}
  body{width:920px;min-height:700px;color:#f4f7fa}

  #coupon{
    width:920px;
    background:#173149;
    color:#f4f7fa;
    border:1px solid #2a455d;
    overflow:hidden;
  }

  .topbar{
    height:112px;
    background:#020202;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 24px;
  }

  .brand-wrap{display:flex;align-items:center;height:100%}
  .brand-wrap img{
    width:235px;
    max-height:82px;
    object-fit:contain;
    object-position:left center;
  }

  .promo{
    min-width:410px;
    height:68px;
    background:#efd338;
    color:#050505;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:0 26px;
    font-size:34px;
    font-weight:900;
    letter-spacing:-1.2px;
    white-space:nowrap;
  }

  .summary{
    background:#18344f;
    border-bottom:1px solid #36536d;
    padding:22px 28px 20px;
  }

  .summary-row{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:20px;
  }

  .events{
    display:flex;
    align-items:center;
    font-size:28px;
    font-weight:600;
    color:#dbe6ef;
  }
  .events-icon{
    margin-right:11px;
    color:#93a8ba;
    font-size:25px;
  }
  .finished{
    font-size:26px;
    color:#e2eaf0;
  }

  .status-row{
    margin-top:18px;
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-size:27px;
  }
  .status-label{color:#8ca2b5}
  .accepted{color:#4b96df;font-weight:700}

  .event-card{
    margin:14px 16px 20px;
    background:#163149;
    border:1px solid #0e273b;
    border-radius:24px;
    overflow:hidden;
    box-shadow:0 4px 10px rgba(0,0,0,.18);
  }

  .event-head{
    display:flex;
    align-items:center;
    padding:20px 22px 13px;
    color:#91a5b7;
  }
  .ball{
    width:38px;height:38px;border:2px solid #7d91a3;border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    margin-right:13px;font-size:22px;flex:0 0 auto;
  }
  .event-meta{display:flex;flex-direction:column;gap:4px}
  .league{font-size:21px;color:#93a6b7}
  .date{font-size:20px;color:#8da1b3}

  .teams{
    min-height:190px;
    display:grid;
    grid-template-columns:1fr 110px 1fr;
    align-items:center;
    gap:10px;
    padding:10px 24px 22px;
  }

  .team{
    display:flex;
    align-items:center;
    min-width:0;
  }
  .team.home{justify-content:flex-end}
  .team.away{justify-content:flex-start}

  .team-name{
    font-size:28px;
    font-weight:600;
    line-height:1.12;
    color:#f5f8fa;
    max-width:245px;
  }
  .home .team-name{text-align:right;margin-right:14px}
  .away .team-name{text-align:left;margin-left:14px}

  .team-logo{
    width:72px;height:72px;object-fit:contain;flex:0 0 auto;
  }
  .team-fallback{
    width:72px;height:72px;border-radius:50%;
    border:3px solid #4b96df;color:#4b96df;
    align-items:center;justify-content:center;
    font-size:25px;font-weight:900;flex:0 0 auto;
  }

  .vs{
    display:flex;align-items:center;justify-content:center;
    color:#f5f7f9;font-size:34px;font-weight:500;
  }

  .separator{height:1px;background:#2f4b63;width:100%}

  .pick-row{
    min-height:105px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:18px 24px;
  }
  .pick-left{display:flex;flex-direction:column;gap:8px}
  .pick-caption{font-size:21px;color:#8fa4b6}
  .pick-value{font-size:30px;font-weight:700;color:#f8fafc}
  .pick-status{font-size:26px;color:#4b96df;font-weight:700}

  .footer-status{
    min-height:70px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 24px;
    font-size:25px;
  }
  .footer-status .label{color:#8fa4b6}

  .responsible{
    height:64px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#10273a;
    border-top:1px solid #29465f;
    color:#8198aa;
    font-size:18px;
    letter-spacing:.1px;
  }
</style>
</head>
<body>
  <div id="coupon">
    <div class="topbar">
      <div class="brand-wrap"><img src="${esc(oneXbetLogo)}" alt="1XBET"></div>
      <div class="promo">CODE PROMO XPVIP</div>
    </div>

    <div class="summary">
      <div class="summary-row">
        <div class="events"><span class="events-icon">▰</span>Événements : 1</div>
        <div class="finished">0 sur 1 terminé</div>
      </div>
      <div class="status-row">
        <div class="status-label">Statut:</div>
        <div class="accepted">Accepté</div>
      </div>
    </div>

    <div class="event-card">
      <div class="event-head">
        <div class="ball">⚽</div>
        <div class="event-meta">
          <div class="league">Football · ${esc(match.league)}</div>
          <div class="date">${esc(eventDateLabel(match.event_date))}</div>
        </div>
      </div>

      <div class="teams">
        <div class="team home">
          <div class="team-name">${esc(match.home_team)}</div>
          ${homeVisual}
        </div>

        <div class="vs">VS</div>

        <div class="team away">
          ${awayVisual}
          <div class="team-name">${esc(match.away_team)}</div>
        </div>
      </div>

      <div class="separator"></div>

      <div class="pick-row">
        <div class="pick-left">
          <div class="pick-caption">Pronostic Mr XPRONOS</div>
          <div class="pick-value">${esc(predictionLabel(match.prediction))}</div>
        </div>
        <div class="pick-status">Accepté</div>
      </div>

      <div class="separator"></div>

      <div class="footer-status">
        <div class="label">Statut:</div>
        <div class="accepted">Accepté</div>
      </div>
    </div>

    <div class="responsible">18+ · Joue responsablement · Mr XPRONOS</div>
  </div>
</body>
</html>`;
}

(async () => {
  const picked = pickTopSimpleToday(LIMIT);

  if (!picked.length) {
    console.log("Aucun match simple aujourd'hui.");
    process.exit(0);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 980, height: 900 },
    deviceScaleFactor: 2,
  });

  let exported = 0;

  for (let i = 0; i < picked.length; i++){
    const match = picked[i];

    await page.setContent(couponHtml(match), { waitUntil: "domcontentloaded" });

    await page.waitForFunction(() => {
      const images = Array.from(document.images);
      return images.every(img => img.complete);
    }, { timeout: 10000 }).catch(() => {});

    await page.waitForTimeout(250);

    const coupon = page.locator("#coupon").first();
    const file = path.join(OUT_DIR, `simple_${pad(i+1)}.png`);
    await coupon.screenshot({ path: file });
    exported++;
  }

  const manifest = {
    kind: "daily_simple",
    date: todayUtc(),
    count: exported,
    matches: picked.slice(0, exported),
  };

  fs.writeFileSync(
    path.join(OUT_DIR, "manifest.json"),
    JSON.stringify(manifest, null, 2),
    "utf-8",
  );

  console.log(`Export terminé: ${exported}/${picked.length} coupons style 1xBet -> ${OUT_DIR}/`);
  await browser.close();
})();
