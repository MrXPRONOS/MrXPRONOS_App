// Free Pronos Telegram Mini App: trusted, signed initData only.
import {summary,periodKey} from './features.js';
const enc=new TextEncoder();
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{
  'content-type':'application/json; charset=utf-8','cache-control':'no-store',
  'x-content-type-options':'nosniff','referrer-policy':'no-referrer'}});
export async function authenticateInitData(raw,botToken,nowSeconds=Math.floor(Date.now()/1000)){
  if(typeof raw!=='string'||raw.length>8192||!botToken)return null;
  const params=new URLSearchParams(raw),hash=params.get('hash');
  if(!hash||!/^[a-f0-9]{64}$/i.test(hash)||params.getAll('hash').length!==1)return null;
  const t=Number(params.get('auth_date'));
  if(!Number.isSafeInteger(t)||t>nowSeconds+60||nowSeconds-t>86400)return null;
  let user;
  try{user=JSON.parse(params.get('user')||'null')}catch{return null}
  if(!user||!Number.isSafeInteger(user.id)||user.id<1)return null;
  // HMAC_SHA256(HMAC_SHA256(botToken, key=WebAppData), canonicalData).
  const key1=await crypto.subtle.importKey('raw',enc.encode('WebAppData'),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const bytes=await crypto.subtle.sign('HMAC',key1,enc.encode(botToken));
  const key2=await crypto.subtle.importKey('raw',bytes,{name:'HMAC',hash:'SHA-256'},false,['sign']);
  params.delete('hash');
  const message=[...params.entries()].map(([k,v])=>k+'='+v).sort().join('\n');
  const calculated=new Uint8Array(await crypto.subtle.sign('HMAC',key2,enc.encode(message)));
  const supplied=Uint8Array.from(hash.match(/../g).map(x=>parseInt(x,16)));
  let mismatch=0;for(let i=0;i<calculated.length;i++)mismatch|=calculated[i]^supplied[i];
  return mismatch===0?{userId:user.id}:null;
}
const query=async(env,sql,...args)=>(await env.DB.prepare(sql).bind(...args).all()).results||[];
export async function miniApi(request,env){
  if(request.method!=='GET'&&request.method!=='POST')return json({error:'method_not_allowed'},405);
  const header=request.headers.get('authorization')||'';
  if(!header.startsWith('tma '))return json({error:'telegram_auth_required'},401);
  const verified=await authenticateInitData(header.slice(4),env.CF_BOT_TOKEN);
  if(!verified)return json({error:'invalid_or_expired_telegram_session'},401);
  const id=verified.userId,url=new URL(request.url);
  const me=await summary(env,id);
  if(!me)return json({error:'start_bot_first'},403);
  if(!me.adult)return json({error:'adult_confirmation_required'},403);
  if(url.pathname==='/api/me'&&request.method==='GET'){
    const p=await env.DB.prepare('SELECT notify_coupons,notify_results FROM user_preferences WHERE user_id=?').bind(id).first();
    return json({me,alerts:{coupons:!!p?.notify_coupons,results:!!p?.notify_results}});
  }
  if(!me.verified)return json({error:'channel_verification_required'},403);
  if(url.pathname==='/api/coupons'&&request.method==='GET'){
    const tier=url.searchParams.get('category')||'ALL';
    if(!['ALL','SIMPLE','PRO','VIP'].includes(tier))return json({error:'invalid_category'},400);
    const rows=await query(env,
      "SELECT id,title,tier,total_odds,xp_cost,stock,expires_at FROM coupons WHERE active=1 AND result_status='available' AND stock<>0 AND expires_at>?"+
      (tier==='ALL'?'':' AND tier=?')+" ORDER BY created_at DESC,id DESC LIMIT 50",
      ...[new Date().toISOString(),...(tier==='ALL'?[]:[tier])]);
    return json({coupons:rows});
  }
  if(url.pathname==='/api/tasks'&&request.method==='GET'){
    const [tasks,claims]=await Promise.all([
      query(env,'SELECT t.id,t.chat_id,t.url,t.xp FROM tasks t WHERE t.active=1 AND NOT EXISTS(SELECT 1 FROM task_claims c WHERE c.task_id=t.id AND c.user_id=?) ORDER BY t.id DESC LIMIT 30',id),
      query(env,'SELECT kind,period_key,claimed_at FROM engagement_claims WHERE user_id=? ORDER BY claimed_at DESC LIMIT 30',id)
    ]);
    return json({tasks,claims,dailyKey:periodKey('daily'),weeklyKey:periodKey('weekly')});
  }
  if(url.pathname==='/api/history'&&request.method==='GET'){
    const [ledger,coupons,referrals]=await Promise.all([
      query(env,'SELECT delta,reason,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 30',id),
      query(env,'SELECT r.coupon_id,r.claimed_at,r.xp_spent,c.title,c.tier,c.total_odds,c.result_status FROM redemptions r JOIN coupons c ON c.id=r.coupon_id WHERE r.user_id=? ORDER BY r.claimed_at DESC LIMIT 20',id),
      query(env,'SELECT name,referral_rewarded,created_at FROM users WHERE referred_by=? ORDER BY created_at DESC LIMIT 20',id)
    ]);
    return json({ledger,coupons,referrals});
  }
  if(url.pathname==='/api/results'&&request.method==='GET'){
    const rows=await query(env,"SELECT id,title,tier,result_status,result_reviewed_at,result_source FROM coupons WHERE result_status IN ('live','won','lost','void') ORDER BY coalesce(result_reviewed_at,created_at) DESC LIMIT 30");
    return json({results:rows});
  }
  if(url.pathname==='/api/alerts'&&request.method==='POST'){
    if(Number(request.headers.get('content-length')||0)>1024)return json({error:'too_large'},413);
    let preferences;
    try{preferences=await request.json()}catch{return json({error:'invalid_json'},400)}
    if(!preferences||typeof preferences.coupons!=='boolean'||typeof preferences.results!=='boolean')
      return json({error:'invalid_preferences'},400);
    await env.DB.prepare("INSERT INTO user_preferences(user_id,notify_coupons,notify_results) VALUES(?,?,?) "+
      "ON CONFLICT(user_id) DO UPDATE SET notify_coupons=excluded.notify_coupons,notify_results=excluded.notify_results,"+
      "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')").bind(id,preferences.coupons?1:0,preferences.results?1:0).run();
    return json({ok:true,alerts:{coupons:preferences.coupons,results:preferences.results}});
  }
  return json({error:'not_found'},404);
}
