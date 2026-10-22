import test from 'node:test';
import assert from 'node:assert/strict';
import {Script} from 'node:vm';
import {miniPage} from '../src/minipage.js';
import {premiumCSS} from '../src/premium-style.js';
import {premiumJS} from '../src/premium-ui.js';

test('Premium Free Pronos Mini App serves one complete browser script and 10 existing screens',async()=>{
 const r=miniPage();
 assert.equal(r.status,200);
 const html=await r.text();
 assert.match(html,/Free Pronos/);
 assert.match(html,/premium|p-hello/);
 const scripts=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)].filter(x=>x[1].trim());
 assert.equal(scripts.length,1);
 assert.doesNotThrow(()=>new Script(scripts[0][1],{filename:'FreePronosPremium.js'}));
 for(const view of ['home','coupons','mycoupons','detail','missions','history','referrals','alerts','support','admin']){
   assert.match(premiumJS,new RegExp(view==='detail'?"async function detail\\(":view==='admin'?"page==='admin'":view==='home'?"function home\\(":"function "+view+"\\("));
 }
});
test('Premium uses soft vector icons and mockup navigation, without glossy generated images',()=>{
 assert.match(premiumJS,/stroke-linecap="round"/);
 assert.match(premiumJS,/pPaths/);
 assert.match(premiumJS,/Coupons cote 4\+/);
 assert.match(premiumJS,/Parrainage/);
 assert.match(premiumJS,/data-page=/);
 assert.match(premiumCSS,/--orange:/);
 assert.match(premiumCSS,/--bg:/);
 assert.match(premiumCSS,/p-shortcuts/);
 assert.doesNotMatch(premiumCSS,/backdrop-filter:\s*blur\(3[0-9]px\)/);
});
test('Coupon detail shows selections only after unlock, and social rewards reflect existing rules',()=>{
 assert.match(premiumJS,/const unlocked=!!d/);
 assert.match(premiumJS,/unlocked&&Array\.isArray\(snap\.selections\)/);
 assert.match(premiumJS,/\+30 XP par parrainage validé/);
 assert.match(premiumJS,/id="p-alert-coupons"/);
 assert.match(premiumJS,/id="p-alert-results"/);
 assert.doesNotMatch(premiumJS,/Rappels d.expiration/);
});
test('API returns coupon snapshots only to authenticated owners, with user_id SQL filtering',async()=>{
 const {miniApi}=await import('../src/miniapp.js');
 const r=await miniApi(new Request('https://example.invalid/api/history'),{CF_BOT_TOKEN:'test'});
 assert.equal(r.status,401);
 const fs=await import('node:fs/promises');
 const apiSource=await fs.readFile(new URL('../src/miniapp.js',import.meta.url),'utf8');
 assert.match(apiSource,/r\.snapshot/);
 assert.match(apiSource,/WHERE r\.user_id=\?/);
});
