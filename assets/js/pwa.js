/**
 * Mr XPRONOS — Installation PWA, phase 2.
 * Les boutons restent facultatifs et accessibles, même sans beforeinstallprompt.
 * Les événements sont déclaratifs : aucune installation iOS ne peut être prouvée
 * par le navigateur web d'origine. Aucune inscription n'est exigée.
 */
(function () {
  "use strict";

  const base = location.hostname.includes("github.io")
    ? (location.pathname.match(/^\/([^/]+)\//) || [null, ""])[1]
    : location.pathname.includes("/MrXPRONOS_App/") ? "MrXPRONOS_App" : "";
  const scope = "/" + (base ? base + "/" : "");
  const eventKey = "mx_pwa_install_events_v2";
  const welcomeKey = "mx_pwa_welcome_v2";
  const state = window.__MRXPWA__ = {
    registration: null, deferredPrompt: null, isInstalled: false,
    installAvailable: false, updateAvailable: false, platform: null
  };
  let modal = null;
  let previousFocus = null;
  let installing = false;
  const impressions = new Set();
  const isDev = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);

  function getPlatform() {
    const ua = (navigator.userAgent || "").toLowerCase();
    const touchMac = (navigator.platform || "").toLowerCase() === "macintel" &&
      navigator.maxTouchPoints > 1;
    const isIOS = /iphone|ipad|ipod/.test(ua) || touchMac;
    const isAndroid = /android/.test(ua);
    const inApp = /instagram|fban|fbav|fb_iab|messenger|whatsapp|telegram|snapchat|tiktok|line\//.test(ua) ||
      (isAndroid && /;\s?wv[);]/.test(ua));
    let standalone = navigator.standalone === true;
    try { standalone = standalone || window.matchMedia("(display-mode: standalone)").matches; } catch (_) {}
    return {
      isIOS, isAndroid, isMobile: isIOS || isAndroid || /mobile/.test(ua),
      inApp, isStandalone: standalone,
      isSafari: /safari/.test(ua) && !/crios|fxios|edgios|chrome|android/.test(ua),
      isFirefox: /firefox|fxios/.test(ua),
      isEdge: /edg\//.test(ua),
      isSamsung: /samsungbrowser/.test(ua)
    };
  }

  function track(stage, surface) {
    if (isDev || typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") return;
    try {
      const p = getPlatform();
      const items = JSON.parse(sessionStorage.getItem(eventKey) || "[]");
      const list = Array.isArray(items) ? items : [];
      list.push({
        event_id: crypto.randomUUID(), stage: stage, surface: surface || "system",
        platform: p.isIOS ? "ios" : p.isAndroid ? "android" : "desktop",
        context: p.isStandalone ? "standalone" : p.inApp ? "in_app" : "browser"
      });
      sessionStorage.setItem(eventKey, JSON.stringify(list.slice(-40)));
      void import("./pwa-telemetry.mjs").then(function (module) { return module.flush(); }).catch(function () {});
    } catch (_) { /* analytics must never block the product */ }
  }

  function updateState(partial) {
    Object.assign(state, partial);
    state.platform = getPlatform();
    updateInstallButtons();
    window.dispatchEvent(new CustomEvent("mrx-pwa-state-change", { detail: state }));
  }

  function getOrCreateInstallRow() {
    const header = document.querySelector("header");
    if (!header) return null;
    let row = header.querySelector(".header-install-row");
    if (!row) {
      row = document.createElement("div");
      row.className = "header-install-row";
      const inner = document.createElement("div");
      inner.className = "container";
      row.appendChild(inner);
      header.appendChild(row);
    }
    return row;
  }

  function updateInstallButtons() {
    const p = getPlatform();
    const hidden = p.isStandalone || state.isInstalled;
    const headerButton = document.getElementById("install-app");
    const row = headerButton && getOrCreateInstallRow();
    if (headerButton && row) {
      const inner = row.querySelector(".container");
      if (inner && headerButton.parentElement !== inner) inner.appendChild(headerButton);
      headerButton.style.display = hidden ? "none" : "inline-flex";
      headerButton.disabled = hidden;
      row.classList.toggle("show", !hidden);
      headerButton.classList.add("btn-primary");
      Array.from(headerButton.childNodes).filter(function (node) { return node.nodeType === 3; }).forEach(function (node) { node.remove(); });
      const label = headerButton.querySelector(".mx-install-text") ||
        headerButton.querySelector(".mx-install-label") || document.createElement("span");
      if (!label.parentElement) {
        label.className = "mx-install-label";
        headerButton.appendChild(label);
      }
      label.textContent = p.inApp ? "Comment installer" :
        p.isIOS ? "Ajouter à l’accueil" : "Installer";
      headerButton.setAttribute("aria-label", label.textContent);
    }
    const card = document.getElementById("mx-install-panel");
    if (card) card.hidden = hidden;
    document.querySelectorAll("[data-mx-install-trigger]").forEach(function (button) {
      button.hidden = hidden;
      button.disabled = hidden;
      const label = button.querySelector("[data-mx-install-label]");
      if (label) label.textContent = p.inApp ? "Comment installer" :
        p.isIOS ? "Ajouter à l’accueil" : "Installer";
    });
  }

  function markImpressions() {
    if (getPlatform().isStandalone || state.isInstalled) return;
    const targets = [];
    const header = document.getElementById("install-app");
    if (header && header.style.display !== "none") targets.push([header, "header"]);
    const panel = document.getElementById("mx-install-panel");
    if (panel && !panel.hidden) targets.push([panel, "home"]);
    if (typeof IntersectionObserver === "undefined") {
      targets.forEach(function (pair) {
        if (!impressions.has(pair[1])) {
          impressions.add(pair[1]); track("cta_visible", pair[1]);
        }
      });
      return;
    }
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        const source = entry.target.id === "mx-install-panel" ? "home" : "header";
        if (entry.isIntersecting && !impressions.has(source)) {
          impressions.add(source);
          track("cta_visible", source);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.25 });
    targets.forEach(function (pair) { observer.observe(pair[0]); });
  }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "mx-install-help";
    modal.className = "mx-install-help";
    modal.hidden = true;
    modal.innerHTML =
      '<div class="mx-install-help-backdrop" data-mx-guide-close></div>' +
      '<section class="mx-install-help-dialog" role="dialog" aria-modal="true" aria-labelledby="mx-install-guide-title" aria-describedby="mx-install-guide-text">' +
      '<button type="button" class="mx-install-help-x" data-mx-guide-close aria-label="Fermer le guide">×</button>' +
      '<span class="mx-install-help-kicker">INSTALLER MR XPRONOS</span>' +
      '<h2 id="mx-install-guide-title"></h2>' +
      '<p id="mx-install-guide-text"></p>' +
      '<ol id="mx-install-guide-steps"></ol>' +
      '<p class="mx-install-help-note">L’installation est facultative. Les analyses et résultats restent accessibles sur le site.</p>' +
      '<div class="mx-install-help-actions">' +
      '<button type="button" id="mx-copy-install-link">Copier le lien du site</button>' +
      '<button type="button" id="mx-close-install-guide" data-mx-guide-close>Compris</button>' +
      '</div></section>';
    document.body.appendChild(modal);
    modal.querySelectorAll("[data-mx-guide-close]").forEach(function (el) {
      el.addEventListener("click", closeGuide);
    });
    modal.querySelector("#mx-copy-install-link").addEventListener("click", async function (event) {
      const button = event.currentTarget;
      try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) throw Error("Clipboard unavailable");
        await navigator.clipboard.writeText(new URL(scope, location.origin).href);
        button.textContent = "Lien copié !";
      } catch (_) {
        button.textContent = "Copiez l’adresse depuis votre navigateur";
      }
    });
    modal.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { event.preventDefault(); closeGuide(); }
      if (event.key !== "Tab") return;
      const all = Array.from(modal.querySelectorAll("button:not([disabled])"));
      if (!all.length) return;
      if (event.shiftKey && document.activeElement === all[0]) {
        event.preventDefault(); all[all.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === all[all.length - 1]) {
        event.preventDefault(); all[0].focus();
      }
    });
    return modal;
  }

  function guideContent() {
    const p = getPlatform();
    if (p.inApp) {
      return {
        title: "Ouvrez le site dans votre navigateur",
        body: "Les navigateurs intégrés à WhatsApp, Instagram et d’autres applications ne proposent pas toujours l’installation.",
        steps: [
          "Ouvrez le menu ⋮ ou ⋯ de cette fenêtre.",
          p.isIOS ? "Choisissez « Ouvrir dans Safari » (ou dans votre navigateur habituel)." :
            "Choisissez « Ouvrir dans Chrome » ou « Ouvrir dans le navigateur ».",
          "Dans ce navigateur, revenez sur Mr XPRONOS et utilisez le menu d’installation."
        ]
      };
    }
    if (p.isIOS) {
      return {
        title: "Ajouter Mr XPRONOS sur votre iPhone",
        body: "Sur iPhone et iPad, l’ajout s’effectue manuellement dans le menu de partage du navigateur.",
        steps: [
          "Appuyez sur Partager (icône carré avec flèche) dans Safari, Chrome ou un navigateur compatible.",
          "Faites défiler et sélectionnez « Sur l’écran d’accueil » ou « Ajouter à l’écran d’accueil ».",
          "Confirmez avec « Ajouter ». Si proposé, laissez « Ouvrir comme app web » activé."
        ]
      };
    }
    if (p.isAndroid) {
      return {
        title: "Installer Mr XPRONOS sur Android",
        body: "L’installation dépend du navigateur et des fonctionnalités de votre appareil.",
        steps: [
          "Ouvrez Mr XPRONOS dans Chrome ou votre navigateur habituel.",
          "Touchez ⋮ puis « Installer l’application » ou « Ajouter à l’écran d’accueil ».",
          "Confirmez. Si seule une icône de raccourci est proposée, elle ouvrira le site dans le navigateur."
        ]
      };
    }
    if (p.isSafari) {
      return {
        title: "Ajouter Mr XPRONOS sur Mac",
        body: "Sur les versions récentes de Safari pour Mac, utilisez le menu du navigateur.",
        steps: ["Ouvrez le menu Fichier.", "Sélectionnez « Ajouter au Dock » si cette option est présente.", "Confirmez l’ajout."]
      };
    }
    return {
      title: "Installer Mr XPRONOS sur ordinateur",
      body: "L’installation dépend de votre navigateur. Si l’option n’apparaît pas, le site reste pleinement accessible en ligne.",
      steps: [
        "Dans Chrome ou Edge, cherchez l’icône d’installation près de la barre d’adresse.",
        "Sinon, ouvrez le menu ⋮ ou ⋯ puis cherchez « Installer » ou « Applications ».",
        "Confirmez. Certains navigateurs, notamment Firefox sur ordinateur, ne proposent pas d’installation PWA native."
      ]
    };
  }

  function showGuide(source) {
    const content = guideContent();
    const overlay = ensureModal();
    previousFocus = document.activeElement;
    overlay.querySelector("#mx-install-guide-title").textContent = content.title;
    overlay.querySelector("#mx-install-guide-text").textContent = content.body;
    const list = overlay.querySelector("#mx-install-guide-steps");
    list.replaceChildren();
    content.steps.forEach(function (step) {
      const li = document.createElement("li");
      li.textContent = step;
      list.appendChild(li);
    });
    overlay.querySelector("#mx-copy-install-link").textContent = "Copier le lien du site";
    overlay.hidden = false;
    document.body.classList.add("mx-install-guide-open");
    track("guide_open", source || "guide");
    overlay.querySelector(".mx-install-help-x").focus();
  }

  function closeGuide() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove("mx-install-guide-open");
    track("guide_closed", "guide");
    if (previousFocus && previousFocus.isConnected && typeof previousFocus.focus === "function") {
      previousFocus.focus();
    }
  }

  function showInstalledToast() {
    const toast = document.createElement("div");
    toast.className = "mx-pwa-toast";
    toast.setAttribute("role", "status");
    toast.textContent = "Mr XPRONOS a été installé. Retrouvez son icône sur votre appareil.";
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 5000);
  }

  function showUpdateToast() {
    try {
      const last = Number(localStorage.getItem("mx_update_toast") || 0);
      if (Date.now() - last < 3600000) return;
      localStorage.setItem("mx_update_toast", String(Date.now()));
    } catch (_) {}
    const toast = document.createElement("button");
    toast.type = "button";
    toast.className = "mx-pwa-toast mx-pwa-toast--update";
    toast.textContent = "Mise à jour · Actualiser ↻";
    toast.setAttribute("aria-label", "Nouvelle version disponible, actualiser Mr XPRONOS");
    toast.addEventListener("click", function () { location.reload(); });
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 5500);
  }

  async function promptInstall(source) {
    source = ["header","home","guide"].includes(source) ? source : "header";
    const p = getPlatform();
    if (p.isStandalone || state.isInstalled || installing) return false;
    track("cta_click", source);
    if (p.inApp || p.isIOS || !state.deferredPrompt) {
      showGuide(source);
      return false;
    }
    const prompt = state.deferredPrompt;
    installing = true;
    updateState({ deferredPrompt: null, installAvailable: false });
    try {
      track("prompt_shown", source);
      await prompt.prompt();
      const result = await prompt.userChoice;
      if (result && result.outcome === "accepted") {
        track("prompt_accepted", source);
        return true; // Acceptation du dialogue ≠ installation confirmée.
      }
      track("prompt_dismissed", source);
      return false;
    } catch (_) {
      showGuide(source);
      return false;
    } finally {
      installing = false;
    }
  }

  function showWelcome() {
    const p = getPlatform();
    if (!p.isStandalone) return;
    track("standalone_open", "system");
    try {
      if (localStorage.getItem(welcomeKey)) return;
      localStorage.setItem(welcomeKey, "1");
    } catch (_) { return; }
    const welcome = document.createElement("section");
    welcome.className = "mx-pwa-welcome";
    welcome.setAttribute("aria-label", "Bienvenue dans l'application");
    welcome.innerHTML =
      '<div><strong>Bienvenue sur Mr XPRONOS !</strong><p>Votre accès direct aux pronostics, analyses football et résultats.</p></div>' +
      '<div class="mx-pwa-welcome-actions"><a href="pronos.html">Voir les pronostics</a><a href="historique.html">Voir les résultats</a>' +
      '<button type="button">Continuer ici</button></div>';
    welcome.querySelector("button").addEventListener("click", function () { welcome.remove(); });
    const main = document.querySelector("main");
    if (main) main.insertAdjacentElement("afterbegin", welcome);
    else document.body.prepend(welcome);
    track("welcome_visible", "system");
  }

  function bindButtons() {
    document.querySelectorAll("#install-app,[data-mx-install-trigger]").forEach(function (button) {
      if (button.dataset.mxInstallBound) return;
      button.dataset.mxInstallBound = "1";
      button.addEventListener("click", function () {
        void promptInstall(button.dataset.mxInstallSurface || (button.id === "install-app" ? "header" : "home"));
      });
    });
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      const reg = await navigator.serviceWorker.register(scope + "service-worker.js", {
        scope: scope, updateViaCache: "imports"
      });
      updateState({ registration: reg });
      reg.addEventListener("updatefound", function () {
        const worker = reg.installing;
        if (!worker) return;
        worker.addEventListener("statechange", function () {
          if (worker.state === "installed" && navigator.serviceWorker.controller) {
            updateState({ updateAvailable: true });
            showUpdateToast();
          }
        });
      });
    } catch (error) {
      if (isDev) console.warn("PWA : enregistrement du Service Worker impossible", error);
    }
  }

  function installListeners() {
    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      if (getPlatform().isStandalone) return;
      track("prompt_ready", "system");
      updateState({ deferredPrompt: event, installAvailable: true });
    });
    window.addEventListener("appinstalled", function () {
      track("appinstalled", "system");
      // L'ancien flag mx_pwa_installed n'est pas fiable après désinstallation.
      try { localStorage.removeItem("mx_pwa_installed"); } catch (_) {}
      updateState({ deferredPrompt: null, installAvailable: false, isInstalled: true });
      showInstalledToast();
    });
    try { localStorage.removeItem("mx_pwa_installed"); } catch (_) {}
  }

  function addStyles() {
    if (document.getElementById("mx-install-styles")) return;
    const style = document.createElement("style");
    style.id = "mx-install-styles";
    style.textContent = [
      ".mx-install-help[hidden],.mx-pwa-welcome[hidden],#mx-install-panel[hidden],[data-mx-install-trigger][hidden]{display:none!important}",
      ".mx-install-guide-open{overflow:hidden}",
      ".mx-install-help{position:fixed;inset:0;z-index:5000;display:grid;place-items:center;padding:18px}",
      ".mx-install-help-backdrop{position:absolute;inset:0;background:rgba(0,5,13,.83)}",
      ".mx-install-help-dialog{position:relative;z-index:1;width:min(100%,470px);max-height:90dvh;overflow:auto;padding:24px;border:1px solid #b89655;border-radius:17px;background:#0c1a29;color:#f5f5f5;box-shadow:0 20px 80px #000b;line-height:1.55}",
      ".mx-install-help-kicker{font-size:11px;color:#e7bc64;letter-spacing:1.4px;font-weight:750}",
      ".mx-install-help-dialog h2{font-size:23px;line-height:1.2;margin:12px 25px 12px 0;color:#fff}",
      ".mx-install-help-dialog p{font-size:14px;color:#ced6df}",
      ".mx-install-help-dialog ol{padding-left:22px;display:grid;gap:12px;margin:18px 0}",
      ".mx-install-help-dialog li{font-size:14px;color:#f3f5f8}",
      ".mx-install-help-note{border-top:1px solid #354558;padding-top:12px;font-size:12px!important}",
      ".mx-install-help-x{position:absolute;right:14px;top:12px;font-size:26px;line-height:1;color:#fff;border:0;background:transparent;cursor:pointer;padding:4px 8px}",
      ".mx-install-help-actions{display:flex;gap:9px;flex-wrap:wrap}",
      ".mx-install-help-actions button,.mx-pwa-welcome-actions a,.mx-pwa-welcome-actions button{border:1px solid #cda35d;background:#b89555;color:#0a1724;border-radius:9px;padding:10px 12px;font-weight:750;font-size:13px;cursor:pointer;text-decoration:none}",
      ".mx-install-help-actions button:first-child,.mx-pwa-welcome-actions a:nth-child(2),.mx-pwa-welcome-actions button{background:#182f42;color:#f2f5f6;border-color:#486079}",
      ".mx-pwa-toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);z-index:5001;background:#142b3b;border:1px solid #caa864;color:#fff;border-radius:11px;padding:13px 18px;max-width:min(92%,430px);box-shadow:0 8px 30px #0008}",
      ".mx-pwa-toast--update{display:inline-flex;align-items:center;justify-content:center;width:max-content;max-width:calc(100vw - 24px);min-height:38px;padding:8px 12px;font:700 12px/1.3 Manrope,'Segoe UI',sans-serif;white-space:nowrap;cursor:pointer}",
      "@media(max-width:700px){.mx-pwa-toast--update{left:auto;right:10px;bottom:calc(75px + env(safe-area-inset-bottom,0px));transform:none;max-width:calc(100vw - 20px);border-radius:10px;box-shadow:0 4px 15px #0008}}",
      ".mx-pwa-welcome{margin:15px auto;padding:17px;background:linear-gradient(110deg,#0b2438,#162c38);color:#fff;border:1px solid #bd9c62;border-radius:13px;max-width:1120px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:13px}",
      ".mx-pwa-welcome strong{color:#f1cc81;font-size:17px}.mx-pwa-welcome p{margin:5px 0;font-size:13px;color:#e3e9ee}",
      ".mx-pwa-welcome-actions{display:flex;flex-wrap:wrap;gap:8px}",
      "@media(max-width:470px){.mx-install-help-dialog{padding:18px}.mx-install-help-dialog h2{font-size:20px}.mx-pwa-welcome{margin:10px}.mx-pwa-welcome-actions{width:100%}}",
      "@media(prefers-reduced-motion:reduce){.mx-pwa-toast{transition:none}}"
    ].join("\n");
    document.head.appendChild(style);
  }

  function init() {
    addStyles();
    bindButtons();
    updateState({ platform: getPlatform(), isInstalled: getPlatform().isStandalone });
    markImpressions();
    if (getPlatform().isStandalone) showWelcome();
    void registerServiceWorker();
    // Phase 4 : un seul contact d’acquisition par onglet, sans adresse référente brute.
    void import("./acquisition-attribution.mjs").then(module=>module.start()).catch(()=>{});
    void import("./experiment-ux.mjs").then(module=>module.startInstall()).catch(()=>{});
    setInterval(function () {
      if (document.visibilityState === "visible" && state.registration) {
        state.registration.update().catch(function () {});
      }
    }, 3600000);
  }

  // Écoute les événements du navigateur le plus tôt possible (avant DOMContentLoaded).
  installListeners();
  try {
    if (JSON.parse(sessionStorage.getItem(eventKey) || "[]").length) {
      void import("./pwa-telemetry.mjs").then(function (module) { return module.flush(); }).catch(function () {});
    }
  } catch (_) {}
  window.addEventListener("online", function () {
    void import("./pwa-telemetry.mjs").then(function (module) { return module.flush(); }).catch(function () {});
  });

  window.MrXPWA = {
    getState: function () { return state; },
    getPlatform: getPlatform,
    promptInstall: promptInstall,
    isInstallable: function () { return state.installAvailable; },
    isInstalled: function () { return getPlatform().isStandalone || state.isInstalled; },
    openGuide: showGuide
  };
  window.promptPWAInstall = promptInstall;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
