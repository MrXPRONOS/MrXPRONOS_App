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

// Sélectionne jusqu'à 'limit' matchs du jour, dans l'ordre : simple, pro, vip
function pickTopPronos(limit) {
  const data = JSON.parse(fs.readFileSync("data.json", "utf-8"));
  const t = todayUtc();
  const allMatches = Array.isArray(data?.matches) ? data.matches : [];
  const todayMatches = allMatches.filter(m => {
    const d = (m.event_date || m.date || "").slice(0,10);
    return d === t;
  });

  const simple = todayMatches.filter(m => m.category === "simple");
  const pro   = todayMatches.filter(m => m.category === "pro");
  const vip   = todayMatches.filter(m => m.category === "vip");

  const ordered = [
    ...sortMatchesByLeague(simple),
    ...sortMatchesByLeague(pro),
    ...sortMatchesByLeague(vip)
  ];

  return ordered.slice(0, limit).map(m => ({
    match_id: String(m.id),
    home_team: m.home_team,
    away_team: m.away_team,
    league: m.league,
    event_date: m.event_date,
    prediction: m?.prediction?.double_chance || null,
    confidence: m?.prediction?.confidence || null,
    category: m.category
  }));
}

// Attend que le chargement des matchs soit terminé (disparition du texte "Chargement")
async function waitForMatchesToLoad(page) {
  await page.waitForSelector("#matches-container", { timeout: 30000 });
  await page.waitForFunction(
    () => {
      const container = document.querySelector("#matches-container");
      if (!container) return false;
      return !container.innerText.includes("Chargement");
    },
    { timeout: 30000 }
  );
}

// Simule un partage pour débloquer les catégories pro/vip
async function unlockCategory(page, category) {
  if (category === "simple") return; // pas besoin
  // Vérifier si déjà débloqué (nombre de partages >=1)
  const shareCount = await page.evaluate(() => {
    const lastReset = localStorage.getItem("shareLastReset");
    const today = new Date().toDateString();
    if (lastReset !== today) return 0;
    return parseInt(localStorage.getItem("shareCount") || "0", 10);
  });
  if (shareCount >= 1) return; // déjà débloqué

  // Forcer le déblocage en définissant directement les valeurs
  await page.evaluate(() => {
    const today = new Date().toDateString();
    localStorage.setItem("shareLastReset", today);
    localStorage.setItem("shareCount", "1");
    // Déclencher manuellement la mise à jour de l'interface
    const event = new Event("storage");
    window.dispatchEvent(event);
  });
  // Attendre un court instant que l'UI se mette à jour
  await page.waitForTimeout(500);
}

async function captureCardForMatch(page, match, outputPath) {
  // Chercher la carte avec data-matchid
  const cardSelector = `#matches-container .match-card[data-matchid="${match.match_id}"]`;
  await page.waitForSelector(cardSelector, { timeout: 10000 });
  const card = await page.$(cardSelector);
  if (!card) throw new Error(`Carte non trouvée pour le match ${match.match_id}`);
  await card.screenshot({ path: outputPath });
}

(async () => {
  const selectedMatches = pickTopPronos(LIMIT);
  if (selectedMatches.length === 0) {
    console.log("Aucun match du jour.");
    process.exit(0);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });

  await page.addInitScript(() => {
    localStorage.setItem("mx_push_snooze_until", String(Date.now() + 365*24*60*60*1000));
    localStorage.setItem("iosGuideLastClosed", String(Date.now()));
  });

  await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 });
  await waitForMatchesToLoad(page);

  // Masquer les éléments superflus (header, footer, boutons, etc.) une fois pour toutes
  await page.addStyleTag({
    content: `
      header, footer, #share-popup, #push-permission, .ios-guide-popup { display:none !important; }
      body { padding-top: 0 !important; }
      .btn-share, .btn, .vip-locked-overlay { display:none !important; }
    `,
  });

  let captured = 0;
  const manifests = [];

  // On va traiter les matchs dans l'ordre, en changeant de catégorie si nécessaire
  let currentCategory = null;

  for (const match of selectedMatches) {
    const cat = match.category;
    if (cat !== currentCategory) {
      // Changer d'onglet
      await page.evaluate((c) => {
        const btn = document.querySelector(`.tab-btn[data-cat="${c}"]`);
        if (btn) btn.click();
      }, cat);
      // Débloquer la catégorie si besoin (pro/vip)
      await unlockCategory(page, cat);
      // Attendre le rechargement des cartes après changement d'onglet
      await waitForMatchesToLoad(page);
      currentCategory = cat;
    }

    const filename = `simple_${pad(captured+1)}.png`;
    const outPath = path.join(OUT_DIR, filename);
    await captureCardForMatch(page, match, outPath);
    manifests.push({
      ...match,
      file: filename,
    });
    captured++;
  }

  // Écrire le manifest
  const manifest = {
    kind: "daily_pronos",
    date: todayUtc(),
    count: captured,
    matches: manifests
  };
  fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2), "utf-8");

  console.log(`Export terminé: ${captured}/${selectedMatches.length} cartes -> ${OUT_DIR}/ (manifest.json créé)`);
  await browser.close();
})();