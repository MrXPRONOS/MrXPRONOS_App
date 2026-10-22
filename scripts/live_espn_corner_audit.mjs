// Read-only ESPN feed audit: compare league-specific summaries and scoreboard
// fields without touching predictions, Telegram, Neon tables or secrets.
const origin="https://site.api.espn.com/apis/site/v2/sports/soccer/";
const tests=[
 ["UEFA club competition","401915832",["all","uefa.europa","uefa.europa.conf","uefa.conference"]],
 ["U17 national teams","401890782",["all","fifa.world.u17.womens","fifa.world.u17","fifa.world"]],
 ["Other UEFA fixture","401915743",["all","uefa.europa","uefa.europa.conf","uefa.conference"]],
];
const fetchJSON=async path=>{
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),8000);
 try{
  const r=await fetch(origin+path,{headers:{"Accept":"application/json","User-Agent":"Mozilla/5.0 (MrXPRONOS diagnostic)"},
    signal:controller.signal});
  const body=r.ok?await r.json().catch(()=>null):null;
  return {status:r.status,body};
 }catch(e){return {status:"network:"+String(e.name||"error"),body:null}}
 finally{clearTimeout(timer)}
};
function describe(x){
 if(!x)return null;
 return {
  keys:Object.keys(x).slice(0,22),
  teams:(x.boxscore?.teams||[]).map(t=>({
    team:t?.team?.displayName||t?.team?.id,homeAway:t.homeAway,
    count:t?.statistics?.length,
    stats:(t?.statistics||[]).map(s=>({name:s.name,displayName:s.displayName,
      label:s.label,abbreviation:s.abbreviation,displayValue:s.displayValue,
      value:s.value})).slice(0,55)
  })),
  header_competitor_stats:x.header?.competitions?.[0]?.competitors?.map(t=>({
    side:t.homeAway,team:t.team?.displayName,stats:(t.statistics||[]).map(z=>z.name||z.type||z.abbreviation).slice(0,50)
  })),
  summary_stat_keys:x.boxscore?.statistics?Object.keys(x.boxscore.statistics):null
 };
}
for(const [label,id,leagues] of tests){
 for(const league of leagues){
  const p=league+"/summary?event="+id;
  const r=await fetchJSON(p);
  console.log(JSON.stringify({label,league,status:r.status,fields:describe(r.body)}).slice(0,5000))
 }
}
const scoreboard=await fetchJSON("all/scoreboard?dates=20261022&limit=500");
console.log("SCOREBOARD",JSON.stringify({status:scoreboard.status,count:scoreboard.body?.events?.length,
 events:(scoreboard.body?.events||[]).filter(e=>tests.some(t=>t[1]===String(e.id))).map(e=>({
 id:e.id,name:e.name,league:e.league,season:e.season,
 competitions:(e.competitions||[]).map(c=>({type:c.type,competitors:c.competitors?.map(t=>({side:t.homeAway,stats:(t.statistics||[]).map(s=>({name:s.name,abbreviation:s.abbreviation,displayValue:s.displayValue}))}))}))
 }))}).slice(0,10000));
