import test from "node:test";
import assert from "node:assert/strict";
import {normalize,distance,searchRank,qualityScore,recommendations,extractTelegramActivity,categorizeCandidate,notificationEligible} from "../radar-intelligence.mjs";

const film={id:11,title:"Films comiques en français",description:"Canal de cinéma comédie et humour",content_type:"films",genre:"comedie",language:"VF",updated_at:"2026-10-21 08:00:00",favorites_count:5,opens:15,check_status:"reachable"};
const series={id:12,title:"Séries de police VF",description:"Séries policières",content_type:"series",genre:"policier",language:"VF",updated_at:"2026-10-20 08:00:00",favorites_count:12,opens:22,check_status:"reachable"};
const anime={id:13,title:"Dessins animés fantastiques",description:"Anime adventure",content_type:"animes",genre:"fantasy",language:"VOSTFR",updated_at:"2026-10-20 08:00:00",favorites_count:2,opens:1,check_status:"unknown"};

test("12 — Text accents and mild typos normalize predictably",()=>{
 assert.equal(normalize("Séries & Comédie !"),"series comedie");
 assert.equal(distance("comedie","comedi"),1);
 assert.ok(searchRank(film,"films drôles")>0);
 assert.ok(searchRank(film,"comedie francias")>0);
 assert.equal(searchRank(film,"universitaire médicale"),0);
});
test("13 — Semantically related genre terms are matched",()=>{
 assert.ok(searchRank(series,"serie enquete")>0);
 assert.ok(searchRank(anime,"manga")>0);
 assert.ok(searchRank(film,"cinéma humour VF")>0);
});
test("14 — Quality ranking uses observed activity, not made-up ratings",()=>{
 const high=qualityScore(film,Date.parse("2026-10-22T00:00:00Z"));
 const low=qualityScore({...film,check_status:"not_found",favorites_count:0,opens:0},Date.parse("2026-10-22T00:00:00Z"));
 assert.ok(high>low);
});
test("15 — Recommendations react to favorites and category",()=>{
 const ranked=recommendations([film,series,anime],[{id:11,genre:"comedie"}],{category:"series",language:"VF"});
 assert.ok(ranked.length===3);
 assert.ok(ranked.find(x=>x.id===12)._recommendation_score>ranked.find(x=>x.id===13)._recommendation_score);
});
test("16 — Telegram previews provide real ISO dates or unknown",()=>{
 const page='<div class="tgme_widget_message_date"><time datetime="2026-10-21T17:22:00+00:00">17:22</time></div>';
 assert.equal(extractTelegramActivity(page,Date.parse("2026-10-22T00:00:00Z")).lastPost,"2026-10-21T17:22:00.000Z");
 assert.equal(extractTelegramActivity("<html></html>").status,"unverifiable");
});
test("17 — Film, series and anime classification does not fabricate genre",()=>{
 assert.deepEqual(categorizeCandidate("Série incroyable","series"),{content_type:"series",genre:"general"});
 assert.deepEqual(categorizeCandidate("Films d'action","films"),{content_type:"films",genre:"action"});
 assert.deepEqual(categorizeCandidate("Animés VF","anime"),{content_type:"animes",genre:"general"});
});
test("18 — Notifications require explicit opt-in and user interests",()=>{
 assert.equal(notificationEligible({notification_enabled:0,category:"films",language:"VF"},film),false);
 assert.equal(notificationEligible({notification_enabled:1,category:"films",language:"VF"},film),true);
 assert.equal(notificationEligible({notification_enabled:1,category:"animes",language:"VF"},film),false);
});
