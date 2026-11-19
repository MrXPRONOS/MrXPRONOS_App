import test from 'node:test';
import assert from 'node:assert/strict';
import {APP_HTML} from '../app-page.mjs';

const scripts=[...APP_HTML.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const nav=scripts.find(source=>source.includes('function posterTile('));
assert.ok(nav,'Poster rendering logic must be present');
const begin=nav.indexOf('function posterTile(entry,hero=false){');
const end=nav.indexOf('\nfunction renderCinemaShowcase(){',begin);
assert.ok(begin>=0&&end>begin,'Poster renderer boundaries missing');
const snippet=nav.slice(begin,end);

function makeNode(tag,cls,text){
 const names=new Set(cls?cls.split(/\s+/):[]);
 return {tag,cls:cls||'',textContent:text||'',children:[],removed:false,
  classList:{add(name){names.add(name)},contains(name){return names.has(name)}},
  append(...kids){this.children.push(...kids)},
  remove(){this.removed=true}
 };
}
const opened=[];
const posterTile=new Function('node','pinnedImage','pinnedLink','openPinnedMessage','posterTypeTitle',
 snippet+';return posterTile;')(
 makeNode,
 src=>/^\/assets\/pin-cover\/(films|series|animes)\/\d+\.jpg$/.test(src),
 href=>/^https:\/\/t\.me\/(CineXFilms_vf|seriesvf_cinex|CineXAnimeFR)\/\d+$/.test(href),
 entry=>opened.push(entry),
 {films:'Films',series:'Séries',animes:'Animés'}
);

function assertCleanArtwork(tile){
 assert.equal(tile.children.filter(x=>x.tag==='img').length,1,'Real poster artwork should be rendered');
 assert.equal(tile.children.filter(x=>x.tag==='span').length,1,'Only the caption is allowed over a real poster');
 assert.ok(!tile.children.some(x=>/placeholder|icon|pin-kind/.test(x.cls||'')),'No icon or category badge may cover artwork');
}

test('real pinned movie poster contains clean image and caption only',()=>{
 const entry={title:'Poster de film',type:'films',poster:'/assets/pin-cover/films/42.jpg',link:'https://t.me/CineXFilms_vf/42'};
 const tile=posterTile(entry,false);
 assert.equal(tile.tag,'button');
 assertCleanArtwork(tile);
 assert.equal(tile.children[0].src,entry.poster);
 assert.equal(tile.children[1].textContent,entry.title);
 tile.onclick();
 assert.deepEqual(opened,[entry],'Click must still open the actual Telegram post');
});

test('moving hero carousel poster has no floating 3D icon over the artwork',()=>{
 const entry={title:'Film du moment',type:'series',poster:'https://image.tmdb.org/t/p/w342/ABC123defG.jpg'};
 const tile=posterTile(entry,true);
 assert.equal(tile.tag,'div');
 assertCleanArtwork(tile);
 assert.equal(tile.children[0].src,entry.poster);
});

test('missing poster image remains a colored poster, not a giant icon',()=>{
 const missing={title:'Film sans affiche',type:'animes',poster:'',link:'https://t.me/CineXAnimeFR/18'};
 const tile=posterTile(missing,false);
 assert.equal(tile.children.length,1,'Without artwork, only the title should remain');
 assert.ok(tile.classList.contains('cine-poster-fallback'));
 assert.equal(tile.children[0].textContent,'Film sans affiche');
 const withError=posterTile({...missing,poster:'/assets/pin-cover/animes/18.jpg'},false);
 const img=withError.children[0];
 img.onerror();
 assert.equal(img.removed,true,'Broken cover should be removed');
 assert.ok(withError.classList.contains('cine-poster-fallback'));
});

test('poster code and CSS never overlay category, play or placeholder graphics',()=>{
 for(const token of ['cineLot4Icon(', 'cineCategoryIcon(', 'cine-poster-placeholder', 'cine-pin-kind']){
  assert.ok(!snippet.includes(token),'Over-poster graphic remains: '+token);
 }
 assert.ok(!APP_HTML.includes('.cine-film-poster>.cine-lot4-play'));
 assert.ok(APP_HTML.includes('.cine-film-poster.cine-poster-fallback{background:'));
 assert.ok(APP_HTML.includes('.cine-hero-cover.cine-poster-fallback{background:'));
 assert.ok(APP_HTML.includes('img.onerror=()=>{img.remove();item.classList.add("cine-poster-fallback")}'));
 assert.ok(APP_HTML.includes('function autoScrollPromos()'),'Promotion movement must be preserved');
 assert.ok(APP_HTML.includes('function chooseCategory(chosen,exclusive=false){'),'Advanced filters must remain working');
});
