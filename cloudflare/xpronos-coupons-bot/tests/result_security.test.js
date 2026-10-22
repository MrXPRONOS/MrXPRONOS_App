import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';

test('ancien bouton inline ne peut pas débloquer un coupon ayant un résultat validé',async()=>{
 const queries=[],sent=[],before=globalThis.fetch;
 globalThis.fetch=async(url,opts)=>{
  const m=String(url).split('/').at(-1);
  if(m==='sendMessage')sent.push(JSON.parse(opts.body));
  return new Response(JSON.stringify({ok:true,result:{message_id:12}}),{status:200,headers:{'content-type':'application/json'}});
 };
 const env={
  CF_BOT_TOKEN:'test',CF_BOT_WEBHOOK_SECRET:'securite',CF_BOT_ADMIN_IDS:'12000',
  CF_BOT_CHANNELS_JSON:'[]',
  DB:{prepare:(sql)=>{
    queries.push(sql);
    return {bind:()=>({
      async first(){
        if(sql.includes('processed_updates'))return {update_id:12345};
        if(sql.startsWith('SELECT * FROM users'))return {adult_confirmed:1,required_verified:1,xp:100};
        if(sql.includes('INSERT OR IGNORE INTO redemptions'))return null;
        if(sql.includes('SELECT 1 AS yes FROM redemptions'))return null;
        if(sql.startsWith('SELECT * FROM coupons'))return {id:1,active:1,stock:1,result_status:'won',expires_at:'2099-01-01T00:00:00Z'};
        return null;
      },
      async run(){return {meta:{changes:1}}}
    })}
  }}
 };
 try{
  const body={
    update_id:12345,
    callback_query:{id:'cb1',from:{id:12000,first_name:'Utilisateur'},
      data:'coupon:1',message:{message_id:11,chat:{id:12000,type:'private'}}}
  };
  const r=await worker.fetch(new Request('https://test.invalid/telegram',{
    method:'POST',headers:{'x-telegram-bot-api-secret-token':'securite','content-type':'application/json'},
    body:JSON.stringify(body)
  }),env);
  assert.equal(r.status,200);
  assert.ok(queries.some(sql=>sql.includes("c.result_status='available'")),'La requête SQL doit refuser un coupon terminé');
  assert.ok(sent.some(x=>x.text.includes('Coupon indisponible')),'Message correct pour un coupon terminé');
 }finally{globalThis.fetch=before}
});
