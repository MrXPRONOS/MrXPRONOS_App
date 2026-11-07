import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {COPY} from "../assets/js/experiment-ux.mjs";
const dir=new URL("../",import.meta.url);
function source(path){return fs.readFileSync(new URL(path,dir),"utf8");}

test("two explicitly bounded, genuine UX copy experiments",()=>{
 assert.deepEqual(Object.keys(COPY).sort(),
   ["favorites_guidance_v1","install_value_v1"]);
 for(const [id,ab] of Object.entries(COPY)){
   assert.ok(ab.a.title&&ab.b.title&&ab.a.body&&ab.b.body);
   assert.notEqual(ab.a.title,ab.b.title);
   assert.match(ab.a.body,/sur votre appareil|sur cet appareil/i);
   assert.match(ab.b.body,/sur cet appareil|téléphone/i);
   for(const v of Object.values(ab)){
     assert.ok(!/garanti|gagnerez|dépêchez-vous|dernier chance|jackpot|cote élevée/i.test(v.body+" "+v.title));
   }
 }
 assert.match(COPY.install_value_v1.b.title,/écran d’accueil/);
 assert.match(COPY.favorites_guidance_v1.b.body,/Choisissez une équipe/);
});
test("only visible exposure and confirmed goals are sent",()=>{
 const js=source("assets/js/experiment-ux.mjs");
 assert.match(js,/document\.hidden/);
 assert.match(js,/IntersectionObserver/);
 assert.match(js,/observer\.disconnect/);
 assert.match(js,/record|addEvent\(state,"exposure"\)/);
 assert.match(js,/addEvent\(state,"conversion"\)/);
 assert.match(js,/data-mx-install-trigger/);
 assert.match(js,/mx-experiment-favorite-added/);
 assert.match(js,/function visitor\(\)/);
 assert.match(js,/localStorage\.setItem\("mx_user_id"/);
 assert.match(js,/p_experiment:entry\.experiment/);
 assert.match(js,/p_user_id:entry\.user_id/);
 assert.match(js,/p_event_id:entry\.event_id/);
 assert.ok(!/p_team|p_match|p_email|p_ip|p_referrer/.test(js));
});
test("public events are distinct from marketing campaigns and static admin data",()=>{
 const pwa=source("assets/js/pwa.js");
 const daily=source("assets/js/daily-hub.mjs");
 assert.match(pwa,/startInstall\(\)/);
 assert.match(daily,/startFavorites\(\)/);
 assert.match(daily,/new Event\("mx-experiment-favorite-added"\)/);
 assert.match(source("service-worker.js"),/const VERSION = 'v\\d+/);
 assert.match(source("service-worker.js"),/'\.\/assets\/js\/experiment-ux\.mjs'/);
 assert.match(source("scripts/build_public_site.py"),/experiment-ux\.mjs/);
});
