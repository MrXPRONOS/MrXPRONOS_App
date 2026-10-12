/**
 * main.js - Mr XPRONOS
 * Version stable + SEO amélioré (slug articles + conseils + metas dynamiques)
 * + Cookies (mx_user_id)
 * + Accès libre aux pronostics Simple, Pro et VIP
 *
 * (VIP PAYANT SUPPRIMÉ)
 */
if (location.hostname !== "localhost" && !location.hostname.includes("127.0.0.1")) {
  console.log = () => {};
  console.warn = () => {};
}

let supabase = null;
let supabaseAvailable = false;
let supabaseConfig = { url: "", anonKey: "" };

let allData = null;
let currentCategory = "simple";
// Tant que le visiteur ne choisit pas lui-même un onglet (ou ?cat=...),
// afficher automatiquement la catégorie la plus fournie pour le jour affiché.
let autoSelectCategoryByCount = true;
let currentSubcat = "pronostics";
let currentDay = "today";
let filteredMatchesWithoutSearch = [];
let searchTerm = "";
let usingCachedData = false;

let onlineChannel = null;
let generatedContentPromise = null;
const activeChannels = new Set();


const BASE_SITE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/";

const POPULAR_LEAGUES = [
  "Premier League",
  "LaLiga",
  "Serie A",
  "Bundesliga",
  "Ligue 1",
  "Eredivisie",
  "Primeira Liga",
  "Super Lig",
  "Russian Premier League",
  "MLS",
  "Brasileirão",
  "Liga Profesional",
  "Jupiler Pro League",
  "Super League",
  "Championship",
  "Liga Portugal",
  "Trendyol Super Lig",
];

const DOM = {
  matches: null,
  bookmakersFooter: null,
  bookmakersBonus: null,
  vipSubtabs: null,
  usersCount: null,
  onlineCount: null,
  sharesCount: null,
  winsCount: null,
  successFill: null,
  successPercent: null,
  winsTrack: null,
  testimonials: null,

  // (ancien) container accueil
  todayPicks: null,

  // NOUVEAU (accueil)
  topTodayPicks: null,
  verifiedPicks: null,
  dataUpdated: null,

  searchInput: null,
  historyContainer: null,

  bonusSelect: null,
  bonusGrid: null,
  bonusThumbnails: null,
  bonusModal: null,

  articleModal: null,
  conseilModal: null,
  newsModal: null,

  winPopup: null,
  iosGuidePopup: null,
  installButton: null,

  blogList: null,
  blogPost: null,

  conseilPost: null,
  conseilsList: null,

  infosList: null,
  footNewsContainer: null,

  successRateContainer: null,
};

function qs(sel, root = document) {
  return root.querySelector(sel);
}
function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

function initDOM() {
  DOM.matches = document.getElementById("matches-container");

  DOM.bookmakersFooter = document.getElementById("bookmakers-footer");
  DOM.bookmakersBonus = document.getElementById("bookmakers-bonus");
  DOM.vipSubtabs = document.getElementById("vip-subtabs");

  DOM.usersCount = document.getElementById("total-users-count");
  DOM.onlineCount = document.getElementById("online-users-count");
  DOM.sharesCount = document.getElementById("total-shares-count");

  DOM.winsCount = document.getElementById("wins-count");
  DOM.successFill = document.getElementById("success-fill");
  DOM.successPercent = document.getElementById("success-percent");
  DOM.winsTrack = document.getElementById("wins-track");
  DOM.testimonials = document.getElementById("testimonials-container");

  // (ancien id - peut ne plus exister)
  DOM.todayPicks = document.getElementById("today-picks");

  // NOUVEAU (accueil)
  DOM.topTodayPicks = document.getElementById("top-today-picks");
  DOM.verifiedPicks = document.getElementById("verified-picks");
  DOM.dataUpdated = document.getElementById("data-updated");

  DOM.searchInput = document.getElementById("search-input");
  DOM.historyContainer = document.getElementById("history-container");

  DOM.bonusSelect = document.getElementById("bonus-bookmaker-select");
  DOM.bonusGrid = document.getElementById("bonus-grid");
  DOM.bonusThumbnails = document.getElementById("bonus-thumbnails");
  DOM.bonusModal = document.getElementById("bonus-modal");

  DOM.articleModal = document.getElementById("article-modal");
  DOM.conseilModal = document.getElementById("conseil-modal");
  DOM.newsModal = document.getElementById("news-modal");

  DOM.winPopup = document.getElementById("win-popup");
  DOM.iosGuidePopup = document.getElementById("ios-guide-popup");
  DOM.installButton = document.getElementById("install-app");

  DOM.blogList = document.getElementById("blog-list");
  DOM.blogPost =
    document.getElementById("blog-post") ||
    document.getElementById("blog-post-content") ||
    document.getElementById("article-page-content");

  DOM.conseilPost = document.getElementById("conseil-post");
  DOM.conseilsList = document.getElementById("conseils-list");
  DOM.infosList = document.getElementById("infos-list");

  DOM.footNewsContainer = document.getElementById("foot-news-container");
  DOM.successRateContainer = document.getElementById("success-rate-container");
}

function syncHeaderOffset() {
  const header = document.querySelector("header");
  if (!header) return;
  document.documentElement.style.setProperty("--header-offset", header.offsetHeight + "px");
}

syncHeaderOffset();
window.addEventListener("resize", syncHeaderOffset);
setTimeout(syncHeaderOffset, 150); // au cas où pwa.js modifie le header après
/* =======================================================
 SECURITY
======================================================= */
function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

function escapeAttribute(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function stripMarkdown(text = "") {
  return String(text)
    .replace(/#+\s*/g, "")
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .replace(/`/g, "")
    .replace(/\[|\]/g, "")
    .trim();
}

function sanitizeHtml(unsafeHtml = "") {
  const template = document.createElement("template");
  template.innerHTML = unsafeHtml;

  const allowedTags = new Set([
    "div",
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "span",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
  ]);

  const allowedAttrs = {
    "*": new Set(["class"]),
    a: new Set(["href", "target", "rel"]),
    img: new Set(["src", "alt", "loading", "decoding"]),
    table: new Set(["class"]),
    th: new Set(["class"]),
    td: new Set(["class"]),
  };

  const cleanNode = (node) => {
    [...node.childNodes].forEach((child) => {
      if (child.nodeType === Node.COMMENT_NODE) {
        child.remove();
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) return;

      const tag = child.tagName.toLowerCase();
      if (!allowedTags.has(tag)) {
        const fragment = document.createDocumentFragment();
        while (child.firstChild) fragment.appendChild(child.firstChild);
        child.replaceWith(fragment);
        cleanNode(node);
        return;
      }

      [...child.attributes].forEach((attr) => {
        const name = attr.name.toLowerCase();
        const value = attr.value || "";
        const isAllowed =
          (allowedAttrs[tag] && allowedAttrs[tag].has(name)) ||
          (allowedAttrs["*"] && allowedAttrs["*"].has(name));

        if (name.startsWith("on") || !isAllowed) {
          child.removeAttribute(attr.name);
          return;
        }
        if ((name === "href" || name === "src") && /^\s*javascript:/i.test(value)) {
          child.removeAttribute(attr.name);
          return;
        }
        if (tag === "a" && name === "href") {
          child.setAttribute("target", "_blank");
          child.setAttribute("rel", "noopener noreferrer");
        }
      });

      cleanNode(child);
    });
  };

  cleanNode(template.content);
  return template.innerHTML;
}

function renderSafeRichContent(content = "") {
  try {
    if (window.marked) {
      return sanitizeHtml(window.marked.parse(String(content)));
    }
  } catch (e) {
    console.error("Erreur marked:", e);
  }
  return sanitizeHtml(escapeHtml(String(content)).replace(/\n/g, "<br>"));
}

/* =======================================================
 UTILS
======================================================= */
function showToast(message, type = "info", duration = 4000) {
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: ${
      type === "success" ? "#4CAF50" : type === "error" ? "#f44336" : "#2196F3"
    };
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 10000;
    font-weight: 600;
    max-width: 90vw;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

function toFloatSafe(value, defaultValue = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : defaultValue;
}

function safeJsonParse(value, fallback = null) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

/* =======================================================
 COPY (XPVIP)
======================================================= */
async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {}
  // fallback
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    return true;
  } catch {
    return false;
  }
}

function initPromoCopy() {
  // Support : bouton .promo-copy avec data-copy
  qsa(".promo-copy[data-copy]").forEach((el) => {
    el.addEventListener("click", async () => {
      const code = el.getAttribute("data-copy") || "XPVIP";
      const ok = await copyText(code);
      showToast(ok ? `Code copié : ${code}` : "Impossible de copier (essayez manuellement).", ok ? "success" : "error");
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        el.click();
      }
    });
  });
}

/* =======================================================
 COOKIES (long)
======================================================= */
const COOKIE_DAYS = 1000000;

function getCookie(name) {
  const m = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)")
  );
  return m ? decodeURIComponent(m[1]) : null;
}

function setCookie(name, value, days = COOKIE_DAYS) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; Expires=${expires}; Path=/; SameSite=Lax${secure}`;
}

function deleteCookie(name) {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; SameSite=Lax${secure}`;
}

/* =======================================================
 USER ID (cookie + localStorage)
======================================================= */
function getUserId() {
  let userId = localStorage.getItem("mx_user_id") || getCookie("mx_user_id");
  if (!userId) {
    try {
      userId = "MX-" + crypto.randomUUID();
    } catch {
      userId = "MX-" + Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
  }
  localStorage.setItem("mx_user_id", userId);
  setCookie("mx_user_id", userId, COOKIE_DAYS);
  return userId;
}
window.getUserId = getUserId;

function isFinishedMatch(match) {
  if (!match) return false;
  if (match.is_finished === true) return true;
  const status = (match.status || "").toLowerCase();
  return status.includes("finished") || status.includes("terminé") || status.includes("ended") || status.includes("ft");
}

function getTodayString() {
  return new Date().toDateString();
}

function cleanupChannels() {
  activeChannels.forEach((channel) => {
    try {
      channel.unsubscribe?.();
      if (supabaseAvailable && supabase?.removeChannel) supabase.removeChannel(channel);
    } catch (e) {}
  });
  activeChannels.clear();
}
window.addEventListener("beforeunload", cleanupChannels);

/* =======================================================
 PAGE DETECTION
======================================================= */
function detectPage() {
  if (DOM.matches) return "pronos";
  if (DOM.historyContainer) return "history";
  if (DOM.blogList) return "blog-list";
  if (DOM.blogPost) return "blog-post";
  if (DOM.conseilPost) return "conseil-post";
  if (DOM.conseilsList) return "conseils";
  if (DOM.bonusSelect || DOM.bonusGrid || DOM.bonusThumbnails) return "bonus";
  if (DOM.footNewsContainer) return "infos";
  // HOME : nouveaux containers ou témoignages
  if (DOM.topTodayPicks || DOM.verifiedPicks || DOM.testimonials || DOM.todayPicks) return "home";
  return "generic";
}

/* =======================================================
 SUPABASE
======================================================= */
async function initSupabase() {
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout Supabase")), 5000));
  try {
    const initPromise = (async () => {
      const { supabaseUrl, supabaseAnonKey } = await import("./config.js");
      if (!supabaseUrl || !supabaseUrl.startsWith("https://")) throw new Error("URL Supabase invalide");
      if (!supabaseAnonKey) throw new Error("Clé Supabase manquante");

      supabaseConfig.url = supabaseUrl;
      supabaseConfig.anonKey = supabaseAnonKey;

      const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
      supabase = createClient(supabaseUrl, supabaseAnonKey);
      supabaseAvailable = true;
    })();

    await Promise.race([initPromise, timeout]);
  } catch (error) {
    supabaseAvailable = false;
  }
}

/* =======================================================
 PUSH / COUNTERS / ANALYTICS
======================================================= */
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

async function subscribeToPush(askPermission = false) {
  if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) return;
  if (!supabaseConfig.url) return;

  try {
    let permission = Notification.permission;
    if (permission === "default" && askPermission) permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    let swReady = null;
    try {
      swReady = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), 3000)),
      ]);
    } catch (e) {
      console.warn("Service Worker non prêt, push désactivé");
      return;
    }
    if (!swReady) return;

    let subscription = await swReady.pushManager.getSubscription();
    if (!subscription) {
      try {
        const keyResp = await fetch(`${supabaseConfig.url}/functions/v1/vapid-public-key`, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        }).catch(() => null);

        if (!keyResp || !keyResp.ok) {
          console.warn("Impossible de récupérer la clé VAPID");
          return;
        }
        const publicKey = (await keyResp.text()).trim();
        if (!publicKey) return;

        const convertedKey = urlBase64ToUint8Array(publicKey);
        subscription = await swReady.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: convertedKey,
        });
      } catch (pushError) {
        console.warn("Push non supporté:", pushError);
        return;
      }
    }

    const userId = getUserId();
    await fetch(`${supabaseConfig.url}/functions/v1/push-subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, subscription }),
    }).catch((e) => {
      console.debug("Push subscription non enregistrée (CORS)", e.message);
    });
  } catch (err) {
    console.debug("Push non disponible:", err.message);
  }
}

window.enablePushNotifications = async function () {
  await subscribeToPush(true);
};

function getOS() {
  const ua = window.navigator.userAgent;
  if (/iPad|iPhone|iPod/.test(ua)) return "iOS";
  if (/Android/.test(ua)) return "Android";
  return "Other";
}

function isPwaInstalled() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

/* =======================================================
 PUSH PERMISSION PROMPT (popup interne)
======================================================= */
function getPushPromptMode() {
  if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return "unsupported";
  }
  if (getOS() === "iOS" && !isPwaInstalled()) return "ios_need_install";
  const perm = Notification.permission;
  if (perm === "granted") return "granted";
  if (perm === "denied") return "denied";

  const snoozeUntil = Number(localStorage.getItem("mx_push_snooze_until") || "0");
  if (Date.now() < snoozeUntil) return "snoozed";

  return "ask";
}

function buildPushPromptEl() {
  let el = document.getElementById("push-permission");
  if (el) return el;

  el = document.createElement("div");
  el.id = "push-permission";
  el.style.cssText = `
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: 14px;
    z-index: 10060;
    display: none;
  `;
  document.body.appendChild(el);
  return el;
}

function showPushPrompt() {
  const mode = getPushPromptMode();
  if (mode === "granted" || mode === "unsupported" || mode === "ios_need_install" || mode === "snoozed") return;

  const el = buildPushPromptEl();

  if (mode === "denied") {
    el.innerHTML = `
      <div style="
        background:#1A1A1A;
        border:1px solid rgba(212,175,55,.55);
        border-radius:16px;
        padding:12px;
        box-shadow:0 18px 60px rgba(0,0,0,.6);
      ">
        <div style="font-weight:900;color:#D4AF37;margin-bottom:6px;">Notifications bloquées</div>
        <div style="color:#ddd;font-size:.92rem;margin-bottom:10px;">
          Vous avez bloqué les notifications pour ce site.
          <br><br>
          <strong>Pour réactiver :</strong><br>
          Chrome → (i) / cadenas → Paramètres du site → Notifications → Autoriser
        </div>
        <div style="display:flex;gap:10px;">
          <button type="button" id="push-close" class="btn btn-secondary" style="flex:1;">Fermer</button>
          <button type="button" id="push-remind" class="btn btn-primary" style="flex:1;">Me le rappeler</button>
        </div>
      </div>
    `;
    el.querySelector("#push-close")?.addEventListener("click", () => {
      el.style.display = "none";
    });
    el.querySelector("#push-remind")?.addEventListener("click", () => {
      localStorage.setItem("mx_push_snooze_until", String(Date.now() + 2 * 60 * 60 * 1000));
      el.style.display = "none";
    });
    el.style.display = "block";
    return;
  }

  el.innerHTML = `
    <div style="
      background:#1A1A1A;
      border:1px solid rgba(212,175,55,.55);
      border-radius:16px;
      padding:12px;
      box-shadow:0 18px 60px rgba(0,0,0,.6);
    ">
      <div style="font-weight:900;color:#D4AF37;margin-bottom:6px;">Activer les notifications ?</div>
      <div style="color:#ddd;font-size:.92rem;margin-bottom:10px;">
        Recevez une alerte quand de nouveaux coupons sont disponibles.
      </div>
      <div style="display:flex;gap:10px;">
        <button type="button" id="push-allow" class="btn btn-primary" style="flex:1;">Activer</button>
        <button type="button" id="push-later" class="btn btn-secondary" style="flex:1;">Plus tard</button>
      </div>
    </div>
  `;

  el.querySelector("#push-later")?.addEventListener("click", () => {
    localStorage.setItem("mx_push_snooze_until", String(Date.now() + 24 * 60 * 60 * 1000));
    el.style.display = "none";
  });

  el.querySelector("#push-allow")?.addEventListener("click", async () => {
    try {
      await window.enablePushNotifications?.();
    } catch (e) {
      console.error("enablePushNotifications error:", e);
    } finally {
      el.style.display = "none";
      if ("Notification" in window && Notification.permission === "granted") {
        localStorage.removeItem("mx_push_snooze_until");
      }
    }
  });

  el.style.display = "block";
}

async function incrementCounter(counterName) {
  if (!supabaseAvailable || !supabase) {
    const local = parseInt(localStorage.getItem(counterName) || "0", 10);
    localStorage.setItem(counterName, String(local + 1));
    return;
  }
  try {
    await supabase.rpc("increment_counter", { counter_name: counterName });
  } catch (e) {
    console.error("Erreur incrémentation:", e);
  }
}

async function updateDisplayedCounters() {
  if (!supabaseAvailable || !supabase) return;
  try {
    const { data, error } = await supabase
      .from("counters")
      .select("total_visits, total_shares, unique_users")
      .eq("id", 1)
      .single();
    if (error) throw error;

    if (DOM.usersCount) DOM.usersCount.textContent = (data?.unique_users || 0).toLocaleString() + "+";
    if (DOM.sharesCount) DOM.sharesCount.textContent = (data?.total_shares || 0).toLocaleString() + "+";
  } catch (e) {
    console.error("Erreur récupération counters:", e);
  }
}

function subscribeToCounters() {
  if (!supabaseAvailable || !supabase) return;

  const channel = supabase
    .channel("counters-live")
    .on("postgres_changes", { event: "UPDATE", schema: "public", table: "counters", filter: "id=eq.1" }, (payload) => {
      if (DOM.usersCount) DOM.usersCount.textContent = (payload.new?.unique_users || 0).toLocaleString() + "+";
      if (DOM.sharesCount) DOM.sharesCount.textContent = (payload.new?.total_shares || 0).toLocaleString() + "+";
    })
    .subscribe((status) => {
      if (status === "SUBSCRIBED") activeChannels.add(channel);
    });
}

async function recordEvent(type, page = "") {
  if (!supabaseAvailable || !supabase) return;
  const userId = getUserId();
  try {
    await supabase.from("analytics").insert({ event_type: type, user_id: userId, page });
  } catch (e) {
    console.error("Erreur analytics:", e);
  }
}

function countVisitOncePerDay() {
  const todayKey = getTodayString();
  const lastVisit = localStorage.getItem("mx_last_visit");
  if (lastVisit !== todayKey) {
    localStorage.setItem("mx_last_visit", todayKey);
    incrementCounter("total_visits");
    recordEvent("visit", window.location.pathname);
  }
}

async function registerUniqueUser() {
  if (!supabaseAvailable || !supabase) return;
  const userId = getUserId();
  const registered = localStorage.getItem("mx_registered");
  if (registered) return;

  try {
    const { error } = await supabase.from("users").insert({ user_id: userId });
    if (!error) await supabase.rpc("increment_counter", { counter_name: "unique_users" });
    localStorage.setItem("mx_registered", "true");
  } catch (e) {
    console.error("Erreur enregistrement user:", e);
  }
}

async function initOnlineUsers() {
  if (!supabaseAvailable || !supabase || !DOM.onlineCount) return;

  if (onlineChannel) {
    try {
      onlineChannel.unsubscribe();
      supabase.removeChannel?.(onlineChannel);
    } catch {}
  }

  onlineChannel = supabase.channel("online-users", {
    config: { presence: { key: getUserId() } },
  });

  onlineChannel
    .on("presence", { event: "sync" }, () => {
      const state = onlineChannel.presenceState();
      const onlineUsers = Object.keys(state).length;
      if (DOM.onlineCount) DOM.onlineCount.textContent = onlineUsers;
    })
    .subscribe(async (status) => {
      if (status === "SUBSCRIBED") {
        try {
          await onlineChannel.track({ online_at: new Date().toISOString() });
          activeChannels.add(onlineChannel);
        } catch (e) {}
      }
    });
}

/* =======================================================
 IOS GUIDE
======================================================= */
function showIosGuideIfNeeded() {
  if (getOS() === "iOS" && !isPwaInstalled()) {
    const lastClosed = localStorage.getItem("iosGuideLastClosed");
    if (lastClosed) {
      const hoursSince = (Date.now() - parseInt(lastClosed, 10)) / (1000 * 60 * 60);
      if (hoursSince < 24) return;
    }
    if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = "flex";
  }
}

function closeIosGuide() {
  if (DOM.iosGuidePopup) DOM.iosGuidePopup.style.display = "none";
  localStorage.setItem("iosGuideLastClosed", String(Date.now()));
}

/* =======================================================
 PARTAGE FACULTATIF — aucun accès n'est conditionné au partage
======================================================= */
function openShareWindow(url) {
  window.open(url, "_blank", "noopener,noreferrer");
}

function sharePronostic(match) {
  if (!match || !match.prediction) return;
  const msg = `⚽ COUPONS GRATUITS
${match.home_team} vs ${match.away_team}
Pronostic : ${match.prediction.type || match.prediction.double_chance || "-"} – Fiabilité ${match.prediction.confidence}%
Plus de coupons : ${BASE_SITE_URL}`;
  const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(msg)}`;
  const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(BASE_SITE_URL)}&text=${encodeURIComponent(msg)}`;
  const useWhatsapp = confirm("Partager sur WhatsApp ? (OK = WhatsApp, Annuler = Telegram)");
  openShareWindow(useWhatsapp ? whatsappUrl : telegramUrl);
  // Mesure uniquement une intention volontaire de partage, jamais une condition d'accès.
  incrementCounter("total_shares");
  recordEvent("share", window.location.pathname);
  recordEvent("click_pronostic", window.location.pathname);
}

/* =======================================================
 LIVE VIP MENU CLICK (PAYANT SUPPRIMÉ)
======================================================= */
window.handleVipMenuClick = function () {
  // Accès direct au LIVE : aucune obligation de partage.
  window.location.href = `${BASE_SITE_URL}live.html`;
};
window.handleVipClick = window.handleVipMenuClick;

/* =======================================================
 DATA LOADING
======================================================= */
function isPronosticsPayload(value) {
  return !!value && typeof value === "object" && Array.isArray(value.matches);
}

function getPayloadTimestamp(value) {
  const ts = Date.parse(String(value?.generated_at || ""));
  return Number.isFinite(ts) ? ts : 0;
}

async function fetchJsonWithCache(url, cacheKey, timeoutMs = 8000) {
  const cachedData = safeJsonParse(localStorage.getItem(cacheKey), null);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    });
    clearTimeout(timeoutId);

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();

    // data.json doit toujours contenir un tableau matches.
    if (cacheKey === "cachedData" && !isPronosticsPayload(data)) {
      throw new Error("data.json invalide : tableau matches absent");
    }

    // Ne jamais écraser un bon cache par un faux JSON vide plus ancien ou sans date.
    if (
      cacheKey === "cachedData" &&
      isPronosticsPayload(cachedData) &&
      cachedData.matches.length > 0 &&
      data.matches.length === 0 &&
      getPayloadTimestamp(data) <= getPayloadTimestamp(cachedData)
    ) {
      console.warn("data.json vide/ancien ignoré : conservation du cache non vide");
      return { data: cachedData, fromCache: true, reason: "empty-network-payload" };
    }

    localStorage.setItem(cacheKey, JSON.stringify(data));
    return { data, fromCache: false, reason: "network" };
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn(`Chargement ${url} échoué :`, error?.message || error);

    if (cachedData) {
      return { data: cachedData, fromCache: true, reason: "network-error" };
    }

    return { data: null, fromCache: false, reason: "no-data" };
  }
}

async function loadData() {
  const { data, fromCache } = await fetchJsonWithCache(`data.json?t=${Date.now()}`, "cachedData", 8000);
  usingCachedData = fromCache;
  allData = data;

  if (!allData) {
    if (DOM.matches) DOM.matches.innerHTML = `<div class="error">■■ Aucune donnée disponible.</div>`;
    return;
  }

  renderBookmakers(allData.bookmakers);
  filterAndDisplay();
  updatePronosticsSuccessRate();
}

async function loadDataGeneric() {
  const { data, fromCache } = await fetchJsonWithCache(`data.json?t=${Date.now()}`, "cachedData", 8000);
  usingCachedData = fromCache;
  return data;
}

/* =======================================================
 BOOKMAKERS
======================================================= */
function renderBookmakers(bookmakers) {
  const defaultBookmakers = [
    {
      name: "1xBet",
      logo: "assets/images/1xbet.webp",
      url: "https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573",
      desc: "Bonus de bienvenue jusqu'à 130€",
    },
    {
      name: "1win",
      logo: "assets/images/1win.webp",
      url: "https://1wrbgb.com/?open=register&p=qqcw",
      desc: "Bonus exclusif avec XPVIP",
    },
    {
      name: "Betwinner",
      logo: "assets/images/betwinner.webp",
      url: "https://bwredir.com/299Y",
      desc: "Offre spéciale nouveaux joueurs",
    },
    {
      name: "Melbet",
      logo: "assets/images/melbet.webp",
      url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041",
      desc: "Bonus premium Melbet avec inscription rapide",
    },
    {
      name: "Linebet",
      logo: "assets/images/linebet.webp",
      url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611",
      desc: "Bonus et promotions spéciales Linebet",
    },
    {
      name: "BetClic",
      logo: "assets/images/betclic.webp",
      url: "https://betpari-click.com/2vY0?extid=USD",
      desc: "Offre de bienvenue Betclic",
    },
  ];

  const published = Array.isArray(window.publishedBookmakers) && window.publishedBookmakers.length ? window.publishedBookmakers : null;

  const items = published || (Array.isArray(bookmakers) && bookmakers.length ? bookmakers : defaultBookmakers);

  if (DOM.bookmakersFooter) {
    DOM.bookmakersFooter.innerHTML = "";
    items.forEach((b) => {
      const a = document.createElement("a");
      a.href = b.url || "#";
      a.target = "_blank";
      a.rel = "noopener noreferrer";

      const img = document.createElement("img");
      img.src = b.logo || "assets/images/default-logo.webp";
      img.alt = b.name || "Bookmaker";
      img.loading = "lazy";
      img.decoding = "async";
      img.style.maxHeight = "40px";

      img.onerror = function () {
        this.style.display = "none";
        const span = document.createElement("span");
        span.textContent = b.name || "Bookmaker";
        span.style.color = "var(--or)";
        span.style.fontWeight = "600";
        span.style.fontSize = "0.8rem";
        a.appendChild(span);
      };

      a.appendChild(img);
      DOM.bookmakersFooter.appendChild(a);
    });
  }

  if (DOM.bookmakersBonus) {
    DOM.bookmakersBonus.innerHTML = "";
    items.forEach((b) => {
      const div = document.createElement("div");
      div.className = "bookmaker-card";
      div.innerHTML = `
        <img src="${escapeAttribute(b.logo || "assets/images/default-logo.webp")}" alt="${escapeAttribute(b.name || "Bookmaker")}" loading="lazy" decoding="async">
        <h3>${escapeHtml(b.name || "Bookmaker")}</h3>
        <p>${escapeHtml(b.desc || b.description || "Bonus exclusif bookmaker")}</p>
        <a href="${escapeAttribute(b.url || "#")}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">S'inscrire avec XPVIP</a>
      `;
      DOM.bookmakersBonus.appendChild(div);
    });
  }
}

/* =======================================================
 PRONOS PAGE
======================================================= */
function getLocalDateString(day) {
  const now = new Date();
  const target = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  if (day === "tomorrow") target.setUTCDate(target.getUTCDate() + 1);
  else if (day === "yesterday") target.setUTCDate(target.getUTCDate() - 1);

  const y = target.getUTCFullYear();
  const m = String(target.getUTCMonth() + 1).padStart(2, "0");
  const d = String(target.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getLocalDateFromEvent(isoString) {
  if (!isoString) return null;
  const date = new Date(isoString);
  if (isNaN(date)) return null;

  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getMatchDate(match) {
  const explicitDate = String(match?.date || "").slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(explicitDate)) return explicitDate;
  return getLocalDateFromEvent(match?.event_date);
}

function sortMatchesByLeague(matches) {
  return matches.sort((a, b) => {
    const leagueA = a.league || "";
    const leagueB = b.league || "";
    const indexA = POPULAR_LEAGUES.findIndex((l) => leagueA.includes(l) || leagueA === l);
    const indexB = POPULAR_LEAGUES.findIndex((l) => leagueB.includes(l) || leagueB === l);
    const rankA = indexA === -1 ? 999 : indexA;
    const rankB = indexB === -1 ? 999 : indexB;
    if (rankA !== rankB) return rankA - rankB;
    return new Date(a.event_date || 0) - new Date(b.event_date || 0);
  });
}

function translateStatus(status) {
  if (!status) return "À venir";
  const s = String(status).toLowerCase();
  if (s.includes("finished") || s.includes("terminé") || s.includes("ended")) return "Terminé";
  if (s.includes("inprogress") || s.includes("live") || s.includes("en cours")) return "En cours";
  if (s.includes("notstarted") || s.includes("à venir")) return "À venir";
  if (s.includes("postponed")) return "Reporté";
  if (s.includes("cancelled")) return "Annulé";
  return escapeHtml(status);
}

function getStatusClass(status) {
  if (!status) return "";
  const s = String(status).toLowerCase();
  if (
    s.includes("finished") || s.includes("terminé") || s.includes("ended") ||
    s === "ft" || s.includes("after extra time") || s.includes("after penalties")
  ) return "finished";
  if (
    s.includes("inprogress") || s.includes("live") || s.includes("en cours") ||
    s.includes("1st half") || s.includes("2nd half") || s.includes("first half") ||
    s.includes("second half") || s.includes("halftime") || s === "ht" ||
    s.includes("extra time") || s.includes("penalties")
  ) return "live";
  return "";
}

function isLiveMatch(match) {
  if (!match || isFinishedMatch(match)) return false;
  return getStatusClass(match.status) === "live";
}

function getVisibleMatchScore(match) {
  if (!match) return null;
  const home = Number(match.home_score);
  const away = Number(match.away_score);
  const scoreKnown = Number.isFinite(home) && Number.isFinite(away) && home >= 0 && away >= 0;
  if (!scoreKnown) return null;
  if (!isLiveMatch(match) && !isFinishedMatch(match)) return null;
  return {
    home: Math.trunc(home),
    away: Math.trunc(away),
    finished: isFinishedMatch(match),
  };
}

function formatMatchTime(isoString) {
  if (!isoString) return "Horaire inconnu";
  const date = new Date(isoString);
  if (isNaN(date)) return "Horaire inconnu";
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function getTeamLogoPath(teamName, isHome = true) {
  if (!teamName) return isHome ? "assets/images/home.webp" : "assets/images/away.webp";
  const normalized = String(teamName)
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
  return `assets/images/${normalized}.webp`;
}

const CATEGORY_LABELS = { simple: "Simple", pro: "Pro", vip: "VIP" };

function readInitialCategory() {
  const cat = String(new URLSearchParams(window.location.search).get("cat") || "").toLowerCase();
  if (CATEGORY_LABELS[cat]) {
    // Respecter les liens directs du type pronos.html?cat=vip.
    autoSelectCategoryByCount = false;
    return cat;
  }
  return "simple";
}

// Comparer uniquement les catégories disposant de pronostics affichables
// pour le jour sélectionné. En cas d'égalité : Simple, puis Pro, puis VIP.
function mostPopulatedCategory(counts) {
  return Object.keys(CATEGORY_LABELS).reduce(
    (best, cat) => (counts[cat] || 0) > (counts[best] || 0) ? cat : best,
    "simple"
  );
}

function syncCategoryTabs(counts = null) {
  qsa(".pronostic-category-tabs .tab-btn").forEach((btn) => {
    const cat = btn.dataset.cat;
    const active = cat === currentCategory;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
    btn.tabIndex = active ? 0 : -1;
    const count = document.getElementById(`count-${cat}`);
    if (count && counts) count.textContent = String(counts[cat] || 0);
  });
  DOM.matches?.setAttribute("aria-labelledby", `tab-${currentCategory}`);
}

function updateCategorySummary(shown, searchActive = false) {
  const node = document.getElementById("category-summary");
  if (!node) return;

  const label = CATEGORY_LABELS[currentCategory] || "Simple";
  const target = getLocalDateString(currentDay);
  const parsed = new Date(target + "T12:00:00");
  const dayPrefix = { today: "Aujourd’hui", tomorrow: "Demain", yesterday: "Hier" }[currentDay] || "Ce jour";
  const formattedDate = Number.isNaN(parsed.getTime())
    ? ""
    : parsed.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });

  node.textContent = `Pronostics ${label} — ${dayPrefix}${formattedDate ? ", " + formattedDate : ""}`;

  const description = document.getElementById("category-description");
  if (description) {
    const descriptions = {
      simple: "Des pronostics fiables et accessibles pour tous. Analyses basées sur les statistiques et la forme actuelle des équipes.",
      pro: "Des sélections plus exigeantes, avec une lecture approfondie des données et des scénarios de match.",
      vip: "Nos sélections les plus strictes, retenues parmi les meilleures opportunités détectées par le système.",
    };
    description.textContent = searchActive
      ? `${shown} résultat${shown > 1 ? "s" : ""} correspondant à votre recherche.`
      : (descriptions[currentCategory] || descriptions.simple);
  }
}

function filterAndDisplay() {
  if (!DOM.matches) return;
  if (!allData || !Array.isArray(allData.matches)) {
    DOM.matches.innerHTML = '<div class="no-events">Aucune donnée de pronostics disponible.</div>';
    return;
  }

  const targetDate = getLocalDateString(currentDay);
  const counts = { simple: 0, pro: 0, vip: 0 };
  const currentDayMatches = allData.matches.filter((m) => {
    const category = String(m.category || "").trim().toLowerCase();
    if (!(category in counts) || m.combo_only || getMatchDate(m) !== targetDate) return false;
    if (m.source === "bsd" && !m.is_finished && m.recommendation_eligible !== true) return false;
    counts[category] += 1;
    return true;
  });

  if (autoSelectCategoryByCount) {
    currentCategory = mostPopulatedCategory(counts);
  }
  syncCategoryTabs(counts);

  filteredMatchesWithoutSearch = currentDayMatches
    .filter((m) => String(m.category || "").trim().toLowerCase() === currentCategory)
    .sort((a, b) => Number(b.final_score || b.xpronos_score || 0) - Number(a.final_score || a.xpronos_score || 0));

  applySearchFilter();
}

function applySearchFilter() {
  if (!DOM.matches) return;
  const term = searchTerm.toLowerCase().trim();
  const filtered = !term
    ? filteredMatchesWithoutSearch
    : filteredMatchesWithoutSearch.filter((m) =>
        String(m.home_team || "").toLowerCase().includes(term) ||
        String(m.away_team || "").toLowerCase().includes(term) ||
        String(m.league || "").toLowerCase().includes(term)
      );
  updateCategorySummary(filtered.length, Boolean(term));
  if (!filtered.length) {
    const label = CATEGORY_LABELS[currentCategory] || "Simple";
    const message = term
      ? `Aucun pronostic ${label} ne correspond à cette recherche.`
      : `Aucun pronostic ${label} disponible pour cette date.`;
    DOM.matches.innerHTML = `<div class="no-events">${message}</div>`;
    return;
  }
  renderMatches(filtered);
}

function getLeagueFlag(leagueName = "") {
  const name = String(leagueName).toLowerCase();
  if (name.includes("premier league") || name.includes("championship") || name.includes("fa cup")) return "🏴";
  if (name.includes("ligue 1") || name.includes("coupe de france")) return "🇫🇷";
  if (name.includes("laliga") || name.includes("la liga") || name.includes("copa del rey")) return "🇪🇸";
  if (name.includes("serie a") || name.includes("coppa")) return "🇮🇹";
  if (name.includes("bundesliga") || name.includes("dfb")) return "🇩🇪";
  if (name.includes("champions") || name.includes("europa") || name.includes("conference")) return "🇪🇺";
  if (name.includes("eredivisie")) return "🇳🇱";
  if (name.includes("primeira") || name.includes("liga portugal")) return "🇵🇹";
  if (name.includes("pro league") && name.includes("saudi")) return "🇸🇦";
  return "⚽";
}

function renderMatches(matches) {
  if (!DOM.matches) return;

  const offlineBanner =
    usingCachedData && !navigator.onLine
      ? `<div style="background:#ffcc00; color:#000; text-align:center; padding:8px; font-weight:700; font-size:0.95rem; margin-bottom:12px;">
          ■■ MODE HORS LIGNE — Pronostics chargés depuis le cache
        </div>`
      : "";

  if (!matches || matches.length === 0) {
    DOM.matches.innerHTML = `${offlineBanner}<div class="no-events">Aucun match.</div>`;
    return;
  }

  const grouped = {};
  // Treat two independent market selections for the same fixture as two
  // full match cards. Each card keeps its own market, probability and share CTA.
  const standalone = matches.filter((match) => !match.combo_only).flatMap((match) => {
    const selections = Array.isArray(match.predictions) && match.predictions.length
      ? match.predictions.slice(0, 2) : [match.prediction || {}];
    return selections.filter((pick) => match.source !== "bsd" || match.is_finished || (match.recommendation_eligible === true && pick.recommendation_eligible === true)).map((pick) => ({
      ...match,
      id: String(match.id) + ":" + String(pick.selection_key || "primary"),
      prediction: pick,
      predictions: undefined,
    }));
  });
  if (standalone.length === 0) {
    DOM.matches.innerHTML = `${offlineBanner}<div class="no-events">Aucune sélection admissible disponible pour le moment.</div>`;
    return;
  }
  standalone.forEach((m) => {
    const league = m.league || "Autres ligues";
    if (!grouped[league]) grouped[league] = [];
    grouped[league].push(m);
  });

  let html = offlineBanner;
  const leagueOrder = [...POPULAR_LEAGUES, "Autres ligues"];
  const sortedLeagues = Object.keys(grouped).sort((a, b) => {
    const ia = leagueOrder.findIndex((l) => a.includes(l) || a === l);
    const ib = leagueOrder.findIndex((l) => b.includes(l) || b === l);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });

  sortedLeagues.forEach((league) => {
    const leagueCount = grouped[league].length;
    html += `
      <div class="league-header">
        <div class="league-header__title">
          <span class="league-flag" aria-hidden="true">${getLeagueFlag(league)}</span>
          <h2>${escapeHtml(league)}</h2>
        </div>
        <div class="league-header__meta">
          <span>${leagueCount} pronostic${leagueCount > 1 ? "s" : ""}</span>
          <span class="league-chevron" aria-hidden="true"><img src="assets/images/pronostics-premium/icon-chevron.webp?v=20261011-gen2" alt=""></span>
        </div>
      </div>`;

    grouped[league].forEach((m) => {
      const pred = m.prediction || {};
      const doubleChance = escapeHtml(pred.type || pred.label || pred.double_chance || "N/A");


      let confidence = toFloatSafe(pred.confidence, 0) || 0;
      if (confidence <= 1) confidence = confidence * 100;
      else if (confidence > 100) confidence = confidence / 100;
      confidence = Math.min(100, Math.round(confidence * 10) / 10);

      const matchTime = formatMatchTime(m.event_date);
      const statusFr = translateStatus(m.status);
      const statusClass = getStatusClass(m.status);
      const displayStatus = statusFr === "À venir"
        ? ({ today: "Aujourd’hui", tomorrow: "Demain", yesterday: "Hier" }[currentDay] || statusFr)
        : statusFr;

      const eventDate = m.event_date ? String(m.event_date).split("T")[0] : "";
      const yesterdayStr = getLocalDateString("yesterday");
      const verifiedDouble = eventDate === yesterdayStr && m.verified_double ? "checked" : "";

      const category = String(m.category || "").toLowerCase();
      const signalTier = String(pred.signal_tier || m.signal_tier || "").toUpperCase();
      const signalBadge = ["PREMIUM","QUALIFIE","OBSERVATION"].includes(signalTier)
        ? `<span class="v21-signal-tier v21-tier-${signalTier.toLowerCase()}">${escapeHtml(signalTier === "QUALIFIE" ? "QUALIFIÉ" : signalTier)}</span>` : "";
      const premiumBadge = category === "pro" || category === "vip"
        ? `<span class="badge-premium">${category === "vip" ? "VIP" : "PRO"}</span>`
        : "";

      const homeDefault = "assets/images/home.webp";
      const awayDefault = "assets/images/away.webp";

      const homeLogo = escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true));
      const awayLogo = escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false));

      const isWinner = !!m.verified_double;
      const winnerClass = isWinner ? "winner" : "";
      const visibleScore = getVisibleMatchScore(m);
      const matchFinished = isFinishedMatch(m);
      const resultBadge = isWinner
        ? `<span class="prediction-validation-badge ${matchFinished ? "won" : "validated"}"><span class="prediction-validation-badge__check" aria-hidden="true">✓</span>${matchFinished ? "GAGNÉ" : "VALIDÉ"}</span>`
        : "";
      const centerScore = visibleScore
        ? `<div class="match-score-center ${visibleScore.finished ? "is-final" : "is-live"}" aria-label="Score ${visibleScore.home} à ${visibleScore.away}">
            <strong>${visibleScore.home} - ${visibleScore.away}</strong>
            <span>${visibleScore.finished ? "Final" : "Live"}</span>
          </div>`
        : `<div class="vs">VS</div>`;

      const xpronosBadge = m.badge ? `<span class="xpronos-badge">${escapeHtml(m.badge)}</span>` : "";

      const matchDataForSharing = {
        home_team: m.home_team,
        away_team: m.away_team,
        prediction: {
          double_chance: pred.double_chance,
          type: pred.type || pred.label || pred.double_chance,
          confidence: confidence,
        },
      };
      const matchDataEncoded = encodeURIComponent(JSON.stringify(matchDataForSharing));

      const oddsValue = typeof pred.odds === "number"
        ? pred.odds.toFixed(2).replace(".", ",")
        : "—";
      const marketLabel = escapeHtml(
        pred.market_label || pred.market || pred.category_label || "Pronostic"
      );

      html += `
        <div class="match-card ${winnerClass}${isWinner ? " has-result-badge" : ""}" data-matchid="${escapeAttribute(m.id)}">
          <div class="win-effect"></div>
          ${resultBadge}

          <div class="match-info">
            <div class="match-meta">
              <span class="league-badge">${escapeHtml(m.league || "Ligue")}</span>
              <span class="match-schedule">
                <span class="status ${statusClass}">${displayStatus}</span>
                <span class="match-time">${matchTime}</span>
              </span>
              ${m.venue ? `<span class="match-venue">${escapeHtml(m.venue)}</span>` : ""}
            </div>

            <div class="teams">
              <div class="team">
                <img src="${homeLogo}"
                  alt="${escapeAttribute(m.home_team)}"
                  class="team-logo"
                  loading="lazy"
                  decoding="async"
                  onerror="this.onerror=null; this.src='${homeDefault}';">
                <span class="team-name">${escapeHtml(m.home_team)}</span>
                <span class="team-score">${m.home_score ?? "-"}</span>
              </div>

              ${centerScore}

              <div class="team">
                <img src="${awayLogo}"
                  alt="${escapeAttribute(m.away_team)}"
                  class="team-logo"
                  loading="lazy"
                  decoding="async"
                  onerror="this.onerror=null; this.src='${awayDefault}';">
                <span class="team-name">${escapeHtml(m.away_team)}</span>
                <span class="team-score">${m.away_score ?? "-"}</span>
              </div>
            </div>
          </div>

          <div class="analysis-panel ticket ${winnerClass}">
            <h4>Pronostic ${xpronosBadge} ${signalBadge}</h4>
            <p><strong>Pronostic :</strong> ${doubleChance}</p>

            <div class="prediction-market">
              <div class="prediction-market__pick">
                <span class="prediction-market__label">${marketLabel}</span>
                <strong class="prediction-market__value">${doubleChance}</strong>
              </div>
              <div class="prediction-market__odds">
                <span>Cote</span>
                <strong>${oddsValue}</strong>
              </div>
            </div>

            <div class="confidence-line">
              <span class="confidence-label">Fiabilité : <strong>${confidence}%</strong></span>
              <div class="confidence-bar"><div class="confidence-fill" data-value="${confidence}"></div></div>
            </div>

            ${premiumBadge}
            <button class="btn btn-secondary btn-share" data-match="${matchDataEncoded}"><span class="share-glyph" aria-hidden="true"><img src="assets/images/pronostics-premium/icon-share.webp?v=20261011-gen2" alt=""></span> Partager ce prono</button>
          </div>
        </div>
      `;    });
  });

  DOM.matches.innerHTML = html;

  requestAnimationFrame(() => {
    qsa(".confidence-fill").forEach((bar) => {
      const value = bar.getAttribute("data-value") || "0";
      bar.style.width = value + "%";
    });
  });
}

/* =======================================================
 HISTORY PAGE
======================================================= */
async function displayHistory() {
  if (!DOM.historyContainer) return;
  allData = await loadDataGeneric();

  if (!allData || !Array.isArray(allData.matches)) {
    DOM.historyContainer.innerHTML = '<div class="no-events">Aucun historique disponible.</div>';
    return;
  }

  const todayStr = getLocalDateString("today");
  const outcomeForBsdPick = (pick, home, away) => {
    const key = String(pick?.selection_key || "");
    const h = Number(home), a = Number(away);
    if (!Number.isInteger(h) || !Number.isInteger(a) || h < 0 || a < 0) return false;
    if (key === "1") return h > a;
    if (key === "X") return h === a;
    if (key === "2") return a > h;
    if (key === "1X") return h >= a;
    if (key === "X2") return a >= h;
    if (key === "12") return h !== a;
    if (key === "BTTS_YES") return h > 0 && a > 0;
    if (key === "BTTS_NO") return h === 0 || a === 0;
    const goals = key.match(/^(OVER|UNDER)_(15|25|35|45)$/);
    if (!goals) return false;
    const line = Number(goals[2]) / 10;
    return goals[1] === "OVER" ? h + a > line : h + a < line;
  };

  const historyMatches = allData.matches
    .filter((m) => {
      const d = getLocalDateFromEvent(m.event_date);
      return !m.combo_only && d && d < todayStr;
    })
    .flatMap((m) => {
      const choices = Array.isArray(m.predictions) && m.predictions.length
        ? m.predictions.slice(0, 2)
        : [m.prediction || {}];

      return choices.map((selection) => {
        const scoreKnown =
          Number.isInteger(Number(m.home_score)) &&
          Number.isInteger(Number(m.away_score)) &&
          Number(m.home_score) >= 0 &&
          Number(m.away_score) >= 0;
        const finished = Boolean(m.is_finished && scoreKnown);
        return {
          ...m,
          id: String(m.id) + ":" + String(selection.selection_key || "primary"),
          prediction: selection,
          history_finished: finished,
          verified_double: finished
            ? outcomeForBsdPick(selection, m.home_score, m.away_score)
            : false,
        };
      });
    })
    .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0));

  if (!historyMatches.length) {
    DOM.historyContainer.innerHTML = '<div class="no-events">Aucun match dans cette période.</div>';
    return;
  }

  const finished = historyMatches.filter((m) => m.history_finished);
  const winCount = finished.filter((m) => m.verified_double).length;
  const successRate = finished.length ? Math.round((winCount / finished.length) * 100) : 0;

  const totalNode = document.getElementById("history-total-count");
  const winNode = document.getElementById("history-win-count");
  const rateNode = document.getElementById("history-success-rate");
  const rateRing = document.getElementById("history-rate-ring");
  if (totalNode) totalNode.textContent = String(historyMatches.length);
  if (winNode) winNode.textContent = String(winCount);
  if (rateNode) rateNode.textContent = finished.length ? `${successRate}%` : "—";
  if (rateRing) rateRing.style.setProperty("--rate", String(successRate));

  let html = "";

  historyMatches.forEach((m) => {
    const pred = m.prediction || {};
    let confidence = toFloatSafe(pred.confidence, 0) || 0;
    if (confidence <= 1) confidence *= 100;
    else if (confidence > 100) confidence /= 100;
    confidence = Math.min(100, Math.max(0, Math.round(confidence)));

    const dateObj = new Date(m.event_date || "");
    const formattedDate = Number.isNaN(dateObj.getTime())
      ? "Date inconnue"
      : dateObj.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });

    const homeLogo = escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true));
    const awayLogo = escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false));
    const prediction = escapeHtml(pred.type || pred.label || pred.double_chance || "N/A");
    const odds = typeof pred.odds === "number"
      ? pred.odds.toFixed(2).replace(".", ",")
      : "—";
    const filledStars = Math.min(5, Math.max(0, Math.round(confidence / 20)));
    const stars = "★".repeat(filledStars) + "☆".repeat(5 - filledStars);

    const resultClass = !m.history_finished
      ? "pending"
      : (m.verified_double ? "won" : "lost");
    const resultLabel = !m.history_finished
      ? "En attente"
      : (m.verified_double ? "GAGNÉ" : "PERDU");
    const resultIcon = !m.history_finished
      ? "•"
      : (m.verified_double ? "✓" : "×");

    html += `
      <article class="history-row">
        <div class="history-competition">
          <div class="history-league">
            <span class="history-league-icon" aria-hidden="true">${getLeagueFlag(m.league || "")}</span>
            <span>${escapeHtml(m.league || "Compétition")}</span>
          </div>
          <span class="history-date">${escapeHtml(formattedDate)}</span>
        </div>

        <div class="history-match">
          <div class="history-team">
            <img src="${homeLogo}" alt="${escapeAttribute(m.home_team)}" loading="lazy"
              onerror="this.onerror=null;this.src='assets/images/home.webp';">
            <span>${escapeHtml(m.home_team)}</span>
          </div>
          <div class="history-score">
            <strong>${m.home_score ?? "—"} - ${m.away_score ?? "—"}</strong>
            <span>Score final</span>
          </div>
          <div class="history-team">
            <img src="${awayLogo}" alt="${escapeAttribute(m.away_team)}" loading="lazy"
              onerror="this.onerror=null;this.src='assets/images/away.webp';">
            <span>${escapeHtml(m.away_team)}</span>
          </div>
        </div>

        <div class="history-pick">
          <small>Notre pronostic</small>
          <strong>${prediction}</strong>
          <span>Cote : ${odds}</span>
        </div>

        <div class="history-confidence">
          <small>Fiabilité</small>
          <span class="history-stars" aria-label="${filledStars} étoiles sur 5">${stars}</span>
          <strong>${confidence}%</strong>
        </div>

        <div class="history-result">
          <div class="history-result-badge ${resultClass}"><span aria-hidden="true">${resultIcon}</span> ${resultLabel}</div>
          <small>${m.history_finished ? "Terminé" : "Non vérifié"}</small>
        </div>
      </article>
    `;
  });

  DOM.historyContainer.innerHTML = html;
}

/* =======================================================
 CONTENT GENERATION
======================================================= */
async function loadGeneratedContent() {
  if (generatedContentPromise) return generatedContentPromise;
  generatedContentPromise = (async () => {
    try {
      const [articlesResp, conseilsResp] = await Promise.all([
        fetch(`articles.json?t=${Date.now()}`, { cache: "no-cache" }).catch(() => null),
        fetch(`conseils.json?t=${Date.now()}`, { cache: "no-cache" }).catch(() => null),
      ]);
      window.generatedArticles = articlesResp && articlesResp.ok ? await articlesResp.json() : [];
      window.generatedConseils = conseilsResp && conseilsResp.ok ? await conseilsResp.json() : [];
    } catch (error) {
      console.error("Erreur contenu généré:", error);
      window.generatedArticles = [];
      window.generatedConseils = [];
    }
  })();
  return generatedContentPromise;
}

/* =======================================================
 PUBLISHED JSON EXTRAS
======================================================= */
async function fetchOptionalJson(file) {
  try {
    const r = await fetch(`${file}?t=${Date.now()}`, { cache: "no-cache" });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

async function loadPublishedExtras() {
  const [bookmakers, bonus, infos] = await Promise.all([
    fetchOptionalJson("bookmakers.json"),
    fetchOptionalJson("bonus.json"),
    fetchOptionalJson("infos.json"),
  ]);

  window.publishedBookmakers = Array.isArray(bookmakers) ? bookmakers.filter((b) => b && b.active !== false) : [];
  window.publishedBonus = Array.isArray(bonus) ? bonus.filter((b) => b && b.active !== false) : [];
  window.publishedInfos = Array.isArray(infos) ? infos.filter((i) => i && i.active !== false) : [];
}

/* =======================================================
 BLOG
======================================================= */
window.showArticleDetail = function (index) {
  const article = window.articlesData?.[index];
  if (!article) return;

  if (!DOM.articleModal) {
    const slug = article.slug || "";
    window.location.href = slug
      ? `articles/${encodeURIComponent(slug)}/`
      : `article.html?article=${encodeURIComponent(index)}`;
    return;
  }

  const title = stripMarkdown(article.title || "Article");
  const image = article.image_url || "assets/images/default-logo.png";
  const contentHtml = renderSafeRichContent(article.content || "");

  const titleEl = document.getElementById("article-modal-title");
  const imageEl = document.getElementById("article-modal-image");
  const contentEl = document.getElementById("article-modal-content");
  const linkEl = document.getElementById("article-modal-link");

  if (titleEl) titleEl.textContent = title;
  if (imageEl) {
    imageEl.src = image;
    imageEl.alt = title;
  }
  if (contentEl) contentEl.innerHTML = contentHtml;

  const slug = article.slug || "";
  if (linkEl) {
    linkEl.href = slug
      ? `articles/${encodeURIComponent(slug)}/`
      : `article.html?article=${encodeURIComponent(index)}`;
  }

  DOM.articleModal.style.display = "flex";
};

window.closeArticleModal = function () {
  if (DOM.articleModal) DOM.articleModal.style.display = "none";
};

function blogArticleCategory(article = {}) {
  const haystack = [
    article.title,
    article.keywords,
    article.type,
    article.topic_id,
    article.category,
  ].filter(Boolean).join(" ").toLowerCase();

  if (/transfert|mercato|recrutement|signature|prêt|pret/.test(haystack)) return "Transferts";
  if (/règlement|reglement|règle|regle|var|arbitrage|fair.?play/.test(haystack)) return "Règlement";
  if (/calendrier|programme|programmation|horaire|journée|journee/.test(haystack)) return "Calendrier";
  if (/championnat|compétition|competition|coupe|ligue|tournoi/.test(haystack)) return "Compétitions";
  if (/actualité|actualite|news|annonce|officiel|breaking/.test(haystack)) return "Actualités";
  if (/erreur|début|debut|conseil|guide|psychologie|astuce/.test(haystack)) return "Conseils";
  if (/tendance|saison|forme|serie|série/.test(haystack)) return "Tendances";
  if (/statistique|xg|donnée|donnee|décrypt|decrypt|analyse|tactique/.test(haystack)) return "Analyses";
  if (/bankroll|gestion|mise|discipline|budget|stratégie|strategie/.test(haystack)) return "Conseils";
  return "Analyses";
}

function blogCategoryIcon(category = "") {
  const base = "assets/images/blog-premium/";
  const icons = {
    "Actualités": "icon-blog-news.webp",
    "Analyses": "icon-blog-analysis.webp",
    "Conseils": "icon-blog-tips.webp",
    "Tendances": "icon-blog-trending.webp",
    "Calendrier": "icon-blog-schedule.webp",
    "Transferts": "icon-blog-transfers.webp",
    "Compétitions": "icon-blog-competitions.webp",
    "Règlement": "icon-blog-rules.webp",
  };
  return base + (icons[category] || "icon-blog-category.webp");
}

const blogViewState = { category: "Tous", query: "" };

function renderBlogPremiumCards() {
  if (!DOM.blogList) return;
  const allArticles = Array.isArray(window.articlesData) ? window.articlesData : [];
  const query = blogViewState.query.trim().toLowerCase();

  const visible = allArticles
    .map((article, originalIndex) => ({ article, originalIndex }))
    .filter(({ article }) => {
      const category = blogArticleCategory(article);
      if (blogViewState.category !== "Tous" && category !== blogViewState.category) return false;
      if (!query) return true;
      const haystack = [
        article.title,
        article.meta_description,
        article.excerpt,
        article.content,
        article.keywords,
        category,
      ].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(query);
    });

  const countNode = document.getElementById("blog-visible-count");
  if (countNode) countNode.textContent = `${visible.length} article${visible.length > 1 ? "s" : ""}`;

  DOM.blogList.innerHTML =
    visible.map(({ article, originalIndex }) => {
      const title = stripMarkdown(article.title || "Article");
      const excerpt = stripMarkdown(
        article.meta_description || article.excerpt || article.content || ""
      ).replace(title, "").trim().slice(0, 175);
      const category = blogArticleCategory(article);
      const date = formatBlogDate(article.date || article.published_at);
      const categoryIcon = blogCategoryIcon(category);
      const image = article.image_url || "assets/images/blog-premium/hero-blog.webp";

      return `
        <article class="blog-premium-card" role="button" tabindex="0"
          data-blog-category="${escapeAttribute(category)}"
          aria-label="Lire l'article ${escapeAttribute(title)}"
          onclick="showArticleDetail(${originalIndex})"
          onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();showArticleDetail(${originalIndex})}">
          <div class="blog-card-media">
            <img src="${escapeAttribute(image)}" alt="${escapeAttribute(title)}" loading="lazy"
              onerror="this.onerror=null;this.src='assets/images/blog-premium/hero-blog.webp';">
            <span class="blog-card-category"><img src="${categoryIcon}" alt="" aria-hidden="true">${escapeHtml(category)}</span>
            <span class="blog-card-date">${escapeHtml(date)}</span>
          </div>
          <div class="blog-card-body">
            <div class="blog-card-meta"><img src="${categoryIcon}" alt="" aria-hidden="true"><span>${escapeHtml(category)}</span></div>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(excerpt)}${excerpt.length >= 175 ? "…" : ""}</p>
            <span class="blog-card-cta">Lire l'article <span aria-hidden="true">›</span></span>
          </div>
        </article>
      `;
    }).join("") ||
    '<div class="no-events">Aucun article ne correspond à votre recherche.</div>';
}

function setupBlogPremiumControls() {
  const search = document.getElementById("blog-search");
  const filters = Array.from(document.querySelectorAll("[data-blog-filter]"));

  if (search && search.dataset.blogReady !== "1") {
    search.dataset.blogReady = "1";
    search.addEventListener("input", () => {
      blogViewState.query = search.value || "";
      renderBlogPremiumCards();
    });
  }

  filters.forEach((button) => {
    if (button.dataset.blogReady === "1") return;
    button.dataset.blogReady = "1";
    button.addEventListener("click", () => {
      blogViewState.category = button.dataset.blogFilter || "Tous";
      filters.forEach((node) => node.classList.toggle("is-active", node === button));
      renderBlogPremiumCards();
    });
  });
}

function formatBlogDate(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

async function displayBlogList() {
  if (!DOM.blogList) return;
  await loadGeneratedContent();
  const data = await loadDataGeneric();

  const allArticles = [...(window.generatedArticles || []), ...((data?.blog) || [])]
    .filter((a) => a?.active !== false)
    .sort((a, b) => new Date(b.date || b.published_at || 0) - new Date(a.date || a.published_at || 0));
  window.articlesData = allArticles;

  const horizontalContainer = document.getElementById("blog-horizontal-list");
  if (horizontalContainer) {
    horizontalContainer.innerHTML = allArticles
      .slice(0, 8)
      .map(
        (article, index) => `
      <div class="horizontal-item" onclick="showArticleDetail(${index})">
        <img src="${escapeAttribute(article.image_url || "assets/images/default-logo.png")}" alt="${escapeAttribute(stripMarkdown(article.title || "Article"))}">
        <div class="item-title">${escapeHtml(stripMarkdown(article.title || "Article"))}</div>
      </div>
    `
      )
      .join("");
  }

  setupBlogPremiumControls();
  renderBlogPremiumCards();
}

function setMetaContent(id, value) {
  const el = document.getElementById(id);
  if (el) el.setAttribute("content", value);
}

function ensureCanonical(href) {
  let canonical = document.querySelector('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.rel = "canonical";
    document.head.appendChild(canonical);
  }
  canonical.href = href;
}

function updateArticleSeo(article, resolvedSlug) {
  const title = stripMarkdown(article.title || "Article");
  const metaDesc = (article.meta_description || article.excerpt || "").slice(0, 160) || `Analyse et pronostic : ${title}`;
  const url = new URL(window.location.href);

  const canonicalUrl = resolvedSlug
    ? `${url.origin}${url.pathname}?slug=${encodeURIComponent(resolvedSlug)}`
    : window.location.href;

  document.title = `${title} - Mr XPRONOS`;

  const descEl = document.getElementById("article-description");
  if (descEl) descEl.setAttribute("content", metaDesc);

  setMetaContent("og-title", title);
  setMetaContent("og-description", metaDesc);
  setMetaContent("og-url", canonicalUrl);
  setMetaContent("og-image", article.og_image || article.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

  setMetaContent("twitter-title", title);
  setMetaContent("twitter-description", metaDesc);
  setMetaContent("twitter-image", article.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

  ensureCanonical(canonicalUrl);

  const jsonLdEl = document.getElementById("article-jsonld");
  if (jsonLdEl) {
    const baseArticle = {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: title,
      author: { "@type": "Person", name: article.author || "Mr XPRONOS" },
      datePublished: article.date || article.published_at || new Date().toISOString(),
      image: [article.image_url].filter(Boolean),
      mainEntityOfPage: canonicalUrl,
    };

    if (Array.isArray(article.faq) && article.faq.length) {
      const graph = [
        baseArticle,
        {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: article.faq
            .filter((x) => x && x.q && x.a)
            .map((x) => ({
              "@type": "Question",
              name: String(x.q),
              acceptedAnswer: { "@type": "Answer", text: String(x.a) },
            })),
        },
      ];
      jsonLdEl.textContent = JSON.stringify({ "@graph": graph }, null, 2);
    } else {
      jsonLdEl.textContent = JSON.stringify(baseArticle, null, 2);
    }
  }
}

async function displayBlogPost() {
  if (!DOM.blogPost) return;
  await loadGeneratedContent();
  const data = await loadDataGeneric();

  const allArticles = [...(window.generatedArticles || []), ...((data?.blog) || [])].filter((a) => a?.active !== false);

  const params = new URLSearchParams(window.location.search);
  const slug = params.get("slug");
  const articleIndex = params.get("article") ?? params.get("id");

  let article = null;
  if (slug) article = allArticles.find((a) => (a.slug || "") === slug) || null;
  if (!article && articleIndex !== null && articleIndex !== "") {
    const idx = parseInt(articleIndex, 10);
    if (!isNaN(idx) && allArticles[idx]) article = allArticles[idx];
  }
  if (!article) {
    DOM.blogPost.innerHTML = '<div class="no-events">Article introuvable.</div>';
    return;
  }

  const title = stripMarkdown(article.title || "Article");
  const contentHtml = renderSafeRichContent(article.content || "");

  DOM.blogPost.innerHTML = `
    <article class="card article-page-card">
      <img src="${escapeAttribute(article.image_url || "assets/images/default-logo.png")}" alt="${escapeAttribute(title)}" class="news-image" loading="lazy">
      <h1>${escapeHtml(title)}</h1>
      <div class="article-content">${contentHtml}</div>
    </article>
  `;

  updateArticleSeo(article, article.slug || slug || "");
  const titleMeta = document.getElementById("article-title");
  if (titleMeta) titleMeta.textContent = `${title} - Mr XPRONOS`;
}

/* =======================================================
 CONSEILS
======================================================= */
window.openConseilPage = function (slug) {
  if (!slug) return;
  window.location.href = `conseils/${encodeURIComponent(slug)}/`;
};

function updateConseilSeo(conseil, resolvedSlug) {
  const title = stripMarkdown(conseil.title || "Conseil");
  const metaDesc = (conseil.excerpt || "").slice(0, 160) || `Conseil pratique : ${title}`;
  const url = new URL(window.location.href);

  const canonicalUrl = resolvedSlug
    ? `${url.origin}${url.pathname}?slug=${encodeURIComponent(resolvedSlug)}`
    : window.location.href;

  document.title = `${title} - Mr XPRONOS`;

  const descEl = document.getElementById("conseil-description");
  if (descEl) descEl.setAttribute("content", metaDesc);

  setMetaContent("og-title", title);
  setMetaContent("og-description", metaDesc);
  setMetaContent("og-url", canonicalUrl);
  setMetaContent("og-image", conseil.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

  setMetaContent("twitter-title", title);
  setMetaContent("twitter-description", metaDesc);
  setMetaContent("twitter-image", conseil.image_url || `${BASE_SITE_URL}assets/images/preview.jpg`);

  ensureCanonical(canonicalUrl);
}

function conseilVisualMeta(conseil = {}) {
  const haystack = [conseil.title, conseil.keywords, conseil.slug, conseil.category]
    .filter(Boolean).join(" ").toLowerCase();
  const base = "assets/images/conseils-premium/";

  if (/bankroll|budget|mise/.test(haystack)) {
    return { label: "Gestion", icon: base + "icon-conseils-bankroll.webp" };
  }
  if (/cote|value|valeur/.test(haystack)) {
    return { label: "Value", icon: base + "icon-conseils-value.webp" };
  }
  if (/erreur|piège|piege|danger|tilt/.test(haystack)) {
    return { label: "Pièges", icon: base + "icon-conseils-danger.webp" };
  }
  if (/responsable|discipline|limite/.test(haystack)) {
    return { label: "Discipline", icon: base + "icon-conseils-discipline.webp" };
  }
  if (/analyse|match|statistique|h2h|xg/.test(haystack)) {
    return { label: "Analyse", icon: base + "icon-conseils-analysis.webp" };
  }
  return { label: "Guide", icon: base + "icon-conseils-guide.webp" };
}

async function displayConseils() {
  if (!DOM.conseilsList) return;
  await loadGeneratedContent();
  const data = await loadDataGeneric();

  const allConseils = window.generatedConseils && window.generatedConseils.length
    ? window.generatedConseils
    : (data?.conseils) || [];

  window.conseilsData = allConseils
    .filter((c) => c?.active !== false)
    .sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

  const horizontalContainer = document.getElementById("conseils-horizontal-list");
  if (horizontalContainer) {
    horizontalContainer.innerHTML = window.conseilsData
      .slice(0, 8)
      .map(
        (conseil) => `
      <div class="horizontal-item" onclick="openConseilPage('${escapeAttribute(conseil.slug || "")}')">
        <img src="${escapeAttribute(conseil.image_url || "assets/images/default-logo.png")}" alt="${escapeAttribute(stripMarkdown(conseil.title || "Conseil"))}">
        <div class="item-title">${escapeHtml(stripMarkdown(conseil.title || "Conseil"))}</div>
      </div>
    `
      )
      .join("");
  }

  DOM.conseilsList.innerHTML =
    window.conseilsData
      .map((conseil) => {
        const title = stripMarkdown(conseil.title || "Conseil");
        const excerpt = stripMarkdown(
          conseil.excerpt || conseil.meta_description || conseil.content || ""
        ).replace(title, "").trim().slice(0, 180);
        const visual = conseilVisualMeta(conseil);
        const slug = escapeAttribute(conseil.slug || "");
        const cover = conseil.image_url || "assets/images/conseils-premium/hero-conseils.webp";

        return `
          <article class="conseil-premium-card" role="link" tabindex="0"
            data-conseil-type="${escapeAttribute(visual.label)}"
            aria-label="Lire le conseil ${escapeAttribute(title)}"
            onclick="openConseilPage('${slug}')"
            onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openConseilPage('${slug}')}">
            <div class="conseil-card-media">
              <img src="${escapeAttribute(cover)}"
                alt="${escapeAttribute(title)}" loading="lazy"
                onerror="this.onerror=null;this.src='assets/images/conseils-premium/hero-conseils.webp';">
              <span class="conseil-card-icon" aria-hidden="true"><img src="${visual.icon}" alt=""></span>
              <span class="conseil-card-type"><img src="${visual.icon}" alt="" aria-hidden="true">${escapeHtml(visual.label)}</span>
            </div>
            <div class="conseil-card-body">
              <span class="conseil-card-kicker">CONSEIL MR XPRONOS</span>
              <h3>${escapeHtml(title)}</h3>
              <p>${escapeHtml(excerpt)}${excerpt.length >= 180 ? "…" : ""}</p>
              <span class="conseil-card-cta">Lire le guide <span aria-hidden="true">›</span></span>
            </div>
          </article>
        `;
      })
      .join("") || '<div class="no-events">Aucun conseil disponible pour le moment.</div>';
}

async function displayConseilPost() {
  if (!DOM.conseilPost) return;
  await loadGeneratedContent();
  const data = await loadDataGeneric();

  const allConseils = window.generatedConseils && window.generatedConseils.length ? window.generatedConseils : (data?.conseils) || [];
  const conseils = allConseils.filter((c) => c?.active !== false);

  const params = new URLSearchParams(window.location.search);
  const slug = params.get("slug");

  let conseil = null;
  if (slug) conseil = conseils.find((c) => (c.slug || "") === slug) || null;

  if (!conseil) {
    DOM.conseilPost.innerHTML = '<div class="no-events">Conseil introuvable.</div>';
    return;
  }

  const title = stripMarkdown(conseil.title || "Conseil");
  const contentHtml = renderSafeRichContent(conseil.content || "");

  DOM.conseilPost.innerHTML = `
    <article class="card article-page-card">
      <img src="${escapeAttribute(conseil.image_url || "assets/images/default-logo.png")}" alt="${escapeAttribute(title)}" class="news-image" loading="lazy">
      <h1>${escapeHtml(title)}</h1>
      <div class="article-content">${contentHtml}</div>
    </article>
  `;

  updateConseilSeo(conseil, conseil.slug || slug || "");
}

window.showConseilDetail = function (index) {
  const conseil = window.conseilsData?.[index];
  if (!conseil || !DOM.conseilModal) return;

  document.getElementById("conseil-modal-title").textContent = stripMarkdown(conseil.title || "Conseil");
  const img = document.getElementById("conseil-modal-image");
  if (img) {
    img.src = conseil.image_url || "assets/images/default-logo.png";
    img.alt = stripMarkdown(conseil.title || "Conseil");
  }

  const contentEl = document.getElementById("conseil-modal-content");
  if (contentEl) contentEl.innerHTML = renderSafeRichContent(conseil.content || "");
  DOM.conseilModal.style.display = "flex";
};

window.closeConseilModal = function () {
  if (DOM.conseilModal) DOM.conseilModal.style.display = "none";
};

/* =======================================================
 INFOS / NEWS
======================================================= */
async function displayInfos() {
  if (!DOM.infosList) return;

  const data = await loadDataGeneric();
  const infos = Array.isArray(window.publishedInfos) && window.publishedInfos.length ? window.publishedInfos : data?.infos || [];

  DOM.infosList.innerHTML = infos.length
    ? infos
        .map(
          (i) => `
        <div class="news-card card">
          <h3>${escapeHtml(i.title || "")}</h3>
          <p>${escapeHtml(i.content || "")}</p>
        </div>
      `
        )
        .join("")
    : '<div class="no-events">Aucune info disponible.</div>';
}

function footballNewsCategory(item = {}) {
  if (item.category) return String(item.category);
  const text = [item.title, item.summary].filter(Boolean).join(" ").toLowerCase();
  if (/champions league|uefa/.test(text)) return "Champions League";
  if (/transfer|sign|loan|gossip|mercato/.test(text)) return "Mercato";
  if (/injur|blessur|fitness/.test(text)) return "Blessures";
  if (/premier league|england|arsenal|city|united|liverpool|chelsea/.test(text)) return "Premier League";
  if (/ligue 1|psg|france|french/.test(text)) return "Ligue 1";
  if (/laliga|real madrid|barcelona|spain/.test(text)) return "Liga";
  if (/ital|serie a/.test(text)) return "Serie A";
  return "Football";
}

function footballNewsIcon(category = "") {
  const base = "assets/images/infos-premium/";
  const icons = {
    "Football": "icon-infos-football.webp",
    "Champions League": "icon-infos-champions.webp",
    "Mercato": "icon-infos-mercato.webp",
    "Blessures": "icon-infos-injuries.webp",
    "Premier League": "icon-infos-premierleague.webp",
    "Ligue 1": "icon-infos-ligue1.webp",
    "Liga": "icon-infos-liga.webp",
    "Serie A": "icon-infos-seriea.webp",
  };
  return base + (icons[category] || "icon-infos-football.webp");
}

const infosViewState = { category: "Tous", query: "" };

function renderFootNewsCards() {
  if (!DOM.footNewsContainer) return;
  const allNews = Array.isArray(window.newsData) ? window.newsData : [];
  const query = infosViewState.query.trim().toLowerCase();

  const visible = allNews
    .map((item, originalIndex) => ({ item, originalIndex }))
    .filter(({ item }) => {
      const category = footballNewsCategory(item);
      if (infosViewState.category !== "Tous" && category !== infosViewState.category) return false;
      if (!query) return true;
      return [item.title, item.summary, category]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query);
    });

  const countNode = document.getElementById("infos-visible-count");
  if (countNode) countNode.textContent = `${visible.length} actualité${visible.length > 1 ? "s" : ""}`;

  DOM.footNewsContainer.innerHTML = visible.map(({ item, originalIndex }, position) => {
    const title = item.title || "Actualité";
    const summary = String(item.summary || "").slice(0, position === 0 ? 320 : 190);
    const category = footballNewsCategory(item);
    const categoryIcon = footballNewsIcon(category);
    const date = formatFootballNewsDate(item.published);
    const featured = position === 0;
    const titleHtml = featured ? featuredNewsTitleHtml(title) : escapeHtml(title);
    const fallback = "assets/images/infos-premium/hero-infos.webp";

    return `
      <article class="news-premium-card${featured ? " featured" : ""}" role="button" tabindex="0"
        data-news-category="${escapeAttribute(category)}"
        aria-label="Lire l'actualité ${escapeAttribute(title)}"
        onclick="showNewsDetail(${originalIndex})"
        onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();showNewsDetail(${originalIndex})}">
        <div class="news-media">
          <img src="${escapeAttribute(item.image || fallback)}" alt="${escapeAttribute(title)}" loading="lazy"
            onerror="this.onerror=null;this.src='${fallback}';">
          <span class="news-category"><img src="${categoryIcon}" alt="" aria-hidden="true">${escapeHtml(category)}</span>
        </div>
        <div class="news-premium-body">
          <div class="news-date"><img src="assets/images/infos-premium/icon-infos-clock.webp" alt="" aria-hidden="true"><span>${escapeHtml(date)}</span></div>
          <h3>${titleHtml}</h3>
          <p>${escapeHtml(summary)}${String(item.summary || "").length > summary.length ? "…" : ""}</p>
          <span class="news-card-cta">${item.manual ? "Voir le contenu" : "Lire la suite"} <span aria-hidden="true">›</span></span>
        </div>
      </article>
    `;
  }).join("") || '<div class="no-events">Aucune actualité ne correspond à votre recherche.</div>';
}

function setupInfosPremiumControls() {
  const search = document.getElementById("infos-search");
  const filters = Array.from(document.querySelectorAll("[data-infos-filter]"));

  if (search && search.dataset.infosReady !== "1") {
    search.dataset.infosReady = "1";
    search.addEventListener("input", () => {
      infosViewState.query = search.value || "";
      renderFootNewsCards();
    });
  }

  filters.forEach((button) => {
    if (button.dataset.infosReady === "1") return;
    button.dataset.infosReady = "1";
    button.addEventListener("click", () => {
      infosViewState.category = button.dataset.infosFilter || "Tous";
      filters.forEach((node) => node.classList.toggle("is-active", node === button));
      renderFootNewsCards();
    });
  });
}

function formatFootballNewsDate(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    + " à "
    + date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function featuredNewsTitleHtml(title = "") {
  const words = String(title).trim().split(/\s+/).filter(Boolean);
  if (words.length < 6) return escapeHtml(title);
  const pivot = Math.max(3, Math.floor(words.length * 0.56));
  const first = escapeHtml(words.slice(0, pivot).join(" "));
  const second = escapeHtml(words.slice(pivot).join(" "));
  return `${first} <span>${second}</span>`;
}

async function displayFootNews() {
  if (!DOM.footNewsContainer) return;
  try {
    const resp = await fetch(`footnews.json?t=${Date.now()}`, { cache: "no-cache" });
    const rssNews = resp.ok ? await resp.json() : [];

    const manualInfos = Array.isArray(window.publishedInfos) ? window.publishedInfos : [];
    const merged = [
      ...manualInfos.map((i) => ({
        title: i.title,
        summary: i.content,
        image: i.image_url || null,
        link: null,
        published: i.date || i.published_at || new Date().toISOString(),
        category: i.category || i.tag || null,
        manual: true,
      })),
      ...(Array.isArray(rssNews) ? rssNews : []).map((n) => ({ ...n, manual: false })),
    ].sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));

    if (!merged.length) {
      DOM.footNewsContainer.innerHTML = '<div class="no-events">Aucune actualité pour le moment.</div>';
      return;
    }

    window.newsData = merged;
    setupInfosPremiumControls();
    renderFootNewsCards();
  } catch (error) {
    console.error("Erreur actualités:", error);
    DOM.footNewsContainer.innerHTML = '<div class="error">Impossible de charger les actualités.</div>';
  }
}

window.showNewsDetail = function (index) {
  const news = window.newsData?.[index];
  if (!news || !DOM.newsModal) return;

  const titleEl = document.getElementById("news-modal-title");
  const img = document.getElementById("news-modal-image");
  const contentEl = document.getElementById("news-modal-content");
  const linkEl = document.getElementById("news-modal-link");

  if (titleEl) titleEl.textContent = news.title || "Actualité";
  if (img) {
    img.src = news.image || "assets/images/default-logo.png";
    img.alt = news.title || "Actualité";
    img.style.display = news.image ? "block" : "none";
  }
  if (contentEl) contentEl.innerHTML = renderSafeRichContent(news.summary || "");
  if (linkEl) {
    if (news.manual || !news.link) {
      linkEl.style.display = "none";
    } else {
      linkEl.style.display = "inline-block";
      linkEl.href = news.link || "#";
      linkEl.target = "_blank";
      linkEl.rel = "noopener noreferrer";
    }
  }
  DOM.newsModal.style.display = "flex";
};

window.closeNewsModal = function () {
  if (DOM.newsModal) DOM.newsModal.style.display = "none";
};

/* =======================================================
 BONUS
======================================================= */
function initBonusPage() {
  const copyBonusCodeButton = document.getElementById("bonus-copy-code");
  if (copyBonusCodeButton && !copyBonusCodeButton.dataset.ready) {
    copyBonusCodeButton.dataset.ready = "1";
    copyBonusCodeButton.addEventListener("click", async () => {
      const ok = await copyText("XPVIP");
      const original = copyBonusCodeButton.textContent;
      copyBonusCodeButton.textContent = ok ? "Code copié ✓" : "Copiez : XPVIP";
      setTimeout(() => { copyBonusCodeButton.textContent = original; }, 1800);
    });
  }

  const publishedBonus = Array.isArray(window.publishedBonus) ? window.publishedBonus : [];
  const publishedBookmakers = Array.isArray(window.publishedBookmakers) ? window.publishedBookmakers : [];

  if (publishedBonus.length && DOM.bonusGrid) {
    window.currentPublishedBonus = publishedBonus;

    const grouped = {};
    publishedBonus.forEach((b) => {
      const key = (b.bookmaker || "Autres").trim();
      grouped[key] = grouped[key] || [];
      grouped[key].push(b);
    });

    const bookmakerNames = Object.keys(grouped).sort();

    if (DOM.bonusSelect) {
      DOM.bonusSelect.innerHTML = bookmakerNames
        .map((name) => `<option value="${escapeAttribute(name)}">${escapeHtml(name)}</option>`)
        .join("");

      DOM.bonusSelect.addEventListener("change", () => {
        renderBonusOffers(DOM.bonusSelect.value);
      });
    }

    function renderBonusOffers(bookmakerName) {
      const list = grouped[bookmakerName] || [];

      DOM.bonusGrid.innerHTML =
        list
          .map((b) => {
            const bonusIndex = publishedBonus.indexOf(b);
            const code = String(b.code || "").trim();

            return `
        <div class="bookmaker-card bonus-bookmaker-card" data-bonus-index="${bonusIndex}">
          <img src="${escapeAttribute(b.image || "assets/images/default-logo.webp")}"
               alt="${escapeAttribute(b.title || "Bonus")}"
               loading="lazy"
               decoding="async"
               onerror="this.onerror=null; this.src='assets/images/default-logo.webp';">

          <div class="bonus-card-body">
            <div class="bonus-bookmaker-name">${escapeHtml(b.bookmaker || "Bookmaker")}</div>
            <h3>${escapeHtml(b.title || "Bonus")}</h3>
            <p>${escapeHtml(b.description || "")}</p>

            ${code ? `<div class="bonus-card-meta"><span class="bonus-code">Code : ${escapeHtml(code)}</span></div>` : ""}
            ${b.footer ? `<div class="muted bonus-card-footer">${escapeHtml(b.footer)}</div>` : ""}

            <div class="bonus-card-actions">
              <button class="btn btn-secondary" type="button" onclick="openPublishedBonusModal(${bonusIndex})">Détails</button>
              ${b.link ? `<a href="${escapeAttribute(b.link)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Profiter de l'offre</a>` : ""}
            </div>
          </div>
        </div>
      `;
          })
          .join("") || '<div class="no-events">Aucune offre active.</div>';
    }

    renderBonusOffers(bookmakerNames[0]);
    return;
  }

  window.currentPublishedBonus = [];

  const defaultBookmakers = [
    {
      name: "1xBet",
      logo: "assets/images/1xbet.webp",
      url: "https://reffpa.com/L?tag=d_2054511m_1573c_&site=2054511&ad=1573",
      desc: "Bonus de bienvenue jusqu'à 130€",
    },
    { name: "1win", logo: "assets/images/1win.webp", url: "https://1wrbgb.com/?open=register&p=qqcw", desc: "Bonus exclusif avec XPVIP" },
    { name: "Betwinner", logo: "assets/images/betwinner.webp", url: "https://bwredir.com/299Y", desc: "Offre spéciale nouveaux joueurs" },
    { name: "Melbet", logo: "assets/images/melbet.webp", url: "https://refpa3665.com/L?tag=d_3034561m_57041c_&site=3034561&ad=57041", desc: "Bonus premium Melbet avec inscription rapide" },
    { name: "Linebet", logo: "assets/images/linebet.webp", url: "https://lb-aff.com/L?tag=d_3072389m_22611c_&site=3072389&ad=22611", desc: "Bonus et promotions spéciales Linebet" },
    { name: "Betclic", logo: "assets/images/betclic.webp", url: "https://betpari-click.com/2vY0?extid=USD", desc: "Offre de bienvenue Betclic" },
  ];

  const sourceBookmakers = publishedBookmakers.length
    ? publishedBookmakers.map((b) => ({
        name: b.name || "Bookmaker",
        logo: b.logo || "assets/images/default-logo.webp",
        url: b.url || "#",
        desc: b.description || b.desc || `Bonus exclusif chez ${b.name || "ce bookmaker"}`,
      }))
    : defaultBookmakers;

  window.currentBonusBookmakers = sourceBookmakers;

  if (DOM.bonusSelect) {
    DOM.bonusSelect.innerHTML = sourceBookmakers.map((b, i) => `<option value="${i}">${escapeHtml(b.name)}</option>`).join("");
    DOM.bonusSelect.addEventListener("change", () => {
      const index = parseInt(DOM.bonusSelect.value, 10);
      highlightBonusCard(index);
    });
  }

  renderBonusGrid(sourceBookmakers);
}

function renderBonusGrid(bookmakers) {
  if (!DOM.bonusGrid) return;
  DOM.bonusGrid.innerHTML = bookmakers
    .map(
      (b, i) => `
    <article class="bonus-premium-card bonus-bookmaker-card" data-index="${i}">
      <div class="bonus-card-head">
        <img src="${escapeAttribute(b.logo || "assets/images/default-logo.webp")}"
             alt="${escapeAttribute(b.name || "Bookmaker")}"
             loading="lazy"
             onerror="this.onerror=null; this.src='assets/images/default-logo.webp';">
        ${i === 0 ? '<span class="bonus-card-badge">SÉLECTION</span>' : ""}
      </div>
      <div class="bonus-card-body">
        <h3>${escapeHtml(b.name || "Bookmaker")}</h3>
        <p>${escapeHtml(b.desc || b.description || "Bonus exclusif bookmaker")}</p>
        <div class="bonus-actions">
          <a href="${escapeAttribute(b.url || "#")}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Voir l'offre</a>
          <button class="btn btn-secondary" type="button" onclick="openBonusModal(${i})">Détails</button>
        </div>
      </div>
    </article>
  `
    )
    .join("");
}

function highlightBonusCard(index) {
  qsa(".bonus-bookmaker-card").forEach((card) => card.classList.remove("active-bonus-card"));
  const target = document.querySelector(`.bonus-bookmaker-card[data-index="${index}"]`);
  if (target) {
    target.classList.add("active-bonus-card");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

window.openBonusModal = function (index) {
  const b = window.currentBonusBookmakers?.[index];
  if (!b || !DOM.bonusModal) return;

  const titleEl = document.getElementById("bonus-modal-title");
  const img = document.getElementById("bonus-modal-image");
  const descEl = document.getElementById("bonus-modal-description");
  const footerEl = document.getElementById("bonus-modal-footer");
  const linkEl = document.getElementById("bonus-modal-link");

  if (titleEl) titleEl.textContent = b.name;
  if (img) {
    img.src = b.logo || "assets/images/default-logo.webp";
    img.alt = b.name || "Bookmaker";
  }

  if (descEl) {
    descEl.innerHTML = `
      <p>${escapeHtml(b.desc || b.description || "Bonus exclusif bookmaker")}</p>
      <p style="margin-top:10px;">Utilisez le code promo <strong>XPVIP</strong> si l'offre le permet.</p>
    `;
  }

  if (footerEl) footerEl.textContent = "Inscription via notre lien recommandé.";

  if (linkEl) {
    linkEl.href = b.url || "#";
    linkEl.target = "_blank";
    linkEl.rel = "noopener noreferrer";
  }

  DOM.bonusModal.style.display = "flex";
};

window.openPublishedBonusModal = function (index) {
  const b = window.currentPublishedBonus?.[index];
  if (!b || !DOM.bonusModal) return;

  const titleEl = document.getElementById("bonus-modal-title");
  const img = document.getElementById("bonus-modal-image");
  const descEl = document.getElementById("bonus-modal-description");
  const footerEl = document.getElementById("bonus-modal-footer");
  const linkEl = document.getElementById("bonus-modal-link");

  if (titleEl) {
    const bookmaker = b.bookmaker ? `${b.bookmaker} — ` : "";
    titleEl.textContent = bookmaker + (b.title || "Bonus");
  }

  if (img) {
    img.src = b.image || "assets/images/default-logo.webp";
    img.alt = b.title || b.bookmaker || "Bonus";
  }

  if (descEl) {
    const code = String(b.code || "").trim();
    descEl.innerHTML = `
      <p>${escapeHtml(b.description || "")}</p>
      ${code ? `<p class="bonus-modal-code">Code : <strong>${escapeHtml(code)}</strong></p>` : ""}
    `;
  }

  if (footerEl) {
    const footer = b.footer ? `<div>${escapeHtml(b.footer)}</div>` : "";
    const official = b.official_url
      ? `<a class="bonus-official-link" href="${escapeAttribute(b.official_url)}" target="_blank" rel="noopener noreferrer">Voir les conditions officielles</a>`
      : "";
    footerEl.innerHTML = footer + official;
  }

  if (linkEl) {
    linkEl.href = b.link || "#";
    linkEl.target = "_blank";
    linkEl.rel = "noopener noreferrer";
    linkEl.textContent = "Profiter de l'offre";
  }

  DOM.bonusModal.style.display = "flex";
};

window.closeBonusModal = function () {
  if (DOM.bonusModal) DOM.bonusModal.style.display = "none";
};

/* =======================================================
 HOME WIDGETS (nouvelle structure)
======================================================= */
function normalizeConfidence(conf) {
  let c = toFloatSafe(conf, 0) || 0;
  if (c <= 1) c = c * 100;
  else if (c > 100) c = c / 100;
  return Math.min(100, Math.round(c));
}

/**
 * ✅ REFAIT : cartes HOME propres (Top coupons + Validés)
 * - meilleure structure
 * - logos avec fallback onerror
 * - infos alignées + badge
 */
function renderHomePickCard(m, { winner = false } = {}) {
  const pred = m.prediction || {};
  const conf = normalizeConfidence(pred.confidence);
  const pick = pred.type || pred.label || pred.double_chance || "N/A";
  const league = m.league || "Ligue";
  const time = formatMatchTime(m.event_date);
  const category = String(m.category || "simple").toLowerCase();
  const categoryLabel = category === "vip" ? "VIP" : category === "pro" ? "PRO" : "SIMPLE";

  const homeDefault = "assets/images/home.webp";
  const awayDefault = "assets/images/away.webp";
  const homeLogo = escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true));
  const awayLogo = escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false));
  const href = winner ? "historique.html" : "pronos.html";

  return `
    <a class="pick-card ${winner ? "pick-card--winner" : ""}" href="${href}" aria-label="${winner ? "Voir ce résultat dans l’historique" : "Voir cette sélection dans les pronostics"}">
      <div class="pick-badge">${winner ? "GAGNÉ" : "SÉLECTION"}</div>
      <div class="pick-category pick-category--${escapeAttribute(category)}">${categoryLabel}</div>

      <div class="pick-head">
        <div class="pick-league" title="${escapeAttribute(league)}">${escapeHtml(league)}</div>
        <div class="pick-time">${escapeHtml(time)}</div>
      </div>

      <div class="pick-teams">
        <div class="pick-team">
          <img class="pick-logo"
            src="${homeLogo}"
            alt="${escapeAttribute(m.home_team)}"
            loading="lazy" decoding="async"
            onerror="this.onerror=null;this.src='${homeDefault}';">
          <div class="pick-team-name" title="${escapeAttribute(m.home_team)}">${escapeHtml(m.home_team)}</div>
        </div>

        <div class="pick-vs">
          ${winner
            ? `<strong>${escapeHtml(String(m.home_score ?? "-"))}-${escapeHtml(String(m.away_score ?? "-"))}</strong><small>FIN</small>`
            : `<strong>VS</strong><small>${escapeHtml(time)}</small>`}
        </div>

        <div class="pick-team pick-team--right">
          <img class="pick-logo"
            src="${awayLogo}"
            alt="${escapeAttribute(m.away_team)}"
            loading="lazy" decoding="async"
            onerror="this.onerror=null;this.src='${awayDefault}';">
          <div class="pick-team-name" title="${escapeAttribute(m.away_team)}">${escapeHtml(m.away_team)}</div>
        </div>
      </div>

      <div class="pick-highlight">
        <span>Pronostic</span>
        <strong>${escapeHtml(pick)}</strong>
      </div>

      <div class="pick-confidence">
        <span>Confiance</span>
        <div class="pick-confidence-bar"><i style="width:${conf}%"></i></div>
        <b>${conf}%</b>
      </div>
    </a>
  `;
}

function displayTopTodayCoupons() {
  if (!DOM.topTodayPicks) return;
  if (!Array.isArray(allData?.matches)) {
    DOM.topTodayPicks.innerHTML = '<div class="no-events">Sélections momentanément indisponibles.</div>';
    return;
  }

  const todayStr = getLocalDateString("today");
  const picks = allData.matches
    .filter((m) => ["simple", "pro", "vip"].includes(String(m.category || "").toLowerCase()))
    .filter((m) => getLocalDateFromEvent(m.event_date) === todayStr)
    .filter((m) => !isFinishedMatch(m))
    .sort((a, b) => {
      const scoreDiff = (Number(b.final_score) || 0) - (Number(a.final_score) || 0);
      if (scoreDiff) return scoreDiff;
      return normalizeConfidence(b.prediction?.confidence) - normalizeConfidence(a.prediction?.confidence);
    })
    .slice(0, 3);

  DOM.topTodayPicks.innerHTML = picks.length
    ? picks.map((m) => renderHomePickCard(m, { winner: false })).join("")
    : `<div class="no-events">Aucune sélection publiée aujourd’hui.</div>`;
}

function displayLatestVerifiedHome() {
  if (!DOM.verifiedPicks) return;
  if (!Array.isArray(allData?.matches)) {
    DOM.verifiedPicks.innerHTML = '<div class="no-events">Résultats momentanément indisponibles.</div>';
    return;
  }

  const verified = allData.matches
    .filter((m) => isFinishedMatch(m) && m.verified_double)
    .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0))
    .slice(0, 3);

  DOM.verifiedPicks.innerHTML = verified.length
    ? verified.map((m) => renderHomePickCard(m, { winner: true })).join("")
    : `<div class="no-events">Aucun résultat gagnant récent.</div>`;
}

// Backward compatibility (si un ancien index existe encore)
function displayLatestVerified() {
  if (DOM.verifiedPicks) {
    displayLatestVerifiedHome();
    return;
  }
  if (!DOM.todayPicks || !allData?.matches) return;

  const verified = allData.matches
    .filter((m) => isFinishedMatch(m) && m.verified_double && (m.category === "pro" || m.category === "vip"))
    .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0))
    .slice(0, 4);

  DOM.todayPicks.innerHTML = verified.length
    ? verified
        .map(
          (m) => `
      <div class="match-card winner">
        <div class="match-info">
          <div class="teams">
            <div class="team">
              <img src="${escapeAttribute(m.home_logo || getTeamLogoPath(m.home_team, true))}" alt="${escapeAttribute(m.home_team)}" class="team-logo" loading="lazy">
              <span class="team-name">${escapeHtml(m.home_team)}</span>
              <span class="team-score">${m.home_score ?? "-"}</span>
            </div>
            <div class="vs">VS</div>
            <div class="team">
              <img src="${escapeAttribute(m.away_logo || getTeamLogoPath(m.away_team, false))}" alt="${escapeAttribute(m.away_team)}" class="team-logo" loading="lazy">
              <span class="team-name">${escapeHtml(m.away_team)}</span>
              <span class="team-score">${m.away_score ?? "-"}</span>
            </div>
          </div>
        </div>
        <div class="analysis-panel">
          <h4>Pronostic</h4>
          <p><strong>Pronostic :</strong> ${escapeHtml(m.prediction?.type || m.prediction?.label || m.prediction?.double_chance || "N/A")}
            <input type="checkbox" class="prediction-checkbox" checked disabled>
          </p>
          <p><strong>Fiabilité :</strong> ${escapeHtml(String(m.prediction?.confidence || 0))}%</p>
        </div>
      </div>
    `
        )
        .join("")
    : '<div class="no-events">■ Aucun pronostic validé récent.</div>';
}

function startWinsSlider() {
  if (!DOM.winsTrack || !allData?.matches) return;

  const wins = allData.matches
    .filter((m) => isFinishedMatch(m) && m.verified_double)
    .sort((a, b) => new Date(b.event_date || 0) - new Date(a.event_date || 0))
    .slice(0, 10);

  const html = wins
    .map((m) => {
      const score = `${m.home_score ?? "-"} - ${m.away_score ?? "-"}`;
      return `<div class="win-item">■ <span>${escapeHtml(m.home_team)} ${escapeHtml(score)} ${escapeHtml(m.away_team)}</span> • ${escapeHtml(m.prediction?.type || m.prediction?.label || m.prediction?.double_chance || "")}</div>`;
    })
    .join("");

  DOM.winsTrack.innerHTML = html + html;
}

function animateWins() {
  if (!DOM.winsCount || !allData?.matches) return;
  const target = allData.matches.filter((m) => isFinishedMatch(m) && m.verified_double).length;

  if (target <= 0) {
    DOM.winsCount.textContent = "0";
    return;
  }

  let count = 0;
  const interval = setInterval(() => {
    count++;
    DOM.winsCount.textContent = String(count);
    if (count >= target) clearInterval(interval);
  }, 20);
}

async function displayTestimonials() {
  if (!DOM.testimonials) return;
  try {
    const resp = await fetch(`testimonials.json?t=${Date.now()}`, { cache: "no-cache" });
    if (!resp.ok) throw new Error("Erreur");
    const testimonials = await resp.json();
    DOM.testimonials.innerHTML = testimonials
      .map(
        (t) => `
      <div class="card">
        <p>"${escapeHtml(t.text)}"</p>
        <p style="margin-top:1rem; color:var(--or);">— ${escapeHtml(t.name)}</p>
      </div>
    `
      )
      .join("");
  } catch {
    DOM.testimonials.innerHTML = `
      <div class="card">
        <p>"Grâce à Mr XPRONOS, j'ai mieux structuré mes paris."</p>
        <p style="margin-top:1rem;color:var(--or);">— Client</p>
      </div>
    `;
  }
}

function startWinNotifications() {
  if (!DOM.winPopup) return;

  const firstNames = ["Jean", "Michel", "David", "Lucas", "Thomas", "Patrick", "Samuel", "Kevin"];
  const lastNames = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand"];

  // gains FCFA (ex : 10 000 à 150 000)
  const notifications = Array.from({ length: 5 }).map(() => ({
    name: `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`,
    gain: Math.floor(Math.random() * (150000 - 10000 + 1)) + 10000,
  }));

  let index = 0;
  function showPopup() {
    const { name, gain } = notifications[index];
    DOM.winPopup.innerHTML = `■ <b>${escapeHtml(name)}</b> a gagné <b>${escapeHtml(gain.toLocaleString("fr-FR"))} FCFA</b> aujourd'hui.`;
    DOM.winPopup.classList.add("show");
    setTimeout(() => DOM.winPopup.classList.remove("show"), 4000);
    index = (index + 1) % notifications.length;
  }
  setTimeout(showPopup, 5000);
}

function updateHomeSuccessRate() {
  if (!DOM.successFill || !DOM.successPercent || !allData?.matches) return;

  const finished = allData.matches.filter(isFinishedMatch);
  if (finished.length === 0) {
    DOM.successFill.style.width = "0%";
    DOM.successPercent.textContent = "0%";
    return;
  }

  const successful = finished.filter((m) => m.verified_double).length;
  const percent = Math.round((successful / finished.length) * 100);
  DOM.successFill.style.width = percent + "%";
  DOM.successPercent.textContent = percent + "%";
}

function updatePronosticsSuccessRate() {
  if (!DOM.successRateContainer) return;
  if (!allData?.matches) {
    DOM.successRateContainer.style.display = "none";
    return;
  }

  const finished = allData.matches.filter(isFinishedMatch);
  const successful = finished.filter((m) => m.verified_double);

  if (finished.length === 0) {
    DOM.successRateContainer.style.display = "none";
    return;
  }

  const rate = ((successful.length / finished.length) * 100).toFixed(1);

  // ■ ROI supprimé
  DOM.successRateContainer.innerHTML = `
    <div class="success-rate-item" style="margin:0 auto;">
      <div class="success-rate-value">${escapeHtml(rate)}%</div>
      <div class="success-rate-label">Réussite</div>
    </div>
  `;
  DOM.successRateContainer.style.display = "flex";
}

/* =======================================================
 HOME - LAST UPDATE
======================================================= */
function updateHomeLastUpdate() {
  if (!DOM.dataUpdated) return;
  const ts = allData?.generated_at;
  if (!ts) {
    DOM.dataUpdated.textContent = "";
    return;
  }
  const d = new Date(ts);
  const label = isNaN(d) ? String(ts) : d.toLocaleString("fr-FR");
  DOM.dataUpdated.textContent = `Mis à jour : ${label}`;
}

/* =======================================================
 SCROLL PROGRESS
======================================================= */
function initScrollProgress() {
  if (document.querySelector(".scroll-progress")) return;
  const progressBar = document.createElement("div");
  progressBar.className = "scroll-progress";
  document.body.appendChild(progressBar);

  window.addEventListener("scroll", () => {
    const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = height > 0 ? (winScroll / height) * 100 : 0;
    progressBar.style.width = scrolled + "%";
  });
}

/* =======================================================
 EVENT LISTENERS
======================================================= */
function setupGlobalButtons() {
  document.getElementById("close-ios-guide")?.addEventListener("click", closeIosGuide);
  document.getElementById("close-ios-guide-btn")?.addEventListener("click", closeIosGuide);

}

function setupPronosticPageListeners() {
  const tabs = qsa(".pronostic-category-tabs .tab-btn");
  tabs.forEach((btn, index) => {
    btn.addEventListener("click", () => {
      // Un choix explicite doit primer sur la sélection automatique.
      autoSelectCategoryByCount = false;
      currentCategory = btn.dataset.cat;
      currentSubcat = "pronostics";
      syncCategoryTabs();
      // Un lien direct vers une catégorie peut ainsi être partagé sans verrou d'accès.
      const url = new URL(window.location.href);
      url.searchParams.set("cat", currentCategory);
      window.history.replaceState(null, "", url.toString());
      handleCategoryChange();
    });
    btn.addEventListener("keydown", (event) => {
      const nextIndex = event.key === "ArrowRight" ? (index + 1) % tabs.length
        : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
        : event.key === "Home" ? 0
        : event.key === "End" ? tabs.length - 1
        : -1;
      if (nextIndex < 0) return;
      event.preventDefault();
      tabs[nextIndex].focus();
      tabs[nextIndex].click();
    });
  });

  qsa(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      qsa(".subtab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentSubcat = btn.dataset.subcat;
      filterAndDisplay();
    });
  });

  qsa(".day-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      qsa(".day-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentDay = btn.dataset.day;
      filterAndDisplay();
    });
  });

  DOM.searchInput?.addEventListener("input", (e) => {
    searchTerm = e.target.value || "";
    applySearchFilter();
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-share");
    if (!btn) return;
    try {
      const matchData = JSON.parse(decodeURIComponent(btn.dataset.match));
      sharePronostic(matchData);
    } catch (err) {
      console.error("Erreur parsing données match", err);
    }
  });
}

async function handleCategoryChange() {
  // Simple, Pro et VIP sont accessibles sans action de partage.
  filterAndDisplay();
}

/* =======================================================
 INIT APP
======================================================= */
document.addEventListener("DOMContentLoaded", async () => {
  initDOM();
  setupGlobalButtons();
  initPromoCopy();

  const page = detectPage();
  if (page === "pronos") {
    currentCategory = readInitialCategory();
    syncCategoryTabs();
  }

  try {
    // Priorité absolue : afficher les pronostics avant toute dépendance Supabase.
    if (page === "pronos") {
      setupPronosticPageListeners();
      await loadData();
    }

    // Le contenu public a priorité : analytics, présence et compteurs
    // ne doivent jamais retenir les skeletons à l'écran.
    await loadPublishedExtras();
    void (async () => {
      try {
        await initSupabase();
        await updateDisplayedCounters();
        subscribeToCounters();
        await registerUniqueUser();
        await initOnlineUsers();
        countVisitOncePerDay();
        if ("Notification" in window && Notification.permission === "granted") {
          subscribeToPush(false);
        }
      } catch (secondaryError) {
        console.warn("Services secondaires non disponibles :", secondaryError);
      }
    })();
    showIosGuideIfNeeded();

    switch (page) {
      case "pronos":
        // Déjà chargé en priorité plus haut.
        renderBookmakers(allData?.bookmakers);
        break;

      case "history":
        await displayHistory();
        renderBookmakers();
        break;

      case "blog-list":
        await displayBlogList();
        renderBookmakers();
        break;

      case "blog-post":
        await displayBlogPost();
        renderBookmakers();
        break;

      case "conseil-post":
        await displayConseilPost();
        renderBookmakers();
        break;

      case "conseils":
        await displayConseils();
        renderBookmakers();
        break;

      case "bonus": {
        const data = await loadDataGeneric();
        if (data) allData = data;
        initBonusPage();
        renderBookmakers(allData?.bookmakers);
        break;
      }

      case "infos":
        await displayFootNews();
        renderBookmakers();
        break;

      case "home": {
        const data = await loadDataGeneric();
        if (data) {
          allData = data;
          renderBookmakers(data.bookmakers);
          updateHomeLastUpdate();
        }
        // Terminer systématiquement les deux états de chargement, même
        // lorsque data.json est absent ou hors ligne.
        displayTopTodayCoupons();
        displayLatestVerifiedHome();
        if (data) {
          startWinsSlider();
          animateWins();
          updateHomeSuccessRate();
        }
        await displayTestimonials();
        startWinNotifications();
        break;
      }

      default:
        renderBookmakers();
        break;
    }

    await displayInfos();
    initScrollProgress();
    setTimeout(showPushPrompt, 6500);
  } catch (error) {
    console.error("Erreur initialisation application :", error);

    // Même en cas d’erreur secondaire, on retente l’affichage des pronostics.
    if (page === "pronos") {
      try {
        if (!allData) await loadData();
        else filterAndDisplay();
      } catch (dataError) {
        console.error("Erreur chargement pronostics :", dataError);
        if (DOM.matches) {
          DOM.matches.innerHTML = `
            <div class="error">
              Impossible d’afficher les pronostics.<br>
              <small>${escapeHtml(dataError?.message || error?.message || "Erreur inconnue")}</small>
            </div>
          `;
        }
      }
    }
  }
});
