// Pure CMS publishing inspection. No network or database side effects.
export const CMS_PATHS = Object.freeze([
  "articles.json", "conseils.json", "bonus.json", "infos.json", "bookmakers.json"
]);

// Always retain verified automatically generated match articles when publishing CMS
// entries. The CMS is an overlay, not a replacement of the editorial pipeline.
export function mergeGeneratedMatchArticles(cmsRows, existingRows) {
  if (!Array.isArray(cmsRows) || !Array.isArray(existingRows)) {
    throw new Error("Articles CMS invalides");
  }
  const isAutomatic = row => /^bsd-match-[a-z0-9-]+$/i.test(String(row?.slug || ""));
  if (cmsRows.some(isAutomatic)) {
    throw new Error("Les articles de matchs automatiques sont gérés par le moteur, pas par le CMS");
  }
  const auto = existingRows.filter(row => row && typeof row === "object" && isAutomatic(row));
  return [...cmsRows, ...auto];
}
function cmsIdentity(path, row, index) {
  if (path === "articles.json" || path === "conseils.json") return String(row?.slug || "missing:" + index);
  if (path === "bookmakers.json") return String(row?.name || "missing:" + index);
  if (path === "bonus.json") return [row?.bookmaker, row?.title, row?.start_date].map(x=>String(x||"")).join("|");
  if (path === "infos.json") return String(row?.title || "missing:" + index);
  return JSON.stringify(row);
}

function arrayFromJson(value, path) {
  if (typeof value !== "string") throw new Error("Fichier manquant : " + path);
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) throw new Error("Fichier CMS invalide : " + path);
  return parsed;
}

export function inspectPublishFiles(nextFiles, currentFiles) {
  const paths = Object.keys(nextFiles || {});
  if (paths.length !== CMS_PATHS.length ||
      CMS_PATHS.some(path => !Object.hasOwn(nextFiles, path))) {
    throw new Error("Ensemble de fichiers CMS incomplet");
  }
  const changes = {};
  const emptied_files = [];
  const removed_files = [];
  const removed_counts = {};
  let has_changes = false;
  let empty_all = true;

  for (const path of CMS_PATHS) {
    const previous = arrayFromJson(currentFiles?.[path], path);
    const next = arrayFromJson(nextFiles[path], path);
    const different = JSON.stringify(previous) !== JSON.stringify(next);
    if (different) has_changes = true;
    if (next.length > 0) empty_all = false;
    if (previous.length > 0 && next.length === 0) emptied_files.push(path);
    const currentKeys = new Set(next.map((row,i)=>cmsIdentity(path,row,i)));
    const removed = previous.filter((row,i)=>!currentKeys.has(cmsIdentity(path,row,i))).length;
    removed_counts[path] = removed;
    if (removed > 0) removed_files.push(path);
    changes[path] = { before: previous.length, after: next.length, different };
  }
  return { has_changes, empty_all, emptied_files, removed_files, removed_counts, changes };
}
