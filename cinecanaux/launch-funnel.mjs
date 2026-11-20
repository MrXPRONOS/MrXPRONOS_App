// Privacy-preserving bot → Mini App launch funnel.
// A salted, domain-separated hash associates a Telegram /start with a
// signed Mini App open. No raw Telegram IDs, usernames or messages are stored.
import {verifiedIdentity} from './v2.mjs';

const enc=new TextEncoder();
const hex=bytes=>Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
const tablePromises=new WeakMap();
async function ensureTable(env){
 if(!env.DB)throw Error('D1 unavailable');
 let pending=tablePromises.get(env.DB);
 if(!pending){
  pending=env.DB.prepare("CREATE TABLE IF NOT EXISTS cine_bot_launch_funnel (visitor_hash TEXT PRIMARY KEY,first_start_at TEXT,last_start_at TEXT,starts INTEGER NOT NULL DEFAULT 0,first_launch_at TEXT,last_launch_at TEXT,launches INTEGER NOT NULL DEFAULT 0)")
   .run().catch(error=>{tablePromises.delete(env.DB);throw error});
  tablePromises.set(env.DB,pending);
 }
 return pending;
}
async function identityHash(env,telegramId){
 if(!env.TELEGRAM_WEBHOOK_SECRET||!Number.isSafeInteger(telegramId)||telegramId<=0)
  throw Error('Invalid Telegram identity');
 return hex(await crypto.subtle.digest('SHA-256',enc.encode('cine-radar-funnel:v1:'+env.TELEGRAM_WEBHOOK_SECRET+':'+telegramId)));
}
export async function recordBotStartFunnel(env,update){
 const msg=update?.message,from=msg?.from;
 if(msg?.chat?.type!=='private'||msg?.chat?.id!==from?.id||!Number.isSafeInteger(from?.id))return false;
 if(!/^\/start(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(String(msg?.text||'')))return false;
 const hash=await identityHash(env,from.id);
 await ensureTable(env);
 await env.DB.prepare("INSERT INTO cine_bot_launch_funnel(visitor_hash,first_start_at,last_start_at,starts) VALUES(?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1) ON CONFLICT(visitor_hash) DO UPDATE SET last_start_at=CURRENT_TIMESTAMP,starts=starts+1").bind(hash).run();
 return true;
}
export async function recordSignedAppLaunch(env,request){
 if(request.method!=='POST')return Response.json({error:'Method not allowed'},{status:405});
 const url=new URL(request.url);
 const origin=request.headers.get('origin');
 if(origin&&origin!==url.origin)return Response.json({error:'Invalid origin'},{status:403});
 const signed=await verifiedIdentity(request,env);
 if(!signed?.telegram_id)return Response.json({error:'Telegram authentication required'},{status:403,headers:{'cache-control':'no-store'}});
 const hash=await identityHash(env,signed.telegram_id);
 await ensureTable(env);
 await env.DB.prepare("INSERT INTO cine_bot_launch_funnel(visitor_hash,first_launch_at,last_launch_at,launches) VALUES(?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1) ON CONFLICT(visitor_hash) DO UPDATE SET last_launch_at=CURRENT_TIMESTAMP,launches=launches+1").bind(hash).run();
 return Response.json({ok:true},{headers:{'cache-control':'no-store'}});
}
export async function launchFunnelStats(env){
 await ensureTable(env);
 const result=await env.DB.prepare("SELECT COUNT(CASE WHEN first_start_at IS NOT NULL THEN 1 END) AS started,COUNT(CASE WHEN first_start_at IS NOT NULL AND first_launch_at IS NOT NULL THEN 1 END) AS started_and_launched,COUNT(CASE WHEN first_start_at IS NOT NULL AND first_launch_at IS NULL THEN 1 END) AS started_without_launch,COUNT(CASE WHEN first_launch_at IS NOT NULL THEN 1 END) AS total_launch_users,COALESCE(SUM(starts),0) AS start_commands,COALESCE(SUM(launches),0) AS app_opens FROM cine_bot_launch_funnel").first();
 const n=k=>Math.max(0,Number(result?.[k]||0));
 return {
  since:'activation',
  started_users:n('started'),
  launched_after_start:n('started_and_launched'),
  started_without_launch:n('started_without_launch'),
  total_telegram_launch_users:n('total_launch_users'),
  start_commands:n('start_commands'),
  signed_app_opens:n('app_opens'),
  note:'Nouveaux comptes suivis depuis l’activation. Les visites anonymes ou hors Telegram ne peuvent pas être liées à un démarrage du bot.'
 };
}
