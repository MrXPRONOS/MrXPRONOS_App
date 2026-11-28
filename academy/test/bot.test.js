import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {membershipEvent,validateDue,autoReward,handleWebhook,internals,formatTelegram,tg} from '../src/bot.js';
function setup(){
 const sql=new DatabaseSync(':memory:');sql.exec(readFileSync(new URL('../migrations/0001_init.sql',import.meta.url),'utf8'));sql.exec(readFileSync(new URL('../migrations/0002_catalog.sql',import.meta.url),'utf8'));
 const make=(q,args=[])=>({bind:(...a)=>make(q,a),first:async()=>sql.prepare(q).get(...args)||null,all:async()=>({results:sql.prepare(q).all(...args)}),run:async()=>({meta:{changes:Number(sql.prepare(q).run(...args).changes)}}),_run:()=>sql.prepare(q).run(...args)});
 const DB={prepare:make,batch:async ss=>{sql.exec('BEGIN');try{const r=ss.map(s=>s._run());sql.exec('COMMIT');return r;}catch(e){sql.exec('ROLLBACK');throw e;}}};
 sql.exec(`UPDATE products SET active=1,file_id='file123'; INSERT INTO users VALUES ('1',0),('2',0); INSERT INTO campaigns VALUES ('mc','masterclass','-10012345','https://t.me/testchan',10,86400,1); INSERT INTO links VALUES ('mc','1','https://t.me/+test','-10012345',0);`);
 const env={DB,FILES:{get:async()=>null,head:async()=>null},BOT_TOKEN:'test',WEBHOOK_SECRET:'secret',ADMIN_IDS:'1'};
 return {sql,env};
}
const n=()=>Math.floor(Date.now()/1000);
function ev(user,opts={}){return {update_id:opts.uid||100+Number(user),chat_member:{chat:{id:opts.channel||-10012345},date:opts.at||n()-90000,old_chat_member:{status:opts.old||'left'},new_chat_member:{status:opts.status||'member',user:{id:Number(user),is_bot:opts.bot||false}},...(opts.link===null?{}:{invite_link:{invite_link:opts.link||'https://t.me/+test'}})}};}
function withTelegram(t,fn){const original=globalThis.fetch;globalThis.fetch=async(url,options)=>{const method=url.split('/').at(-1);const body=options.body instanceof FormData?options.body:JSON.parse(options.body);const val=fn(method,body);return Response.json({ok:true,result:val??{}});};t.after(()=>{globalThis.fetch=original;});}
const count=(sql,table)=>Number(sql.prepare(`SELECT COUNT(*) n FROM ${table}`).get().n);
test('Telegram member semantics and input validation',()=>{assert.equal(internals.member({status:'restricted',is_member:false}),false);assert.equal(internals.member({status:'restricted',is_member:true}),true);assert.equal(internals.member({status:'administrator'}),true);assert.equal(internals.validChannel('-10012345'),true);assert.equal(internals.validJoinURL('https://evil.invalid'),false);assert.equal(internals.slug('a:x'),false);});
test('only genuine first join via exact link counts; self, bot, wrong channel and repeats excluded',async()=>{const {sql,env}=setup();for(const x of [ev(1),ev(3,{bot:true}),ev(4,{channel:-10099999}),ev(5,{link:'https://t.me/+other'}),ev(5),ev(6),ev(6)])await membershipEvent(env,x);assert.equal(count(sql,'referrals'),1);assert.equal(sql.prepare('SELECT invitee_id FROM referrals').get().invitee_id,'6');});
test('leaving before validation rejects permanently, even if rejoining',async()=>{const {sql,env}=setup();await membershipEvent(env,ev(7,{uid:1}));await membershipEvent(env,ev(7,{old:'member',status:'left',uid:2,at:n()-80000}));await membershipEvent(env,ev(7,{uid:3,at:n()-70000}));assert.equal(sql.prepare('SELECT state FROM referrals').get().state,'rejected');});
test('older leave event does not undo newer state',async()=>{const {sql,env}=setup();await membershipEvent(env,ev(7,{uid:2,at:n()-80000}));await membershipEvent(env,ev(7,{uid:1,old:'member',status:'left',at:n()-90000}));assert.equal(sql.prepare('SELECT state FROM referrals').get().state,'pending');});
test('retention window enforced and validation uses live membership',async t=>{const {sql,env}=setup();withTelegram(t,(_m,b)=>({status:b.user_id===7?'left':'member'}));await membershipEvent(env,ev(7));await membershipEvent(env,ev(8));await membershipEvent(env,ev(9,{at:n()-100}));await validateDue(env);assert.deepEqual(sql.prepare('SELECT invitee_id,state FROM referrals ORDER BY invitee_id').all().map(x=>[x.invitee_id,x.state]),[['7','rejected'],['8','valid'],['9','pending']]);});
test('nine invitations cannot unlock and ten unlock once with private delivery',async t=>{const {sql,env}=setup();let sent=0;withTelegram(t,(method)=>{if(method==='getChatMember')return {status:'member'};if(method==='sendDocument'){sent++;return {document:{file_id:'file123'}};}return {};});for(let i=10;i<19;i++)await membershipEvent(env,ev(i));await validateDue(env);await internals.claim(env,'1','mc');assert.equal(count(sql,'entitlements'),0);await membershipEvent(env,ev(19));await validateDue(env);await internals.claim(env,'1','mc');assert.equal(count(sql,'entitlements'),1);assert.equal(sent,1);await internals.claim(env,'1','mc');assert.equal(count(sql,'entitlements'),1);assert.equal(count(sql,'deliveries'),1);});
test('automatic reward after threshold works and does not duplicate entitlement',async t=>{const {sql,env}=setup();let sent=0;withTelegram(t,m=>{if(m==='getChatMember')return {status:'member'};if(m==='sendDocument')sent++;return {};});for(let i=20;i<30;i++)await membershipEvent(env,ev(i));await validateDue(env);assert.equal(await autoReward(env),true);assert.equal(await autoReward(env),false);assert.equal(sent,1);assert.equal(count(sql,'entitlements'),1);});
test('direct premium callback without entitlement denied, free PDF works',async t=>{const {sql,env}=setup();let sent=0;withTelegram(t,m=>{if(m==='sendDocument')sent++;return {};});await internals.sendPDF(env,'2','masterclass');assert.equal(sent,0);await internals.sendPDF(env,'2','fondamentaux');assert.equal(sent,1);assert.equal(count(sql,'entitlements'),1);});
test('same Telegram update replay is ignored; wrong secret denied',async t=>{const {env}=setup();let sent=0;withTelegram(t,m=>{if(m==='sendMessage')sent++;return {};});const data={update_id:4,message:{chat:{id:2,type:'private'},from:{id:2},text:'/id'}};const req=secret=>new Request('https://test/telegram/webhook',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':secret},body:JSON.stringify(data)});assert.equal((await handleWebhook(req('bad'),env)).status,403);assert.equal((await handleWebhook(req('secret'),env)).status,200);assert.equal((await handleWebhook(req('secret'),env)).status,200);assert.equal(sent,1);});
test('non administrator cannot grant a product',async t=>{const {sql,env}=setup();withTelegram(t,()=>({}));await internals.dispatch(env,{message:{chat:{id:2,type:'private'},from:{id:2},text:'/grant 2 masterclass'}});assert.equal(count(sql,'entitlements'),0);});
test('multiple campaign links on same channel cannot credit one account twice',async()=>{const {sql,env}=setup();sql.exec("INSERT INTO campaigns VALUES ('other','masterclass','-10012345','https://t.me/testchan',5,0,1); INSERT INTO links VALUES ('other','2','https://t.me/+other','-10012345',0)");await membershipEvent(env,ev(31));await membershipEvent(env,ev(31,{link:'https://t.me/+other',uid:200}));assert.equal(count(sql,'referrals'),1);});

test('allowlisted private storage imports a PDF; other channels cannot replace it',async t=>{const {sql,env}=setup();env.STORAGE_CHANNEL_ID='-100987654';withTelegram(t,()=>({}));const post=(chat,f)=>({channel_post:{chat:{id:chat,type:'channel'},caption:'/file masterclass',document:{mime_type:'application/pdf',file_id:f,file_size:123,file_name:'Masterclass.pdf'}}});await internals.dispatch(env,post(-100987654,'new_pdf'));assert.equal(sql.prepare("SELECT file_id FROM products WHERE id='masterclass'").get().file_id,'new_pdf');await internals.dispatch(env,post(-100777777,'bad_pdf'));assert.equal(sql.prepare("SELECT file_id FROM products WHERE id='masterclass'").get().file_id,'new_pdf');});
test('private storage imports the welcome photo only from its allowlisted channel',async t=>{const {sql,env}=setup();env.STORAGE_CHANNEL_ID='-100987654';withTelegram(t,()=>({}));await internals.dispatch(env,{channel_post:{chat:{id:-100987654,type:'channel'},caption:'/banner',photo:[{file_id:'banner'}]}});assert.equal(sql.prepare("SELECT value FROM settings WHERE key='welcome_file_id'").get().value,'banner');});
test('free PDF remains shareable while premium is protected',async t=>{const {env}=setup();let protections=[];withTelegram(t,(m,b)=>{if(m==='sendDocument')protections.push(b.protect_content);return {};});await internals.sendPDF(env,'2','fondamentaux');await internals.dispatch(env,{message:{chat:{id:1,type:'private'},from:{id:1},text:'/grant 2 masterclass'}});await internals.sendPDF(env,'2','masterclass');assert.deepEqual(protections,[false,true]);});


test('guided admin creates a draft, skips description, archives files, publishes and edits in place',async t=>{
 const {sql,env}=setup();env.STORAGE_CHANNEL_ID='-100987654';const calls=[];withTelegram(t,(method,body)=>{calls.push({method,body});return {message_id:1};});
 const msg=(text,more={},user=1)=>internals.dispatch(env,{message:{chat:{id:user,type:'private'},from:{id:user},...(text==null?{}:{text}),...more}});
 const click=(data,user=1)=>internals.dispatch(env,{callback_query:{id:'cb',from:{id:user},message:{chat:{id:user,type:'private'}},data}});
 const state=()=>internals.wizRead(env,'1');const act=async a=>{const d=await state();return click('aw:'+d.session+':'+d.step+':'+a);};
 await click('aw:new',2);assert.equal(await state(),null);
 await click('aw:new');await msg('Guide business');await act('cat0');await msg('invalid');assert.equal((await state()).step,'price');
 await msg('5000');await msg('0');assert.equal((await state()).description,'');
 await msg(null,{photo:[{file_id:'cover'}]});assert.ok(calls.some(x=>x.method==='sendPhoto'&&x.body.chat_id===env.STORAGE_CHANNEL_ID));
 await click('aw:menu');await msg('unrelated');assert.equal((await state()).paused,true);await click('aw:resume');
 await msg(null,{document:{file_id:'bad',mime_type:'text/plain'}});assert.equal((await state()).step,'pdf');
 await msg(null,{document:{file_id:'pdf',mime_type:'application/pdf',file_name:'guide.pdf'}});
 assert.ok(calls.some(x=>x.method==='sendDocument'&&x.body.chat_id===env.STORAGE_CHANNEL_ID));
 await act('skip');await act('keep_campaign');const d=await state();assert.equal(d.step,'review');await act('draft');
 assert.equal(sql.prepare('SELECT active FROM products WHERE id=?').get(d.id).active,0);
 await click('aw:'+d.session+':review:publish');assert.equal(sql.prepare('SELECT active FROM products WHERE id=?').get(d.id).active,0);
 await click('aw:show:'+d.id);assert.equal(sql.prepare('SELECT active FROM products WHERE id=?').get(d.id).active,1);
 await click('aw:edit:'+d.id);for(let j=0;j<6;j++)await act('keep');await act('skip');await act('keep_campaign');await act('publish');
 assert.equal(sql.prepare('SELECT file_id FROM products WHERE id=?').get(d.id).file_id,'pdf');
 assert.equal(count(sql,'products'),3);
 await click('aw:new');await act('cancel');assert.equal(await state(),null);
});


test('premium wizard verifies a private channel and creates an entry link and campaign',async t=>{
 const {sql,env}=setup();env.STORAGE_CHANNEL_ID='-100987654';let canInvite=true;const calls=[];
 withTelegram(t,(method,body)=>{calls.push({method,body});if(method==='getChat')return {id:Number(body.chat_id),type:'channel',title:'Privé'};if(method==='getMe')return {id:99,username:'AcademyTestBot'};if(method==='getChatMember')return {status:'administrator',can_invite_users:canInvite};if(method==='createChatInviteLink')return {invite_link:'https://t.me/+private-entry'};return {};});
 const msg=(text,more={})=>internals.dispatch(env,{message:{chat:{id:1,type:'private'},from:{id:1},...(text==null?{}:{text}),...more}});
 const click=data=>internals.dispatch(env,{callback_query:{id:'cb',from:{id:1},message:{chat:{id:1,type:'private'}},data}});
 const state=()=>internals.wizRead(env,'1');const act=async a=>{const d=await state();return click('aw:'+d.session+':'+d.step+':'+a);};
 await click('aw:new');await msg('Guide premium');await act('cat0');await msg('5000');await msg('0');
 await msg(null,{photo:[{file_id:'cover'}]});await msg(null,{document:{file_id:'pdf',mime_type:'application/pdf',file_name:'guide.pdf'}});
 await msg('http://example.com');assert.equal((await state()).step,'shop');await msg('https://example.com/guide');
 await act('new_campaign');await act('private');await act('picker');
 const picker=calls.at(-1).body.reply_markup.keyboard[0][0].request_chat;
 await msg('https://t.me/+opaque');assert.equal((await state()).step,'channel');
 await msg(env.STORAGE_CHANNEL_ID);assert.equal((await state()).step,'channel');
 canInvite=false;await msg('-100777');assert.equal((await state()).step,'channel');canInvite=true;
 await msg(null,{chat_shared:{request_id:picker.request_id,chat_id:-100777}});assert.equal((await state()).step,'target');
 await msg('21');assert.equal((await state()).step,'target');await act('n10');await act('h24');
 const d=await state();canInvite=false;await act('publish');assert.equal(sql.prepare('SELECT id FROM products WHERE id=?').get(d.id),undefined);canInvite=true;await act('publish');
 const camp=sql.prepare('SELECT * FROM campaigns WHERE product_id=?').get(d.id);
 assert.equal(camp.channel_id,'-100777');assert.equal(camp.target,10);assert.equal(camp.hold_seconds,86400);assert.equal(camp.channel_url,'https://t.me/+private-entry');
 assert.equal(sql.prepare('SELECT value FROM settings WHERE key=?').get('product_shop:'+d.id).value,'https://example.com/guide');
});


test('formatting uses safe UTF-16 entities for emoji and literal special characters',()=>{
 const s='🎓 Bienvenue dans MR X ACADEMY !\n\nVotre espace pour apprendre.\n\nApprendre. Appliquer. Réussir.\n\nChoisissez une rubrique :';
 const e=formatTelegram(s,'welcome'),has=(type,word)=>e.some(x=>x.type===type&&s.slice(x.offset,x.offset+x.length)===word);
 assert.ok(has('bold','🎓 Bienvenue dans MR X ACADEMY !'));assert.ok(has('italic','Votre espace pour apprendre.'));assert.ok(has('blockquote','Apprendre. Appliquer. Réussir.'));assert.ok(has('underline','Choisissez une rubrique :'));
 const raw='Livre <b> & _ * [test] 📚\nFinance\n\n💰 Prix : 5 000 FCFA';
 const f=formatTelegram(raw,'product');assert.equal(raw.slice(f[0].offset,f[0].offset+f[0].length),'Livre <b> & _ * [test] 📚');
 for(const [txt,items] of [[s,e],[raw,f]])assert.ok(items.every((x,i)=>x.length>0&&x.offset>=0&&x.offset+x.length<=txt.length&&(!i||items[i-1].offset+items[i-1].length<=x.offset)));
});
test('Telegram message and caption formatting preserve original text and protection',async t=>{
 const {env}=setup();let last;withTelegram(t,(_m,b)=>{last=b;return {};});
 const text='🎓 Guide & <test>\n\nApprendre. Appliquer. Réussir.';
 await tg(env,'sendMessage',{chat_id:'1',text});assert.equal(last.text,text);assert.ok(last.entities.some(x=>x.type==='blockquote'));assert.equal(last.parse_mode,undefined);
 await tg(env,'sendDocument',{chat_id:'1',document:'file123',caption:text,protect_content:true});assert.equal(last.caption,text);assert.ok(last.caption_entities.length);assert.equal(last.protect_content,true);
});
