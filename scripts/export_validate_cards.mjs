import fs from "fs";
import path from "path";
import { chromium } from "playwright";

const OUT_DIR = process.env.OUT_DIR || "telegram_out";
const EXPORT_URL = process.env.EXPORT_URL || "http://127.0.0.1:8000/pronos.html";
const LIST_FILE = process.env.LIST_FILE || path.join(OUT_DIR, "validate_list.json");

fs.mkdirSync(OUT_DIR, { recursive: true });

function pad(n){ return String(n).padStart(2,"0"); }

(async () => {
  if (!fs.existsSync(LIST_FILE)) {
    console.log("validate_list.json introuvable:", LIST_FILE);
    process.exit(0);
  }

  const payload = JSON.parse(fs.readFileSync(LIST_FILE, "utf-8"));
  const items = Array.isArray(payload?.items) ? payload.items : [];
  if (!items.length) {
    console.log("Aucun item à exporter.");
    process.exit(0);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });

  await page.addInitScript(() => {
    localStorage.setItem("mx_push_snooze_until", String(Date.now() + 365*24*60*60*1000));
    localStorage.setItem("iosGuideLastClosed", String(Date.now()));
  });

  await page.goto(EXPORT_URL, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#matches-container .match-card", { timeout: 30000 });

  // Switch Simple + Yesterday
  await page.evaluate(() => {
    document.querySelector('.tab-btn[data-cat="simple"]')?.click();
    document.querySelector('.day-btn[data-day="yesterday"]')?.click();
  });

  await page.waitForTimeout(1200);

  await page.addStyleTag({
    content: `
      header, footer, #share-popup, #push-permission, .ios-guide-popup { display:none !important; }
      body { padding-top: 0 !important; }
      .btn-share, .btn, .vip-locked-overlay { display:none !important; }

      /* badge résultat injecté */
      .tg-result{
        position:absolute;
        top:10px;
        left:10px;
        padding:6px 10px;
        border-radius:999px;
        font-weight:900;
        font-size:12px;
        background:rgba(0,0,0,.70);
        border:1px solid rgba(255,255,255,.12);
        z-index:50;
      }
      .tg-win{ color:#22C55E; border-color: rgba(34,197,94,.55); }
      .tg-lose{ color:#FF6B6B; border-color: rgba(255,107,107,.55); }
    `,
  });

  // Injecter badge win/lose selon la liste
  await page.evaluate((items) => {
    items.forEach(it => {
      const id = String(it.match_id || "");
      if (!id) return;
      const card = document.querySelector(`#matches-container .match-card[data-matchid="${CSS.escape(id)}"]`);
      if (!card) return;
      if (card.querySelector(".tg-result")) return;

      const badge = document.createElement("div");
      badge.className = "tg-result " + (it.outcome === "win" ? "tg-win" : "tg-lose");
      badge.textContent = it.outcome === "win" ? "✅ VALIDÉ" : "❌ ÉCHOUÉ";
      card.appendChild(badge);
    });
  }, items);

  let exported = 0;

  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    const matchId = String(it.match_id || "");
    if (!matchId) continue;

    const locator = page.locator(`#matches-container .match-card[data-matchid="${matchId}"]`).first();
    const count = await locator.count();
    if (!count) {
      console.log("Carte introuvable pour match_id:", matchId);
      continue;
    }

    const fileName = it.file || `yesterday_${pad(i+1)}.png`;
    const outPath = path.join(OUT_DIR, fileName);

    await locator.screenshot({ path: outPath });
    exported += 1;
  }

  console.log(`Export validation terminé: ${exported}/${items.length} images -> ${OUT_DIR}/`);
  await browser.close();
})();