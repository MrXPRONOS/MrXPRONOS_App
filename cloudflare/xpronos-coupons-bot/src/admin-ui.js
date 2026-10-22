// Secure graphical administration for Free Pronos Telegram Mini App.
// The caller identity MUST come from verified Telegram initData, never a client user_id.
import {calculateCoupon} from './logic.js';
import {normalizeSelection,getFixture,settleFromESPN,MARKETS} from './sports.js';
import {adminResult} from './features.js';
import {pendingTickets,replyToTicket} from './support.js';
export const isAdmin=(env,id)=>String(env.CF_BOT_ADMIN_IDS||'').split(',').some(s=>Number(s.trim())===id);
const json=(result,status=200)=>new Response(JSON.stringify(result),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const all=async(db,sql,...p)=>(await db.prepare(sql).bind(...p).all()).results||[];
const one=async(db,sql,...p)=>db.prepare(sql).bind(...p).first();
async function telegram(env,method,data){
 const response=await fetch('https://api.telegram.org/bot'+env.CF_BOT_TOKEN+'/'+method,
  {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(9000)});
 const body=await response.json();
 if(!response.ok||!body.ok)throw Error('Telegram HTTP '+response.status);
 return body.result;
}
async function bodyJson(req){
 if(Number(req.headers.get('content-length')||0)>12000)throw Error('Requête trop longue');
 const b=await req.json();if(!b||typeof b!=='object'||Array.isArray(b))throw Error('Corps JSON invalide');return b;
}
export async function createEnrichedCoupon(env,input,{lookup=getFixture}={}){
 const tier=String(input.tier||'').toUpperCase();
 const title=String(input.title||'').trim();
 const price=Number(input.xp_cost),stock=Number(input.stock);
 const date=new Date(input.expires_at);
 if(!['SIMPLE','PRO','VIP'].includes(tier)||title.length<3||title.length>120||!
   Number.isSafeInteger(price)||price<0||price>100000||!Number.isSafeInteger(stock)||stock< -1||stock>100000||!
   Number.isFinite(date.getTime())||date.getTime()<=Date.now()||date.getTime()>Date.now()+31*86400000)
   throw Error('Catégorie, titre, prix XP, stock ou échéance invalide.');
 if(!Array.isArray(input.selections)||input.selections.length<1||input.selections.length>5)
   throw Error('De 1 à 5 sélections par coupon.');
 const rows=[];const games=new Map();
 for(const raw of input.selections){
  const s=normalizeSelection(raw),key=[s.fixture.league,s.fixture.date,s.fixture.id].join('/');
  if(!games.has(key))games.set(key,await lookup(s.fixture));
  const g=games.get(key);
  if(g.completed)throw Error('Un match déjà terminé ne peut pas être ajouté.');
  rows.push({...s,match:g.home+' - '+g.away,competition:g.competition,home_logo:g.homeLogo,away_logo:g.awayLogo});
 }
 const odds=calculateCoupon(rows);
 const logos=[...games.values()].map(g=>({id:g.id,league:g.league,date:g.date,
   competition:g.competition,home:g.home,away:g.away,homeLogo:g.homeLogo,awayLogo:g.awayLogo}));
 const created=await one(env.DB,
   'INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,stock,competition,media_json,auto_settlement,provider) VALUES(?,?,?,?,?,?,?,?,?,1,?) RETURNING id',
   tier,title,JSON.stringify(rows),odds.total,price,date.toISOString(),stock,
   logos.map(g=>g.competition).filter((x,i,a)=>a.indexOf(x)===i).join(', ').slice(0,150),
   JSON.stringify({games:logos}),'espn');
 return {id:created.id,title,total_odds:odds.total,media:{games:logos}};
}
export async function adminApi(req,env,uid){
 if(!isAdmin(env,uid))return json({error:'admin_access_required'},403);
 const url=new URL(req.url);
 if(url.pathname==='/api/admin/overview'&&req.method==='GET'){
  const stats=await one(env.DB,"SELECT "+
   "(SELECT count(*) FROM users) AS users,(SELECT count(*) FROM users WHERE required_verified=1) AS verified,"+
   "(SELECT count(*) FROM coupons) AS coupons,(SELECT count(*) FROM redemptions) AS redemptions,"+
   "(SELECT count(*) FROM user_preferences WHERE notify_coupons=1) AS coupon_subscribers,"+
   "(SELECT count(*) FROM support_tickets WHERE status='open') AS open_tickets,"+
   "(SELECT count(*) FROM delivery_audit WHERE status='sent') AS alerts_sent");
  const coupons=await all(env.DB,"SELECT id,title,tier,total_odds,xp_cost,active,auto_settlement,result_status,expires_at,media_json FROM coupons ORDER BY id DESC LIMIT 40");
  return json({stats,coupons:coupons.map(c=>({...c,media:JSON.parse(c.media_json||'{}')})),markets:MARKETS});
 }
 if(url.pathname==='/api/admin/provider-check'&&req.method==='GET'){
  const day=new Date().toISOString().slice(0,10).replaceAll('-','');
  const upstream='https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates='+day;
  try{
   const response=await fetch(upstream,{headers:{accept:'application/json'},signal:AbortSignal.timeout(9000)});
   if(!response.ok)return json({provider:'ESPN soccer',state:'unavailable',http_status:response.status},503);
   const data=await response.json();
   if(!Array.isArray(data.events))return json({provider:'ESPN soccer',state:'invalid_response'},503);
   return json({provider:'ESPN soccer',state:'reachable',matches_for_today:data.events.length});
  }catch(error){return json({provider:'ESPN soccer',state:'unavailable',reason:String(error).slice(0,130)},503)}
 }
 if(url.pathname==='/api/admin/tickets'&&req.method==='GET')
  return json({tickets:await pendingTickets(env)});
 if(req.method!=='POST')return json({error:'method_not_allowed'},405);
 let data;try{data=await bodyJson(req)}catch(e){return json({error:String(e.message||e)},400)}
 if(url.pathname==='/api/admin/coupons/create'){
  try{return json({ok:true,coupon:await createEnrichedCoupon(env,data)},201)}
  catch(e){return json({error:String(e.message||e).slice(0,180)},400)}
 }
 if(url.pathname==='/api/admin/results'){
  const id=Number(data.coupon_id),status=String(data.status||''),source=String(data.source||'');
  const result=await adminResult(env,String(id)+' '+status+' '+source);
  return json(result,result.status==='ok'?200:400);
 }
 if(url.pathname==='/api/admin/tickets/reply'){
  const result=await replyToTicket(env,uid,data.ticket_id,data.message,telegram);
  return json(result,result.status==='ok'?200:400);
 }
 if(url.pathname==='/api/admin/test-alert'){
  try{
   const sent=await telegram(env,'sendMessage',{chat_id:uid,parse_mode:'HTML',
    text:'🔔 <b>FREE PRONOS · TEST DE NOTIFICATION</b>\n\n<blockquote>✅ Telegram a accepté cet envoi de contrôle.</blockquote>\n\n<i>Aucun coupon, solde XP ou pari n’a été modifié.</i>'});
   await env.DB.prepare("INSERT INTO delivery_audit(user_id,delivery_type,status,telegram_message_id) VALUES(?,'selftest','sent',?)")
     .bind(uid,sent?.message_id||null).run();
   return json({status:'sent',message_id:sent?.message_id});
  }catch(e){
   await env.DB.prepare("INSERT INTO delivery_audit(user_id,delivery_type,status,detail) VALUES(?,'selftest','failed',?)")
     .bind(uid,String(e).slice(0,160)).run();
   return json({status:'failed',error:'telegram_delivery_failed'},502);
  }
 }
 if(url.pathname==='/api/admin/settlement/run'){
  return json({status:'checked',report:await settleFromESPN(env,fetch,5)});
 }
 return json({error:'not_found'},404);
}
