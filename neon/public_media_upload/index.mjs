import { createHash, createHmac, createPublicKey, verify as rsaVerify } from "node:crypto";

const ISS = "https://token.actions.githubusercontent.com";
const AUD = "mrxpronos-public-media";
const REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED = new Set([
  REPO + "/.github/workflows/shorts-coupons-production.yml@refs/heads/main",
  REPO + "/.github/workflows/accumulator-photo-production.yml@refs/heads/main",
]);
const json = (value, status=200) => new Response(JSON.stringify(value), {
  status, headers: {"content-type":"application/json","cache-control":"no-store"}
});
const sha256 = b => createHash("sha256").update(b).digest("hex");
const hmac = (key, value) => createHmac("sha256", key).update(value).digest();
const enc = path => "/" + path.split("/").map(encodeURIComponent).join("/");

async function auth(req) {
  const bearer = req.headers.get("authorization") || "";
  if (!bearer.startsWith("Bearer ") || bearer.length > 15000) throw Error("auth");
  const token = bearer.slice(7);
  const parts = token.split(".");
  if (parts.length !== 3) throw Error("jwt");
  const header = JSON.parse(Buffer.from(parts[0], "base64url").toString());
  const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString());
  const now = Math.floor(Date.now()/1000);
  if (header.alg !== "RS256" || !header.kid ||
      claims.iss !== ISS || claims.aud !== AUD || claims.repository !== REPO ||
      claims.ref !== "refs/heads/main" || !ALLOWED.has(claims.workflow_ref) ||
      !Number.isInteger(claims.exp) || claims.exp < now || claims.exp > now+900 ||
      !Number.isInteger(claims.iat) || claims.iat < now-900 || claims.iat > now+60)
    throw Error("claims");
  const result = await fetch(ISS + "/.well-known/jwks", {
    signal: AbortSignal.timeout(12000)
  });
  if (!result.ok) throw Error("jwks");
  const keys = (await result.json()).keys;
  const jwk = keys?.find(x => x.kid === header.kid && x.kty === "RSA");
  if (!jwk || !rsaVerify("RSA-SHA256", Buffer.from(parts[0]+"."+parts[1]),
                        createPublicKey({key:jwk,format:"jwk"}),
                        Buffer.from(parts[2],"base64url"))) throw Error("signature");
}

function objectKey(req) {
  const key = req.headers.get("x-mrx-object-key") || "";
  const mime = req.headers.get("content-type") || "";
  const video = /^shorts\/20\d\d\/(?:0[1-9]|1[0-2])\/[0-3]\d\/[a-zA-Z0-9_-]{8,85}\.mp4$/.test(key);
  const photo = /^images\/mrxpronos-combine\/20\d\d-[01]\d-[0-3]\d\/[a-zA-Z0-9_-]{1,75}\.jpg$/.test(key);
  if (!((video && mime === "video/mp4") || (photo && mime === "image/jpeg")))
    throw Error("invalid_key_or_media_type");
  return {key,mime,limit:video ? 48_000_000 : 8_000_000};
}

async function putObject(key, mime, bytes) {
  const endpoint = process.env.AWS_ENDPOINT_URL_S3;
  const access = process.env.AWS_ACCESS_KEY_ID;
  const secret = process.env.AWS_SECRET_ACCESS_KEY;
  const region = process.env.AWS_REGION || "eu-central-1";
  if (!endpoint || !access || !secret) throw Error("storage_unavailable");
  const base = new URL(endpoint);
  if (base.protocol !== "https:") throw Error("insecure_storage_origin");
  const resource = "videos/" + key;
  const uri = enc(resource);
  const amzdate = new Date().toISOString().replace(/[-:]|\.\d{3}/g,"");
  const date = amzdate.slice(0,8);
  const digest = sha256(bytes);
  const headers = {
    "content-type": mime,
    "host": base.host,
    "x-amz-content-sha256": digest,
    "x-amz-date": amzdate,
  };
  const session = process.env.AWS_SESSION_TOKEN;
  if (session) headers["x-amz-security-token"] = session;
  const names = Object.keys(headers).sort();
  const signed = names.join(";");
  const canonicalHeaders = names.map(k=>k+":"+headers[k]+"\n").join("");
  const canonical = ["PUT",uri,"",canonicalHeaders,signed,digest].join("\n");
  const scope = date+"/"+region+"/s3/aws4_request";
  const toSign = ["AWS4-HMAC-SHA256",amzdate,scope,sha256(Buffer.from(canonical))].join("\n");
  const signing = hmac(hmac(hmac(hmac(Buffer.from("AWS4"+secret), date),region),"s3"),"aws4_request");
  headers["authorization"] = "AWS4-HMAC-SHA256 Credential="+access+"/"+scope+
    ", SignedHeaders="+signed+", Signature="+hmac(signing,toSign).toString("hex");
  delete headers.host;
  const url = base.origin + uri;
  const response = await fetch(url, {method:"PUT",headers,body:bytes,
    signal:AbortSignal.timeout(120000)});
  if (!response.ok) throw Error("storage_write_http_"+response.status);
  const probe = await fetch(url, {method:"HEAD",signal:AbortSignal.timeout(15000)});
  if (!probe.ok) throw Error("public_media_not_accessible_http_"+probe.status);
  return {url,sha256:digest,bytes:bytes.length,verified:true};
}

export default {
  async fetch(req) {
    const path = new URL(req.url).pathname;
    if (req.method === "GET" && path === "/health")
      return json({ok:true,service:"mrx-public-media",bucket:"videos"});
    if (req.method !== "POST" || path !== "/") return json({error:"not_found"},404);
    try { await auth(req); }
    catch { return json({error:"unauthorized"},401); }
    let media;
    try { media = objectKey(req); }
    catch { return json({error:"invalid_media"},400); }
    const length = Number(req.headers.get("content-length")||0);
    if (length > media.limit) return json({error:"media_too_large"},413);
    try {
      const bytes = Buffer.from(await req.arrayBuffer());
      if (!bytes.length || bytes.length > media.limit) return json({error:"invalid_size"},413);
      const expected = req.headers.get("x-mrx-sha256") || "";
      if (!/^[0-9a-f]{64}$/i.test(expected) || sha256(bytes) !== expected.toLowerCase())
        return json({error:"sha256_mismatch"},422);
      return json(await putObject(media.key,media.mime,bytes));
    } catch (e) {
      return json({error:"storage_write_failed",type:String(e?.message||"error").slice(0,90)},502);
    }
  }
};
