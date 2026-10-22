import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
const file="migration/free-stack/live/index.signals-safe.mjs";
execFileSync(process.execPath,["--check",file],{stdio:"inherit"});
const code=readFileSync(file,"utf8");
const start=code.indexOf("function supplementalName("),end=code.indexOf("function diagnostic(events)",start);
assert(start>0&&end>start&&end-start<20000,"add-on implementation missing");
const build="const buildLiveStats=(parts)=>{const totals={};for(const [k,n] of [[\"corner_kicks\",\"corners\"],[\"total_shots\",\"total_shots\"],[\"shots_on_target\",\"shots_on_target\"]])if(Number.isFinite(parts.home[k])&&Number.isFinite(parts.away[k]))totals[n]=parts.home[k]+parts.away[k];return {...parts,totals}};";
const helper=new Function(build+code.slice(start,end)+"\nreturn {fetchVerifiedSupplementalLive};")();
const startTime=new Date(Date.now()-44*60_000).toISOString();
const fixture=(home,away,id,slug)=>({home,away,status:"live",time:startTime,home_score:0,away_score:0,url:"https://sportscore.com/football/match/"+slug+"/"+id+"/",competition:"Test league"});
const stats=()=>({updated_at:new Date(Date.now()-8_000).toISOString(),home:{corners:5,shots:11,shots_on_target:4},away:{corners:4,shots:8,shots_on_target:2}});
const movi=(home,away,id,st=stats())=>({id,home,away,kickoff_utc:startTime,in_play:true,polled_at:new Date(Date.now()-11_000).toISOString(),stats:st});
const fixtureRows=[
 fixture("Cumbaya FC","CD El Nacional","10001","cumbaya-fc-vs-cd-el-nacional"),
 fixture("Manchester Utd (Player)","Arsenal (Player)","10002","fake-esoccer"),
 fixture("Deportivo Chiriqui Women","Inter Panama CF Women","10003","deportivo-vs-inter")
];
const moviRows=[
 movi("Cumbaya","El Nacional","20001"),
 movi("Manchester Utd (Player)","Arsenal (Player)","20002"),
 movi("Deportivo Chiriqui (W)","Inter Panama CF (W)","20003",{...stats(),updated_at:new Date(Date.now()-4000000).toISOString()})
];
const old=globalThis.fetch;
globalThis.fetch=async url=>{
 const u=String(url);
 if(u.includes("sportscore.com/api/v1/fixtures"))return Response.json({matches:fixtureRows});
 if(u.includes("moviodds.com/odds"))return Response.json({matches:moviRows});
 if(u.includes("sportscore.com/api/v1/match/"))return Response.json({match:{home:"Cumbaya FC",away:"CD El Nacional",status:"live",live_minute:44}});
 throw Error("Unexpected network "+u);
};
try{
 const r=await helper.fetchVerifiedSupplementalLive([]);
 assert.equal(r.matches.length,1,JSON.stringify(r.report));
 assert.equal(r.matches[0].id,"sportscore:10001");
 assert.equal(r.matches[0].live_stats.totals.corners,9);
 assert.equal(r.matches[0].live_stats.totals.total_shots,19);
 assert.deepEqual(r.matches[0].stats_sources,["sportscore_fixture","moviodds_verified"]);
 assert.equal(r.report.stale_stats,1);
 const repeat=await helper.fetchVerifiedSupplementalLive([{is_live:true,home_team:"Cumbaya",away_team:"El Nacional",event_date:startTime}]);
 assert.equal(repeat.matches.length,0,"duplicate ESPN fixture must not yield second coupon");
 assert.equal(repeat.report.duplicate_espn,1);
 console.log("PASS verified real fixture/multi-source corners=9 shots=19; stale, virtual and duplicate rejected");
}finally{globalThis.fetch=old}
