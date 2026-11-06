/** Pure, testable notification selection. No personal data leaves the user's preferences. */
export function normalize(text) {
  return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();
}
export function cleanFavorites(value) {
  const output = { teams: [], leagues: [] };
  if (!value || typeof value !== "object") return output;
  for (const field of ["teams", "leagues"]) {
    const arr = Array.isArray(value[field]) ? value[field] : [];
    if (arr.length > 20) throw new Error("Maximum 20 favoris par catégorie");
    const seen = new Set();
    for (const raw of arr) {
      if (typeof raw !== "string" || raw.length > 90) throw new Error("Favori invalide");
      const cleaned = raw.trim().replace(/\s+/g, " ");
      const key = normalize(cleaned);
      if (!cleaned || seen.has(key)) continue;
      seen.add(key);
      output[field].push(cleaned);
    }
  }
  return output;
}
export function localClock(now, offset, timezoneName) {
  if (timezoneName) {
    try {
      const format = new Intl.DateTimeFormat("en-US", {
        timeZone: timezoneName, year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", hourCycle: "h23"
      });
      const parts = Object.fromEntries(format.formatToParts(now)
        .filter(p => ["year","month","day","hour"].includes(p.type))
        .map(p => [p.type,p.value]));
      if (parts.year && parts.month && parts.day && parts.hour)
        return { day: parts.year+"-"+parts.month+"-"+parts.day, hour: Number(parts.hour) };
    } catch { /* Stored offsets retained as fallback. */ }
  }
  const local = new Date(now.getTime() - Number(offset) * 60000);
  return { day: local.toISOString().slice(0,10), hour: local.getUTCHours() };
}
function favoriteIncludes(value, favorites) {
  const normalized = normalize(value);
  if (!normalized) return false;
  const all = [...(favorites?.teams || []), ...(favorites?.leagues || [])];
  return all.some(t => {
    const term = normalize(t);
    return term.length >= 3 && (normalized === term || normalized.includes(term));
  });
}
export function selectRelevant(matches, news, favorites, day) {
  const matchesToday = [];
  const newsToday = [];
  for (const match of Array.isArray(matches) ? matches : []) {
    if (!match || match.date !== day || match.is_finished === true ||
        match.recommendation_eligible !== true || match.combo_only === true ||
        !["pro", "vip"].includes(String(match.category || "").toLowerCase()) ||
        ["finished","settlement_pending","postponed","cancelled","canceled"].includes(
          String(match.status || "").toLowerCase())) continue;
    const confidence = Number(match.prediction?.confidence);
    const percent = confidence > 0 && confidence <= 1 ? confidence * 100 : confidence;
    if (!Number.isFinite(percent) || percent < 79 || percent > 100) continue;
    if (!favoriteIncludes(match.home_team, favorites) &&
        !favoriteIncludes(match.away_team, favorites) &&
        !favoriteIncludes(match.league, favorites)) continue;
    if (!match.home_team || !match.away_team) continue;
    matchesToday.push(String(match.home_team).slice(0,36) + " – " +
      String(match.away_team).slice(0,36));
    if (matchesToday.length >= 3) break;
  }
  for (const item of Array.isArray(news) ? news : []) {
    if (!item || typeof item.published !== "string" || item.published.slice(0,10) !== day) continue;
    const names = Array.isArray(item.espn_verification?.teams) ? item.espn_verification.teams : [];
    const leagues = Array.isArray(item.espn_verification?.leagues) ? item.espn_verification.leagues : [];
    if (!favoriteIncludes(item.title, favorites) &&
        !names.some(v => favoriteIncludes(v, favorites)) &&
        !leagues.some(v => favoriteIncludes(v, favorites))) continue;
    newsToday.push(String(item.title || "").slice(0,90));
    if (newsToday.length >= 2) break;
  }
  return { matchesToday, newsToday };
}
