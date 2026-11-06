import test from "node:test";
import assert from "node:assert/strict";
import {normalize,cleanFavorites,localClock,selectRelevant}
  from "../supabase/functions/daily-favorite-alerts/logic.mjs";

const day="2026-11-06";
const match=(id,props={})=>({
  id,date:day,home_team:"Real Madrid",away_team:"Barcelone",league:"La Liga",
  category:"pro",prediction:{confidence:81},
  recommendation_eligible:true,is_finished:false,combo_only:false,status:"notstarted",
  ...props
});

test("favorites normalized, capped and deduplicated",()=>{
  const f=cleanFavorites({teams:["Réál Madrid","réal   madrid","Chelsea"],leagues:["La Liga"]});
  assert.deepEqual(f.teams,["Réál Madrid","Chelsea"]);
  assert.equal(normalize("  Ligá   1 "), "liga 1");
  assert.throws(()=>cleanFavorites({teams:Array.from({length:21},(_,i)=>"Club "+i)}),/20 favoris/);
  assert.throws(()=>cleanFavorites({teams:[45]}),/Favori invalide/);
  assert.deepEqual(cleanFavorites({}),{teams:[],leagues:[]});
});

test("matches are only today's verified eligible candidate fixtures, never past results",()=>{
  const f={teams:["real madrid"],leagues:[]};
  const rows=[
    match("a"),match("b",{date:"2026-11-07"}),
    match("c",{is_finished:true,status:"finished"}),
    match("d",{prediction:{confidence:78}}),
    match("e",{recommendation_eligible:false}),
    match("f",{category:"simple"}),
    match("g",{home_team:"Chelsea",away_team:"Tottenham",league:"Premier League"}),
    match("h",{status:"settlement_pending"}),
    match("i",{combo_only:true})
  ];
  const result=selectRelevant(rows,[],f,day);
  assert.deepEqual(result.matchesToday,["Real Madrid – Barcelone"]);
  assert.deepEqual(selectRelevant(rows,[],{teams:["Arsenal"],leagues:[]},day).matchesToday,[]);
  assert.deepEqual(selectRelevant(rows,[],{teams:[],leagues:["La Liga"]},day).matchesToday,["Real Madrid – Barcelone"]);
});

test("relevant article must be published on matching day, not general press",()=>{
  const news=[
    {title:"Real Madrid annonce son entraîneur",published:day+"T08:00:00Z",
      espn_verification:{teams:["Real Madrid"]}},
    {title:"Autre club",published:day+"T11:00:00Z"},
    {title:"Real Madrid d'hier",published:"2026-11-05T12:00:00Z"}
  ];
  const p=selectRelevant([],news,{teams:["Real Madrid"],leagues:[]},day);
  assert.equal(p.newsToday.length,1);
  assert.match(p.newsToday[0],/Real Madrid/);
});

test("local time is based on IANA timezone and correctly handles daylight saving",()=>{
  const winter=new Date("2026-01-10T13:20:00Z");
  assert.deepEqual(localClock(winter,0,"Africa/Lome"),{day:"2026-01-10",hour:13});
  assert.deepEqual(localClock(winter,0,"America/New_York"),{day:"2026-01-10",hour:8});
  assert.deepEqual(localClock(new Date("2026-07-10T13:20:00Z"),0,"America/New_York"),
    {day:"2026-07-10",hour:9});
  assert.deepEqual(localClock(new Date("2026-11-06T23:10:00Z"),0,"Asia/Tokyo"),
    {day:"2026-11-07",hour:8});
  assert.deepEqual(localClock(winter,60,"Invalid/Timezone"),{day:"2026-01-10",hour:12});
});
