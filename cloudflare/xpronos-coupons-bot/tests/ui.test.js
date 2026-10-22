import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {MENU,referralCard,telegramShareUrl} from '../src/worker.js';

test('Boutons officiels bleu/vert et clavier de confirmation vert/rouge',()=>{
  const buttons=MENU.keyboard.flat();
  assert.ok(buttons.some(b=>b.style==='primary'));
  assert.ok(buttons.some(b=>b.style==='success'));
  assert.ok(buttons.every(b=>['primary','success','danger'].includes(b.style)));
});
test('Carte de parrainage riche, autonome et transférable',()=>{
  const url='https://t.me/FreePronos_mrxp_bot?start=ref_8099115334';
  const card=referralCard(url);
  assert.match(card,/<b>.*<\/b>/);
  assert.match(card,/<i>.*<\/i>/);
  assert.match(card,/<blockquote>[\s\S]*<\/blockquote>/);
  assert.ok(card.includes(url));
  assert.ok(!card.includes('Transfère'));
  assert.ok(!card.includes('Mon lien'));
  assert.ok(!card.includes('Mon portefeuille'));
});
test('Lien de partage Telegram conserve le parrainage dans URL',()=>{
  const ref='https://t.me/FreePronos_mrxp_bot?start=ref_8099115334';
  const url=new URL(telegramShareUrl(ref));
  assert.equal(url.origin,'https://t.me');
  assert.equal(url.pathname,'/share/url');
  assert.equal(url.searchParams.get('url'),ref);
  assert.match(url.searchParams.get('text'),/XPRONOS 4\+/);
});
test('La commande /share envoie une carte SANS clavier puis les instructions AVEC boutons colorés',async()=>{
  const oldFetch=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async(url,options)=>{
    const method=String(url).split('/').at(-1);
    calls.push({method,data:JSON.parse(options.body)});
    return new Response(JSON.stringify({ok:true,result:method==='getMe'?{username:'FreePronos_mrxp_bot'}:{message_id:100}}),{status:200,headers:{'content-type':'application/json'}});
  };
  const env={
    CF_BOT_TOKEN:'test',CF_BOT_WEBHOOK_SECRET:'secret',CF_BOT_ADMIN_IDS:'8099115334',
    CF_BOT_CHANNELS_JSON:'[{"id":"@canal","url":"https://t.me/canal"}]',
    DB:{prepare:()=>({bind:()=>({run:async()=>({meta:{changes:1}})})})}
  };
  try {
    const update={
      update_id:1234,
      message:{from:{id:8099115334,first_name:'Utilisateur'},chat:{id:8099115334,type:'private'},text:'/share'}
    };
    const result=await worker.fetch(new Request('https://example.invalid/telegram',{
      method:'POST',headers:{'content-type':'application/json','x-telegram-bot-api-secret-token':'secret'},
      body:JSON.stringify(update)
    }),env);
    assert.equal(result.status,200);
    const sends=calls.filter(c=>c.method==='sendMessage');
    assert.equal(sends.length,2);
    assert.equal(sends[0].data.parse_mode,'HTML');
    assert.equal(sends[0].data.reply_markup,undefined);
    assert.ok(sends[0].data.text.includes('<blockquote>'));
    assert.ok(sends[0].data.text.includes('start=ref_8099115334'));
    assert.equal(sends[1].data.parse_mode,'HTML');
    assert.match(sends[1].data.text,/Transfère le message précédent/);
    const keyboard=sends[1].data.reply_markup.inline_keyboard.flat();
    assert.ok(keyboard.some(b=>b.style==='success'&&b.url?.startsWith('https://t.me/share/url?')));
    assert.ok(keyboard.some(b=>b.style==='primary'&&b.copy_text?.text?.includes('ref_8099115334')));
  } finally {globalThis.fetch=oldFetch}
});
