import fs from "fs";
import path from "path";
import { chromium } from "playwright";

const OUT_DIR = process.env.OUT_DIR || "telegram_out";
const URL = process.env.EXPORT_URL || "http://127.0.0.1:8000/pronos.html";
const LIMIT = Number(process.env.LIMIT || "5");

fs.mkdirSync(OUT_DIR, { recursive: true });

function pad(n) {
  return String(n).padStart(2, "0");
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1400, height: 900 },
    deviceScaleFactor: 2,
  });

  // évite popups
  await page.addInitScript(() => {
    localStorage.setItem("mx_push_snooze_until", String(Date.now() + 365 * 24 * 60 * 60 * 1000));
    localStorage.setItem("iosGuideLastClosed", String(Date.now()));
  });

  await page.goto(URL, { waitUntil: "domcontentloaded" });

  // attend rendu initial
  await page.waitForSelector("#matches-container .match-card", { timeout: 30000 });

  // force onglet Simple + Aujourd'hui
  await page.evaluate(() => {
    document.querySelector('.tab-btn[data-cat="simple"]')?.click();
    document.querySelector('.day-btn[data-day="today"]')?.click();
  });

  await page.waitForTimeout(1200);
  await page.waitForSelector("#matches-container .match-card", { timeout: 30000 });

  // CSS uniquement pour la capture (on enlève les boutons du site)
  await page.addStyleTag({
    content: `
      header, footer, #share-popup, #push-permission, .ios-guide-popup { display:none !important; }
      body { padding-top: 0 !important; }
      .btn-share, .btn, .vip-locked-overlay { display:none !important; }
    `,
  });

  const cards = await page.$$("#matches-container .match-card");
  if (!cards.length) {
    console.log("Aucune carte trouvée.");
    await browser.close();
    process.exit(0);
  }

  const take = cards.slice(0, LIMIT);
  let i = 0;
  for (const card of take) {
    i += 1;
    const file = path.join(OUT_DIR, `simple_${pad(i)}.png`);
    await card.screenshot({ path: file });
  }

  console.log(`Export terminé: ${take.length}/${cards.length} cartes -> ${OUT_DIR}/`);
  await browser.close();
})();