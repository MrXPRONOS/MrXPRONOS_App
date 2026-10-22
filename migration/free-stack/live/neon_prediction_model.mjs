// Reprise conservatrice du modele live-value-v2.3-playability-envelope de
// supabase/functions/live/index.ts (2026-10-22). Sans source bookmaker ni Telegram.
// No empirical accuracy claims. Model-only implied odds are NOT bookmaker odds.
export const NEON_SIGNAL_MODEL_VERSION = "neon-live-value-v2.3-playability-espn";
const MARKETS = {
  corners:{ stat:"corner_kicks", db:"total_corners", unit:"corners",
    lines:[7.5,8.5,9.5,10.5,11.5,12.5,13.5],
    baseline:[7.5,8.5,9.5,10.5,11.5], first:18,last:82,min:3,
    probability:.58,reliability:52},
  shots:{ stat:"total_shots",db:"total_shots",unit:"tirs",
    lines:[15.5,17.5,19.5,21.5,23.5,25.5,27.5,29.5,31.5,33.5],
    baseline:[17.5,19.5,21.5,23.5,25.5,27.5,29.5],
    first:15,last:83,min:6,probability:.60,reliability:55},
  fouls:{stat:"fouls",db:"total_fouls",unit:"fautes",
    lines:[17.5,19.5,21.5,23.5,24.5,25.5,27.5,29.5,31.5],
    baseline:[19.5,21.5,23.5,24.5,25.5,27.5],
    first:18,last:84,min:6,probability:.57,reliability:54}
};
const num=(v)=>v===null||v===undefined||v===""?null:(Number.isFinite(Number(v))?Number(v):null);
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const round=(n,d=2)=>Number(n.toFixed(d));
function pair(stats,key){
  const h=num(stats?.home?.[key]),a=num(stats?.away?.[key]);
  return h!==null&&a!==null&&h>=0&&a>=0&&h<10000&&a<10000 ? h+a : null;
}
function momentum(stats){
  const m=(side)=>side?2*(num(side.total_shots)||0)+3*(num(side.shots_on_target)||0)+1.5*(num(side.corner_kicks)||0)+.15*(num(side.ball_possession)||0):0;
  return {total:Math.round(m(stats?.home)+m(stats?.away))};
}
function matchFlow(stats,minute,mom){
  const shots=pair(stats,"total_shots")||0,corners=pair(stats,"corner_kicks")||0;
  const shotOn=pair(stats,"shots_on_target")||0;
  const ph=num(stats?.home?.ball_possession)||0,pa=num(stats?.away?.ball_possession)||0;
  const shotRate=shots/Math.max(1,minute),cornerRate=corners/Math.max(1,minute);
  const pressure=shotOn*2+corners*1.4+Math.abs(ph-pa)*.08+(mom?.total||0)*.12;
  let flow="neutral";
  if(pressure>=18||shotRate>=.22||cornerRate>=.09)flow="offensive";
  if(minute>=65&&pressure<12&&shotRate<.18&&cornerRate<.07)flow="defensive";
  return flow;
}
function projection(current,minute,type,flow){
  const elapsed=Math.max(1,minute),left=Math.max(0,90-elapsed);
  let multiplier=flow==="offensive"?.82:flow==="defensive"?.52:.70;
  if(minute>=70)multiplier-=.08;
  if(minute>=78)multiplier-=.10;
  multiplier=Math.max(.35,multiplier);
  const extra=type==="corners"?4:8;
  return round(Math.min(current+(current/elapsed)*left*multiplier,current+extra),1);
}
function poissonTail(lambda,atLeast){
  if(atLeast<=0)return 1;
  if(!(lambda>0))return 0;
  let term=Math.exp(-lambda),sum=term;
  for(let i=1;i<atLeast;i++){term*=lambda/i;sum+=term;}
  return clamp(1-sum,.005,.995);
}
function probability(current,threshold,projected,heuristic,reliability){
  const additional=Math.max(0,Math.floor(threshold)+1-current);
  const ct=poissonTail(Math.max(.05,projected-current),additional);
  const blended=ct*.72+clamp(heuristic,.20,.95)*.18+.05;
  const val=.50+(blended-.50)*(.72+clamp(reliability/100,0,1)*.28);
  return round(clamp(val,.18,.94),4);
}
function tier(fairOdds){
  if(fairOdds>=1.45&&fairOdds<=1.75)return "quality";
  if(fairOdds>1.75&&fairOdds<=2.30)return "value";
  if(fairOdds>2.30&&fairOdds<=3.20)return "high_value";
  return null;
}
function tierQuality(t,p,rel,dq){
  if(t==="quality")return p>=.56&&rel>=68&&dq>=67;
  if(t==="value")return p>=.43&&rel>=72&&dq>=67;
  if(t==="high_value")return p>=.31&&rel>=78&&dq>=100;
  return false;
}
function uplift(type,minute){
  if(type==="corners")return minute<45?3:minute<60?2:1;
  if(type==="shots")return minute<45?6:minute<60?4:minute<75?2:1;
  return minute<45?4:minute<60?3:minute<75?2:1;
}
function historicalUplift(type,minute){
  if(type==="shots")return minute<30?6:minute<45?5:minute<60?2:minute<75?1:0;
  if(type==="corners")return minute>=30&&minute<45?1:0;
  return null;
}
function dataQuality(stats,type){
  const shots=pair(stats,"total_shots")!==null, corners=pair(stats,"corner_kicks")!==null;
  const on=pair(stats,"shots_on_target")!==null,fouls=pair(stats,"fouls")!==null;
  if(type==="corners")return corners?(shots&&on?100:82):0;
  if(type==="shots")return shots?(on?100:82):0;
  return fouls?(corners||shots?100:82):0;
}
function gates(type,stats,minute,current,flow){
  let p=MARKETS[type].probability,r=MARKETS[type].reliability;
  const shots=pair(stats,"total_shots")||0,on=pair(stats,"shots_on_target")||0;
  if(type==="shots"){
    if(current>=8){p+=.06;r+=6}
    if(on>=3){p+=.06;r+=5}
    if(flow==="offensive"){p+=.08;r+=7}
    if(flow==="defensive"){p-=.10;r-=8}
    if(minute>=20&&minute<=72){p+=.05;r+=5}
  }else if(type==="corners"){
    if(current>=4){p+=.06;r+=6}
    if(shots>=10){p+=.06;r+=5}
    if(on>=4){p+=.04;r+=4}
    if(flow==="offensive"){p+=.07;r+=7}
    if(flow==="defensive"){p-=.08;r-=8}
    if(minute>=25&&minute<=70){p+=.05;r+=6}
  }else{
    if(current>=8){p+=.05;r+=6}
    if(minute>=25&&minute<=75){p+=.05;r+=5}
    if(flow==="defensive"){p+=.03;r+=3}
    if(flow==="offensive"){p-=.03;r-=2}
  }
  const limit=type==="shots"?.91:type==="corners"?.90:.88;
  const maxR=type==="shots"?93:type==="corners"?92:90;
  return {heuristic:clamp(p,.5,limit),reliability:clamp(r,40,maxR)};
}
function valueScore(signal){
  return clamp(Math.round(signal.reliability*.35+signal.data_quality_score*.30+
    clamp((signal.model_fair_odds-1.3)*20,0,25)),0,99);
}
export function evaluateNeonLiveMatch(match,{maximumAgeSeconds=180}={}){
  const result={signals:[],rejects:{},evaluated_markets:0};
  if(!match?.is_live||match?.is_finished){result.rejects.match_not_live=1;return result}
  const minute=num(match.current_minute);
  const ageSeconds=num(match.freshness_seconds);
  if(ageSeconds===null||ageSeconds<0||ageSeconds>maximumAgeSeconds){
    result.rejects.stale=1;return result;
  }
  if(minute===null||minute<1||minute>95){result.rejects.minute_invalid=1;return result}
  const stats=match.live_stats||{},mom=momentum(stats),flow=matchFlow(stats,minute,mom);
  for(const [type,market] of Object.entries(MARKETS)){
    const reject=(why)=>{result.rejects[type+"_"+why]=(result.rejects[type+"_"+why]||0)+1};
    const current=pair(stats,market.stat);
    if(current===null){reject("missing_pair");continue}
    if(!Number.isInteger(current)){reject("not_integer");continue}
    if(minute<market.first||minute>market.last){reject("minute_gate");continue}
    if(current<market.min){reject("minimum_gate");continue}
    result.evaluated_markets++;
    const f=type==="fouls"&&flow==="offensive"?"neutral":flow;
    const projected=projection(current,minute,type,f);
    const {heuristic,reliability}=gates(type,stats,minute,current,flow);
    if(reliability<(type==="shots"?64:type==="corners"?63:62) ||
       type==="corners"&&minute>=45&&minute<60&&reliability<78){reject("weak_reliability");continue}
    const quality=dataQuality(stats,type);
    const baseline=market.baseline.find(line=>current<line&&line-current>=2&&projected>=line+.5)??null;
    if((type==="corners"||type==="shots")&&baseline===null){reject("baseline_unavailable");continue}
    const modelBuffer=type==="corners"?1.5:type==="shots"?6:3;
    const maxUplift=uplift(type,minute);
    const minProb=type==="corners"?(minute>=75?.55:.52):minute>=75?.54:.50;
    const minHeadroom=type==="corners"?(minute>=75?.5:1):minute>=60?1.5:2;
    const candidates=[];
    for(const threshold of market.lines){
      if(!(current<threshold&&threshold-current>=2&&threshold<=projected+modelBuffer))continue;
      const p=probability(current,threshold,projected,heuristic,reliability);
      const fair=round(1/p,2),t=tier(fair);
      if((type==="corners"||type==="fouls")&&t==="high_value")continue;
      if(baseline!==null&&(threshold<baseline||threshold>baseline+maxUplift))continue;
      if(p<minProb||projected-threshold<minHeadroom)continue;
      if(!tierQuality(t,p,reliability,quality))continue;
      candidates.push({threshold,probability:p,model_fair_odds:fair,signal_tier:t});
    }
    if(!candidates.length){reject("model_quality");continue}
    // Historical market-facing candidate is the highest eligible line.
    const chosen=candidates[candidates.length-1];
    const signal={
      type:market.db,threshold:chosen.threshold,probability:chosen.probability,
      model_fair_odds:chosen.model_fair_odds,signal_tier:chosen.signal_tier,
      signal_value:current,current_value:current,projected_value:projected,
      reliability, data_quality_score:quality,source_count:1,source_confidence:65,
      pricing_mode:"model_only",bookmaker_odds:null,live_odds:null,odds_source:null,
      line_candidate_count:candidates.length,line_candidate_rank:candidates.length,
      baseline_threshold:baseline,historical_uplift_cap:historicalUplift(type,minute),
      selected_uplift:baseline===null?null:round(chosen.threshold-baseline),
      model_version:NEON_SIGNAL_MODEL_VERSION,
      confidence:reliability>=80?"high":"medium",
      freshness_seconds:ageSeconds,
      message:current+" "+market.unit+" actuellement",
      reasons:["Projection finale "+projected,"Ligne modèle "+chosen.threshold],
      title:"Over "+chosen.threshold+" "+market.unit,
      headroom:round(projected-chosen.threshold)
    };
    signal.value_score=valueScore(signal);
    result.signals.push(signal);
  }
  result.signals.sort((a,b)=>b.value_score-a.value_score);
  return result;
}
