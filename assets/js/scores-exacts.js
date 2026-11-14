/* Mr XPRONOS — Dixon-Coles scores from the VERIFIED daily video storyboard.
   Never rebrand Hybrid V3 results. Never synthesize or borrow stale picks. */
(() => {
  "use strict";
  const SCHEMA = "mrx-dixon-coles-video-scores-v1";
  const status = document.getElementById("scores-status");
  const list = document.getElementById("scores-simple-list");
  const count = document.getElementById("simple-count");
  const stamp = document.getElementById("scores-updated");
  const dayLabel = document.getElementById("scores-date");
  if (!status || !list || !count || !stamp || !dayLabel) return;

  const today = () => new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Lome", year: "numeric", month: "2-digit", day: "2-digit"
  }).format(new Date());
  const offsetDay = n => {
    const d = new Date(today() + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const formatDate = raw => new Date(raw + "T12:00:00Z").toLocaleDateString("fr-FR", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC"
  });
  const clock = iso => new Date(iso).toLocaleTimeString("fr-FR", {
    hour: "2-digit", minute: "2-digit", timeZone: "Africa/Lome"
  });
  const safe = v => String(v == null ? "" : v);
  const element = (tag, css, value) => {
    const node = document.createElement(tag);
    if (css) node.className = css;
    if (value !== undefined) node.textContent = safe(value);
    return node;
  };
  const validURL = raw => {
    try {
      const u = new URL(raw);
      return u.protocol === "https:" &&
        ["crests.football-data.org", "upload.wikimedia.org", "a.espncdn.com"].includes(u.hostname) &&
        !u.username && !u.password && !u.port && !u.search && !u.hash;
    } catch (_) { return false; }
  };
  const isDate = raw => typeof raw === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw) &&
    !Number.isNaN(Date.parse(raw)) && new Date(raw + "T00:00:00Z").toISOString().slice(0, 10) === raw;
  const utcTime = raw => typeof raw === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(raw) &&
    Number.isFinite(Date.parse(raw));
  const setStatus = (message, state) => {
    status.dataset.state = state;
    status.textContent = message;
  };
  const empty = (message, state = "unavailable") => {
    list.replaceChildren(element("p", "mx-scores-empty", message));
    count.textContent = "0 / 10";
    stamp.textContent = "Publication : non disponible";
    setStatus(message, state);
  };

  function verify(payload, selectedDay) {
    if (!payload || payload.schema_version !== SCHEMA ||
        payload.model !== "dixon_coles_video" ||
        payload.origin !== "verified_social_video_render" ||
        payload.status !== "published" || payload.date !== selectedDay ||
        !isDate(payload.date) || !utcTime(payload.generated_at) ||
        !/^[a-f0-9]{64}$/.test(payload.video_sha256 || "") ||
        !Number.isInteger(payload.count) || payload.count < 1 || payload.count > 10 ||
        !Array.isArray(payload.matches) || payload.matches.length !== payload.count ||
        Date.parse(payload.generated_at) > Date.now() + 60000) return null;
    const gen = Date.parse(payload.generated_at);
    if (payload.generated_at.slice(0,10) !== selectedDay &&
        offsetDate(selectedDay, -1) !== payload.generated_at.slice(0,10)) return null;
    const ids = new Set();
    for (const m of payload.matches) {
      if (!m || typeof m !== "object" ||
          typeof m.id !== "string" || !m.id || ids.has(m.id) ||
          typeof m.home !== "string" || !m.home.trim() || m.home.length > 120 ||
          typeof m.away !== "string" || !m.away.trim() || m.away.length > 120 ||
          typeof m.league !== "string" || m.league.length > 140 ||
          !/^(?:10|[0-9]):(?:10|[0-9])$/.test(m.score || "") ||
          !utcTime(m.kickoff_utc) || m.kickoff_utc.slice(0,10) !== selectedDay ||
          Date.parse(m.kickoff_utc) <= gen ||
          !validURL(m.home_logo) || !validURL(m.away_logo) ||
          !Number.isFinite(m.probability) || m.probability <= 0 || m.probability > 1) return null;
      ids.add(m.id);
    }
    return payload;
  }
  const offsetDate = (dateString, diff) => {
    const d = new Date(dateString + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + diff);
    return d.toISOString().slice(0,10);
  };
  function club(name, image) {
    const node = element("div", "mx-score-team");
    const crest = element("img", "mx-score-crest");
    crest.src = image;
    crest.alt = "";
    crest.loading = "lazy";
    crest.decoding = "async";
    crest.referrerPolicy = "no-referrer";
    crest.onerror = function () { this.remove(); };
    node.append(crest, element("span", "mx-score-teamname", name));
    return node;
  }
  function card(p, index) {
    const root = element("article", "mx-score-card");
    const top = element("div", "mx-score-card-top");
    top.append(
      element("span", "mx-score-rank", "#" + index),
      element("span", "mx-score-league", p.league || "Football")
    );
    const time = element("time", "mx-score-time", clock(p.kickoff_utc) + " GMT");
    time.dateTime = p.kickoff_utc;
    top.append(time);
    const started = Date.parse(p.kickoff_utc) <= Date.now();
    if (started) top.append(element("span", "mx-score-foot-label is-archive", "Match commencé · archive"));
    const match = element("div", "mx-score-match");
    const center = element("div", "mx-score-score");
    center.append(
      element("strong", "", p.score.replace(":", " : ")),
      element("small", "", "Score exact")
    );
    match.append(club(p.home, p.home_logo), center, club(p.away, p.away_logo));
    const foot = element("div", "mx-score-foot");
    foot.append(
      element("span", "mx-score-foot-label", "Probabilité statistique"),
      element("strong", "mx-score-probability",
        (p.probability * 100).toLocaleString("fr-FR", {maximumFractionDigits:1,minimumFractionDigits:1}) + " %")
    );
    root.append(top, match, foot);
    return root;
  }

  let offset = 0;
  let serial = 0;
  let active = null;
  const buttons = [...document.querySelectorAll("[data-scores-day]")];
  function paint(payload) {
    const fragment = document.createDocumentFragment();
    payload.matches.forEach((m, i) => fragment.append(card(m, i + 1)));
    list.replaceChildren(fragment);
    count.textContent = payload.count + " / 10";
    stamp.textContent = "Prévisions générées le " +
      formatDate(payload.generated_at.slice(0, 10)) + " à " + clock(payload.generated_at) + " GMT";
    const started = payload.matches.filter(m => Date.parse(m.kickoff_utc) <= Date.now()).length;
    setStatus(
      payload.count + " score(s) exact(s) Dixon-Coles · mêmes sélections que la vidéo" +
      (offset < 0 || started > 0 ? " · archives des prévisions pré-match" : ""),
      offset < 0 || started > 0 ? "archive" : "ready"
    );
  }
  async function load() {
    const request = ++serial;
    const day = offsetDay(offset);
    dayLabel.textContent = "Sélections du " + formatDate(day);
    setStatus("Vérification des scores Dixon-Coles…", "loading");
    try {
      const res = await fetch("dixon-scores-daily/" + day + ".json?t=" + Date.now(), {
        cache: "no-store", headers: {Accept: "application/json"}
      });
      if (request !== serial) return;
      if (!res.ok) throw Error("No verified video feed");
      const payload = verify(await res.json(), day);
      if (request !== serial) return;
      if (!payload) throw Error("Invalid video provenance");
      active = payload;
      paint(payload);
    } catch (_) {
      if (request !== serial) return;
      active = null;
      empty("Aucune sélection Dixon-Coles issue d’une vidéo vérifiée pour le " +
        formatDate(day) + ".", "unavailable");
    }
  }
  buttons.forEach(btn => btn.addEventListener("click", () => {
    offset = Number(btn.dataset.scoresDay);
    buttons.forEach(b => {
      b.classList.toggle("is-active", b === btn);
      b.setAttribute("aria-pressed", String(b === btn));
    });
    active = null;
    void load();
  }));
  const promo = document.querySelector(".mx-code-button");
  promo?.addEventListener("click", async () => {
    if (!navigator.clipboard?.writeText) return;
    try { await navigator.clipboard.writeText(promo.querySelector("strong")?.textContent?.trim() || "XPVIP"); }
    catch (_) { /* existing visible code stays usable */ }
  });
  let lastDay = today();
  document.addEventListener("visibilitychange", () => { if (!document.hidden) void load(); });
  window.setInterval(() => {
    if (document.hidden) return;
    if (lastDay !== today()) {lastDay = today(); void load();}
    else if (active) paint(active);
  }, 60000);
  window.setInterval(() => {if (!document.hidden) void load();}, 15 * 60000);
  void load();
})();
