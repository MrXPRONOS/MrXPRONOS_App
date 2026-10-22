import postgres from "postgres";

const sql = postgres(process.env.DATABASE_URL, {
  max: 3, idle_timeout: 20, connect_timeout: 6,
  prepare: false, transform: { undefined: null },
});
const origins = new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000"]);
const num = (value,fallback=0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const time = value => value ? new Date(value).toISOString() : null;
function headers(request) {
  const origin = request.headers.get("origin") || "";
  const h = {"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","vary":"Origin"};
  if (origins.has(origin)) h["access-control-allow-origin"] = origin;
  return h;
}
function json(req,body,status=200){return new Response(JSON.stringify(body),{status,headers:headers(req)});}
const safeDate = date => /^\d{4}-\d{2}-\d{2}$/.test(date)&&!Number.isNaN(Date.parse(date+"T00:00:00Z"));
const freshness = value => Math.max(0,Math.floor((Date.now()-Date.parse(value))/1000));
function prediction(p){
 const threshold=num(p.threshold);
 const prob=num(p.probability);
 return {id:p.id,type:p.prediction_type,title:p.prediction_type,badge:p.signal_tier||"",color:"",probability:prob,
   message:p.message,threshold,pronostic:threshold,current:p.current_value,signal_value:p.signal_value??p.current_value,
   projected:p.projected_value,projected_value:p.projected_value,reliability:Math.round(num(p.reliability_score,prob*100)),
   model_fair_odds:p.model_fair_odds,bookmaker_odds:p.bookmaker_odds,implied_probability:p.implied_probability,
   edge:p.edge,expected_value:p.expected_value,value_score:p.value_score,data_quality_score:p.data_quality_score,
   freshness_seconds:p.freshness_seconds,source_count:p.source_count,source_confidence:p.source_confidence,
   source_agreement_score:p.source_agreement_score,signal_tier:p.signal_tier,pricing_mode:p.pricing_mode,
   line_candidate_count:p.line_candidate_count,line_candidate_rank:p.line_candidate_rank,
   baseline_threshold:p.baseline_threshold,historical_uplift_cap:p.historical_uplift_cap,
   selected_uplift:p.selected_uplift,model_version:p.model_version,final_value:p.final_value,headroom:p.headroom,
   reasons:[],confidence:p.confidence,validated:!!p.validated,outcome:p.outcome,
   validation_type:p.validation_type,created_at:p.created_at,signal_home_score:p.signal_home_score,
   signal_away_score:p.signal_away_score,signal_minute:p.signal_minute,signal_half1_home:p.signal_half1_home,
   signal_half1_away:p.signal_half1_away,signal_half2_home:p.signal_half2_home,signal_half2_away:p.signal_half2_away,
   home_score:p.signal_home_score,away_score:p.signal_away_score,minute:p.signal_minute,
   live_odds:p.live_odds,stake_fcfa:p.stake_fcfa,potential_gain_fcfa:p.potential_gain_fcfa,odds_source:p.odds_source};
}
async function currentMatches(){
 const rows=await sql`SELECT id,raw_data,updated_at FROM public.matches_live
   WHERE updated_at >= now()-INTERVAL '240 seconds' ORDER BY updated_at DESC LIMIT 150`;
 if(!rows.length)return [];
 const ids=rows.map(x=>String(x.id));
 const pp=await sql`SELECT id,match_id,prediction_type,probability,message,threshold,current_value,projected_value,
   signal_value,reliability_score,model_fair_odds,bookmaker_odds,implied_probability,edge,expected_value,
   value_score,data_quality_score,freshness_seconds,source_count,source_confidence,source_agreement_score,
   signal_tier,pricing_mode,line_candidate_count,line_candidate_rank,baseline_threshold,historical_uplift_cap,
   selected_uplift,model_version,final_value,headroom,confidence,validated,outcome,validation_type,created_at,
   signal_home_score,signal_away_score,signal_minute,signal_half1_home,signal_half1_away,signal_half2_home,
   signal_half2_away,live_odds,stake_fcfa,potential_gain_fcfa,odds_source
   FROM public.live_predictions WHERE match_id=ANY(${sql.array(ids)}) AND validated=false
   ORDER BY created_at DESC LIMIT 1000`;
 const byId=new Map();
 for(const p of pp){const k=String(p.match_id);if(!byId.has(k))byId.set(k,[]);byId.get(k).push(prediction(p));}
 return rows.map(row=>{
   const base=(row.raw_data && typeof row.raw_data==="object")?row.raw_data:{};
   const preds=(byId.get(String(row.id))||[]).sort((a,b)=>num(b.value_score)-num(a.value_score));
   return {...base, id:String(row.id),predictions:preds,all_predictions:preds,events:[],
     freshness_seconds:freshness(row.updated_at),updated_at:row.updated_at};
 });
}
async function predictionHistory(){
 const rows=await sql`SELECT id,match_id,match_name,home_team,away_team,home_score,away_score,minute,league_name,
 prediction_type,probability,message,threshold,current_value,projected_value,confidence,validated,outcome,
 created_at,validated_at,validation_type,signal_value,reliability_score,model_fair_odds,bookmaker_odds,
 implied_probability,edge,expected_value,value_score,data_quality_score,freshness_seconds,source_count,
 source_confidence,signal_tier,pricing_mode,line_candidate_count,line_candidate_rank,baseline_threshold,
 historical_uplift_cap,selected_uplift,model_version,final_value,headroom,signal_home_score,signal_away_score,
 signal_minute,signal_half1_home,signal_half1_away,signal_half2_home,signal_half2_away,live_odds,stake_fcfa,
 potential_gain_fcfa,odds_source FROM public.live_predictions WHERE created_at >= now()-INTERVAL '48 hours'
 ORDER BY created_at DESC LIMIT 350`;
 return rows.map(p=>({...prediction(p),match_id:String(p.match_id),home_team:p.home_team,
 away_team:p.away_team,current_minute:p.minute,league:{name:p.league_name},match:p.match_name,
 home_score:p.signal_home_score??p.home_score??0,away_score:p.signal_away_score??p.away_score??0,
 minute:p.signal_minute??p.minute??null,validated_at:p.validated_at,timestamp:Date.parse(p.created_at)}));
}
async function scheduled(){
 const rows=await sql`SELECT fixture,updated_at,event_date FROM public.live_scheduled_fixtures
   WHERE event_date BETWEEN now()-INTERVAL '10 minutes' AND now()+INTERVAL '48 hours'
   AND updated_at >= now()-INTERVAL '6 hours' ORDER BY event_date LIMIT 150`;
 return rows.map(x=>x.fixture).filter(x=>x && !x.is_live&&!x.is_finished);
}
export default {
 async fetch(req) {
  const url=new URL(req.url);
  const path=url.pathname.replace(/^\/functions\/v1\/live/,"").replace(/\/$/,"")||"/";
  if(req.method==="OPTIONS")return new Response(null,{status:204,headers:{...headers(req),"access-control-allow-methods":"GET,OPTIONS","access-control-allow-headers":"content-type,authorization,apikey,x-cron-secret"}});
  if(req.method!=="GET")return json(req,{error:"refresh_engine_not_migrated",service:"neon-live-readonly"},503);
  try{
   if(path==="/"||path==="/health"){
    const rows=await sql`SELECT (SELECT count(*)::integer FROM public.live_predictions) AS prediction_count,
      (SELECT max(updated_at) FROM public.matches_live) AS latest_match_update`;
    return json(req,{ok:true,service:"neon-live-readonly",engine:"not_started",prediction_count:rows[0].prediction_count,latest_match_update:rows[0].latest_match_update});
   }
   if(path==="/matches")return json(req,{matches:await currentMatches()});
   if(path==="/opportunities"){
    const matches=await currentMatches();
    const out=matches.filter(x=>x.predictions.length).sort((a,b)=>num(b.predictions[0].value_score)-num(a.predictions[0].value_score));
    return json(req,{opportunities:out.slice(0,12)});
   }
   if(path==="/today"){
    const date=url.searchParams.get("date")||new Date().toISOString().slice(0,10);
    if(!safeDate(date))return json(req,{error:"invalid_date"},400);
    const live=await currentMatches();const future=await scheduled();
    return json(req,{data:{live:{count:live.length,matches:live},scheduled:{count:future.length,matches:future},finished:{count:0,matches:[]}},
      meta:{source:"neon-live-staging",bsd_calls:0,upstream_espn_calls:0,refresh_engine:"not_started"}});
   }
   if(path==="/predictions/history")return json(req,{history:await predictionHistory()});
   if(path==="/predictions/by-id"){
    const id=url.searchParams.get("id")||"";
    if(!/^[0-9a-f-]{36}$/i.test(id))return json(req,{error:"invalid_id"},400);
    const history=await sql`SELECT id FROM public.live_predictions WHERE id=${id}::uuid LIMIT 1`;
    if(!history.length)return json(req,{error:"not_found"},404);
    // Details are limited to the public history fields; never expose telegram state.
    const pp=await predictionHistory();
    const found=pp.find(x=>x.id===id);
    return found?json(req,{prediction:found}):json(req,{error:"outside_history_window"},404);
   }
   if(path==="/daily/today"){
     const date=url.searchParams.get("date")||new Date().toISOString().slice(0,10);
     if(!safeDate(date))return json(req,{error:"invalid_date"},400);
     const pp=await sql`SELECT * FROM public.daily_predictions WHERE prediction_date=${date}::date ORDER BY kickoff LIMIT 150`;
     return json(req,{date,predictions:pp,count:pp.length,source:"daily_predictions",snapshot_available:pp.length>0});
   }
   return json(req,{error:"not_found"},404);
  }catch(e){
   console.error("NEON_LIVE_READ_ERROR",e?.code||e?.name);
   return json(req,{error:"database_unavailable",service:"neon-live-readonly"},503);
  }
 }
};
