/**
 * pwa.js - Gestion PWA complète (version unifiée)
 * - Bouton "Installer l'app" en bas du header
 * - La ligne disparaît quand le bouton est caché
 */
(function () {
  "use strict";

  // ========================================================
  // CONFIGURATION
  // ========================================================
  const CONFIG = (() => {
    const isGitHubPages = location.hostname.includes("github.io");
    const path = location.pathname;

    let base = "/";

    if (isGitHubPages) {
      const match = path.match(/^\/([^/]+)\//);
      if (match) base = `/${match[1]}/`;
    } else if (path.includes("/MrXPRONOS_App/")) {
      base = "/MrXPRONOS_App/";
    }

    return {
      swPath: `${base}service-worker.js`,
      scope: base,
      isGitHubPages,
    };
  })();

  // ========================================================
  // LOGGER
  // ========================================================
  const isDev =
    location.hostname === "localhost" || location.hostname === "127.0.0.1";

  function pwaLog(msg) {
    if (isDev) console.log("[PWA]", msg);
  }
  function pwaWarn(msg) {
    if (isDev) console.warn("[PWA]", msg);
  }
  function pwaError(msg) {
    console.error("[PWA]", msg);
  }

  // ========================================================
  // ÉTAT GLOBAL
  // ========================================================
  window.__MRXPWA__ = {
    registration: null,
    deferredPrompt: null,
    isInstalled: false,
    installAvailable: false,
    updateAvailable: false,
    platform: null,
  };

  // ========================================================
  // UTILS
  // ========================================================
  function getPlatform() {
    const ua = navigator.userAgent.toLowerCase();
    const platform = (navigator.platform || "").toLowerCase();

    const isIOS =
      /iphone|ipad|ipod/.test(ua) ||
      (platform === "macintel" && navigator.maxTouchPoints > 1);

    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true ||
      localStorage.getItem("mx_pwa_installed") === "true";

    return {
      isIOS,
      isAndroid: /android/.test(ua),
      isStandalone,
      isSafari: /^((?!chrome|android).)*safari/i.test(ua),
      isChrome: /chrome/.test(ua) && !/edge|edg/.test(ua),
      isFirefox: /firefox/.test(ua),
      isMobile: /mobile|android|iphone|ipad|ipod/i.test(ua),
    };
  }

  function updateGlobalState(partial) {
    Object.assign(window.__MRXPWA__, partial);
    window.dispatchEvent(
      new CustomEvent("mrx-pwa-state-change", { detail: window.__MRXPWA__ })
    );
    updateInstallButton();
  }

  // ========================================================
  // UI : ligne install en bas du header
  // ========================================================
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

  function moveInstallButtonToHeaderBottom() {
    const btn = document.getElementById("install-app");
    const row = getOrCreateInstallRow();
    if (!btn || !row) return;

    const innerContainer = row.querySelector(".container");
    if (innerContainer && btn.parentElement !== innerContainer) {
      innerContainer.appendChild(btn);
    }
  }

  function showInstallRow() {
    const row = getOrCreateInstallRow();
    if (!row) return;
    row.classList.add("show");
  }

  function hideInstallRow() {
    const header = document.querySelector("header");
    const row = header?.querySelector(".header-install-row");
    if (!row) return;
    row.classList.remove("show");
  }

  function bindInstallButton() {
    const btn = document.getElementById("install-app");
    if (!btn) return;

    // évite double bind
    if (btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";

    btn.addEventListener("click", () => {
      promptInstall();
    });
  }

  function updateInstallButton() {
    const installBtn = document.getElementById("install-app");
    if (!installBtn) return;

    const platform = getPlatform();

    // Affichage :
    // - iOS : on l'affiche (guide "Ajouter à l'écran d'accueil")
    // - Android/desktop : seulement si installAvailable est true
    const shouldShow =
      !platform.isStandalone &&
      (window.__MRXPWA__.installAvailable || platform.isIOS);

    if (shouldShow) {
      moveInstallButtonToHeaderBottom();
      showInstallRow();

      installBtn.style.display = "inline-flex";
      installBtn.classList.add("btn-primary");
      installBtn.classList.remove("btn-secondary");
      installBtn.textContent = platform.isIOS
        ? "Ajouter à l’écran d’accueil"
        : "Installer l'app";
    } else {
      // ✅ cache bouton + cache la ligne (plus d'espace vide)
      installBtn.style.display = "none";
      hideInstallRow();
    }
  }

  function showUpdateToast() {
    const lastToast = localStorage.getItem("mx_update_toast");
    if (lastToast && Date.now() - parseInt(lastToast, 10) < 3600000) return;

    localStorage.setItem("mx_update_toast", Date.now().toString());

    const toast = document.createElement("div");
    toast.textContent = "Nouvelle version disponible. Touchez pour rafraîchir.";
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 20px;
      right: 20px;
      background: #D4AF37;
      color: #000;
      padding: 12px 16px;
      border-radius: 12px;
      font-weight: 700;
      text-align: center;
      z-index: 10001;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;

    toast.onclick = () => window.location.reload();
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 8000);
  }

  function showInstallSuccessToast() {
    const toast = document.createElement("div");
    toast.textContent = "Mr XPRONOS est installé sur votre appareil !";
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 20px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 12px 16px;
      border-radius: 12px;
      font-weight: 700;
      text-align: center;
      z-index: 10001;
      box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  // ========================================================
  // SERVICE WORKER
  // ========================================================
  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
      pwaWarn("Service Worker non supporté");
      return null;
    }

    try {
      pwaLog("Enregistrement SW: " + CONFIG.swPath);

      const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
        scope: CONFIG.scope,
        updateViaCache: "imports",
      });

      pwaLog("SW enregistré: " + registration.scope);
      updateGlobalState({ registration });

      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        pwaLog("Nouvelle version SW détectée");
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            pwaLog("Mise à jour disponible");
            updateGlobalState({ updateAvailable: true });
            showUpdateToast();
          }
        });
      });

      return registration;
    } catch (err) {
      pwaError("Erreur SW: " + err.message);
      return null;
    }
  }

  // ========================================================
  // INSTALL PROMPT
  // ========================================================
  function setupInstallPromptHandling() {
    const platform = getPlatform();
    updateGlobalState({ platform });

    if (platform.isStandalone) {
      pwaLog("App déjà installée");
      updateGlobalState({ isInstalled: true, installAvailable: false });
      return;
    }

    if (platform.isIOS) {
      pwaLog("iOS - installation via menu partage");
      updateGlobalState({ installAvailable: false });
      return;
    }

    window.addEventListener("beforeinstallprompt", (e) => {
      pwaLog("beforeinstallprompt capturé");
      e.preventDefault();

      updateGlobalState({
        deferredPrompt: e,
        installAvailable: true,
      });
    });

    window.addEventListener("appinstalled", () => {
      pwaLog("App installée avec succès");
      localStorage.setItem("mx_pwa_installed", "true");

      updateGlobalState({
        deferredPrompt: null,
        isInstalled: true,
        installAvailable: false,
      });

      showInstallSuccessToast();
      // updateInstallButton() est rappelé via updateGlobalState -> donc la ligne disparaît
    });

    // sécurité
    setTimeout(() => {
      const p = getPlatform();
      if (!window.__MRXPWA__.installAvailable && !p.isStandalone && !p.isIOS) {
        pwaLog("Aucune installation disponible");
        updateGlobalState({ installAvailable: false });
      }
    }, 5000);
  }

  async function promptInstall() {
    const state = window.__MRXPWA__;
    const platform = getPlatform();

    if (platform.isIOS) {
      const guidePopup = document.getElementById("ios-guide-popup");
      if (guidePopup) {
        guidePopup.style.display = "flex";
      } else {
        alert(
          'Pour installer sur iPhone :\n1. Touchez "Partager"\n2. "Sur l\'écran d\'accueil"\n3. "Ajouter"'
        );
      }
      return false;
    }

    if (!state.deferredPrompt) {
      pwaWarn("Aucune installation disponible");
      return false;
    }

    try {
      state.deferredPrompt.prompt();
      const result = await state.deferredPrompt.userChoice;

      pwaLog("Résultat installation: " + result?.outcome);

      updateGlobalState({
        deferredPrompt: null,
        installAvailable: false,
      });

      return result?.outcome === "accepted";
    } catch (err) {
      pwaError("Erreur install: " + err.message);
      return false;
    }
  }

  // ========================================================
  // STYLES
  // ========================================================
  function addStyles() {
    if (document.getElementById("pwa-styles")) return;

    const style = document.createElement("style");
    style.id = "pwa-styles";
    style.textContent = `
      #install-app { transition: all 0.25s ease; }
      #install-app:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(212,175,55,0.35); }
    `;
    document.head.appendChild(style);
  }

  // ========================================================
  // INITIALISATION
  // ========================================================
  function init() {
    pwaLog("Initialisation PWA...");
    pwaLog("Config: " + JSON.stringify(CONFIG));

    addStyles();

    // On prépare le bouton
    bindInstallButton();

    updateGlobalState({ platform: getPlatform() });

    registerServiceWorker();
    setupInstallPromptHandling();

    // update SW périodique si page visible
    setInterval(() => {
      if (document.visibilityState === "visible") {
        window.__MRXPWA__?.registration?.update().catch(() => {});
      }
    }, 3600000);

    // init état bouton + ligne
    updateInstallButton();

    pwaLog("PWA initialisé");
  }

  // ========================================================
  // API PUBLIQUE
  // ========================================================
  window.MrXPWA = {
    getState: () => window.__MRXPWA__,
    getPlatform,
    promptInstall,
    isInstallable: () => window.__MRXPWA__.installAvailable,
    isInstalled: () => getPlatform().isStandalone,
  };

  window.promptPWAInstall = promptInstall;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();