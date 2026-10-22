import {test} from "node:test";
import assert from "node:assert/strict";
import vapid from "../neon-functions/vapid-public-key/index.mjs";
import quick from "../neon-functions/quick-action/index.mjs";
import embedding from "../neon-functions/generate-embedding/index.mjs";
import membership from "../neon-functions/telegram-membership/index.mjs";

test("VAPID handles preflight and does not fabricate missing key",async()=>{
 const res=await vapid.fetch(new Request("https://staging.example/",{method:"OPTIONS",headers:{origin:"https://mrxpronos.github.io"}}));
 assert.equal(res.status,204);
 delete process.env.VAPID_PUBLIC_KEY;
 const missing=await vapid.fetch(new Request("https://staging.example/"));
 assert.equal(missing.status,503);
});
test("quick action fails closed without configured service authentication",async()=>{
 delete process.env.QUICK_ACTION_TOKEN;
 assert.equal((await quick.fetch(new Request("https://staging.example/"))).status,405);
 const res=await quick.fetch(new Request("https://staging.example/",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name:"Test"})}));
 assert.equal(res.status,503);
});
test("embedding never spends provider credits without keys",async()=>{
 delete process.env.MISTRAL_API_KEY;
 delete process.env.EMBEDDING_API_TOKEN;
 const res=await embedding.fetch(new Request("https://staging.example/",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({text:"Test"})}));
 assert.equal(res.status,503);
});
test("Telegram membership rejects webhook when token is not configured",async()=>{
 delete process.env.TELEGRAM_BOT_TOKEN;
 delete process.env.FOOTBALL_NEWS_BOT_TOKEN;
 const health=await membership.fetch(new Request("https://staging.example/"));
 assert.equal(health.status,200);
 assert.equal((await health.json()).ready,false);
 const res=await membership.fetch(new Request("https://staging.example/",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_join_request:{}})}));
 assert.equal(res.status,503);
});
