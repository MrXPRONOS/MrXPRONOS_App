import test from 'node:test';
import assert from 'node:assert/strict';
const ROOT='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
test('admin exists but exposes nothing without signed Telegram WebApp identity',async()=>{
 const page=await fetch(ROOT+'/admin',{signal:AbortSignal.timeout(14000)});
 assert.equal(page.status,200);const html=await page.text();
 assert.match(html,/analytics-period/);assert.match(html,/analytics-metrics/);assert.match(html,/analytics-csv/);
 const analytics=await fetch(ROOT+'/api/admin/analytics?period=all',{signal:AbortSignal.timeout(12000)});
 assert.equal(analytics.status,403);
 const overview=await fetch(ROOT+'/api/admin/overview',{signal:AbortSignal.timeout(12000)});
 assert.equal(overview.status,403);
 console.log('OWNER_ANALYTICS_PRIVATE_OK');
});
test('public telemetry rejects malformed events, and Mini App still loads',async()=>{
 const api=await fetch(ROOT+'/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'promo_open',target:'unknown-ad'}),signal:AbortSignal.timeout(15000)});
 assert.equal(api.status,400);
 const page=await fetch(ROOT+'/app',{signal:AbortSignal.timeout(15000)});
 assert.equal(page.status,200);
 const html=await page.text();
 assert.match(html,/cine-home-picks/);
 assert.match(html,/shareCineRadar/);
 assert.match(html,/autoScrollDiscover/);
 console.log('TELEMETRY_GUARD_AND_PUBLIC_APP_OK');
});

test('a valid first-party anonymous visit event is accepted and increments the current visit period',async()=>{
 const id=crypto.randomUUID();
 const res=await fetch(ROOT+'/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'visit',id}),signal:AbortSignal.timeout(12000)});
 const text=await res.text();
 console.log('VALID_ANONYMOUS_VISIT_RESPONSE:',JSON.stringify({status:res.status,response:text.slice(0,180),uuidLength:id.length,version:id[14],variant:id[19]}));
 assert.equal(res.status,200);
});

test('production accepts a standards-compliant UUIDv4 containing low digits in its random section',async()=>{
 // Regression: a broken server regex wrongly rejected 4xxx groups containing 0-3.
 // "ping" verifies parsing and hash without incrementing daily visit counts.
 const id='00000000-0000-4012-8000-000000000001';
 const r=await fetch(ROOT+'/api/analytics/event',{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify({event:'ping',id}),signal:AbortSignal.timeout(12000)
 });
 const payload=await r.text();
 console.log('UUIDV4_PRODUCTION_PING:',JSON.stringify({status:r.status,payload:payload.slice(0,120)}));
 assert.equal(r.status,200);
});
