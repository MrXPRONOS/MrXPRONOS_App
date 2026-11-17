import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {LINKS, PARTNER_LINKS, PROJECT_KNOWLEDGE} from '../index.js';

const root=(path)=>readFileSync(new URL('../../../../'+path,import.meta.url),'utf8');
const site=root('index.html'),pronos=root('pronos.html'),bonus=root('bonus.html');
const installer=root('installer.html'),catalogue=root('assets/js/bonus-catalogue.js');

test('site source contains the public code and public Pro/VIP confidence claim',()=>{
 assert.match(site,/XPVIP/);
 assert.match(bonus,/XPVIP/);
 assert.match(pronos,/79\s*%\s*de confiance estimée/i);
 assert.match(pronos,/Pro et VIP/i);
 assert.match(PROJECT_KNOWLEDGE.promo,/^XPVIP$/);
});
test('PWA installation is real and the official help page exists',()=>{
 assert.match(installer,/Installe gratuitement Mr XPRONOS/i);
 assert.match(installer,/pwa\.js/i);
 assert.match(LINKS.installer,/installer\.html$/);
});
test('published six social links match the bot whitelist',()=>{
 const links=[LINKS.instagram,LINKS.youtube,LINKS.facebook,LINKS.whatsapp,LINKS.threads,LINKS.channel];
 for(const url of links)assert.ok(site.includes(url),'Official site missing '+url);
});
test('partner links must match the repository catalogue, not be invented',()=>{
 for(const [bookmaker,url] of Object.entries(PARTNER_LINKS))
   assert.ok(catalogue.includes(url),'Missing catalogue URL for '+bookmaker);
});
