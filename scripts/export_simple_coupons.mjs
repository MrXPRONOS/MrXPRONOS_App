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
    home_team: m.home_team,
    away_team: m.away_team,
    league: m.league,
    event_date: m.event_date,
    prediction: m?.prediction?.double_chance || null,
    confidence: m?.prediction?.confidence || null
  }));
}

(async () => {
  const picked = pickTopSimpleToday(LIMIT);

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });

  await page.addInitScript(() => {
    localStorage.setItem("mx_push_snooze_until", String(Date.now() + 365*24*60*60*1000));
    localStorage.setItem("iosGuideLastClosed", String(Date.now()));
  });

  // 1. Aller sur la page et attendre le chargement initial
  await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 });

  // 2. Attendre que le container des matchs existe au moins (même vide)
  await page.waitForSelector("#matches-container", { timeout: 30000 });

  // 3. Attendre que le script JavaScript ait fini de charger les données
  //    On attend que le texte "Chargement" disparaisse OU que les cartes apparaissent
  await page.waitForFunction(
    () => {
      const container = document.querySelector("#matches-container");
      if (!container) return false;
      // Si le texte "Chargement" est présent, on attend qu'il disparaisse
      const loading = container.innerText.includes("Chargement");
      if (loading) return false;
      // Sinon, on considère que c'est prêt (même s'il n'y a pas de cartes)
      return true;
    },
    { timeout: 30000 }
  );

  // 4. Sélectionner l'onglet "simple" et le jour "today"
  await page.evaluate(() => {
    const simpleBtn = document.querySelector('.tab-btn[data-cat="simple"]');
    if (simpleBtn) simpleBtn.click();
    const todayBtn = document.querySelector('.day-btn[data-day="today"]');
    if (todayBtn) todayBtn.click();
  });

  // 5. Attendre que le contenu se mette à jour (les cartes apparaissent)
  await page.waitForSelector("#matches-container .match-card", { timeout: 30000 });

  // 6. Masquer les éléments inutiles
  await page.addStyleTag({
    content: `
      header, footer, #share-popup, #push-permission, .ios-guide-popup { display:none !important; }
      body { padding-top: 0 !important; }
      .btn-share, .btn, .vip-locked-overlay { display:none !important; }
    `,
  });

  const cards = await page.$$("#matches-container .match-card");
  const n = Math.min(LIMIT, cards.length, picked.length);

  if (n <= 0) {
    console.log("Aucun match simple aujourd'hui.");
    await browser.close();
    process.exit(0);
  }

  for (let i = 0; i < n; i++){
    const file = path.join(OUT_DIR, `simple_${pad(i+1)}.png`);
    await cards[i].screenshot({ path: file });
  }

  const manifest = {
    kind: "daily_simple",
    date: todayUtc(),
    count: n,
    matches: picked.slice(0, n)
  };
  fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2), "utf-8");

  console.log(`Export terminé: ${n}/${cards.length} cartes -> ${OUT_DIR}/ (manifest.json créé)`);
  await browser.close();
})();