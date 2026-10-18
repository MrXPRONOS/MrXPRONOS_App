// Pure CMS publishing inspection. No network or database side effects.
export const CMS_PATHS = Object.freeze([
  "articles.json", "conseils.json", "bonus.json", "infos.json", "bookmakers.json"
]);

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
  let has_changes = false;
  let empty_all = true;

  for (const path of CMS_PATHS) {
    const previous = arrayFromJson(currentFiles?.[path], path);
    const next = arrayFromJson(nextFiles[path], path);
    const different = JSON.stringify(previous) !== JSON.stringify(next);
    if (different) has_changes = true;
    if (next.length > 0) empty_all = false;
    if (previous.length > 0 && next.length === 0) emptied_files.push(path);
    changes[path] = { before: previous.length, after: next.length, different };
  }
  return { has_changes, empty_all, emptied_files, changes };
}
