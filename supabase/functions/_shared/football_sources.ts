// Free football providers used before BSD detail calls.
// SportScore requires visible attribution on pages that expose its data.
export const FREE_SOURCE_QUALITY: Record<string, {overall:number;live:number;detail:number;coverage:number;odds:number}> = {
  espn: { overall: 98, live: 99, detail: 99, coverage: 91, odds: 0 },
  sportscore: { overall: 92, live: 95, detail: 93, coverage: 96, odds: 0 },
  bsd: { overall: 89, live: 91, detail: 91, coverage: 98, odds: 90 },
  thesportsdb: { overall: 79, live: 55, detail: 82, coverage: 73, odds: 0 },
  openligadb: { overall: 76, live: 66, detail: 69, coverage: 54, odds: 0 },
};

const SPORT_SCORE = "https://sportscore.com/api/v1";
// SportScore site URLs are /football/match/<slug>/<provider-id>/.
// /match/?slug= expects the slug, while our source match key uses the stable id.
function sportScoreRefs(x:any, home:string, away:string){
  const path=text(x.url||x.match_url);
  const match=path.match(/\/match\/([^/?#]+)\/([^/?#]+)(?:[/?#]|$)/);
  const slug=text(x.slug||x.match_slug||x.url_slug||match?.[1]) || slugify(home+"-vs-"+away);
  const id=text(x.id||x.match_id||match?.[2]) || slug;
  return {id,slug};
}
function sportScoreMinute(x:any):number|null{
  const values=[x.live_minute,x.minute,x.match_minute,x.elapsed,x.elapsed_time,x.clock?.minute,x.clock?.elapsed];
  for(const v of values){
    const n=int(v);
    if(n!==null&&n<=130)return n;
    // E.g. "45+" means extra time but does not specify added seconds/minutes:
    // only the known elapsed lower bound (45) is preserved.
    const stoppage=text(v).match(/^(\d{1,3})\+['’′]?$/);
    if(stoppage&&Number(stoppage[1])<=130)return Number(stoppage[1]);
    const match=text(v).match(/^(\d{1,3})\s*\+\s*(\d{1,2})\s*['’′]?$/);
    if(match){const n=Number(match[1])+Number(match[2]);if(n<=130)return n;}
  }
  const status=text(x.status_text||x.status);
  const match=status.match(/(?:^|\s)(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*['’′](?:\s|$)/);
  return match?Math.min(130,Number(match[1])+Number(match[2]||0)):null;
}
const TSDB = "https://www.thesportsdb.com/api/v1/json/123";
const OPENLIGA = "https://api.openligadb.de";
const memory = new Map<string,{until:number;data:any}>();
const providerCooldown = new Map<string,{until:number;reason:string}>();
function env(name:string,fallback=""){
  try { return Deno.env.get(name) || fallback; } catch { return fallback; }
}

function text(v:any){ return String(v ?? "").trim(); }
function slugify(v:any){
  return text(v).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"");
}
function num(v:any):number|null {
  if(v===null||v===undefined||v===""||typeof v==="boolean") return null;
  const n=Number(String(v).replace(/%$/,"").replace(",","."));
  return Number.isFinite(n)?n:null;
}
function int(v:any):number|null {
  const n=num(v); return n==null?null:Math.max(0,Math.trunc(n));
}
function iso(v:any):string|null {
  const d=new Date(String(v||"")); return Number.isFinite(d.getTime())?d.toISOString():null;
}
function state(raw:any):"pre"|"in"|"post"|"postponed" {
  const s=text(raw).toLowerCase();
  if(/cancel|postpon|abandon|suspend/.test(s)) return "postponed";
  if(/finish|full.?time|\bft\b|final|ended/.test(s)) return "post";
  if(/live|in.?progress|1st.?half|2nd.?half|half.?time/.test(s)) return "in";
  return "pre";
}
async function json(url:string, ttlMs:number){
  const c=memory.get(url);if(c&&c.until>Date.now())return c.data;
  // A remote 429/5xx must not turn every 1-minute refresh into another burst.
  const path=new URL(url);
  const endpoint=path.origin+path.pathname;
  const cooldown=providerCooldown.get(endpoint);
  if(cooldown&&cooldown.until>Date.now())throw new Error("Provider cooldown: "+cooldown.reason);
  let lastError:Error|null=null;
  for(let attempt=0;attempt<2;attempt++){
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),7000);
    try{
      const r=await fetch(url,{signal:controller.signal,headers:{Accept:"application/json","User-Agent":"MrXPRONOS-MultiSource/1.0"}});
      if(!r.ok){
        const e=new Error("HTTP "+r.status);
        if(r.status===429||r.status>=500){
          lastError=e;
          if(attempt===0){await new Promise(resolve=>setTimeout(resolve,250));continue;}
          providerCooldown.set(endpoint,{until:Date.now()+(r.status===429?120_000:60_000),reason:e.message});
        }
        throw e;
      }
      const data=await r.json();
      providerCooldown.delete(endpoint);
      memory.set(url,{until:Date.now()+ttlMs,data});
      return data;
    }catch(e){
      lastError=e instanceof Error?e:new Error(String(e));
      if(attempt===0&&/AbortError|fetch failed|network/i.test(lastError.message)){
        await new Promise(resolve=>setTimeout(resolve,250));continue;
      }
      throw lastError;
    }finally{clearTimeout(timer);}
  }
  throw lastError||new Error("Provider unavailable");
}
function url(base:string, params:Record<string,string|number|undefined>){
  const u=new URL(base); for(const [k,v] of Object.entries(params)) if(v!==undefined&&v!=="")u.searchParams.set(k,String(v)); return u.toString();
}
function liveShape(provider:string,id:string,home:string,away:string,when:any,extra:any={}){
  const st=state(extra.status ?? extra.status_detail);
  return {
    id: provider+":"+id,
    source_match_id:id,
    home_team:home, away_team:away,
    home_score:int(extra.home_score), away_score:int(extra.away_score),
    event_date:iso(when),
    current_minute:int(extra.minute) ?? 0,
    status:extra.status_detail ?? extra.status ?? st,
    is_live:st==="in", is_finished:st==="post",
    home_logo:extra.home_logo||null, away_logo:extra.away_logo||null,
    league_name:extra.league||null,
    live_stats:extra.live_stats||{home:{},away:{}},
    stats_last_updated_at:extra.stats_last_updated_at||null,
    raw_data:{source:provider,provider_quality:FREE_SOURCE_QUALITY[provider],...(extra.raw_data||{})},
  };
}

export async function fetchSportScoreFixtures(date:string,status?:string){
  const payload=await json(url(SPORT_SCORE+"/fixtures/",{sport:"football",date,status,limit:200}),55_000);
  const rows=Array.isArray(payload?.matches)?payload.matches:Array.isArray(payload?.fixtures)?payload.fixtures:Array.isArray(payload?.results)?payload.results:[];
  return rows.filter((x:any)=>x&&x.home&&x.away).map((x:any)=>{
    const home=text(typeof x.home==="object"?x.home?.name:x.home);
    const away=text(typeof x.away==="object"?x.away?.name:x.away);
    const refs=sportScoreRefs(x,home,away);
    return liveShape("sportscore",refs.id,home,away,x.time||x.date||x.start_time,{
      home_score:x.home_score??x.score_home,away_score:x.away_score??x.score_away,
      status:x.status,status_detail:x.status_text||x.status,minute:sportScoreMinute(x),
      home_logo:x.home_logo,away_logo:x.away_logo,league:typeof x.competition==="object"?x.competition?.name:x.competition||x.league,
      raw_data:{sportscore_slug:refs.slug,raw:x},
    });
  });
}
export async function fetchSportScoreLive(){
  // The documented fixtures endpoint supports status=live and limit=200.
  // This avoids the /matches/ alias (live + recent, max 50) undercounting live coverage.
  const date=new Date().toISOString().slice(0,10);
  const payload=await json(url(SPORT_SCORE+"/fixtures/",{sport:"football",date,status:"live",limit:200}),45_000);
  const rows=Array.isArray(payload?.matches)?payload.matches:
    Array.isArray(payload?.fixtures)?payload.fixtures:
    Array.isArray(payload?.results)?payload.results:[];
  return rows.filter((x:any)=>state(x.status||x.status_text)==="in").map((x:any)=>{
    const home=text(typeof x.home==="object"?x.home?.name:x.home);
    const away=text(typeof x.away==="object"?x.away?.name:x.away);
    const refs=sportScoreRefs(x,home,away);
    return liveShape("sportscore",refs.id,home,away,x.time||x.date||x.start_time,{
      home_score:x.home_score??x.score_home,away_score:x.away_score??x.score_away,
      status:x.status,status_detail:x.status_text||x.status,
      minute:sportScoreMinute(x),home_logo:x.home_logo,away_logo:x.away_logo,
      league:typeof x.competition==="object"?x.competition?.name:x.competition||x.league,
      raw_data:{sportscore_slug:refs.slug,raw:x},
    });
  });
}
export async function fetchSportScoreDetail(slug:string){
  if(!slug)return null;
  return await json(url(SPORT_SCORE+"/match/",{sport:"football",slug}),20_000);
}
export function probeSportScoreOdds(payload:any){
  const sections:any[]=[];
  const walk=(v:any,depth=0)=>{
    if(depth>5)return;
    if(Array.isArray(v)){for(const x of v.slice(0,100))walk(x,depth+1);return;}
    if(!v||typeof v!=="object")return;
    for(const [k,x] of Object.entries(v)){
      if(["odds","markets","betting_markets","live_odds","prematch_odds"].includes(k.toLowerCase()))sections.push(x);
      else walk(x,depth+1);
    }
  };
  walk(payload);
  return {
    available:sections.length>0,
    contract_verified:false,
    automation_allowed:false,
    raw_sections:sections.slice(0,8),
    warning:"SportScore public REST documentation does not currently specify an odds endpoint/schema.",
  };
}
function statKey(v:any){
  return text(v).toLowerCase().replace(/[^a-z0-9]/g,"");
}
function statTarget(name:string):string|null{
  if(["woncorners","corners","cornerkicks"].includes(name))return "corner_kicks";
  if(["totalshots","shots","shotstotal"].includes(name))return "total_shots";
  if(["shotsofftarget","offtargetshots"].includes(name))return "shots_off_target";
  if(["attacks","totalattacks"].includes(name))return "attacks";
  if(["dangerousattacks"].includes(name))return "dangerous_attacks";
  if(["shotsontarget","shotsongoal","shotsontargettotal"].includes(name))return "shots_on_target";
  if(["fouls","foulscommitted"].includes(name))return "fouls";
  if(["yellowcards"].includes(name))return "yellow_cards";
  if(["redcards"].includes(name))return "red_cards";
  if(["possession","possessionpct","possessionpercentage","ballpossession"].includes(name))return "ball_possession";
  return null;
}
function applyStats(out:any, source:any){
  const consume=(side:"home"|"away", values:any)=>{
    if(!values)return;
    if(Array.isArray(values)){
      for(const r of values){
        if(!r||typeof r!=="object")continue;
        const k=statTarget(statKey(r.name||r.label||r.type));
        if(k){const v=num(r.value??r.displayValue??r.total);if(v!=null)out[side][k]=v;}
      }
    } else if(typeof values==="object"){
      for(const [rk,rv] of Object.entries(values)){
        const k=statTarget(statKey(rk)); if(k){const v=num(typeof rv==="object"?(rv as any)?.value??(rv as any)?.displayValue:rv);if(v!=null)out[side][k]=v;}
      }
    }
  };
  if(source&&typeof source==="object"){
    consume("home",source.home||source.home_team||source.homeTeam);
    consume("away",source.away||source.away_team||source.awayTeam);
    if(Array.isArray(source)){
      for(const r of source){
        if(!r||typeof r!=="object")continue;
        const key=statTarget(statKey(r.label||r.name||r.type||r.stat));
        // SportScore live detail: [{label:"Shots on Target",home:3,away:2}, ...]
        if(key){
          const home=num(r.home??r.homeValue);
          const away=num(r.away??r.awayValue);
          if(home!=null)out.home[key]=home;
          if(away!=null)out.away[key]=away;
          continue;
        }
        const side=text(r.side||r.homeAway).toLowerCase();
        if(side==="home"||side==="away")consume(side as any,[r]);
      }
    }
  }
}
export function normalizeSportScoreDetail(payload:any){
  const root=payload?.match&&typeof payload.match==="object"?payload.match:payload||{};
  const stats={home:{},away:{}} as any;
  applyStats(stats,root.stats||root.statistics||root.team_stats);
  const lineups=root.lineups||{};
  const timeline=Array.isArray(root.timeline)?root.timeline:Array.isArray(root.events)?root.events:[];
  return {stats,lineups,timeline,minute:sportScoreMinute(root),odds_probe:probeSportScoreOdds(payload)};
}


// ESPN scoreboard fixtures do not always contain the full boxscore.
// Extract only explicitly reported event statistics from the ESPN summary.
// Home/away are established by matching both known ESPN team IDs.
// Once BSD reports both sides of a core market, other feeds can only fill
// genuinely missing markets. External counts must not displace BSD figures.
export function preserveBsdCoreMarketPairs(bsdStats:any, mergedStats:any){
  const out:any={
    ...(mergedStats||{}),
    home:{...(mergedStats?.home||{})},
    away:{...(mergedStats?.away||{})},
    totals:{...(mergedStats?.totals||{})},
  };
  const fields:[string,string][]=[
    ["corner_kicks","corners"],
    ["total_shots","total_shots"],
    ["fouls","fouls"],
    ["shots_on_target","shots_on_target"],
    ["yellow_cards","yellow_cards"],
    ["red_cards","red_cards"],
  ];
  for(const [key,total] of fields){
    const hv=bsdStats?.home?.[key],av=bsdStats?.away?.[key];
    if(typeof hv==="number"&&Number.isFinite(hv)&&hv>=0 &&
       typeof av==="number"&&Number.isFinite(av)&&av>=0){
      out.home[key]=hv;
      out.away[key]=av;
      out.totals[total]=hv+av;
    }
  }
  return out;
}

export function normalizeEspnSummaryStats(summary:any, homeId:string, awayId:string){
  const teams=Array.isArray(summary?.boxscore?.teams)?summary.boxscore.teams:[];
  const find=(id:string)=>teams.find((x:any)=>String(x?.team?.id??"")===id);
  if(!homeId||!awayId||homeId===awayId)return null;
  const home=find(String(homeId)),away=find(String(awayId));
  if(!home||!away)return null;
  const parse=(stats:any[])=>{
    const out:Record<string,number>={};
    for(const stat of Array.isArray(stats)?stats:[]){
      const key=statTarget(statKey(stat?.name||stat?.label||stat?.type||stat?.abbreviation));
      if(!key)continue;
      const value=num(stat?.displayValue??stat?.value);
      if(value!=null && value>=0)out[key]=value;
    }
    return out;
  };
  return {home:parse(home.statistics),away:parse(away.statistics)};
}

export async function fetchTheSportsDbDay(date:string){
  const payload=await json(url(TSDB+"/eventsday.php",{d:date,s:"Soccer"}),120_000);
  const rows=Array.isArray(payload?.events)?payload.events:[];
  return rows.filter((x:any)=>x?.strHomeTeam&&x?.strAwayTeam).map((x:any)=>liveShape("thesportsdb",text(x.idEvent),text(x.strHomeTeam),text(x.strAwayTeam),x.strTimestamp||(x.dateEvent+"T"+(x.strTime||"00:00:00Z")),{
    home_score:x.intHomeScore,away_score:x.intAwayScore,status:x.strStatus,status_detail:x.strStatus,
    home_logo:x.strHomeTeamBadge,away_logo:x.strAwayTeamBadge,league:x.strLeague,raw_data:{raw:x},
  }));
}
export async function resolveTheSportsDbEvent(home:string, away:string, kickoff?:string){
  const query=[home,away].map(x=>text(x).replace(/\s+/g,"_")).join("_vs_");
  if(!text(home)||!text(away))return null;
  const searchDate=text(kickoff).slice(0,10);
  const payload=await json(url(TSDB+"/searchevents.php",{e:query,d:searchDate||undefined}),300_000);
  const rows=Array.isArray(payload?.event)?payload.event:
    Array.isArray(payload?.events)?payload.events:[];
  const normalized=rows.filter((x:any)=>x?.strHomeTeam&&x?.strAwayTeam).map((x:any)=>
    liveShape("thesportsdb",text(x.idEvent),text(x.strHomeTeam),text(x.strAwayTeam),
      x.strTimestamp||(x.dateEvent+"T"+(x.strTime||"00:00:00Z")),{
        home_score:x.intHomeScore,away_score:x.intAwayScore,
        status:x.strStatus,status_detail:x.strStatus,
        home_logo:x.strHomeTeamBadge,away_logo:x.strAwayTeamBadge,
        league:x.strLeague,raw_data:{raw:x},
      })
  );
  const base={home_team:home,away_team:away,event_date:kickoff||null};
  const hit=matchProvider(base,normalized);
  return hit ? String(hit.source_match_id||"") : null;
}

export async function fetchTheSportsDbStats(eventId:string){
  if(!/^\d+$/.test(eventId))return null;
  const payload=await json(url(TSDB+"/lookupeventstats.php",{id:eventId}),90_000);
  const rows=Array.isArray(payload?.eventstats)?payload.eventstats:Array.isArray(payload?.statistics)?payload.statistics:[];
  const stats={home:{},away:{}} as any;
  for(const r of rows){
    if(!r||typeof r!=="object")continue;
    const k=statTarget(statKey(r.strStat||r.name||r.type)); if(!k)continue;
    const hv=num(r.intHome??r.home??r.homeValue), av=num(r.intAway??r.away??r.awayValue);
    if(hv!=null)stats.home[k]=hv;if(av!=null)stats.away[k]=av;
  }
  return {stats,raw:payload};
}

const OPENLIGA_SHORTCUTS=env("OPENLIGA_SHORTCUTS","bl1,bl2,bl3").split(",").map(x=>x.trim()).filter(Boolean);
function seasonFor(d:Date){return d.getUTCMonth()>=6?d.getUTCFullYear():d.getUTCFullYear()-1;}
export async function fetchOpenLigaDay(date:string){
  const d=new Date(date+"T00:00:00Z"), rows:any[]=[];
  if(!Number.isFinite(d.getTime()))return rows;
  for(const league of OPENLIGA_SHORTCUTS){
    try{
      const payload=await json(OPENLIGA+"/getmatchdata/"+encodeURIComponent(league)+"/"+seasonFor(d),300_000);
      for(const x of Array.isArray(payload)?payload:[]){
        const when=iso(x?.matchDateTimeUTC||x?.matchDateTime);if(!when||when.slice(0,10)!==date)continue;
        const results=Array.isArray(x?.matchResults)?x.matchResults:[];
        const final=[...results].filter(Boolean).sort((a:any,b:any)=>(a.resultOrderID||0)-(b.resultOrderID||0)).at(-1);
        rows.push(liveShape("openligadb",text(x.matchID),text(x?.team1?.teamName),text(x?.team2?.teamName),when,{
          home_score:final?.pointsTeam1,away_score:final?.pointsTeam2,status:x.matchIsFinished?"finished":(
            // OpenLigaDB does not provide a minute. Mark as live only if
            // kickoff passed recently AND a result entry proves match activity.
            !x.matchIsFinished && results.length>0 &&
            Date.now()>=Date.parse(when) && Date.now()-Date.parse(when)<3*3600000
              ?"live":"scheduled"),
          home_logo:x?.team1?.teamIconUrl,away_logo:x?.team2?.teamIconUrl,league,raw_data:{raw:x},
        }));
      }
    }catch(e){console.warn("OpenLigaDB source unavailable",league,e);}
  }
  return rows;
}

function normName(v:any){return text(v).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/\b(fc|cf|sc|afc|club|fk|ac|as)\b/g," ").replace(/[^a-z0-9]+/g," ").trim();}
function similarity(a:any,b:any){
  const aa=new Set(normName(a).split(" ").filter(Boolean)),bb=new Set(normName(b).split(" ").filter(Boolean));
  if(!aa.size||!bb.size)return 0;let n=0;for(const x of aa)if(bb.has(x))n++;return n/(aa.size+bb.size-n);
}
export function providerMatchScore(a:any,b:any){
  const teams=(similarity(a?.home_team,b?.home_team)+similarity(a?.away_team,b?.away_team))/2;
  if(teams<0.45)return 0;
  const ad=new Date(a?.event_date||a?.date||"").getTime(),bd=new Date(b?.event_date||b?.date||"").getTime();
  if(Number.isFinite(ad)&&Number.isFinite(bd)&&Math.abs(ad-bd)>8*3600000)return 0;
  return teams+(Number.isFinite(ad)&&Number.isFinite(bd)?Math.max(0,.15-Math.abs(ad-bd)/3600000*.02):0);
}
export function matchProvider(base:any, rows:any[]){
  let best:any=null,score=0;
  for(const row of rows||[]){const s=providerMatchScore(base,row);if(s>score){score=s;best=row;}}
  return score>=.68?best:null;
}
export async function collectFreeLiveProviders(){
  const today=new Date().toISOString().slice(0,10);
  const results:any={sportscore:[],thesportsdb:[],openligadb:[],errors:{}};
  const settled=await Promise.allSettled([fetchSportScoreLive(),fetchTheSportsDbDay(today),fetchOpenLigaDay(today)]);
  for(const [i,key] of ["sportscore","thesportsdb","openligadb"].entries()){
    const r=settled[i];if(r.status==="fulfilled")results[key]=r.value;else results.errors[key]=String(r.reason);
  }
  return results;
}
