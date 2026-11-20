import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {generateKeyPairSync,sign} from 'node:crypto';
import {verifiedIdentity,telegramAuthStatus} from '../v2.mjs';

const prod='e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d';
const original=readFileSync(new URL('../v2.mjs',import.meta.url),'utf8');
test('Telegram Ed25519 fallback must use official production key and server configured bot ID',()=>{
 assert.ok(original.includes('const TELEGRAM_PRODUCTION_ED25519_KEY="'+prod+'"'));
 assert.ok(original.includes('const id=String(env.TELEGRAM_TOKEN||"").split(":")[0]'));
 assert.ok(original.includes('if(!equalHex(hash.toLowerCase(),signedHash)&&!await signedByTelegramForConfiguredBot(params,env))return null'));
});

test('valid Telegram Ed25519 data can authenticate even if HMAC is different, but never for another bot',async()=>{
 const {publicKey,privateKey}=generateKeyPairSync('ed25519');
 const publicRaw=publicKey.export({type:'spki',format:'der'}).subarray(-32).toString('hex');
 // Replace the official key only in this in-memory test module. Production
 // always uses the hard-coded trusted Telegram production public key.
 const source=original.replace('const TELEGRAM_PRODUCTION_ED25519_KEY="'+prod+'"',
  'const TELEGRAM_PRODUCTION_ED25519_KEY="'+publicRaw+'"');
 const fixture=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const user=JSON.stringify({id:987654321,username:'mr_xpronos',first_name:'Owner'});
 const params=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),user,hash:'0'.repeat(64)});
 const fields=Array.from(params.entries()).filter(([key])=>key!=='hash')
  .sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>k+'='+v).join('\n');
 const signature=sign(null,Buffer.from('123456:WebAppData\n'+fields),privateKey).toString('base64url');
 params.set('signature',signature);
 const make=(token,p=params)=>new Request('https://example.test/api/admin/access',{headers:{'X-Telegram-Init-Data':p.toString()}});
 const env={TELEGRAM_TOKEN:'123456:some-wrong-hmac-token',TELEGRAM_WEBHOOK_SECRET:'private_webhook_secret'};
 assert.equal(await fixture.telegramAuthStatus(make(env.TELEGRAM_TOKEN),env),'verified');
 assert.equal((await fixture.verifiedIdentity(make(env.TELEGRAM_TOKEN),env)).telegram_id,987654321);
 const mismatched={...env,TELEGRAM_TOKEN:'777777:some-wrong-hmac-token'};
 assert.equal(await fixture.telegramAuthStatus(make(mismatched.TELEGRAM_TOKEN),mismatched),'invalid_signature');
 assert.equal(await fixture.verifiedIdentity(make(mismatched.TELEGRAM_TOKEN),mismatched),null);
 const altered=new URLSearchParams(params);altered.set('user',JSON.stringify({id:123,username:'mr_xpronos'}));
 assert.equal(await fixture.verifiedIdentity(make(env.TELEGRAM_TOKEN,altered),env),null);
 const without=new URLSearchParams(params);without.delete('signature');
 assert.equal(await fixture.verifiedIdentity(make(env.TELEGRAM_TOKEN,without),env),null);
});
