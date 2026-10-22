// MrXPRONOS: Neon LIVE bounded refresh, isolated from Telegram.
// Runs only after verifying a GitHub Actions OIDC token.
// Intentionally DOES NOT generate betting signals or invoke Telegram.
const NEON_REFRESH_AUD = "mrxpronos-neon-live-refresh-20261022";
const ALLOWED_REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED_REF = "refs/heads/migration/supabase-to-free-stack-20261022";
const EXPECTED_WORKFLOW = ALLOWED_REPO + "/.github/workflows/neon-live-refresh-test.yml@" + ALLOWED_REF;
const ESPN_ORIGIN = "https://site.api.espn.com/apis/site/v2/sports/soccer/";

function decodeJwtPart(part) {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
}
async function verifyGithubOidc(req) {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ") || auth.length > 9000) return false;
  const token = auth.slice(7);
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  let hdr, claims;
  try {
    hdr = decodeJwtPart(parts[0]); claims = decodeJwtPart(parts[1]);
  } catch { return false; }
  const now = Math.floor(Date.now() / 1000);
  if (hdr.alg !== "RS256" || !hdr.kid || !claims ||
      claims.iss !== "https://token.actions.githubusercontent.com" ||
      claims.aud !== NEON_REFRESH_AUD ||
      claims.repository !== ALLOWED_REPO ||
      claims.ref !== ALLOWED_REF ||
      claims.workflow_ref !== EXPECTED_WORKFLOW ||
      claims.event_name !== "push" && claims.event_name !== "workflow_dispatch" ||
      !(Number(claims.iat) <= now + 60) || !(Number(claims.exp) > now) ||
      Number(claims.exp) > now + 7200) return false;
  try {
    const res = await fetch("https://token.actions.githubusercontent.com/.well-known/jwks", {
      headers: { Accept: "application/json" }, signal: AbortSignal.timeout(7000)
    });
    if (!res.ok) return false;
    const jwks = await res.json();
    const jwk = jwks.keys?.find(k => k.kid === hdr.kid && k.kty === "RSA" && k.use === "sig");
    if (!jwk) return false;
    const key = await crypto.subtle.importKey("jwk", jwk, {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"}, false, ["verify"]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,
      Buffer.from(parts[2],"base64url"),Buffer.from(parts[0]+"."+parts[1]));
  } catch(e) {
    console.error("NEON_OIDC_VERIFICATION_FAILED",String(e?.name || "error"));
    return false;
  }
}
function asNumber(val) {
  if (val === null || val === undefined || val === "" || val === "-") return null;
  const n=Number(String(val).replace(/%$/,"").replace(",","."));
  return Number.isFinite(n) ? n : null;
}
function firstGood(...values) {
  for (const v of values) if (v !== null && v !== undefined && v !== "") return v;
  return null;
}
function normalizeStatsList(stats) {
  const result={};
  const map={
    corners:"corner_kicks",cornerkicks:"corner_kicks",totalcorners:"corner_kicks",
    totalshots:"total_shots",shots:"total_shots",shotattempts:"total_shots",
    shotsongoal:"shots_on_target",shotsontarget:"shots_on_target",
    foul:"fouls",fouls:"fouls",foulscommitted:"fouls",
    possession:"ball_possession",possessionpct:"ball_possession"
  };
  for (const s of Array.isArray(stats)?stats:[]) {
    const raw=String(s?.name || s?.abbreviation || s?.label || s?.type || "").toLowerCase().replace(/[^a-z]/g,"");
    const key=map[raw];
    const num=asNumber(firstGood(s?.value,s?.displayValue,s?.stat));
    if (key && num!==null && num>=0 && num<10000) result[key]=num;
  }
  return result;
}
function fromTeams(teams, homeId, awayId) {
  let result={home:{},away:{}};
  for(const side of Array.isArray(teams)?teams:[]) {
    const id=String(side?.team?.id ?? "");
    const role=String(side?.homeAway ?? "");
    let key=id&&id===homeId?"home":id&&id===awayId?"away":role==="home"?"home":role==="away"?"away":null;
    if (key) result[key]=normalizeStatsList(side?.statistics);
  }
  return result;
}
function mergeStats(base,more) {
  return {home:{...(base?.home||{}),...(more?.home||{})},away:{...(base?.away||{}),...(more?.away||{})}};
}
function buildLiveStats(parts) {
  const home=parts.home||{},away=parts.away||{};
  const totals={};
  for(const [field,totalField] of [["corner_kicks","corners"],["total_shots","total_shots"],["shots_on_target","shots_on_target"],["fouls","fouls"]]){
    if(Number.isFinite(home[field])&&Number.isFinite(away[field]))totals[totalField]=home[field]+away[field];
  }
  return {home,away,totals};
}
function parseEvent(event, sourceLeague) {
  if(!/^\d{1,16}$/.test(String(event?.id??"")))return null;
  const contest=event?.competitions?.[0]||{};
  const competitors=contest.competitors||[];
  const home=competitors.find(x=>x.homeAway==="home"),away=competitors.find(x=>x.homeAway==="away");
  if(!home?.team||!away?.team)return null;
  const homeName=String(home.team.displayName||home.team.name||"").trim().slice(0,200);
  const awayName=String(away.team.displayName||away.team.name||"").trim().slice(0,200);
  if(homeName.length<2||awayName.length<2)return null;
  const dt=Date.parse(event.date||contest.date||"");
  if(!Number.isFinite(dt))return null;
  const state=event?.status?.type?.state||contest?.status?.type?.state||"";
  const finished=state==="post"||event.status?.type?.completed===true;
  const clock=String(event.status?.displayClock||contest.status?.displayClock||event.status?.type?.detail||"");
  const minute=firstGood(asNumber(clock.match(/^\d+/)?.[0]),asNumber(event.status?.period),0);
  const timeNow=Date.now();
  const isLive=state==="in"&&!finished&&dt>timeNow-6*3600000&&dt<timeNow+3600000;
  const isScheduled=state==="pre"&&dt>=timeNow-10*60000&&dt<timeNow+48*3600000;
  if(!isLive&&!isScheduled)return null;
  return {
    id:"espn:"+event.id, provider_id:String(event.id),
    home_team:homeName,away_team:awayName,
    home_team_id:String(home.team.id||""),away_team_id:String(away.team.id||""),
    home_logo:home.team.logo||"",away_logo:away.team.logo||"",
    home_score:Math.max(0,Math.trunc(asNumber(home.score)||0)),
    away_score:Math.max(0,Math.trunc(asNumber(away.score)||0)),
    current_minute:Math.max(0,Math.min(150,Math.trunc(asNumber(minute)||0))),
    event_date:new Date(dt).toISOString(),
    league_name:String(event?.league?.name||contest?.notes?.[0]?.headline||sourceLeague||"Football").slice(0,200),
    status:isLive?"inprogress":"notstarted",
    period:event.status?.type?.description||"",
    is_live:isLive,is_finished:false,
    stats_sources:[],live_stats:{home:{},away:{},totals:{}},
    _scoreboard_stats:fromTeams(competitors,String(home.team.id||""),String(away.team.id||""))
  };
}
async function getEspn(path) {
  const res=await fetch(ESPN_ORIGIN+path,{
    headers:{"Accept":"application/json","User-Agent":"MrXPRONOS/2.0 (+football statistics)"},
    signal:AbortSignal.timeout(9500)
  });
  if(!res.ok)throw new Error("ESPN_HTTP_"+res.status);
  if(!(res.headers.get("content-type")||"").includes("json"))throw new Error("ESPN_NOT_JSON");
  return res.json();
}
async function fetchFromESPN() {
  const now=new Date();
  const dates=[now.toISOString().slice(0,10).replace(/-/g,"")];
  if(now.getUTCHours()<7)dates.unshift(new Date(Date.now()-86400000).toISOString().slice(0,10).replace(/-/g,""));
  const paths=dates.map(d=>"all/scoreboard?dates="+d+"&limit=500");
  // Regional sources supported by the existing MrXPRONOS code. Kept bounded.
  paths.push("conmebol.sudamericana/scoreboard?dates="+dates[dates.length-1]+"&limit=100");
  const upstream=await Promise.allSettled(paths.map(p=>getEspn(p)));
  const events=new Map(), failures=[];
  upstream.forEach((result,i)=>{
    if(result.status!=="fulfilled"){failures.push({source:paths[i].split("/")[0],error:String(result.reason?.message||"network").slice(0,90)});return;}
    const body=result.value;
    if(!Array.isArray(body?.events)){failures.push({source:paths[i].split("/")[0],error:"schema_invalid"});return;}
    for(const e of body.events)if(e?.id&&(!events.has(String(e.id))||e.status?.type?.state==="in"))events.set(String(e.id),{event:e,source:paths[i].split("/")[0]});
  });
  if(failures.length===paths.length)throw new Error("ALL_ESPN_SOURCES_FAILED:"+failures.map(x=>x.error).join(","));
  const normalized=[...events.values()].map(x=>parseEvent(x.event,x.source)).filter(Boolean);
  // A single detailed ESPN summary is requested only for live events, max 6.
  const live=normalized.filter(e=>e.is_live).slice(0,6);
  const detail=await Promise.allSettled(live.map(e=>getEspn("all/summary?event="+e.provider_id)));
  let detailSuccess=0;
  for(let i=0;i<live.length;i++){
    let extra={home:{},away:{}};
    if(detail[i].status==="fulfilled"){
      const j=detail[i].value;
      extra=fromTeams(j?.boxscore?.teams||j?.boxscore?.statistics||[],live[i].home_team_id,live[i].away_team_id);
      detailSuccess++;
    }
    const both=mergeStats(live[i]._scoreboard_stats,extra);
    live[i].live_stats=buildLiveStats(both);
    live[i].stats_sources=Object.keys(both.home).length+Object.keys(both.away).length?["espn"]:[];
  }
  for(const e of normalized){
    if(!e.is_live)e.live_stats=buildLiveStats(e._scoreboard_stats);
    delete e._scoreboard_stats;
  }
  return {events:normalized.slice(0,250),sourceEvents:events.size,feedRequests:paths.length,detailRequested:live.length,detailSuccess,failures};
}
function diagnostic(events) {
  const live=events.filter(e=>e.is_live);
  const scheduled=events.filter(e=>!e.is_live);
  const observed=live.filter(e=>Object.keys(e.live_stats.home||{}).length+Object.keys(e.live_stats.away||{}).length>0);
  return {live_matches:live.length,scheduled_matches:scheduled.length,
    live_with_observed_statistics:observed.length,statistics_fields:observed.reduce((acc,e)=>acc+Object.keys(e.live_stats.home||{}).length+Object.keys(e.live_stats.away||{}).length,0),
    generated_signals:0,telegram_sent:0};
}
async function persistRefresh(events,fetchDetails) {
  const owner=crypto.randomUUID();
  const lock=await sql.unsafe(
    "INSERT INTO public.worker_locks(lock_name,locked_at,expires_at,owner) VALUES ('neon_live_refresh',now(),now()+interval '120 seconds',$1) ON CONFLICT(lock_name) DO UPDATE SET locked_at=now(),expires_at=now()+interval '120 seconds',owner=EXCLUDED.owner WHERE public.worker_locks.expires_at<now() RETURNING lock_name",
    [owner]
  );
  if(!lock.length)return {already_running:true,success:false,telegram_sent:0};
  try{
    // One atomic transaction: failed upstream batches never mark refresh healthy.
    return await sql.begin(async tx=>{
      const encoded=JSON.stringify(events);
      const liveCount=events.filter(e=>e.is_live).length;
      const scheduledCount=events.filter(e=>!e.is_live).length;
      if(events.length){
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements($1::jsonb))"+
          " INSERT INTO public.matches_live(id,home_team,away_team,home_score,away_score,current_minute,league_name,status,raw_data,updated_at)"+
          " SELECT e->>'id',e->>'home_team',e->>'away_team',(e->>'home_score')::int,(e->>'away_score')::int,(e->>'current_minute')::int,e->>'league_name',e->>'status',e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(id) DO UPDATE SET home_team=EXCLUDED.home_team,away_team=EXCLUDED.away_team,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,current_minute=EXCLUDED.current_minute,league_name=EXCLUDED.league_name,status=EXCLUDED.status,raw_data=EXCLUDED.raw_data,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements($1::jsonb))"+
          " INSERT INTO public.live_scheduled_fixtures(fixture_id,event_date,home_team,away_team,source_names,fixture,updated_at)"+
          " SELECT e->>'id',(e->>'event_date')::timestamptz,e->>'home_team',e->>'away_team',ARRAY['espn']::text[],e,now() FROM src WHERE e->>'is_live'='false'"+
          " ON CONFLICT(fixture_id) DO UPDATE SET event_date=EXCLUDED.event_date,home_team=EXCLUDED.home_team,away_team=EXCLUDED.away_team,source_names=EXCLUDED.source_names,fixture=EXCLUDED.fixture,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements($1::jsonb))"+
          " INSERT INTO public.live_stats_sources(canonical_match_id,source_name,source_match_id,home_team,away_team,league_name,event_date,minute,home_score,away_score,is_live,is_finished,stats_json,raw_json,updated_at)"+
          " SELECT e->>'id','espn',e->>'provider_id',e->>'home_team',e->>'away_team',e->>'league_name',(e->>'event_date')::timestamptz,(e->>'current_minute')::int,(e->>'home_score')::int,(e->>'away_score')::int,true,false,e->'live_stats',e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(source_name,source_match_id) DO UPDATE SET minute=EXCLUDED.minute,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,stats_json=EXCLUDED.stats_json,raw_json=EXCLUDED.raw_json,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements($1::jsonb))"+
          " INSERT INTO public.live_stats_merged(canonical_match_id,primary_match_id,home_team,away_team,league_name,event_date,minute,home_score,away_score,is_live,is_finished,merged_stats,sources_used,confidence_score,merged_match_json,updated_at)"+
          " SELECT e->>'id',e->>'id',e->>'home_team',e->>'away_team',e->>'league_name',(e->>'event_date')::timestamptz,(e->>'current_minute')::int,(e->>'home_score')::int,(e->>'away_score')::int,true,false,e->'live_stats','[\"espn\"]'::jsonb,50,e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(canonical_match_id) DO UPDATE SET minute=EXCLUDED.minute,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,merged_stats=EXCLUDED.merged_stats,merged_match_json=EXCLUDED.merged_match_json,updated_at=EXCLUDED.updated_at",
          [encoded]);
      }
      const stats=diagnostic(events);
      const report={...stats,engine:"neon-espn-safe-v1",source_events:fetchDetails.sourceEvents,
        feed_requests:fetchDetails.feedRequests,detail_requests:fetchDetails.detailRequested,
        detail_success:fetchDetails.detailSuccess,failures:fetchDetails.failures,
        no_telegram:true,no_signal_generation:true};
      await tx.unsafe(
        "INSERT INTO public.cron_runs(name,last_run_at,last_ok,meta) VALUES ('live_refresh',now(),true,$1::jsonb) ON CONFLICT(name) DO UPDATE SET last_run_at=EXCLUDED.last_run_at,last_ok=EXCLUDED.last_ok,meta=EXCLUDED.meta",
        [JSON.stringify(report)]
      );
      return {success:true,...report};
    });
  }finally{
    await sql.unsafe("DELETE FROM public.worker_locks WHERE lock_name='neon_live_refresh' AND owner=$1",[owner]).catch(()=>{});
  }
}
const oldNeonLiveFetch=index_default.fetch.bind(index_default);
index_default.fetch=async function(req){
  const path=new URL(req.url).pathname.replace(/\/$/,"");
  if(path!=="/refresh"&&path!=="/functions/v1/live/refresh")return oldNeonLiveFetch(req);
  if(req.method==="OPTIONS")return new Response(null,{status:204,headers:{...headers(req),"access-control-allow-methods":"POST,OPTIONS","access-control-allow-headers":"authorization,content-type"}});
  if(req.method!=="POST")return json(req,{error:"method_not_allowed"},405);
  if(!(await verifyGithubOidc(req)))return json(req,{error:"unauthorized"},401);
  const body=await req.json().catch(()=>({}));
  if(!["preview","apply"].includes(body?.mode))return json(req,{error:"invalid_mode"},400);
  try {
    const pulled=await fetchFromESPN();
    const summary=diagnostic(pulled.events);
    if(body.mode==="preview")return json(req,{success:true,mode:"preview",...summary,source_events:pulled.sourceEvents,feed_requests:pulled.feedRequests,detail_success:pulled.detailSuccess,failures:pulled.failures,no_database_writes:true});
    const report=await persistRefresh(pulled.events,pulled);
    return json(req,{mode:"apply",...report},report.already_running?409:200);
  }catch(e){
    console.error("NEON_REFRESH_FAILED",e?.code||e?.message?.slice(0,140)||e?.name);
    return json(req,{success:false,error:"refresh_failed",reason:String(e?.code||e?.message||"unknown").slice(0,140),telegram_sent:0},503);
  }
};