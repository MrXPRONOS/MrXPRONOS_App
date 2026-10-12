import { BOOKS } from "./bonus-catalogue.js";

const select = document.getElementById("bonus-bookmaker-select");
const grid = document.getElementById("bonus-grid");
const modal = document.getElementById("bonus-modal");

const text = (v) => String(v ?? "");
const esc = (v) => text(v).replace(/[&<>"']/g, (c) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[c]));

const validLink = (u) => {
  try {
    const v = new URL(u);
    return ["https:", "http:"].includes(v.protocol) ? v.href : "";
  } catch {
    return "";
  }
};

const BONUS_IMAGES = {
  "1xBet": [
    "1xbet-bonus-premier-depot-100.webp",
    "1xbet-hyper-bonus-250.webp",
    "1xbet-lucky-friday.webp",
    "1xbet-crypto-freebet.webp",
    "1xbet-pari-sans-risque.webp",
  ],
  "1win": [
    "1win-bienvenue.webp",
    "1win-bonus-recharge.webp",
    "1win-bonus-casino.webp",
    "1win-recompenses-fidelite.webp",
    "1win-promotions-evenementielles.webp",
  ],
  "Betwinner": [
    "betwinner-bienvenue.webp",
    "betwinner-sports-cashback.webp",
    "betwinner-bonus-jeudi.webp",
    "betwinner-serie-perdants.webp",
    "betwinner-bonus-toto.webp",
  ],
  "Melbet": [
    "melbet-bonus-premier-depot-sport.webp",
    "melbet-pack-bienvenue-casino.webp",
    "melbet-cashback-app.webp",
    "melbet-cashback-rewards.webp",
    "melbet-toto-points-bonus.webp",
  ],
  "Linebet": [
    "linebet-bonus-premier-depot-sport.webp",
    "linebet-pack-casino-games.webp",
    "linebet-bonus-depot-recurrent.webp",
    "linebet-paris-gratuits-offres-sport.webp",
    "linebet-recompenses-promo-codes.webp",
  ],
  "Betclic": [
    "betclic-offre-bienvenue-100e.webp",
    "betclic-cotes-boostees.webp",
    "betclic-freebets-evenementiels.webp",
    "betclic-challenges-missions.webp",
    "betclic-parrainage.webp",
  ],
};

const imagePath = (book, index) => {
  const file = BONUS_IMAGES[book.name]?.[index];
  return file
    ? `assets/images/bonus/${file}?v=20261012-hq2`
    : logoPath(book);
};
const logoPath = (book) => book.logo.replace("../", "");

const active = BOOKS.flatMap((b) => b.bonuses.map((x, i) => ({ book: b, offer: x, index: i })));
const desc = "Promotions vérifiées avec les liens officiels disponibles, mais les montants, dates, pays éligibles et conditions peuvent changer. Vérifiez toujours la page officielle avant de déposer.";

function render() {
  const chosen = select.value;
  const list = active.filter((x) => chosen === "all" || x.book.name === chosen);

  grid.innerHTML = list.map(({ book: b, offer: o, index: i }) => {
    const banner = imagePath(b, i);
    const logo = logoPath(b);
    return `
      <article class="bonus-premium-card bonus-bookmaker-card" data-book="${esc(b.name)}">
        <div class="bonus-card-art">
          <img class="bonus-banner-img" src="${esc(banner)}" alt="Visuel promotionnel ${esc(b.name)} — ${esc(o[1])}" loading="lazy" onerror="this.onerror=null;this.src='${esc(logo)}';this.classList.add('is-logo-fallback');">
          <span class="bonus-card-badge">${esc(o[0])}</span>
        </div>
        <div class="bonus-card-body">
          <small class="mx-offer-book">${esc(b.name)}</small>
          <h3>${esc(o[1])}</h3>
          <strong class="mx-offer-value">${esc(o[2])}</strong>
          <p>${esc(o[3])}</p>
          <span class="mx-offer-status">À confirmer auprès du bookmaker</span>
          <div class="bonus-actions">
            <button class="btn btn-primary" type="button" data-book="${esc(b.name)}" data-index="${i}">Voir les détails</button>
            <a class="btn btn-secondary" href="${esc(validLink(o[6]))}" target="_blank" rel="noopener noreferrer">Conditions officielles</a>
          </div>
        </div>
      </article>`;
  }).join("");

  if (!list.length) grid.innerHTML = '<p>Aucune promotion trouvée.</p>';
}

select.innerHTML = '<option value="all">Tous les bookmakers (30 offres)</option>' + BOOKS.map((b) => `<option value="${esc(b.name)}">${esc(b.name)} (5 offres)</option>`).join("");
select.addEventListener("change", render);

grid.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-index]");
  if (!button) return;

  const b = BOOKS.find((book) => book.name === button.dataset.book);
  const i = Number(button.dataset.index);
  const o = b?.bonuses[i];
  if (!o) return;

  const modalImage = document.getElementById("bonus-modal-image");
  modalImage.src = imagePath(b, i);
  modalImage.alt = `Visuel promotionnel ${b.name} — ${o[1]}`;
  modalImage.onerror = (e) => {
    e.currentTarget.src = logoPath(b);
    e.currentTarget.onerror = null;
  };

  document.getElementById("bonus-modal-title").textContent = `${b.name} · ${o[1]} · ${o[2]}`;
  document.getElementById("bonus-modal-description").innerHTML =
    `<p>${esc(o[3])}</p><h4>Conditions mentionnées dans Prono Live</h4><ul>` +
    o[4].map((t) => `<li>${esc(t)}</li>`).join("") +
    `</ul><h4>Marche à suivre</h4><ol>` +
    o[5].map((t) => `<li>${esc(t)}</li>`).join("") +
    `</ol><p class="mx-offer-warning">${esc(desc)}</p>`;

  document.getElementById("bonus-modal-footer").innerHTML = `<a href="${esc(validLink(o[6]))}" target="_blank" rel="noopener noreferrer">Consulter les conditions officielles ↗</a> · Code partenaire : ${esc(b.code)}`;

  const link = document.getElementById("bonus-modal-link");
  link.href = validLink(b.url);
  link.rel = "sponsored noopener noreferrer";
  modal.style.display = "flex";
});

window.closeBonusModal = () => {
  modal.style.display = "none";
};

document.querySelectorAll("[data-copy],#bonus-copy-code").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText("XPVIP");
      const prior = btn.textContent;
      btn.textContent = "Code copié !";
      setTimeout(() => { btn.textContent = prior; }, 1700);
    } catch {
      window.prompt("Copiez le code promo :", "XPVIP");
    }
  });
});

render();
