// Shared ESPN client — bounded requests, durable cache, retry, stale fallback.
export type EspnCacheStore = {
  read(key: string): Promise<any | null>;
  write(row: any): Promise<void>;
};
const scoreboardUrl = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard";
const summaryUrl = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary";
const memory = new Map<string, { until: number; data: any }>();
const inFlight = new Map<string, Promise<any>>();
let failures = 0;
let blockedUntil = 0;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
export function safeEspnDate(value: unknown): string | null {
  if (!value) return null;
  const d = new Date(String(value));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
export function parseEspnNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || value === "-") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const s = String(value).trim().replace(/%$/, "").replace(/\s/g, "");
  // Thousands separators only when grouped as 1,234 or 1.234.
  const normalized = /^-?\d{1,3}(,\d{3})+$/.test(s) ? s.replace(/,/g, "")
    : /^-?\d+,\d{1,2}$/.test(s) ? s.replace(",", ".") : s;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}
function validScoreboard(x: any) { return x && Array.isArray(x.events); }
function validSummary(x: any) { return x && typeof x === "object" && !Array.isArray(x); }
async function requestJson(url: string, validate: (v: any) => boolean): Promise<any> {
  for (let attempt = 0; attempt < 3; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json", "User-Agent": "MrXPRONOS/2.0 (+football statistics)" },
      });
      if (!res.ok) {
        const err: any = new Error(`ESPN HTTP ${res.status}`);
        err.status = res.status;
        const ra = res.headers.get("retry-after");
        if (ra) {
          const seconds = Number(ra);
          err.retryAfterMs = Number.isFinite(seconds) ? seconds * 1000
            : Math.max(0, Date.parse(ra) - Date.now());
        }
        throw err;
      }
      if (!(res.headers.get("content-type") || "").toLowerCase().includes("json")) {
        throw new Error("ESPN returned non-JSON content");
      }
      const data = await res.json();
      if (!validate(data)) throw new Error("ESPN schema invalid");
      failures = 0;
      blockedUntil = 0;
      return data;
    } catch (err: any) {
      const s = Number(err?.status || 0);
      const transient = !s || s === 408 || s === 429 || s >= 500;
      if (!transient || attempt === 2) {
        failures++;
        if (failures >= 3) blockedUntil = Date.now() + 120000;
        throw err;
      }
      const delay = Math.max(0, Math.min(120000, Number(err?.retryAfterMs || 0))) ||
        Math.min(4000, 500 * (2 ** attempt) + Math.floor(Math.random() * 250));
      await sleep(delay);
    } finally {
      clearTimeout(timer);
    }
  }
}
async function cachedRequest(key: string, url: string, ttlMs: number, validate: (v: any) => boolean, store?: EspnCacheStore): Promise<any> {
  const now = Date.now();
  const local = memory.get(key);
  if (local && local.until > now) return local.data;
  const pending = inFlight.get(key);
  if (pending) return pending;
  const promise = (async () => {
    let stored: any = null;
    try { stored = store ? await store.read(key) : null; } catch (e) { console.warn("ESPN cache read failed", e); }
    if (stored && validate(stored.payload) && Date.parse(stored.expires_at || "") > Date.now()) {
      memory.set(key, { data: stored.payload, until: Date.parse(stored.expires_at) });
      return stored.payload;
    }
    if (Date.now() < blockedUntil) {
      if (stored && validate(stored.payload)) return stored.payload;
      if (local && validate(local.data)) return local.data;
      throw new Error("ESPN circuit breaker open");
    }
    try {
      const data = await requestJson(url, validate);
      const until = Date.now() + ttlMs;
      memory.set(key, { until, data });
      if (store) {
        try { await store.write({ cache_key: key, payload: data, fetched_at: new Date().toISOString(), expires_at: new Date(until).toISOString(), last_http_status: 200, fail_count: 0, last_error: null }); }
        catch (e) { console.warn("ESPN cache write failed", e); }
      }
      return data;
    } catch (e) {
      if (stored && validate(stored.payload)) {
        console.warn("ESPN stale cache used", key);
        return stored.payload;
      }
      if (local && validate(local.data)) return local.data;
      throw e;
    }
  })();
  inFlight.set(key, promise);
  try { return await promise; }
  finally { inFlight.delete(key); }
}
export async function fetchSharedEspnScoreboard(date: string, store?: EspnCacheStore) {
  if (!/^\d{8}$/.test(date)) throw new Error("Invalid ESPN date");
  const url = new URL(scoreboardUrl);
  url.searchParams.set("dates", date);
  url.searchParams.set("limit", "500");
  const ttl = date === new Date().toISOString().slice(0,10).replace(/-/g,"") ? 45000 : 6 * 3600000;
  return cachedRequest("scoreboard:" + date, url.toString(), ttl, validScoreboard, store);
}
export async function fetchSharedEspnSummary(eventId: string, store?: EspnCacheStore) {
  if (!/^\d{1,16}$/.test(eventId)) return null;
  const url = new URL(summaryUrl);
  url.searchParams.set("event", eventId);
  return cachedRequest("summary:" + eventId, url.toString(), 5 * 60000, validSummary, store);
}
export function espnCircuitStatus() {
  return { failures, blocked_until: blockedUntil ? new Date(blockedUntil).toISOString() : null, memory_entries: memory.size };
}
