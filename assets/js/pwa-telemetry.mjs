/**
 * Module léger de collecte des événements du parcours d'installation.
 * Aucun évènement de navigation n'est bloqué par la télémétrie.
 * Utilisé par pwa.js sur TOUTES les routes, y compris bonus/scores-exacts.
 */
const KEY = "mx_pwa_install_events_v2";
let clientPromise = null;
let busy = false;

function getUserId() {
  let id = "";
  try { id = localStorage.getItem("mx_user_id") || ""; } catch (_) {}
  if (/^(MX|PL)-[A-Za-z0-9._-]{6,120}$/.test(id)) return id;
  if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") return null;
  id = "MX-" + crypto.randomUUID();
  try { localStorage.setItem("mx_user_id", id); } catch (_) { return null; }
  return id;
}

async function client() {
  if (!clientPromise) {
    clientPromise = (async function () {
      const config = await import("./config.js");
      if (!config.supabaseUrl || !/^https:\/\//.test(config.supabaseUrl) ||
          !config.supabaseAnonKey) throw Error("Supabase config missing");
      const sdk = await import("https://esm.sh/@supabase/supabase-js@2");
      return sdk.createClient(config.supabaseUrl, config.supabaseAnonKey, {
        auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
        realtime: { params: { eventsPerSecond: 1 } }
      });
    })().catch(function (error) { clientPromise = null; throw error; });
  }
  return clientPromise;
}

export async function flush() {
  if (busy || /^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return;
  busy = true;
  try {
    let events;
    try { events = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (_) { return; }
    if (!Array.isArray(events) || !events.length) return;
    const visitor = getUserId();
    if (!visitor) return;
    const sb = await client();
    for (let i = 0; i < 40; i += 1) {
      let queue;
      try { queue = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (_) { break; }
      if (!Array.isArray(queue) || !queue.length) break;
      const event = queue[0];
      if (!event || !/^[a-f0-9-]{36}$/i.test(event.event_id || "")) {
        sessionStorage.setItem(KEY, JSON.stringify(queue.slice(1)));
        continue;
      }
      const { data, error } = await sb.rpc("track_pwa_install_event_v2", {
        p_event_id: event.event_id,
        p_user_id: visitor,
        p_stage: event.stage,
        p_platform: event.platform,
        p_surface: event.surface,
        p_context: event.context
      });
      if (error || data !== true) break;
      // Préserver les événements ajoutés pendant la requête.
      let current;
      try { current = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (_) { break; }
      if (!Array.isArray(current)) break;
      sessionStorage.setItem(KEY,
        JSON.stringify(current.filter(function (item) {
          return item && item.event_id !== event.event_id;
        })));
    }
  } catch (_) {
    // Non-bloquant : nouvelle tentative au prochain lancement, événement ou retour en ligne.
  } finally { busy = false; }
}
