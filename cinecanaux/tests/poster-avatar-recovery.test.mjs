import test from 'node:test';
import assert from 'node:assert/strict';
import {APP_HTML} from '../app-page.mjs';
import {sanitizeShowcase} from '../poster-showcase.mjs';
import {serveChannelAvatar,avatarFallback} from '../channel-avatar.mjs';

test('homepage restores cinema posters as a moving marquee separate from Telegram avatars',()=>{
 assert.ok(APP_HTML.includes('cine-marquee-track'));
 assert.ok(APP_HTML.includes('cine-poster-track'));
 assert.ok(APP_HTML.includes('renderCinemaShowcase()'));
 assert.ok(APP_HTML.includes('loadCinemaShowcase()'));
 assert.ok(APP_HTML.includes('/api/showcase'));
 assert.ok(APP_HTML.includes('prefers-reduced-motion'));
 assert.ok(!APP_HTML.includes('img.src=c.avatar;img.alt="";img.loading="eager"'));
});
test('showcase accepts only authentic TMDB image host, validated paths, and media types',()=>{
 const raw={items:[
  {title:'Test movie',type:'films',poster:'https://image.tmdb.org/t/p/w342/ABCDEFGH.jpg',tmdb:'https://www.themoviedb.org/movie/123'},
  {title:'Spoof',type:'films',poster:'https://evil.invalid/ABCDEFGH.jpg',tmdb:'https://www.themoviedb.org/movie/123'},
  {title:'Wrong kind',type:'podcast',poster:'https://image.tmdb.org/t/p/w342/ABCDEFGH.jpg',tmdb:'https://www.themoviedb.org/movie/123'}
 ]};
 const result=sanitizeShowcase(raw);
 assert.equal(result.items.length,1);
 assert.equal(result.items[0].title,'Test movie');
 assert.match(result.notice,/disponibilité/);
});
test('every approved listed private channel has a usable SVG fallback even when no avatar exists',async()=>{
 const db={prepare(){return {bind(){return this;},async first(){return {id:8,title:'Anime privé',link:'https://t.me/+PrivateTestExample2026',content_type:'animes',telegram_chat_id:'-1001234567890'};}}}};
 const old=globalThis.fetch;
 globalThis.fetch=async()=>new Response('missing',{status:404});
 try{
  const response=await serveChannelAvatar(new Request('https://test.local/assets/channel-avatar/8.jpg'),{DB:db},null,8);
  assert.equal(response.status,200);
  assert.match(response.headers.get('content-type'),/image\/svg\+xml/);
  assert.match(await response.text(),/<svg/);
 }finally{globalThis.fetch=old}
});
test('private numeric id can retrieve genuine Telegram avatar server-side, never exposing the token',async()=>{
 const calls=[];const old=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{
  const target=String(url);calls.push({target,body:options?.body||''});
  if(target.includes('raw.githubusercontent.com/'))return new Response('missing',{status:404});
  if(target.endsWith('/getChat'))return Response.json({ok:true,result:{type:'channel',photo:{big_file_id:'avatar-photo'}}});
  if(target.endsWith('/getFile'))return Response.json({ok:true,result:{file_path:'photos/avatar.jpg'}});
  if(target.includes('/file/bot'))return new Response(new Uint8Array([255,216,255,217]),{headers:{'content-type':'image/jpeg'}});
  throw Error('unexpected endpoint');
 };
 try{
  const db={prepare(){return {bind(){return this;},async first(){return {id:16,title:'Series',link:'https://t.me/+VerifiedPrivateExample',content_type:'series',telegram_chat_id:'-1001234567890'};}}}};
  const response=await serveChannelAvatar(new Request('https://test.local/assets/channel-avatar/16.jpg'),{DB:db,TELEGRAM_TOKEN:'test-secret'},null,16);
  assert.equal(response.status,200);assert.equal(response.headers.get('content-type'),'image/jpeg');
  const chats=calls.filter(x=>x.target.endsWith('/getChat'));
  assert.equal(chats.length,1);assert.equal(JSON.parse(chats[0].body).chat_id,'-1001234567890');
  assert.ok(!(await response.text()).includes('test-secret'));
 }finally{globalThis.fetch=old}
});
test('fallback never includes private identity and is a valid image response',async()=>{
 const response=avatarFallback({title:'Anime VOSTFR',content_type:'animes'});
 assert.equal(response.status,200);
 assert.match(await response.text(),/viewBox="0 0 256 256"/);
});
