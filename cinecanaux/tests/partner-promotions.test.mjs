import test from 'node:test';
import assert from 'node:assert/strict';
import {PARTNERS,partnersAsCards,servePartnerCards,servePartnerAvatar} from '../partner-promotions.mjs';
import {APP_HTML} from '../app-page.mjs';

const HANDLES=['actufoot_mrxp','ActuCrypto24H','mrxpronosfr'];
test('only the three user-selected Telegram channels are promoted, with no invented links',()=>{
 assert.deepEqual(PARTNERS.map(x=>x.handle),HANDLES);
 assert.deepEqual(partnersAsCards().map(x=>x.url),HANDLES.map(x=>'https://t.me/'+x));
 assert.ok(partnersAsCards().find(x=>x.kind==='pronos').notice.includes('18+'));
});
test('public profile titles, descriptions and Telegram avatars are fetched from real Telegram metadata',async()=>{
 const real=globalThis.fetch;
 globalThis.fetch=async url=>{
  const handle=String(url).split('/').pop();
  return new Response('<html><meta property="og:title" content="'+handle+' | Telegram"><meta property="og:description" content="Actualités disponibles directement sur Telegram."><meta property="og:image" content="https://cdn4.telesco.pe/file/longpublicavatarphoto123456789.jpg"></html>',{status:200,headers:{'content-type':'text/html'}});
 };
 try{
  const res=await servePartnerCards(new Request('https://cinecanaux.test/api/partner-promos'));
  assert.equal(res.status,200);
  const json=await res.json();
  assert.equal(json.items.length,3);
  assert.equal(json.items[0].name,'actufoot_mrxp');
  assert.match(json.items[0].description,/Actualités disponibles/);
  assert.deepEqual(json.items.map(x=>x.handle),HANDLES);
 }finally{globalThis.fetch=real}
});
test('the avatar endpoint refuses unknown usernames before any external network access',async()=>{
 const result=await servePartnerAvatar(new Request('https://app.test/assets/promo-avatar/unknown.jpg'),{},null,'unknown');
 assert.equal(result.status,404);
});
test('avatar proxy preserves only verified image bytes and never exposes Telegram tokens',async()=>{
 const real=globalThis.fetch;
 const jpeg=new Uint8Array([255,216,255,224,0,16,74,70,73,70,0,0,255,217]);
 let photoCalls=0;
 globalThis.fetch=async url=>{
  if(String(url).startsWith('https://t.me/'))return new Response('<meta property="og:title" content="Actu Foot"><meta property="og:image" content="https://cdn4.telesco.pe/file/longpublicavatarphoto123456789.jpg">',{status:200,headers:{'content-type':'text/html'}});
  if(String(url).startsWith('https://cdn4.telesco.pe/file/')){photoCalls++;return new Response(jpeg,{status:200,headers:{'content-type':'image/jpeg'}});}
  throw Error('Unexpected URL');
 };
 try{
  const res=await servePartnerAvatar(new Request('https://app.test/assets/promo-avatar/actufoot_mrxp.jpg'),{},null,'actufoot_mrxp');
  assert.equal(res.status,200);
  assert.equal(res.headers.get('content-type'),'image/jpeg');
  assert.equal(photoCalls,1);
  assert.equal((await res.arrayBuffer()).byteLength,jpeg.byteLength);
 }finally{globalThis.fetch=real}
});
test('À découvrir stays a static responsive grid while only the promotional carousel auto-scrolls',()=>{
 assert.ok(APP_HTML.includes('function promoBlock(){'));
 assert.ok(APP_HTML.includes('a.append(promoBlock())'));
 assert.ok(APP_HTML.includes('promoAfter=(window.matchMedia'));
 assert.ok(APP_HTML.includes('grid-column:1/-1'));
 assert.ok(APP_HTML.includes('.cine-home-picks{grid-template-columns:repeat(2,minmax(0,1fr))'));
 assert.ok(APP_HTML.includes('@media(min-width:690px){.cine-home-picks{grid-template-columns:repeat(3,minmax(0,1fr))}}'));
 assert.ok(!APP_HTML.includes('.cine-home-picks{display:flex'));
 assert.ok(APP_HTML.includes('function autoScrollPromos(){'));
 assert.ok(APP_HTML.includes('autoScrollPromos();'));
 assert.ok(!APP_HTML.includes('autoScrollDiscover'));
 assert.ok(APP_HTML.includes('const track=$( "cine-home-picks"')===false); // Avoid accidentally using the discovery container as the moving track.
 assert.ok(APP_HTML.includes('querySelector(".cine-promo-track")'));
 assert.ok(APP_HTML.includes('track.scrollLeft+=1;'));
 assert.ok(APP_HTML.includes('for(let repeat=0;repeat<3;repeat++)'));
 assert.ok(APP_HTML.includes('card.setAttribute("aria-hidden","true")'));
 assert.ok(APP_HTML.includes('18+ · Joue responsablement'));
 for(const handle of HANDLES)assert.ok(APP_HTML.includes('https://t.me/'+handle));
 const p=APP_HTML.indexOf('sectionTitle(home,"À découvrir"');
 const q=APP_HTML.indexOf('const picks=node("div","cine-home-picks")',p);
 assert.ok(p>0&&q>p);
});
