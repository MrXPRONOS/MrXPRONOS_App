import test from 'node:test';
import assert from 'node:assert/strict';
import {avatarFallback} from '../channel-avatar.mjs';
import {APP_HTML} from '../app-page.mjs';
test('fallback image never becomes stale in browser cache',()=>{
 const response=avatarFallback({title:'Cinéma',content_type:'films'});
 assert.equal(response.status,200);
 assert.equal(response.headers.get('cache-control'),'no-store');
 assert.equal(response.headers.get('x-cineradar-avatar'),'fallback');
});
test('failed real Telegram avatar is retried once before icon replacement',()=>{
 assert.ok(APP_HTML.includes('function showChannelImage('));
 assert.ok(APP_HTML.includes('candidates.push(source+"?refresh=1")'));
 assert.ok(APP_HTML.includes('showChannelImage(img,url,null,()=>'));
 assert.ok(APP_HTML.includes('showChannelImage(img,profilePhoto,p?.photo,()=>'));
 assert.ok(APP_HTML.includes('showChannelImage(img,directAvatar,c.photo,()=>'));
});
