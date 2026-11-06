/**
 * Mr XPRONOS — optional personalized alerts.
 * No automatic permission request, subscription, or server-side sync.
 */
import { normalizeFavorites } from "./daily-utils.mjs";

const FAVORITES_KEY = "mx_daily_favorites_v1";
const $ = id => document.getElementById(id);
const url = "/functions/v1/daily-favorite-alerts";
const STORE_HOUR = "mx_daily_favorite_alert_hour_v1";
let sbUrl = null;
let pending = false;
let enabled = false;
let savedFavorites = null;

function message(text) {
  const line = $("daily-favorite-alert-status");
  if (line) line.textContent = String(text);
}
function favorites() {
  try { return normalizeFavorites(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "{}")); }
  catch { return { teams: [], leagues: [] }; }
}
function hasFavorites() {
  const f = favorites();
  return f.teams.length + f.leagues.length > 0;
}
function supported() {
  const ok = "Notification" in window && "serviceWorker" in navigator &&
    "PushManager" in window && typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function";
  let standalone = false;
  try { standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true; }
  catch {}
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  return ok && (!ios || standalone);
}
function updateButtons() {
  const on = $("daily-favorite-alert-enable");
  const off = $("daily-favorite-alert-disable");
  if (!on || !off) return;
  on.disabled = pending || !hasFavorites() || !supported();
  off.disabled = pending || !supported();
}
function userId() {
  let id = "";
  try { id = localStorage.getItem("mx_user_id") || ""; }
  catch {}
  if (/^(MX|PL)-[A-Za-z0-9._-]{6,120}$/.test(id)) return id;
  id = "MX-" + crypto.randomUUID();
  try { localStorage.setItem("mx_user_id",id); }
  catch { throw Error("Stockage local désactivé"); }
  return id;
}
async function projectURL() {
  if (!sbUrl) {
    const conf = await import("./config.js");
    if (!conf.supabaseUrl || !conf.supabaseUrl.startsWith("https://"))
      throw Error("Configuration push indisponible");
    sbUrl = conf.supabaseUrl;
  }
  return sbUrl;
}
async function serviceWorkerReady() {
  const reg = await Promise.race([
    navigator.serviceWorker.ready,
    new Promise((_,reject) => setTimeout(() => reject(Error("Service Worker indisponible")),6500))
  ]);
  return reg;
}
async function activeSubscription() {
  const reg = await serviceWorkerReady();
  const subscription = await reg.pushManager.getSubscription();
  return { reg, subscription };
}
async function request(action, subscription, more = {}) {
  const base = await projectURL();
  const resp = await fetch(base + url, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action,subscription:subscription.toJSON(),...more}),
    cache:"no-store"
  });
  const result = await resp.json().catch(()=>({}));
  if (!resp.ok) throw Error(result.error || ("Service push : HTTP "+resp.status));
  return result;
}
async function registerSubscription() {
  const { reg, subscription: existing } = await activeSubscription();
  let subscription = existing;
  if (!subscription) {
    const base = await projectURL();
    const key = await fetch(base + "/functions/v1/vapid-public-key",{cache:"no-store"});
    if (!key.ok) throw Error("Clé publique des notifications indisponible");
    const raw = (await key.text()).trim();
    if (!raw) throw Error("Clé de notifications vide");
    const normalized = (raw+"=".repeat((4-raw.length%4)%4)).replace(/-/g,"+").replace(/_/g,"/");
    const binary=atob(normalized);
    const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
    subscription = await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
  }
  const base=await projectURL();
  const resp=await fetch(base+"/functions/v1/push-subscribe", {
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({user_id:userId(),subscription})
  });
  if (!resp.ok) throw Error("Abonnement push non enregistré sur le serveur");
  return subscription;
}
async function save() {
  if (pending) return;
  if (!hasFavorites()) {
    message("Ajoutez d'abord une équipe ou une compétition dans « Mes favoris ».");
    return;
  }
  if (!supported()) {
    message("Notifications non prises en charge. Sur iPhone, ouvrez l'app depuis l'écran d'accueil.");
    return;
  }
  // Browser permission must be requested directly from the user's click.
  let permission=Notification.permission;
  if (permission==="default") permission=await Notification.requestPermission();
  if (permission!=="granted") {
    message("Permission non accordée. L'application reste utilisable sans alerte.");
    return;
  }
  pending=true;updateButtons();message("Enregistrement de vos alertes…");
  try {
    const f=favorites();
    const selected=Number($("daily-favorite-alert-hour").value);
    if (!Number.isInteger(selected) || selected<7 || selected>21) throw Error("Heure invalide");
    const subscription=await registerSubscription();
    const result=await request("save",subscription,{
      favorites:f, hour_local:selected,
      timezone_offset_minutes:new Date().getTimezoneOffset()
    });
    enabled=result.enabled===true;
    savedFavorites=JSON.stringify(f);
    try { localStorage.setItem(STORE_HOUR,String(selected)); } catch {}
    message("Alertes personnalisées activées pour "+result.favorite_count+
      " favori(s), autour de "+String(selected).padStart(2,"0")+
      " h (heure locale). Maximum une par jour si une publication concerne vos favoris.");
  } catch (error) {
    message("Activation non confirmée : "+String(error?.message||error)+
      ". Le rappel calendrier reste disponible.");
  } finally { pending=false;updateButtons(); }
}
export async function disable(options = {}) {
  if (pending) return false;
  pending=true;updateButtons();
  if (!options.quiet) message("Désactivation des alertes ciblées…");
  try {
    if (!supported() || Notification.permission!=="granted") {
      enabled=false;
      if (!options.quiet) message("Aucune alerte ciblée active sur cet appareil.");
      return true;
    }
    const { subscription }=await activeSubscription();
    if (!subscription) {
      enabled=false;
      if (!options.quiet) message("Aucun abonnement push actif sur cet appareil.");
      return true;
    }
    const result=await request("disable",subscription);
    if (result.enabled!==false) throw Error("Désactivation non confirmée");
    enabled=false;savedFavorites=null;
    if (!options.quiet) message("Alertes personnalisées désactivées pour cet appareil. Les notifications générales restent indépendantes.");
    return true;
  } catch (error) {
    if (!options.quiet) message("Désactivation non confirmée : "+String(error?.message||error));
    return false;
  } finally { pending=false;updateButtons(); }
}
async function loadStatus() {
  if (!supported()) {
    message("Notifications ciblées indisponibles dans ce navigateur. Sur iPhone, ouvrez l'application installée.");
    updateButtons();return;
  }
  if (Notification.permission!=="granted") {
    message("Alertes ciblées désactivées par défaut. Vous pouvez les activer après avoir choisi vos favoris.");
    updateButtons();return;
  }
  try {
    const { subscription }=await activeSubscription();
    if (!subscription) { updateButtons();return; }
    const result=await request("status",subscription);
    enabled=result.enabled===true;
    savedFavorites=JSON.stringify(normalizeFavorites(result.favorites));
    if (result.hour_local>=7 && result.hour_local<=21)
      $("daily-favorite-alert-hour").value=String(result.hour_local);
    message(enabled ?
      "Vos alertes ciblées sont actives. Modifiez vos favoris puis cliquez sur « Mettre à jour » pour actualiser leur sélection." :
      "Alertes ciblées désactivées. Activez-les seulement si vous souhaitez ce service.");
  } catch {
    message("Impossible de vérifier l'état distant des alertes. Réessayez si nécessaire.");
  } finally {updateButtons();}
}
function changedFavorites() {
  updateButtons();
  if (!hasFavorites() && enabled) {
    // An explicit clear-all operation must also disable server preferences.
    void disable().then(ok => {
      if(!ok)message("Favoris locaux supprimés. Désactivez les alertes ciblées dès que la connexion revient.");
    });
  } else if (enabled && savedFavorites && savedFavorites!==JSON.stringify(favorites())) {
    message("Vos favoris ont changé. Cliquez sur « Activer ou mettre à jour » pour mettre à jour les alertes sur le serveur.");
  }
}
export function init() {
  const activate=$("daily-favorite-alert-enable");
  const stop=$("daily-favorite-alert-disable");
  const hour=$("daily-favorite-alert-hour");
  if (!activate || !stop || !hour) return;
  try {
    const chosen=localStorage.getItem(STORE_HOUR);
    if(chosen && Number(chosen)>=7 && Number(chosen)<=21)hour.value=chosen;
  }catch{}
  activate.addEventListener("click",()=>{void save();});
  stop.addEventListener("click",()=>{void disable();});
  window.addEventListener("mx-favorites-updated",changedFavorites);
  window.addEventListener("storage",event=>{
    if(event.key===FAVORITES_KEY)changedFavorites();
  });
  updateButtons();
  void loadStatus();
}
