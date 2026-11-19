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
