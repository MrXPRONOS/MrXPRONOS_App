import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {Script} from 'node:vm';
import {levelFor,periodKey,dashboardText,faqText} from '../src/features.js';
import {authenticateInitData,miniApi} from '../src/miniapp.js';
import {html,miniPage} from '../src/minipage.js';

const crypto=globalThis.crypto??webcrypto;
test('niveaux déterminés par XP cumulés et progression',()=>{
 assert.equal(levelFor(0).name,'Débutant');
 assert.equal(levelFor(100).name,'Amateur');
 assert.equal(levelFor(300).name,'Expert');
 assert.equal(levelFor(800).name,'Légende');
 assert.equal(levelFor(120).remaining,180);
});
test('clés de semaine UTC commencent lundi',()=>{
 assert.equal(periodKey('daily',new Date('2026-10-22T00:00:00Z')),'2026-10-22');
 assert.equal(periodKey('weekly',new Date('2026-10-22T00:00:00Z')),'2026-10-19');
});
test('tableau de bord et FAQ utilisent marque Free Pronos',()=>{
 const t=dashboardText({name:'Test',xp:45,earnedToday:5,coupons:1,tasks:2,referrals:0,level:levelFor(90)});
 assert.match(t,/FREE PRONOS/);
 assert.match(faqText(),/FREE PRONOS/);
});
async function signed(now,token='123:TEST'){
 const payload=new URLSearchParams({auth_date:String(now),user:JSON.stringify({id:80599,first_name:'Test'})});
 const encoder=new TextEncoder();
 const first=await crypto.subtle.importKey('raw',encoder.encode('WebAppData'),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const bytes=await crypto.subtle.sign('HMAC',first,encoder.encode(token));
 const second=await crypto.subtle.importKey('raw',bytes,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const plain=[...payload].map(([k,v])=>k+'='+v).sort().join('\n');
 const digest=new Uint8Array(await crypto.subtle.sign('HMAC',second,encoder.encode(plain)));
 payload.set('hash',Array.from(digest).map(n=>n.toString(16).padStart(2,'0')).join(''));
 return payload.toString();
}
test('initData Mini App vérifiée via HMAC et expiration',async()=>{
 const now=Math.floor(Date.now()/1000);
 const data=await signed(now);
 assert.deepEqual(await authenticateInitData(data,'123:TEST',now),{userId:80599});
 assert.equal(await authenticateInitData(data,'wrong-token',now),null);
 assert.equal(await authenticateInitData(data.replace('80599','80598'),'123:TEST',now),null);
 assert.equal(await authenticateInitData(data,'123:TEST',now+90000),null);
});
test('API Mini App refuse requêtes sans initData',async()=>{
 const r=await miniApi(new Request('https://example.invalid/api/me'),{CF_BOT_TOKEN:'123:TEST',DB:{}});
 assert.equal(r.status,401);
});
test('Mini App responsive présente couleurs et menus; ne révèle aucun token',()=>{
 assert.match(html,/FREE/);
 assert.match(html,/PRONOS/);
 assert.match(html,/data-page="coupons"/);
 assert.match(html,/data-page="history"/);
 assert.match(html,/telegram-web-app\.js/);
 assert.equal(miniPage().status,200);
});

test('JavaScript embarqué de la Mini App est syntaxiquement valide',()=>{
 const scripts=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)];
 assert.equal(scripts.length,1);
 assert.doesNotThrow(()=>new Script(scripts[0][1],{filename:'FreePronosMiniApp.js'}));
 assert.match(scripts[0][1],/data-filter-xp/);
 assert.match(scripts[0][1],/data-sort/);
 assert.match(scripts[0][1],/api\/support/);
});
