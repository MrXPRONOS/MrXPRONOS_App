import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeName,localDay,nextDay,eligible,displayConfidence,resultState,
  favoriteMatch,normalizeFavorites,toggleFavorite,upcoming,settled,performance,
  makeSnapshot,changesSince,validNews,newsForFavorites,todayTip,reminderICS
} from "../assets/js/daily-utils.mjs";

const NOW=new Date("2026-11-06T13:00:00Z");
function makeMatch(id,extra={}){
  return {
    id, date:"2026-11-06",event_date:"2026-11-06T16:00:00Z",
    home_team:"Real Madrid",away_team:"FC Barcelone",league:"LaLiga",
    category:"pro",recommendation_eligible:true,combo_only:false,
    is_finished:false,status:"notstarted",home_score:null,away_score:null,
    verified_double:false,
    prediction:{type:"1X",confidence:81.2},
    ...extra
  };
}
function makeNews(slug,title,published="2026-11-06T10:00:00Z",meta={}){
  return {slug,title,published,...meta};
}

test("normalization removes accents and duplicate favorites",()=>{
  assert.equal(normalizeName("  Olympíque   Marseille  "),"olympique marseille");
  const favorites=normalizeFavorites({teams:[" FC Barcelone ","fc barcelone","PSG"],
    leagues:["Ligue 1"," ligue 1 "]});
  assert.deepEqual(favorites.teams,["FC Barcelone","PSG"]);
  assert.deepEqual(favorites.leagues,["Ligue 1"]);
  const added=toggleFavorite(favorites,"teams","Arsenal");
  assert.ok(added.teams.includes("Arsenal"));
  assert.ok(!toggleFavorite(added,"teams","arsenal").teams.includes("Arsenal"));
  assert.ok(!favorites.teams.includes("Arsenal"),"original prefs unchanged");
  const names=Array.from({length:26},(_,i)=>"Équipe "+i);
  assert.equal(normalizeFavorites({teams:names}).teams.length,20);
});
test("today and tomorrow never include finished, pending-only or low-confidence picks",()=>{
  const items=[
    makeMatch("today"),
    makeMatch("tomorrow",{date:"2026-11-07",event_date:"2026-11-07T16:00:00Z"}),
    makeMatch("old",{date:"2026-11-05",event_date:"2026-11-05T16:00:00Z"}),
    makeMatch("finished",{is_finished:true,status:"finished"}),
    makeMatch("blocked",{recommendation_eligible:false}),
    makeMatch("low-confidence",{prediction:{type:"1X",confidence:78.9}}),
    makeMatch("combo",{combo_only:true}),
    makeMatch("unauthorized-category",{category:"simple"})
  ];
  assert.deepEqual(upcoming(items,"2026-11-06",{teams:[],leagues:[]}).map(m=>m.id),["today","tomorrow"]);
  assert.equal(eligible(makeMatch("eligible",{prediction:{confidence:.79}})),true);
  assert.equal(eligible(makeMatch("low",{prediction:{confidence:.78}})),false);
  assert.equal(displayConfidence(makeMatch("normalized",{prediction:{confidence:.8}})),80);
  assert.equal(nextDay("2026-11-06"),"2026-11-07");
  assert.equal(localDay(new Date(2026,10,6)),"2026-11-06");
});
test("favorites match home/away teams and league and narrow the daily view",()=>{
  const rows=[
    makeMatch("madrid"),
    makeMatch("arsenal",{home_team:"Arsenal",away_team:"Chelsea",league:"Premier League"}),
    makeMatch("x",{home_team:"Villarreal",away_team:"Girona",league:"LaLiga"})
  ];
  const fav={teams:[" arsenal "],leagues:[]};
  assert.equal(favoriteMatch(rows[1],fav),true);
  assert.equal(favoriteMatch(rows[0],fav),false);
  assert.deepEqual(upcoming(rows,"2026-11-06",fav,true).map(r=>r.id),["arsenal"]);
  assert.deepEqual(upcoming(rows,"2026-11-06",{teams:[],leagues:["laliga"]},true).map(r=>r.id),["madrid","x"]);
});
test("settlement counts wins and non-validated losses, not matches awaiting settlement",()=>{
  const rows=[
    makeMatch("win",{date:"2026-11-05",event_date:"2026-11-05T15:00:00Z",
      is_finished:true,status:"finished",home_score:2,away_score:1,verified_double:true}),
    makeMatch("notwon",{date:"2026-11-05",event_date:"2026-11-05T12:00:00Z",
      is_finished:true,status:"finished",home_score:0,away_score:2,verified_double:false}),
    makeMatch("pending",{date:"2026-11-06",event_date:"2026-11-06T10:00:00Z",
      status:"settlement_pending",home_score:null,away_score:null,verified_double:false}),
    makeMatch("noscore",{date:"2026-11-05",event_date:"2026-11-05T11:00:00Z",
      is_finished:true,status:"finished",home_score:null,away_score:null})
  ];
  assert.equal(resultState(rows[0]),"win");
  assert.equal(resultState(rows[1]),"not_validated");
  assert.equal(resultState(rows[2]),"pending");
  assert.equal(resultState(rows[3]),"unverified");
  assert.equal(settled(rows,NOW,30).length,2);
  const p=performance(rows,NOW,30);
  assert.equal(p.total,2);
  assert.equal(p.won,1);
  assert.equal(p.notValidated,1);
  assert.equal(p.rate,50);
  assert.equal(p.byCategory[0].name,"PRO");
  assert.equal(performance([],NOW,30).rate,null);
});
test("since-last-visit detects added publication, changed score and new news",()=>{
  const older=makeMatch("old",{date:"2026-11-05",event_date:"2026-11-05T10:00:00Z"});
  const original=makeSnapshot([older],[makeNews("abcd1","Article")],new Date("2026-11-05T20:00:00Z"));
  const settledNow={...older,is_finished:true,status:"finished",home_score:1,
    away_score:0,verified_double:true};
  const newPick=makeMatch("new");
  const freshNews=makeNews("abcd2","Nouvelle publication");
  const current=makeSnapshot([settledNow,newPick],[makeNews("abcd1","Article"),freshNews],NOW);
  const diff=changesSince(original,current,[settledNow,newPick],[makeNews("abcd1","Article"),freshNews]);
  assert.equal(diff.firstVisit,false);
  assert.deepEqual(diff.newMatches.map(v=>v.id),["new"]);
  assert.deepEqual(diff.updatedMatches.map(v=>v.id),["old"]);
  assert.deepEqual(diff.newNews.map(v=>v.slug),["abcd2"]);
  assert.equal(changesSince(null,current,[newPick],[]).firstVisit,true);
});
test("news favorites use metadata with fallback headline and reject unsafe slug",()=>{
  const news=[
    makeNews("abcd1","Nouvelle Arsenal",undefined,{espn_verification:{teams:["Arsenal"]}}),
    makeNews("abcd2","Chelsea information"),
    makeNews("../../x","Titre dangereux")
  ];
  assert.equal(validNews(news).length,2);
  assert.deepEqual(newsForFavorites(news,{teams:["arsenal"],leagues:[]}).map(v=>v.slug),["abcd1"]);
});
test("daily tips deterministic and calendar is local floating daily reminder with alarm",()=>{
  const t=todayTip(new Date("2026-11-06T12:00:00Z"));
  assert.equal(t.title,todayTip(new Date("2026-11-06T20:00:00Z")).title);
  const ics=reminderICS(new Date(2026,10,6,7,0,0),"08:30");
  assert.match(ics,/BEGIN:VCALENDAR\r\n/);
  assert.match(ics,/DTSTART:20261106T083000/);
  assert.match(ics,/RRULE:FREQ=DAILY/);
  assert.match(ics,/BEGIN:VALARM/);
  assert.match(ics,/aujourdhui\.html/);
  assert.match(reminderICS(new Date(2026,10,6,18,0,0),"08:30"),/DTSTART:20261107T083000/);
  assert.throws(()=>reminderICS(new Date(),"25:00"),/Heure invalide/);
});
