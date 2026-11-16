import assert from "node:assert/strict";
const base="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev";
async function get(path){
 const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),15000);
 try{
  const res=await fetch(base+path,{cache:"no-store",signal:ctl.signal});
  const raw=await res.text();
  return {status:res.status,body:res.headers.get("content-type")?.includes("json")?JSON.parse(raw):raw};
 }finally{clearTimeout(timer);}
}
const health=await get("/health");
assert.equal(health.status,200);
assert.equal(health.body.version,6);
assert.ok(health.body.publicChannels>0);
console.log("PASS lean worker deployed; channels="+health.body.publicChannels);
const app=await get("/app");
assert.equal(app.status,200);
for(const name of ['Ciné Radar','data-type="films"','data-type="series"','data-type="animes"','sheet-detail','class="brand-mark"','class="hero"']){
 assert.ok(app.body.includes(name),name+" missing");
}
for(const removed of ["Mes favoris","Parrainage","Copier le lien","Mes préférences"]){
 assert.ok(!app.body.includes(removed),removed+" not removed");
}
assert.ok(app.body.includes("button(\"Aperçu\""),"Eye icon button must remain available");
assert.ok(app.body.includes("button(\"Ouvrir\""),"Direct open button must remain available");
assert.ok(app.body.includes("scene-film"),"Movie hero background missing");
assert.ok(app.body.includes("scene-anime"),"Anime hero background missing");
console.log("PASS lightweight UI without favorites, referral or sharing");
const channels=await get("/api/catalog");
assert.equal(channels.status,200);
assert.ok(Array.isArray(channels.body.channels));
assert.ok(channels.body.channels.length>0);
assert.ok(channels.body.channels.every(x=>!Object.hasOwn(x,"favorites_count")));
console.log("PASS public category listings="+channels.body.channels.length);
const first=channels.body.channels[0];
const preview=await get("/api/channel-preview?id="+first.id);
assert.equal(preview.status,200);
assert.equal(preview.body.channel.id,first.id);
assert.ok(preview.body.channel.link.startsWith("https://t.me/"));
assert.ok(Object.hasOwn(preview.body.channel,"photo"));
assert.ok(Object.hasOwn(preview.body.channel,"post_image"));
console.log("PASS true public photo preview endpoint");
for(const route of ["/api/favorite","/api/profile","/api/preferences"]){
 const r=await get(route);assert.equal(r.status,404);
}
console.log("PASS old personal APIs removed");


// V2: filters can be combined and searched from the server, with fast client rendering.
assert.ok(app.body.includes("function applyFilters()"));
assert.ok(app.body.includes('"/api/search?q="'));
assert.ok(app.body.includes("selectedTypes"));
assert.ok(app.body.includes("fillPreview(c,images.get(c.id))"));
console.log("PASS V2 multi-category search and immediate preview shell");
assert.ok(app.body.includes("const PRELOADED_CATALOG=["),
  "Production HTML should include real channels; no second fetch necessary on first paint");
assert.ok(app.body.includes('<script defer src="https://telegram.org/js/telegram-web-app.js?64"></script>'),
  "Telegram SDK should not block first render");
console.log("PASS actual initial channel list embedded into the HTML and non-blocking Telegram SDK");

for(const type of ["films","series","animes"]){
 const start=performance.now();
 const response=await get("/api/catalog?type="+type);
 assert.equal(response.status,200);
 assert.ok(response.body.channels.every(x=>x.type===type));
 console.log("PASS "+type+" live API "+Math.round(performance.now()-start)+" ms");
}

// Production check: minimal Ciné Radar release V6, verified after performance deployment.

const search=await get("/api/search?q=film");
assert.equal(search.status,200);
assert.ok(search.body.total>0,"Film keyword must return indexed film channels");
assert.ok(search.body.channels.every(x=>x.type==="films"));
console.log("PASS live search by category keyword");
const multi=await get("/api/search?types=films,animes&q=film%3Banime");
assert.equal(multi.status,200);
assert.ok(multi.body.channels.some(x=>x.type==="films"));
assert.ok(multi.body.channels.some(x=>x.type==="animes"));
console.log("PASS multi-phrase multi-category live search");
const reviews=await get("/api/channels/"+first.id+"/reviews");
assert.equal(reviews.status,200);
assert.ok(Object.hasOwn(reviews.body,"summary"));
console.log("PASS public aggregate ratings");
const admin=await get("/api/admin/overview");
assert.equal(admin.status,403,"Admin access must not be possible anonymously");
console.log("PASS admin endpoint authentication boundary");
const blocked=await fetch(base+"/api/channels/"+first.id+"/reviews",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({rating:5,matches_description:"yes"})});
assert.equal(blocked.status,401);
console.log("PASS unsigned review rejected");
