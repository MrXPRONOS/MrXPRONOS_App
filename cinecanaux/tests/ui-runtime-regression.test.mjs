import test from 'node:test';
import assert from 'node:assert/strict';
import {Script} from 'node:vm';
import {readFileSync} from 'node:fs';
import {APP_HTML} from '../app-page.mjs';

const scripts=[...APP_HTML.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]).filter(s=>s.trim());
const directory=scripts.find(s=>s.includes('function buildCard('));
const navigation=scripts.find(s=>s.includes('function featuredCard('));

test('every inline UI script parses as JavaScript, not just the surrounding mjs wrapper',()=>{
 assert.ok(scripts.length>=2,'Expected directory and navigation scripts');
 for(const source of scripts)assert.doesNotThrow(()=>new Script(source));
});
test('directory cards own the avatar helper they call',()=>{
 assert.ok(directory,'Directory script missing');
 assert.ok(directory.includes('function showChannelImage('),'Directory image helper must be in same closure');
 assert.ok(directory.includes('function photoHost(')||directory.includes('const photoHost='),'Avatar URL validator missing');
 assert.ok(directory.includes('showChannelImage(img,directAvatar,c.photo,'));
});
test('home/discovery cards own their image fallback helpers',()=>{
 assert.ok(navigation,'Navigation script missing');
 assert.ok(navigation.includes('function showChannelImage('));
 assert.ok(navigation.includes('const photoHost='));
 assert.ok(navigation.includes('showChannelImage(img,url,null,'));
});
test('Films, Series, Animes shortcuts select a type filter, not free-text matches',()=>{
 assert.ok(navigation.includes('const category=["films","series","animes"].includes(term)?term:null'));
 assert.ok(navigation.includes('button.click();'));
 assert.ok(navigation.includes('q.value=category?"":term;'));
});
test('all category controls remain wired to an API-backed directory',()=>{
 for(const type of ['films','series','animes']){
  assert.ok(APP_HTML.includes('data-type="'+type+'"'));
 }
 assert.ok(directory.includes('function chooseCategory(chosen,exclusive=false){'));
 assert.ok(directory.includes('syncCategoryControls();'));
 assert.ok(directory.includes('load(true);'));
 assert.ok(APP_HTML.includes('"/api/search?q="'));
 assert.ok(APP_HTML.includes('const PRELOADED_CATALOG=null;'));
});

test('type shortcut actually selects the right button and clears the search term',()=>{
 const body=navigation.match(/function setFilter\(term\)\{([\s\S]*?)\n\}/)?.[1];
 assert.ok(body,'setFilter implementation missing');
 for(const kind of ['films','series','animes']){
  const state={selected:'series',query:'previous query',hash:'',focus:false,triggered:false};
  const q={get value(){return state.query},set value(v){state.query=v},dispatchEvent(){state.triggered=true},focus(){state.focus=true}};
  const all={get classList(){return {contains:()=>state.selected==='all'}},click(){state.selected='all'}};
  const cats=Object.fromEntries(['films','series','animes'].map(t=>[t,{get classList(){return{contains:()=>state.selected===t}},click(){state.selected=t}}]));
  const context={
   setHash(p){state.hash=p},
   $(id){assert.equal(id,'search');return q},
   document:{querySelector(sel){
    if(sel==='#tabs [data-type="all"]')return all;
    for(const t of ['films','series','animes'])if(sel==='#tabs [data-type="'+t+'"]')return cats[t];
    return null;
   }},
   Event:class Event{},
   setTimeout(fn){fn()}
  };
  const fn=new Function('term','setHash','$','document','Event','setTimeout',body);
  fn(kind,context.setHash,context.$,context.document,context.Event,context.setTimeout);
  assert.equal(state.hash,'explorer');
  assert.equal(state.selected,kind);
  assert.equal(state.query,'');
  assert.equal(state.triggered,true);
  assert.equal(state.focus,true);
 }
});

test('home and discovery hydrate immediately from the same preloaded catalog as Explorer',()=>{
 assert.ok(directory.includes('window.__CINERADAR_INITIAL_CATALOG__=PRELOADED_CATALOG'));
 assert.ok(navigation.includes('const embedded=window.__CINERADAR_INITIAL_CATALOG__'));
 const bootstrap=navigation.indexOf('const embedded=window.__CINERADAR_INITIAL_CATALOG__');
 const fetchIndex=navigation.indexOf('fetch("/api/catalog?limit=80"');
 assert.ok(bootstrap!==-1&&fetchIndex>bootstrap,'Home must render before the network request');
 const step=navigation.slice(bootstrap,fetchIndex);
 for(const fn of ['miniFeatured();','discover();','genreContent();','cardDecorate();'])assert.ok(step.includes(fn),fn+' omitted from instant hydration');
});

test('category counts use correct French singular/plural',()=>{
 assert.ok(APP_HTML.includes('count+(count===1?" canal":" canaux")+" dans l’annuaire"'));
 assert.ok(!APP_HTML.includes('count+" canal"+(count===1?"":"x")'));
});

test('both directory and home use versioned real-avatar URL on the first load',()=>{
 for(const block of [directory,navigation]){
  assert.ok(block.includes('source+"?v=3"'));
  assert.ok(block.includes('source+"?v=3&refresh=1"'));
  assert.ok(block.includes('img.src=candidates[0];'));
 }
});

test('returning from Favorites and History restores the Explorer heading and count',()=>{
 assert.ok(navigation.includes('else if(h)h.textContent=$("search")?.value?.trim()?"Résultats de recherche":"Les canaux";'));
 assert.ok(navigation.includes('if(counter)counter.textContent=visible+" cana"+(visible===1?"l":"ux");'));
});
test('home and Discover recommendations open their channel preview directly without keyword filtering',()=>{
 assert.ok(navigation.includes('document.dispatchEvent(new CustomEvent("cineradar:show-preview"'));
 assert.ok(directory.includes('document.addEventListener("cineradar:show-preview"'));
 assert.ok(directory.includes('showPreview(c);'));
 assert.ok(!navigation.includes('else setFilter(c.title)'));
});

test('public visitor screens omit backend explanations and retain actionable information',()=>{
 for(const unwanted of [
  'Aucun lien inventé',
  'Les suggestions sont calculées',
  'Lien récemment contrôlé',
  'Statut du lien : non encore vérifié',
  'publications épinglées',
  'Version mobile',
  'Le catalogue des publications vérifiées'
 ])assert.ok(!APP_HTML.includes(unwanted),'Technical-facing text remains: '+unwanted);
 for(const useful of [
  'À découvrir aussi',
  'Choix de confidentialité',
  'Désactiver les statistiques',
  'Supprimer mes favoris et mon historique',
  'Partage son lien Telegram',
  'Aucune affiche à présenter pour le moment.'
 ])assert.ok(APP_HTML.includes(useful),'Missing user-facing feature: '+useful);
 assert.ok(!APP_HTML.includes('function radarLoad()'),'Unused radar diagnostics should not be shipped to visitors');
});

test('lot 1: all ten original 3D icons are integrated and the sprite is an optimized transparent WebP',()=>{
 const atlas=readFileSync(new URL('../assets/ui-icons-lot1.webp',import.meta.url));
 assert.equal(atlas.subarray(0,4).toString(),'RIFF');
 assert.equal(atlas.subarray(8,12).toString(),'WEBP');
 assert.equal(atlas.subarray(12,16).toString(),'VP8X');
 assert.equal(atlas.readUIntLE(24,3)+1,400,'Sprite should contain ten 40px-wide icons');
 assert.equal(atlas.readUIntLE(27,3)+1,40);
 assert.ok(atlas.byteLength<12000,'Do not bloat the Mini App with images');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot1.webp')"));
 assert.ok(APP_HTML.includes('background-size:1000% 100%'));
 for(const key of ['sparkle','film','tv','gamepad','search','eye','external','back','x','send']){
  assert.ok(APP_HTML.includes('.cine-icon-'+key+'{background-position-x:'),key+' icon position is missing');
  assert.ok(directory.includes('"'+key+'"'),key+' is not registered as a functional icon');
 }
 assert.ok(directory.includes('holder.classList.add("cine-3d-icon","cine-icon-"+key)'));
 for(const [kind,icon] of [['Films','film'],['Séries','tv'],['Animés','gamepad']])
  assert.ok(navigation.includes('quickButton("'+icon+'","'+kind+'"'),kind+' shortcut is still an emoji');
 assert.ok(APP_HTML.includes('function autoScrollPromos()'),'Existing promotional carousel must be preserved');
});


test('lot 2: all ten approved 3D navigation icons are used in interactive controls',()=>{
 for(const key of ['accueil','explorer','decouvrir','favoris','historique','proposer','apropos','menu','fermer','partager']){
  assert.ok(navigation.includes(' '+key+':[['),key+' 3D vector path is missing');
 }
 assert.ok(APP_HTML.includes('function cineNavIcon(key){'));
 assert.ok(APP_HTML.includes('viewBox="0 0 512 512"'));
 assert.ok(APP_HTML.includes('linearGradient id='));
 assert.ok(APP_HTML.includes('.cine-nav-icon svg{display:block;width:100%'));
 assert.ok(navigation.includes('b.append(cineNavIcon(icon),document.createTextNode(label))'),'Menu and bottom tabs must have matching vector icons');
 for(const key of ['accueil','explorer','decouvrir','favoris','historique','proposer','apropos']){
  assert.ok(navigation.includes('"'+key+'"]'),key+' navigation entry missing');
 }
 assert.ok(navigation.includes('makeNav("Menu","accueil","menu")'),'Menu tab must use the lot 2 menu icon');
 assert.ok(navigation.includes('menuBtn.append(cineNavIcon("menu"))'));
 assert.ok(navigation.includes('close.append(cineNavIcon("fermer"))'));
 assert.ok(navigation.includes('btn.append(cineNavIcon("partager"),document.createTextNode("Partager Ciné Radar"))'));
 assert.ok(navigation.includes('suggest.replaceChildren(cineNavIcon("proposer")'));
 assert.ok(navigation.includes('favoriteLabel(saved,favorites.includes(id))'));
 assert.ok(navigation.includes('favoriteLabel(b,favorites.includes(id),true)'));
 assert.ok(navigation.includes('function favoriteLabel(target,selected,preview=false)'));
 assert.ok(!navigation.includes('makeNav("Menu","accueil","☰")'));
 assert.ok(!navigation.includes('const glyph=node("span",null,icon);'));
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot1.webp')"),'Lot 1 must stay unchanged');
});


test('lot 3: original ten-piece cinematic WebP atlas is valid and routed by the Worker',()=>{
 const atlas=readFileSync(new URL('../assets/ui-icons-lot3.webp',import.meta.url));
 assert.equal(atlas.subarray(0,4).toString(),'RIFF');
 assert.equal(atlas.subarray(8,12).toString(),'WEBP');
 assert.equal(atlas.subarray(12,16).toString(),'VP8X');
 assert.equal(atlas.readUIntLE(24,3)+1,560,'Lot 3 must contain ten full-width 56px sprites');
 assert.equal(atlas.readUIntLE(27,3)+1,56,'Sprite cells must remain square');
 assert.ok(atlas.byteLength<30000,'Do not load large artwork into the Mini App');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot3.webp')"));
 assert.ok(APP_HTML.includes('background-size:1000% 100%'));
 const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
 assert.ok(worker.includes('u.pathname==="/assets/ui-icons-lot3.webp"'));
 assert.ok(worker.includes('main/cinecanaux/assets/ui-icons-lot3.webp'));
 assert.ok(worker.includes('"content-type":"image/webp"'));
});

test('lot 3: category and genre controls use generated icons without placing them over posters',()=>{
 const names=['films','series','animes','action','romance','africain','vostfr','turc','drame','affiches'];
 assert.ok(navigation.includes('function cineCategoryIcon(key){'));
 assert.ok(navigation.includes('icon.setAttribute("aria-hidden","true")'));
 for(const name of names){
  assert.ok(APP_HTML.includes('.cine-cat-'+name+'{background-position-x:'),'Missing '+name+' image slot');
  assert.ok(navigation.includes('"'+name+'"'),'Category '+name+' not registered');
 }
 for(const name of names.slice(0,-1)){
  assert.ok(navigation.includes('["'+name+'",'),'Category '+name+' tile not configured');
 }
 assert.ok(navigation.includes('head.append(cineCategoryIcon(iconKey),node("strong",null,label))'));
 assert.ok(navigation.includes('b.onclick=()=>setFilter(query);grid.append(b);'));
 assert.ok(navigation.includes('showcaseLabel.append(cineCategoryIcon("affiches")'));
 const poster=navigation.slice(navigation.indexOf('function posterTile('),navigation.indexOf('function renderCinemaShowcase('));
 assert.ok(!poster.includes('cineCategoryIcon('),'Never cover a film poster with a category icon');
 assert.ok(!poster.includes('cineLot4Icon('),'Never cover a film poster with a glossy icon');
 assert.ok(!poster.includes('cine-poster-placeholder'),'Avoid unconditional foreground poster placeholders');
 assert.ok(!poster.includes('cine-pin-kind'),'Do not cover pinned artwork with category badges');
 assert.ok(poster.includes('img.onerror=()=>{img.remove();item.classList.add("cine-poster-fallback")}'),'Missing-image fallback must remain available');
 assert.ok(navigation.includes('chip.append(cineCategoryIcon(iconKey),document.createTextNode(title))'));
 assert.ok(!navigation.includes('emoji+" "+label'),'The category grid must not show the legacy emoji list');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot1.webp')"),'Do not regress the lot 1 atlas');
 assert.ok(navigation.includes('function cineNavIcon(key){'),'Do not regress lot 2 navigation');
});


test('lot 4: all ten verified transparent 3D icons ship as a compact WebP atlas',()=>{
 const atlas=readFileSync(new URL('../assets/ui-icons-lot4.webp',import.meta.url));
 assert.equal(atlas.subarray(0,4).toString(),'RIFF');
 assert.equal(atlas.subarray(8,12).toString(),'WEBP');
 assert.equal(atlas.subarray(12,16).toString(),'VP8X');
 assert.equal(atlas.readUIntLE(24,3)+1,560,'Ten 56px icons must occupy exactly one strip');
 assert.equal(atlas.readUIntLE(27,3)+1,56);
 assert.ok(atlas.byteLength<30000,'Do not make the Mini App heavier than necessary');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot4.webp')"));
 assert.ok(APP_HTML.includes('background-size:1000% 100%'));
 const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
 assert.ok(worker.includes('u.pathname==="/assets/ui-icons-lot4.webp"'));
 assert.ok(worker.includes('main/cinecanaux/assets/ui-icons-lot4.webp'));
 assert.ok(worker.includes('"content-type":"image/webp"'));
});

test('lot 4: the correct original icon is connected to each user action',()=>{
 const icons=['football','crypto','pronos','private','star','evaluate','play','series','thanks','popcorn'];
 for(const key of icons)assert.ok(APP_HTML.includes('.cine-lot4-'+key+'{background-position-x:'),key+' sprite location missing');
 for(const script of [directory,navigation]){
  assert.ok(script.includes('function cineLot4Icon(key){'));
  assert.ok(script.includes('el.setAttribute("aria-hidden","true")'));
 }
 assert.ok(directory.includes('cineLot4Icon("private")'),'Private channels must display the padlock icon');
 assert.ok(directory.includes('cineLot4Icon("star")'),'Reviews must display the actual rating star');
 assert.ok(!navigation.includes('cineLot4Icon(info.kind)'),'Promotions must not display an extra icon beside channel photos');
 assert.ok(navigation.includes('cineLot4Icon("evaluate")'),'Feedback invitation icon is absent');
 assert.ok(navigation.includes('cineLot4Icon("thanks")'),'Thank-you icon is absent');
 assert.ok(APP_HTML.includes('.cine-lot4-play{background-position-x:'),'Original play icon asset must remain available for future controls');
 assert.ok(APP_HTML.includes('.cine-lot4-series{background-position-x:'),'Original series icon asset must remain available for categories');
 assert.ok(!APP_HTML.includes('.cine-film-poster>.cine-lot4-play'),'Play icon should not cover pinned poster artwork');
 assert.ok(navigation.includes('cineLot4Icon("popcorn")'),'Cinema popcorn icon is absent');
 for(const key of ['football','crypto','pronos'])assert.ok(navigation.includes('kind:"'+key+'"'));
 assert.ok(navigation.includes('promoCard(info)'),'Promotion click handling must be preserved');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot1.webp')"),'Lot 1 must remain');
 assert.ok(APP_HTML.includes('function cineNavIcon(key){'),'Lot 2 must remain');
 assert.ok(APP_HTML.includes("background-image:url('/assets/ui-icons-lot3.webp')"),'Lot 3 must remain');
 assert.ok(APP_HTML.includes('function chooseCategory(chosen,exclusive=false){'),'Advanced filters must remain working');
 assert.ok(APP_HTML.includes('function autoScrollPromos()'),'The promotion carousel must remain working');
});
