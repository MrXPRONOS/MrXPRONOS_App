import assert from 'node:assert/strict';
const base='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
async function get(path){
 const response=await fetch(base+path,{signal:AbortSignal.timeout(18000),headers:{'cache-control':'no-cache'}});
 const data=await response.json();
 assert.equal(response.status,200,'Expected a successful response from '+path.split('?')[0]);
 return data;
}
const page=await get('/api/search?limit=80&sort=relevant');
const rows=page.channels||[];
const featured=rows.filter(c=>c.featured);
const privates=featured.filter(c=>c.private_channel);
assert.equal(featured.length,20,'Expected 20 administered featured channels');
assert.equal(privates.length,12,'Expected 12 verified private links');
assert.ok(featured.every(c=>['films','series','animes'].includes(c.type)));
assert.ok(featured.every(c=>!String(c.title||'').toLowerCase().includes('torrent9')));
assert.ok(privates.every(c=>/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})$/.test(c.link)));
for(const type of ['films','series','animes']){
 const one=privates.find(c=>c.type===type);
 assert.ok(one,'Missing owned private channel for '+type);
 const preview=await get('/api/channel-preview?id='+one.id);
 assert.equal(preview.channel.id,one.id);
 assert.equal(preview.channel.link,one.link);
}
const mixed=featured.find(c=>String(c.title).includes('CinéX 🎬'));
assert.ok(mixed&&mixed.type==='films');
const series=await get('/api/search?types=series&limit=80');
assert.ok(series.channels.some(x=>x.id===mixed.id),'Mixed Films/Series channel must be discoverable in Series');
console.log('PASS 20 administered highlights, 12 invite-only, 3 private previews, dual-category and Torrent9 exclusion');
