// Public social media bridge: GitHub Actions OIDC -> Cloudflare KV -> Meta CDN readers.
// No Neon, Supabase, or credentials embedded in public media URLs.
const AUDIENCE = "mrxpronos-public-media-v1";
const ISSUER = "https://token.actions.githubusercontent.com";
const REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED_WORKFLOWS = new Set([
  ".github/workflows/shorts-coupons-production.yml",
  ".github/workflows/accumulator-photo-production.yml"
]);
const DAYS = 45;
const MAX_BYTES = 24 * 1024 * 1024;
const keyPattern = /^(?:shorts\/\d{4}\/\d{2}\/\d{2}\/[a-f0-9]{24}\.mp4|images\/mrxpronos-combine\/\d{4}-\d{2}-\d{2}\/[a-f0-9]{24}\.jpg)$/;

function fail(status, message) {
  return new Response(message, { status, headers: { "Cache-Control": "no-store" } });
}
function b64url(input) {
  const fixed = input.replace(/-/g, "+").replace(/_/g, "/");
  const decoded = atob(fixed + "=".repeat((4 - fixed.length % 4) % 4));
  return Uint8Array.from(decoded, c => c.charCodeAt(0));
}
async function checkJwt(raw) {
  if (!raw || raw.length > 18000) return false;
  const parts = raw.split(".");
  if (parts.length !== 3) return false;
  let header, claims;
  try {
    header = JSON.parse(new TextDecoder().decode(b64url(parts[0])));
    claims = JSON.parse(new TextDecoder().decode(b64url(parts[1])));
  } catch { return false; }
  const now = Math.floor(Date.now() / 1000);
  const workflow = claims.job_workflow_ref || "";
  const allowed = [...ALLOWED_WORKFLOWS].some(f => workflow === REPO + "/" + f + "@refs/heads/main");
  if (header.alg !== "RS256" || typeof header.kid !== "string" ||
      claims.iss !== ISSUER || claims.aud !== AUDIENCE ||
      claims.repository !== REPO || claims.ref !== "refs/heads/main" ||
      claims.repository_visibility !== "public" && claims.repository_visibility !== undefined ||
      !allowed || Number(claims.exp) < now || Number(claims.iat) > now + 60 ||
      Number(claims.iat) < now - 600) return false;
  try {
    const jwksResponse = await fetch(ISSUER + "/.well-known/jwks", { cf: { cacheTtl: 3600, cacheEverything: true } });
    if (!jwksResponse.ok) return false;
    const keys = await jwksResponse.json();
    const jwk = keys.keys?.find(k => k.kid === header.kid && k.kty === "RSA");
    if (!jwk) return false;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(parts[2]), new TextEncoder().encode(parts[0] + "." + parts[1]));
  } catch { return false; }
}
function contentType(key) { return key.endsWith(".mp4") ? "video/mp4" : "image/jpeg"; }
function headersFor(key, size) {
  return { "Content-Type": contentType(key), "Content-Disposition": "inline",
           "Accept-Ranges": "bytes", "Access-Control-Allow-Origin": "*",
           "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
           "Content-Length": String(size) };
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET")
      return new Response("media-ready", { headers: { "Cache-Control": "no-store" } });
    const upload = url.pathname === "/upload";
    const key = upload ? url.searchParams.get("key") || "" : decodeURIComponent(url.pathname.slice(1));
    if (!keyPattern.test(key)) return fail(404, "Not found");
    if (upload) {
      if (request.method !== "PUT") return fail(405, "Method not allowed");
      if (!await checkJwt((request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "")))
        return fail(401, "Unauthorized");
      if (request.headers.get("Content-Type")?.split(";")[0] !== contentType(key))
        return fail(415, "Invalid media type");
      const length = Number(request.headers.get("content-length"));
      if (!Number.isInteger(length) || length < 100 || length > MAX_BYTES)
        return fail(413, "Media exceeds maximum size or invalid length");
      const body = await request.arrayBuffer();
      if (body.byteLength !== length) return fail(400, "Length mismatch");
      const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))]
        .map(x => x.toString(16).padStart(2, "0")).join("");
      const expected = key.match(/([a-f0-9]{24})\.(mp4|jpg)$/)?.[1];
      if (expected !== digest.slice(0, 24)) return fail(400, "Digest mismatch");
      await env.MRX_MEDIA.put(key, body, { expirationTtl: DAYS * 86400, metadata: { size: length } });
      return Response.json({ ok: true, key, size: length, sha256: digest,
        url: url.origin + "/" + key }, { headers: { "Cache-Control": "no-store" } });
    }
    if (request.method !== "GET" && request.method !== "HEAD") return fail(405, "Method not allowed");
    const stored = await env.MRX_MEDIA.get(key, { type: "arrayBuffer" });
    if (!stored) return fail(404, "Media not found");
    const size = stored.byteLength;
    let range = request.headers.get("Range");
    const headers = headersFor(key, size);
    if (range) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      if (!match) return new Response(null, { status: 416, headers: { "Content-Range": "bytes */" + size } });
      const start = Number(match[1]), end = match[2] ? Number(match[2]) : size - 1;
      if (start >= size || end < start || end >= size)
        return new Response(null, { status: 416, headers: { "Content-Range": "bytes */" + size } });
      headers["Content-Range"] = "bytes " + start + "-" + end + "/" + size;
      headers["Content-Length"] = String(end - start + 1);
      return new Response(request.method === "HEAD" ? null : stored.slice(start, end + 1),
        { status: 206, headers });
    }
    return new Response(request.method === "HEAD" ? null : stored, { status: 200, headers });
  }
};
