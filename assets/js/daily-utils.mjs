/** Fonctions pures pour l'espace "Aujourd'hui" ; aucune donnée privée. */
export const MAX_FAVORITES = 20;

export function normalizeName(value) {
  return String(value ?? "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .trim().toLocaleLowerCase("fr")
    .replace(/\s+/g, " ");
}

export function localDay(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const two = n => String(n).padStart(2, "0");
  return date.getFullYear() + "-" + two(date.getMonth() + 1) + "-" + two(date.getDate());
}

export function nextDay(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return "";
  const value = new Date(day + "T12:00:00");
  if (Number.isNaN(value.getTime())) return "";
  value.setDate(value.getDate() + 1);
  return localDay(value);
}

export function isFinished(match) {
  const status = String(match?.status || "").toLowerCase();
  return match?.is_finished === true ||
    ["finished", "ft", "full_time", "fulltime"].includes(status);
}

export function eligible(match) {
  return Boolean(match && typeof match === "object" &&
    match.recommendation_eligible === true &&
    match.combo_only !== true &&
    ["pro", "vip"].includes(String(match.category || "").toLowerCase()) &&
    match.prediction && typeof match.prediction === "object");
}

export function matchDay(match) {
  return localDay(match?.event_date || match?.date);
}

export function displayConfidence(match) {
  const n = Number(match?.prediction?.confidence);
  if (!Number.isFinite(n) || n <= 0) return null;
  const percent = n <= 1 ? n * 100 : n;
  return percent > 0 && percent <= 100 ? percent : null;
}

export function resultState(match) {
  if (!isFinished(match)) return "pending";
  if (!Number.isFinite(Number(match.home_score)) || match.home_score == null ||
      !Number.isFinite(Number(match.away_score)) || match.away_score == null) return "unverified";
  if (match.verified_double === true) return "win";
  if (match.verified_double === false) return "not_validated";
  return "unverified";
}

export function favoriteMatch(item, favorites) {
  const teams = new Set((favorites?.teams || []).map(normalizeName));
  const leagues = new Set((favorites?.leagues || []).map(normalizeName));
  return teams.has(normalizeName(item?.home_team)) ||
    teams.has(normalizeName(item?.away_team)) ||
    leagues.has(normalizeName(item?.league));
}

export function normalizeFavorites(raw) {
  const normalized = { teams: [], leagues: [] };
  for (const field of ["teams", "leagues"]) {
    const seen = new Set();
    for (const name of Array.isArray(raw?.[field]) ? raw[field] : []) {
      if (typeof name !== "string" || name.length > 90) continue;
      const clean = name.trim().replace(/\s+/g, " ");
      const key = normalizeName(clean);
      if (!key || seen.has(key)) continue;
      normalized[field].push(clean);
      seen.add(key);
      if (normalized[field].length >= MAX_FAVORITES) break;
    }
  }
  return normalized;
}

export function toggleFavorite(favorites, kind, name) {
  const next = normalizeFavorites(favorites);
  if (!["teams","leagues"].includes(kind) || typeof name !== "string") return next;
  const clean = name.trim().replace(/\s+/g, " ").slice(0, 90);
  const key = normalizeName(clean);
  if (!key) return next;
  const existing = next[kind].findIndex(v => normalizeName(v) === key);
  if (existing >= 0) next[kind].splice(existing, 1);
  else if (next[kind].length < MAX_FAVORITES) next[kind].push(clean);
  return next;
}

export function upcoming(matches, today, favorites, onlyFavorites = false, limit = 60) {
  return (Array.isArray(matches) ? matches : [])
    .filter(m => eligible(m) && !isFinished(m) &&
      [today, nextDay(today)].includes(matchDay(m)) &&
      (!onlyFavorites || favoriteMatch(m, favorites)))
    .sort((a,b) => {
      const time = new Date(a.event_date).getTime() - new Date(b.event_date).getTime();
      if (Number.isFinite(time) && time !== 0) return time;
      return Number(a.display_rank || 9999) - Number(b.display_rank || 9999);
    })
    .slice(0,limit);
}

export function settled(matches, now = new Date(), days = 30) {
  const current = now instanceof Date ? now.getTime() : new Date(now).getTime();
  const lower = current - days * 86400000;
  return (Array.isArray(matches) ? matches : [])
    .filter(m => {
      if (!eligible(m) || !isFinished(m)) return false;
      const stamp = new Date(m.event_date).getTime();
      return Number.isFinite(stamp) && stamp >= lower && stamp <= current &&
        ["win", "not_validated"].includes(resultState(m));
    })
    .sort((a,b) => new Date(b.event_date).getTime()-new Date(a.event_date).getTime());
}

export function performance(matches, now = new Date(), days = 30) {
  const eligibleSettled = settled(matches,now,days);
  const total = eligibleSettled.length;
  const won = eligibleSettled.filter(m => resultState(m) === "win").length;
  const groups = new Map();
  for (const m of eligibleSettled) {
    const key = String(m.category || "autre").toUpperCase();
    if (!groups.has(key)) groups.set(key,{name:key,total:0,won:0});
    const g=groups.get(key);
    g.total++;
    if (resultState(m) === "win") g.won++;
  }
  const confidences = eligibleSettled.map(displayConfidence).filter(n=>n!=null);
  return {
    total, won, notValidated: total - won,
    rate: total ? Math.round(1000 * won / total) / 10 : null,
    confidenceAverage: confidences.length
      ? Math.round(10 * confidences.reduce((s,n)=>s+n,0) / confidences.length) / 10
      : null,
    byCategory:[...groups.values()].sort((a,b)=>a.name.localeCompare(b.name))
  };
}

export function makeSnapshot(matches, news, now = new Date()) {
  const items = {};
  for (const m of (Array.isArray(matches) ? matches : []).slice(-400)) {
    if (m && typeof m.id === "string" && m.id.length < 120) {
      items[m.id] = [
        String(m.status || ""), String(m.home_score ?? ""),
        String(m.away_score ?? ""), String(m.verified_double ?? "")
      ].join("|");
    }
  }
  return {
    when: now instanceof Date ? now.toISOString() : new Date(now).toISOString(),
    matches: items,
    news: (Array.isArray(news) ? news : []).map(n => String(n?.slug || "")).filter(Boolean).slice(0,90)
  };
}

export function changesSince(previous, current, matches, news) {
  if (!previous || !previous.matches || !Array.isArray(previous.news))
    return { firstVisit:true, newMatches:[], updatedMatches:[], newNews:[] };
  const seen = previous.matches;
  const newMatches = [];
  const updatedMatches = [];
  for (const m of (Array.isArray(matches) ? matches : [])) {
    if (!m || !eligible(m) || typeof m.id !== "string") continue;
    if (seen[m.id] === undefined) newMatches.push(m);
    else if (current.matches[m.id] !== seen[m.id]) updatedMatches.push(m);
  }
  const before = new Set(previous.news);
  const newNews = (Array.isArray(news) ? news : []).filter(n => n && n.slug && !before.has(String(n.slug)));
  return { firstVisit:false,newMatches:newMatches.slice(0,20),
    updatedMatches:updatedMatches.slice(0,20),newNews:newNews.slice(0,20) };
}

export function validNews(items) {
  return (Array.isArray(items) ? items : []).filter(item=>
    item && typeof item.title === "string" && item.title.trim() &&
    typeof item.slug === "string" && /^[a-zA-Z0-9_-]{4,80}$/.test(item.slug) &&
    Number.isFinite(new Date(item.published).getTime()))
    .sort((a,b)=>new Date(b.published).getTime()-new Date(a.published).getTime());
}

export function newsForFavorites(items,favorites) {
  const terms=(favorites?.teams||[]).map(normalizeName).filter(s=>s.length>=3);
  const leagues=(favorites?.leagues||[]).map(normalizeName).filter(s=>s.length>=3);
  if (!terms.length && !leagues.length) return [];
  return validNews(items).filter(n=>{
    const title=normalizeName(n.title);
    const teams=Array.isArray(n.espn_verification?.teams)
      ? n.espn_verification.teams.map(normalizeName) : [];
    const competition=Array.isArray(n.espn_verification?.leagues)
      ? n.espn_verification.leagues.map(normalizeName) : [];
    return terms.some(term=>teams.some(t=>t===term)||title.includes(term)) ||
      leagues.some(term=>competition.some(l=>l===term));
  });
}

export const TIPS = Object.freeze([
  { title:"Une probabilité n'est pas une certitude", body:"Une confiance estimée à 80 % laisse toujours une possibilité d'échec. Elle ne prédit pas un résultat garanti." },
  { title:"Attention aux petits échantillons", body:"Deux ou trois matchs ne suffisent pas pour juger durablement la forme d'une équipe. Vérifiez la période et le niveau des adversaires." },
  { title:"Comprendre les confrontations directes", body:"Les historiques H2H sont contextuels : les effectifs, les entraîneurs et le lieu du match peuvent avoir changé." },
  { title:"Vérifier les scores finaux", body:"Un pronostic n'est considéré évalué qu'après un résultat final publié. Un match en attente ne doit pas être compté comme gagné." },
  { title:"Ne pas confondre cote et probabilité", body:"Une cote reflète des conditions de marché et des marges ; elle n'est pas une probabilité exacte ni une garantie." },
  { title:"Lire les tendances avec prudence", body:"Un taux de réussite observé peut varier fortement d'une période à l'autre. Examinez gagnants et non validés, pas seulement les succès." },
  { title:"La discipline passe avant le pronostic", body:"Les analyses football sont informatives. Les paris comportent un risque de perte et ne sont pas un revenu assuré." }
]);

export function todayTip(date=new Date()) {
  const day = Math.floor(Date.UTC(date.getFullYear(),date.getMonth(),date.getDate())/86400000);
  return TIPS[((day % TIPS.length)+TIPS.length)%TIPS.length];
}

function icsEscape(text) {
  return String(text).replace(/\\/g,"\\\\").replace(/\r?\n/g,"\\n").replace(/,/g,"\\,").replace(/;/g,"\\;");
}
function calendarStamp(date) {
  const two = n => String(n).padStart(2,"0");
  return date.getFullYear()+two(date.getMonth()+1)+two(date.getDate())+"T"+
    two(date.getHours())+two(date.getMinutes())+two(date.getSeconds());
}
export function reminderICS(now=new Date(), hour="08:00") {
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(hour)) throw Error("Heure invalide");
  const [h,min] = hour.split(":").map(Number);
  const start = new Date(now);
  start.setHours(h,min,0,0);
  if (start <= now) start.setDate(start.getDate()+1);
  const end=new Date(start.getTime()+15*60000);
  const uid="mrxpronos-daily-"+Math.random().toString(36).slice(2)+"@mrxpronos";
  const lines=[
    "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Mr XPRONOS//Rappel analyse football//FR",
    "CALSCALE:GREGORIAN","BEGIN:VEVENT",
    "UID:"+uid,"DTSTART:"+calendarStamp(start),"DTEND:"+calendarStamp(end),
    "RRULE:FREQ=DAILY",
    "SUMMARY:"+icsEscape("Mr XPRONOS — actualités et résultats"),
    "DESCRIPTION:"+icsEscape("Consulter librement les analyses et résultats football sur https://mrxpronos.github.io/MrXPRONOS_App/aujourdhui.html"),
    "URL:https://mrxpronos.github.io/MrXPRONOS_App/aujourdhui.html",
    "BEGIN:VALARM","TRIGGER:-PT0M","ACTION:DISPLAY",
    "DESCRIPTION:"+icsEscape("Rappel quotidien — Football et résultats"),
    "END:VALARM","END:VEVENT","END:VCALENDAR"
  ];
  return lines.join("\r\n")+"\r\n";
}
