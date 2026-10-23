/**
 * Anonymous, sampled real-user monitoring. This module is loaded independently
 * from main.js so the historical VM tests can execute main.js as a classic script.
 * Measurements are aggregated privately by the administrator-only RPC.
 * No personal identifier, querystring, error text or stack is transmitted.
 */
import {neonDataApiUrl,neonAuthUrl} from "./config.js";
import {createClient} from "https://esm.sh/@neondatabase/neon-js";
const neon = createClient({auth:{url:neonAuthUrl,allowAnonymous:true},dataApi:{url:neonDataApiUrl}});

const page = (location.pathname.replace(/^\/MrXPRONOS_App/i, "").slice(0, 140) || "/");
const eligiblePage = /^\/[a-zA-Z0-9/_.-]+$/.test(page);
const device = /iPad|Tablet/i.test(navigator.userAgent)
  ? "tablet" : /iPhone|Android|Mobile/i.test(navigator.userAgent) ? "mobile" : "desktop";

function sendMetric(table, payload) {
  if (!eligiblePage || !["admin_web_vitals","admin_client_errors"].includes(table)) return;
  // JWT anonymous Neon Auth + restrictive INSERT-only RLS policy.
  void neon.from(table).insert({...payload,page,device}).then(({error})=>{
    if(error)console.debug("Neon telemetry deferred");
  }).catch(()=>{});
}

if (eligiblePage && Math.random() < 0.12) {
  // Load after first rendering, so monitoring does not delay core UI.
  const startVitals = () => {
    import("https://cdn.jsdelivr.net/npm/web-vitals@5/+esm")
      .then(({ onCLS, onINP, onLCP }) => {
        const reported = new Set();
        const report = ({ name, value }) => {
          if (!["CLS", "INP", "LCP"].includes(name)
              || !Number.isFinite(value) || value < 0 || value > 60000
              || reported.has(name)) return;
          reported.add(name);
          sendMetric("admin_web_vitals", {
            metric: name, value: Math.round(value * 1000) / 1000
          });
        };
        onCLS(report);
        onINP(report);
        onLCP(report);
      })
      .catch(() => {});
  };
  if (document.readyState === "complete") startVitals();
  else window.addEventListener("load", startVitals, { once: true });
}

// Error counts, not detailed reports, with strict per-page throttling.
if (eligiblePage) {
  let observedErrors = 0;
  const reportError = kind => {
    if (observedErrors++ >= 3 || Math.random() > 0.20) return;
    sendMetric("admin_client_errors", { kind });
  };
  window.addEventListener("error", event => {
    reportError(event.target === window ? "script" : "resource");
  }, { capture: true });
  window.addEventListener("unhandledrejection", () => reportError("promise"));
}
