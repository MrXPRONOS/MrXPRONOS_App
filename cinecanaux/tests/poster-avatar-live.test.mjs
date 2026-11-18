import test from 'node:test';
import assert from 'node:assert/strict';

const HOST='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
async function get(path){
 const r=await fetch(HOST+path,{headers:{'cache-control':'no-cache'},signal:AbortSignal.timeout(20000)});
 return r;
}
test('actual public homepage has cinematic poster marquee and renewed profile avatar UI',async()=>{
 const r=await get('/app');assert.equal(r.status,200);
 const html=await r.text();
 for(const feature of ['cine-marquee-track','cine-poster-track','loadCinemaShowcase()','renderCinemaShowcase()','/api/showcase','const PRELOADED_CATALOG=[','/assets/channel-avatar/']){
  assert.ok(html.includes(feature),'Missing '+feature);
 }
 assert.ok(html.includes('static\\.tvmaze\\.com')||html.includes('static.tvmaze.com'));
 console.log('LIVE_HOME_POSTER_MARQUEE_OK');
});
test('production poster manifest returns vetted authentic film, TV and anime posters',async()=>{
 const r=await get('/api/showcase');assert.equal(r.status,200);
 const j=await r.json();
 assert.ok(Array.isArray(j.items));
 assert.ok(j.items.length>=10,'Real cinema poster assets missing');
 assert.ok(j.items.some(x=>x.type==='films'));
 assert.ok(j.items.some(x=>x.type==='series'));
 assert.ok(j.items.some(x=>x.type==='animes'));
 assert.ok(j.items.every(x=>/^https:\/\/(image\.tmdb\.org|static\.tvmaze\.com|m\.media-amazon\.com|images-na\.ssl-images-amazon\.com)\//.test(x.poster)),'Unexpected image host');
 console.log('LIVE_REAL_POSTERS_OK',j.items.length, [...new Set(j.items.map(x=>x.type))].join(','));
});
test('featured private channels and public channels serve nonempty, actual profile image endpoints',async()=>{
 const r=await get('/api/search?limit=80&sort=relevant');assert.equal(r.status,200);
 const j=await r.json();
 const owned=j.channels.filter(x=>x.featured);
 const priv=owned.filter(x=>x.private_channel);
 const pub=owned.filter(x=>!x.private_channel);
 assert.ok(priv.length>=12);
 assert.ok(pub.length>=8);
 const selected=[...priv.slice(0,4),...pub.slice(0,3)];
 await Promise.all(selected.map(async c=>{
  assert.match(c.avatar,/^\/assets\/channel-avatar\/[0-9]+\.jpg$/);
  const res=await get(c.avatar);
  assert.equal(res.status,200,'Avatar route missing for channel '+c.id);
  const mime=String(res.headers.get('content-type')||'');
  assert.ok(mime.startsWith('image/jpeg')||mime.startsWith('image/png')||mime.startsWith('image/svg+xml'),'Invalid image MIME for '+c.id+': '+mime);
  assert.ok((await res.arrayBuffer()).byteLength>150,'Avatar was empty for '+c.id);
 }));
 console.log('LIVE_AVATAR_ENDPOINTS_OK',selected.length);
});
