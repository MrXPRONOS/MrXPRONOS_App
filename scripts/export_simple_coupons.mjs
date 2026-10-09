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
    generated_at: m.generated_at || data.generated_at || "",
    home_score: m.home_score,
    away_score: m.away_score,
    is_finished: Boolean(m.is_finished),
    paid_amount: Number(m?.paid_amount) > 0 ? Number(m.paid_amount) : null,
    potential_gain: Number(m?.potential_gain) > 0 ? Number(m.potential_gain) : null,
    home_team: m.home_team || "Équipe A",
    away_team: m.away_team || "Équipe B",
    league: m.league || m.league_name || "Compétition non renseignée",
    event_date: m.event_date || m.date || "",
    prediction: m?.prediction?.label || m?.prediction?.type || m?.prediction?.double_chance || m?.double_chance || "-",
    odds: Number(m?.prediction?.odds) > 0 ? Number(m.prediction.odds) : null,
    odds_source: m?.prediction?.odds_source || "",
    stake: Number(m?.actual_stake) > 0 ? Number(m.actual_stake) : null,
    score: m?.home_score != null && m?.away_score != null ? `${m.home_score}:${m.away_score}` : "VS",
    status: m?.is_finished ? "Terminé" : "Pronostic",
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
  const melbetLogo = new URL("assets/images/melbet.png", URL).href;
  const oddsText = match.odds ? Number(match.odds).toFixed(3) : "—";
  const stakeText = match.stake ? `${Math.round(match.stake).toLocaleString("fr-FR")} F` : "—";
  const paidText = match.paid_amount ? `${match.paid_amount.toLocaleString("fr-FR", {minimumFractionDigits:2,maximumFractionDigits:2})} F` : "—";
  const possibleGain = match.potential_gain || (match.stake && match.odds ? match.stake * match.odds : null);
  const gainText = possibleGain ? `${possibleGain.toLocaleString("fr-FR", {minimumFractionDigits:2,maximumFractionDigits:2})} F` : "—";
  const generatedLabel = match.generated_at ? eventDateLabel(match.generated_at) : "Date indisponible";
  const fixtureDate = eventDateLabel(match.event_date);

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
  * {box-sizing:border-box}
  html,body{margin:0;padding:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#123e64}
  body{width:430px}
  #coupon{width:430px;background:#f5f6f8;overflow:hidden}
  /* Les sponsors restent hors du ticket, comme un bandeau de partenariat. */
  .sponsor{height:53px;background:#0b0d13;display:flex;align-items:center;justify-content:space-between;gap:6px;padding:0 10px}
  .brand-wrap{display:flex;align-items:center;gap:7px;min-width:0}
  .brand-wrap img{width:82px;height:29px;object-fit:contain}
  .brand-or{font-size:12px;color:#eee;font-weight:700}
  .promo{background:#f5d339;border-radius:4px;color:#090909;padding:9px 8px;font-weight:900;font-size:11px;white-space:nowrap}
  .topbar{height:54px;display:grid;grid-template-columns:44px 1fr 76px;align-items:center;background:#fff;color:#5480a1}
  .topbar .back{font-size:34px;line-height:1;text-align:center;font-weight:300}
  .topbar .title{text-align:center;font-size:16px;font-weight:700;white-space:nowrap}
  .topbar .actions{display:flex;justify-content:space-evenly;align-items:center}
  .topbar .bell{font-size:20px;line-height:1;font-weight:400}
  .topbar .more{font-size:21px;letter-spacing:2px;line-height:1}
  .ticket-meta{height:69px;padding:8px 16px;display:flex;align-items:center;gap:12px;background:#fff;border-bottom:1px solid #e7ebef}
  .ball-wrap{position:relative;width:48px;height:48px;flex:none;border-radius:50%;background:#e8eff5;display:grid;place-items:center;color:#809eb3}
  .ball-wrap .ball{font-size:25px;filter:grayscale(1);opacity:.56}
  .ball-wrap .tick{position:absolute;right:0;bottom:-1px;display:grid;place-items:center;border:2px solid white;border-radius:50%;width:20px;height:20px;background:#4d93d4;color:#fff;font-size:13px;font-weight:700}
  .head-text{min-width:0;line-height:1.15}
  .head-time{font-size:12px;color:#5c829e;font-weight:700}
  .head-type{font-size:17px;line-height:1.15;font-weight:800;color:#15436c}
  .head-id{font-size:10px;color:#214c71;font-weight:700;margin-top:3px}
  .summary{background:#fff;padding:9px 15px 9px}
  .summary-row{min-height:25px;display:flex;align-items:center;justify-content:space-between;gap:12px}
  .summary-row .label{font-weight:700;color:#5a83a0;font-size:15.5px}
  .summary-row .value{font-weight:800;color:#0c3962;font-size:15.5px;white-space:nowrap}
  .summary-row .value.status{color:#4796d7}
  .fixture-wrap{padding:5px 4px 0;background:#f0f2f6}
  .fixture{border-radius:15px 15px 0 0;background:#fff;overflow:hidden;border:5px solid #f0f2f6;border-bottom:0}
  .fixture-head{height:53px;padding:8px 11px;display:flex;align-items:center;gap:9px}
  .fixture-head .small-ball{font-size:21px;filter:grayscale(1);opacity:.54;width:27px;flex:none}
  .fixture-meta{min-width:0}
  .league{font-size:12px;font-weight:700;color:#5e839f;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:348px}
  .fixture-date{font-size:12px;font-weight:700;color:#6588a4;margin-top:2px}
  .teams{min-height:52px;display:grid;grid-template-columns:minmax(0,1fr) 40px minmax(0,1fr);align-items:center;padding:1px 12px 9px;column-gap:4px}
  .team{display:flex;align-items:center;gap:8px;min-width:0}
  .team.home{justify-content:flex-end}
  .team.away{justify-content:flex-start}
  .team-name{min-width:0;max-width:132px;font-size:13px;font-weight:800;line-height:1.17;color:#123e67;overflow-wrap:anywhere}
  .home .team-name{text-align:right}
  .away .team-name{text-align:left}
  .team-logo{height:33px;width:33px;flex:none;object-fit:contain}
  .team-fallback{height:33px;width:33px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#edf3f8;color:#507896;border:1px solid #dce6ed;font-size:10px;font-weight:800}
  .vs{font-size:21px;line-height:1;font-weight:900;color:#0d416e;text-align:center}
  .separator{height:1px;background:#e5ebf0}
  .market-row{min-height:30px;padding:5px 14px;display:flex;align-items:center;justify-content:space-between;gap:12px}
  .market-label{font-size:13px;line-height:1.15;font-weight:800;color:#123c64;min-width:0}
  .market-odd{font-size:14px;font-weight:800;color:#123c64;white-space:nowrap}
  .footer-status{min-height:29px;padding:5px 14px;display:flex;justify-content:space-between;align-items:center}
  .footer-status .label{font-size:13px;font-weight:700;color:#5b829e}
  .footer-status .value{font-size:14px;font-weight:800;color:#4e99dc}
  .responsible{height:30px;background:#fff;border-top:1px solid #e9edf1;display:grid;place-items:center;font-size:11px;font-weight:700;color:#7791a6}
</style>
</head>
<body>
  <div id="coupon">
    <div class="sponsor">
      <div class="brand-wrap"><img src="${esc(oneXbetLogo)}" alt="1XBET"><span class="brand-or">ou</span><img src="${esc(melbetLogo)}" alt="MELBET"></div>
      <div class="promo">Code Promo: XPVIP</div>
    </div>
    <div class="topbar">
      <span class="back">‹</span>
      <span class="title">Informations sur le pari</span>
      <div class="actions"><span class="bell">♧</span><span class="more">•••</span></div>
    </div>
    <div class="ticket-meta">
      <span class="ball-wrap"><span class="ball">⚽</span><span class="tick">✓</span></span>
      <div class="head-text">
        <div class="head-time">${esc(generatedLabel)}</div>
        <div class="head-type">Simple</div>
        <div class="head-id">N° ${esc(match.match_id)}</div>
      </div>
    </div>
    <div class="summary">
      <div class="summary-row"><span class="label">Cotes:</span><span class="value">${esc(oddsText)}</span></div>
      <div class="summary-row"><span class="label">Mise:</span><span class="value">${esc(stakeText)}</span></div>
      <div class="summary-row"><span class="label">Versé:</span><span class="value">${esc(paidText)}</span></div>
      <div class="summary-row"><span class="label">Gains potentiels:</span><span class="value">${esc(gainText)}</span></div>
      <div class="summary-row"><span class="label">Statut:</span><span class="value status">${esc(match.status)}</span></div>
    </div>
    <div class="fixture-wrap">
      <div class="fixture">
        <div class="fixture-head">
          <span class="small-ball">⚽</span>
          <div class="fixture-meta">
            <div class="league">Football · ${esc(match.league)}</div>
            <div class="fixture-date">${esc(fixtureDate)}</div>
          </div>
        </div>
        <div class="teams">
          <div class="team home"><div class="team-name">${esc(match.home_team)}</div>${homeVisual}</div>
          <div class="vs">${esc(match.score)}</div>
          <div class="team away">${awayVisual}<div class="team-name">${esc(match.away_team)}</div></div>
        </div>
        <div class="separator"></div>
        <div class="market-row">
          <span class="market-label">${esc(predictionLabel(match.prediction))}</span>
          <span class="market-odd">${esc(oddsText)}</span>
        </div>
        <div class="footer-status"><span class="label">Statut:</span><span class="value">${esc(match.status)}</span></div>
      </div>
    </div>
    <div class="responsible">Parier responsablement.</div>
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
    viewport: { width: 460, height: 720 },
    deviceScaleFactor: 3,
  });

  let exported = 0;

  for (let i = 0; i < picked.length; i++){
    const match = picked[i];

    await page.setContent(couponHtml(match), { waitUntil: "domcontentloaded" });

    await page.waitForFunction(() => {
      const images = Array.from(document.images);
      return images.every(img => img.complete);
    }, null, { timeout: 12000 }).catch(() => {});

    await page.evaluate(() => {
      document.querySelectorAll("img.team-logo").forEach(img => {
        if (!img.complete || img.naturalWidth === 0) img.dispatchEvent(new Event("error"));
      });
    });
    await page.waitForTimeout(150);

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

  console.log(`Export terminé: ${exported}/${picked.length} coupons fidèles au ticket clair -> ${OUT_DIR}/`);
  await browser.close();
})();
