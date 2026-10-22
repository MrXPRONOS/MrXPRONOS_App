import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
const path="migration/free-stack/live/index.signals-safe.mjs";
execFileSync(process.execPath,["--check",path],{stdio:"inherit"});
const code=readFileSync(path,"utf8");
const start=code.indexOf("async function fetchFromESPN()");
const end=code.indexOf("function supplementalName(",start);
assert(start>=0&&end>start,"expected ESPN fetch function");
const body=code.slice(start,end);
assert(body.includes("const ESPN_DETAIL_MAX_PER_REFRESH=20;"));
assert(body.includes("const ESPN_DETAIL_CONCURRENCY=20;"));
let simultaneous=0,peak=0,summaries=0;
const now=new Date().toISOString();
const fake=Array.from({length:26},(_,i)=>({id:String(401000000+i),date:now,status:{type:{state:"in"}}}));
const getEspn=async path=>{
 if(path.includes("/scoreboard"))return {events:fake};
 if(path.includes("/summary?event=")){
  summaries++;simultaneous++;peak=Math.max(peak,simultaneous);
  await new Promise(r=>setTimeout(r,25));
  simultaneous--;
  return {boxscore:{teams:[]}};
 }
 throw Error("Unexpected URL "+path);
};
const parseEvent=e=>({id:"espn:"+e.id,provider_id:e.id,is_live:true,
  home_team:"Home "+e.id,away_team:"Away "+e.id,home_team_id:"1",away_team_id:"2",
  live_stats:{home:{},away:{},totals:{}},stats_sources:[],_scoreboard_stats:{home:{},away:{}}});
const fromTeams=()=>({home:{},away:{}}),mergeStats=()=>({home:{},away:{}}),
 buildLiveStats=()=>({home:{},away:{},totals:{}});
const get=new Function("getEspn","parseEvent","fromTeams","mergeStats","buildLiveStats",body+";return fetchFromESPN")(getEspn,parseEvent,fromTeams,mergeStats,buildLiveStats);
const result=await get();
assert.equal(result.detailCap,20);
assert.equal(result.detailRequested,20);
assert.equal(result.detailSuccess,20);
assert.equal(summaries,20);
assert.equal(peak,20,"all 20 detail requests must overlap in the same refresh");
assert.equal(result.events.length,26,"schedule and other live games must remain visible");
assert(code.includes("home_logo:matchLogos.get(String(p.match_id))?.home_logo||null"));
console.log("PASS: exactly 20 simultaneous detailed requests with 26 live fixtures; logo history lookup configured");
