// Dedicated, authenticated Neon data transport for the EXISTING API-Football
// hourly collector. NO prediction rule, score, threshold or provider quota lives here.
import { timingSafeEqual } from "node:crypto";
import { createClient } from "./_neon_db.ts";
const db=createClient("neon-compat","service");
const JSON_HEADERS={"content-type":"application/json","cache-control":"no-store"};
function response(body:any,status=200){return new Response(JSON.stringify(body),{status,headers:JSON_HEADERS})}
function authorized(got:string|null):boolean{
 const expected=process.env.CRON_SECRET||"";
 if(!expected||!got)return false;
 const a=Buffer.from(got),b=Buffer.from(expected);
 return a.length===b.length&&timingSafeEqual(a,b);
}
function iso(value:any){const t=Date.parse(String(value||""));return Number.isFinite(t)?t:null}
const MINUTE=60_000;
const STATS_FIELDS=["corner_kicks","total_shots","fouls"];
const VALUE_FIELDS=["corner_kicks","total_shots","fouls","shots_on_target","shots_off_target","attacks","dangerous_attacks","yellow_cards","red_cards","ball_possession"];
function realCorePair(stats:any):boolean{
 return STATS_FIELDS.some(k=>{
  const a=stats?.home?.[k],b=stats?.away?.[k];
  return typeof a==="number"&&Number.isFinite(a)&&a>=0&&
         typeof b==="number"&&Number.isFinite(b)&&b>=0;
 });
}
function validStats(stats:any):boolean{
 if(!stats||typeof stats!=="object"||!realCorePair(stats))return false;
 for(const side of ["home","away"]){
  for(const [key,val] of Object.entries(stats[side]||{})){
   if(!VALUE_FIELDS.includes(key)||typeof val!=="number"||!Number.isFinite(val)||val<0||
     val>(key==="ball_possession"?100:400))return false;
  }
 }
 return true;
}
async function getRows(table:string,params:any) {
 if(!params||typeof params!=="object")throw Error("invalid_filter");
 const allowed=table==="live_stats_merged"
  ? new Set(["select","limit","is_live","is_finished","updated_at"])
  : new Set(["select","limit","provider","next_probe_at"]);
 if(Object.keys(params).some(k=>!allowed.has(k)))throw Error("invalid_filter");
 const cols=String(params.select||"");
 const expectedColumns=table==="live_stats_merged"
  ?"canonical_match_id,home_team,away_team,league_name,event_date,minute,is_live,is_finished,merged_stats,updated_at"
  :"probe_key,supports_stats,next_probe_at";
 if(cols!==expectedColumns)throw Error("invalid_columns");
 const lim=Number(params.limit);if(!Number.isInteger(lim)||lim<1||lim>(table==="live_stats_merged"?300:600))throw Error("invalid_limit");
 let query=db.from(table).select(cols);
 if(table==="live_stats_merged"){
  if(params.is_live!=="eq.true"||params.is_finished!=="eq.false"||!String(params.updated_at||"").startsWith("gte."))throw Error("invalid_filters");
  const date=String(params.updated_at).slice(4),ts=iso(date);
  if(ts===null||Math.abs(Date.now()-ts)>15*MINUTE)throw Error("stale_filter");
  query=query.eq("is_live",true).eq("is_finished",false).gte("updated_at",date);
 }else{
  if(params.provider!=="eq.api_football"||!String(params.next_probe_at||"").startsWith("gt."))throw Error("invalid_filters");
  const date=String(params.next_probe_at).slice(3),ts=iso(date);
  if(ts===null||Math.abs(Date.now()-ts)>5*MINUTE)throw Error("stale_filter");
  query=query.eq("provider","api_football").gt("next_probe_at",date);
 }
 const {data,error}=await query.limit(lim);
 if(error)throw Error("database_read_failed:"+error.message);
 return data||[];
}
async function storeRow(table:string,params:any,rows:any){
 if(!Array.isArray(rows)||rows.length!==1||!rows[0]||typeof rows[0]!=="object")throw Error("invalid_rows");
 const item=rows[0];
 if(table==="live_provider_probe_cache"){
  if(params?.on_conflict!=="provider,probe_key"||item.provider!=="api_football"||
    !/^(league|empty):[a-z0-9:-]{1,96}$/i.test(String(item.probe_key||""))||
    iso(item.next_probe_at)===null||iso(item.last_checked_at)===null)throw Error("invalid_probe");
 }else if(table==="live_stats_sources"){
  const age=Date.now()-(iso(item.updated_at)||0);
  if(params?.on_conflict!=="source_name,source_match_id"||item.source_name!=="api_football"||
   !/^\d{1,18}$/.test(String(item.source_match_id||""))||
   !item.canonical_match_id||typeof item.canonical_match_id!=="string"||
   !Number.isInteger(item.minute)||item.minute<1||item.minute>130||
   item.is_live!==true||item.is_finished!==false||
   age< -30_000||age>8*MINUTE||!validStats(item.stats_json)||
   item.raw_json?.statistics_verified!==true)throw Error("invalid_observation");
  // The collector has already verified fixture identity and kickoff.
  // Recheck that the canonical match still exists and is currently live.
  const {data:match,error}=await db.from("live_stats_merged")
    .select("canonical_match_id,home_team,away_team,event_date,is_live,is_finished,updated_at")
    .eq("canonical_match_id",item.canonical_match_id).maybeSingle();
  if(error||!match||match.is_live!==true||match.is_finished!==false||
    Date.now()-(iso(match.updated_at)||0)>10*MINUTE||
    String(match.home_team)!==String(item.home_team)||
    String(match.away_team)!==String(item.away_team)||
    Math.abs((iso(match.event_date)||0)-(iso(item.event_date)||0))>2*60*MINUTE)
    throw Error("canonical_identity_not_verified");
 }else throw Error("invalid_write_table");
 const {error}=await db.from(table).upsert(rows,{onConflict:params.on_conflict});
 if(error)throw Error("database_write_failed:"+error.message);
 return {saved:1};
}
export async function apiFootballGateway(req:Request):Promise<Response> {
 if(req.method!=="POST")return response({error:"method_not_allowed"},405);
 if(!authorized(req.headers.get("x-cron-secret")))return response({error:"unauthorized"},403);
 const size=Number(req.headers.get("content-length")||0);
 if(size>96_000)return response({error:"payload_too_large"},413);
 let payload:any;
 try{payload=await req.json();}catch{return response({error:"invalid_json"},400)}
 if(!payload||typeof payload!=="object")return response({error:"invalid_request"},400);
 const {method,table,params,body}=payload;
 try{
  if(method==="GET"&&(table==="live_stats_merged"||table==="live_provider_probe_cache"))
   return response({data:await getRows(table,params)});
  if(method==="POST"&&(table==="live_provider_probe_cache"||table==="live_stats_sources"))
   return response(await storeRow(table,params,body));
  return response({error:"unsupported_operation"},400);
 }catch(e:any){
  const message=String(e?.message||"gateway_failure");
  console.warn("LIVE_API_FOOTBALL_GATEWAY_REJECTED",message.slice(0,250));
  return response({error:message},/^(invalid_|stale_|canonical_)/.test(message)?400:503);
 }
}
