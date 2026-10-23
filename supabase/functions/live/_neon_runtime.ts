// Runtime-only adaptation for the historical Deno LIVE handler on Neon Node.js.
// Business logic and thresholds are not modified.
import { readFile } from "node:fs/promises";
import { createDecipheriv, privateDecrypt, constants } from "node:crypto";
function bootstrapEncryptedGithubSecrets() {
 const envelopeText=process.env.MRX_LIVE_ENVELOPE;
 const privateKeyB64=process.env.MRX_LIVE_PRIVATE_KEY_B64;
 if(!envelopeText && !privateKeyB64)return;
 if(!envelopeText || !privateKeyB64) throw new Error("NEON_LIVE_SECRETS_INCOMPLETE");
 const e=JSON.parse(envelopeText);
 if(e.version!==1)throw new Error("NEON_LIVE_SECRETS_INVALID_VERSION");
 const privateKey=Buffer.from(privateKeyB64,"base64").toString("utf8");
 const encryptedKey=Buffer.from(e.wrappedKey,"base64");
 const key=privateDecrypt({key:privateKey,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:"sha256"},encryptedKey);
 const cipher=createDecipheriv("aes-256-gcm",key,Buffer.from(e.iv,"base64"));
 cipher.setAuthTag(Buffer.from(e.tag,"base64"));
 const contents=Buffer.concat([cipher.update(Buffer.from(e.ciphertext,"base64")),cipher.final()]).toString("utf8");
 const values=JSON.parse(contents);
 const allowed=new Set([
  "BSD_API_TOKEN","CRON_SECRET","DEBUG_KEY","TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID",
  "TELEGRAM_CHAT_ID_SECONDARY","MOVIODDS_API_KEY","LIVE_PROP_ODDS_URL","LIVE_PROP_ODDS_TOKEN",
  "LIVE_ODDS_ENABLE_DIRECT","LIVE_ODDS_PINNWIRE_KEY","LIVE_ODDS_PINNWIRE_DIRECT_URL",
  "LIVE_ODDS_MOVIODDS_URL","LIVE_ODDS_MOVIODDS_TOKEN","LIVE_ODDS_PINNWIRE_URL",
  "LIVE_ODDS_PINNWIRE_TOKEN","LIVE_ODDS_ODDSLINK_URL","LIVE_ODDS_ODDSLINK_TOKEN",
  "LIVE_ODDS_GOALDIR_URL","LIVE_ODDS_GOALDIR_TOKEN","LIVE_ODDS_ODDSHARVESTER_URL",
  "LIVE_ODDS_ODDSHARVESTER_TOKEN","LIVE_REQUIRE_BOOKMAKER_LINE","SITE_URL"
 ]);
 for(const [k,v] of Object.entries(values)){
  if(allowed.has(k) && typeof v==="string" && v) process.env[k]=v;
 }
 if(!process.env.BSD_API_TOKEN || !process.env.CRON_SECRET) throw Error("NEON_LIVE_REQUIRED_SECRETS_MISSING");
 console.log("NEON_LIVE_SECRET_BOOTSTRAP_READY", {keys_loaded:Object.keys(values).length});
}
bootstrapEncryptedGithubSecrets();
// Neon uses direct PostgreSQL; these legacy names are only constructor compatibility.
process.env.SUPABASE_URL ||= "https://neon-compat.invalid";
process.env.SUPABASE_SERVICE_ROLE_KEY ||= "neon-postgresql-transport";
globalThis.Deno ??= {
 env: { get(name: string) { return process.env[name]; } },
 readFile: async (url: URL | string) => new Uint8Array(await readFile(url)),
};
export {};
