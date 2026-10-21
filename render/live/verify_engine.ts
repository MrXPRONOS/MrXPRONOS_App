// CI build invariant: rollback the ONE authorized transport override and compare
// the exact original source with the GitHub main branch blob SHA.
const path = "supabase/functions/live/index.ts";
const source = await Deno.readTextFile(path);
const patch = "  const endpoint = new URL(\n    Deno.env.get(\"LIVE_BATCH_ENDPOINT\") ||\n      `${SUPABASE_URL.replace(/\\/$/, \"\")}/functions/v1/live/refresh/batch`,\n  );\n";
const original = "  const endpoint = new URL(\n    `${SUPABASE_URL.replace(/\\/$/, \"\")}/functions/v1/live/refresh/batch`,\n  );\n";
if (!source.includes(patch) || source.indexOf(patch) !== source.lastIndexOf(patch)) {
  throw new Error("Transport-only patch missing or duplicated");
}
const restored = source.replace(patch, original);
const data = new TextEncoder().encode(restored);
const meta = new TextEncoder().encode("blob " + data.byteLength + "\u0000");
const githubBlob = new Uint8Array(meta.byteLength + data.byteLength);
githubBlob.set(meta);
githubBlob.set(data,meta.byteLength);
const digest = new Uint8Array(await crypto.subtle.digest("SHA-1",githubBlob));
const hash = [...digest].map(n=>n.toString(16).padStart(2,"0")).join("");
const expected = "36c0f2b2b9c4a24e62e03e83f5f4818849af16e2";
if (hash!==expected) {
  console.error({hash,expected});
  throw new Error("LIVE ENGINE DRIFT: calculations or business rules changed");
}
const mandatory = [
  "computeMomentum","getMatchFlow","conservativeProjection","poissonTail",
  "candidateProbability","estimatedModelOdds","legacyBaselineThreshold",
  "historicalUpliftCap","buildPlayabilityEnvelope","selectMarketFacingCandidate",
  "getLineCandidates","predictionDataQuality","predictTotalCorners",
  "predictTotalShots","predictTotalFouls","computeAiScore","computeValueScore",
  "applyPredictionQualityContext","alignPredictionToAvailableBookmakerLine",
  "computeLiveCouponPricing","validatePredictionsInPlay","validatePredictionsNow",
  "savePrediction","refreshLiveDataInBatches","enrichLiveMatchesWithBsdStats",
  "enrichLiveMatchesWithEspnSummaries","enrichLiveMatchesWithMoviOddsStats",
  "enrichLiveMatchesWithFreeStats","mergeAdditionalProviderMatches",
  "sendTelegramLiveCoupon","sendTelegramValidationResult",
  "dailyGenerateSnapshots","dailyValidateSnapshots",
];
for (const name of mandatory) {
  if (!source.includes("function "+name+"("))
    throw new Error("LIVE function missing: "+name);
}
// Independent Telegram LIVE handler: restore only its private port binding
// and check its original GitHub main blob hash.
const telegramPath = "supabase/functions/telegram-live/index.ts";
const telegramPatched = await Deno.readTextFile(telegramPath);
const telegramPortTail = '}, { hostname: "127.0.0.1", port: Number(Deno.env.get("TELEGRAM_LIVE_INTERNAL_PORT") || 8001) });\\n'.replace(/\\\\n$/, "\\n");
const originalTelegramTail = '});\\n'.replace(/\\\\n$/, "\\n");
if (!telegramPatched.endsWith(telegramPortTail))
  throw new Error("Telegram handler has unexpected changes at tail");
const telegramOriginal = telegramPatched.slice(0,-telegramPortTail.length) + originalTelegramTail;
const telegramBytes = new TextEncoder().encode(telegramOriginal);
const telegramMeta = new TextEncoder().encode("blob " + telegramBytes.byteLength + "\\u0000");
const telegramBlob = new Uint8Array(telegramMeta.byteLength + telegramBytes.byteLength);
telegramBlob.set(telegramMeta);
telegramBlob.set(telegramBytes,telegramMeta.byteLength);
const telegramDigest = new Uint8Array(await crypto.subtle.digest("SHA-1",telegramBlob));
const telegramHash = [...telegramDigest].map(n=>n.toString(16).padStart(2,"0")).join("");
if (telegramHash !== "44f09c7c1b74066090d74af49f6f4da0f5ae85c9")
  throw new Error("Dedicated Telegram LIVE handler business code changed: "+telegramHash);
console.log("TELEGRAM_SOURCE_PARITY_PASS",telegramHash);

console.log("LIVE_SOURCE_PARITY_PASS", {
  original_git_blob:hash,
  preserved_functions:mandatory.length,
  exception:"one local batch transport URL override",
});
