/** Live odds: direct public MoviOdds and optional PinnWire adapter.
 * Global quotas are enforced via Supabase RPC, never per isolate.
 * Fail closed on ambiguous fixture/market/line or stale provider data.
 */
export type LiveQuote={odds:number;source:string;line:number};
type Match={match_id:string;home:string;away:string;kickoff?:string;market:string;line:number;minute:number};
type Rpc={rpc:(name:string, args:Record<string,unknown>)=>PromiseLike<{data:unknown;error:unknown}>};
const clean=(x:unknown)=>String(x??"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"");
const number=(x:unknown)=>x==null||x===""?NaN:Number(x);
const time=(x:unknown)=>typeof x==="string"?Date.parse(x):NaN;
const cap=(n:string, fallback:number)=>{const x=Number(Deno.env.get(n));return Number.isFinite(x)&&x>0?Math.floor(x):fallback;};
const cache=new Map<string,{at:number,data:any}>();
const disabled=new Map<string,number>();

function marketMatches(label:unknown, input:Match):boolean{
  const name=clean(label);
  const wanted=clean(input.market);
  if(wanted==="totalcorners")return name.includes("corner")&&!name.includes("firsthalf")&&!name.includes("1sthalf");
  if(wanted==="totalshots")return name.includes("totalshots")&&!name.includes("ontarget")&&!name.includes("player")&&!name.includes("firsthalf");
  if(wanted==="totalfouls")return name.includes("fouls")&&!name.includes("firsthalf");
  return false;
}
function fixtureMatches(v:any,input:Match):boolean{
  const home=clean(v?.home??v?.home_team??v?.homeTeam?.name);
  const away=clean(v?.away??v?.away_team??v?.awayTeam?.name);
  if(!home||!away||!clean(input.home)||!clean(input.away)||home!==clean(input.home)||away!==clean(input.away))return false;
  const got=time(v?.kickoff_utc??v?.kickoff??v?.starts??v?.commence_time??v?.start_time);
  const wanted=time(input.kickoff);
  return Number.isFinite(got)&&Number.isFinite(wanted)&&Math.abs(got-wanted)<=7200_000;
}
function isFresh(v:any,maxAge=120000){
  const t=time(v?.updated_at??v?.timestamp??v?.polled_at??v?.last_update);
  return Number.isFinite(t)&&Date.now()-t>=-30000&&Date.now()-t<=maxAge;
}
function extractMovi(data:any,input:Match):LiveQuote|null{
  const events=Array.isArray(data?.matches)?data.matches:Array.isArray(data)?data:[];
  const match=events.find((x:any)=>x?.in_play===true&&fixtureMatches(x,input));
  if(!match)return null;
  for(const q of match.quotes??[]){
    if(q?.suspended!==false&&q?.suspended!==undefined)continue;
    if(!marketMatches(q?.group_name??q?.market,input))continue;
    const selection=clean(q?.side??q?.label);
    if(!["over","o"].includes(selection)&&!selection.startsWith("over"))continue;
    const labelLine=String(q?.label??"").match(/over\\s*(\\d+(?:\\.\\d+)?)/i);
    const line=number(q?.line??q?.point??labelLine?.[1]);
    const price=number(q?.odds_dec??q?.price);
    if(!Number.isFinite(line)||Math.abs(line-input.line)>.01||!Number.isFinite(price)||price<=1.01||price>100)continue;
    // Match polling confirms a stable quote is still live; quote.ts is only last change.
    if(!isFresh({updated_at:match?.polled_at}))continue;
    return {odds:Number(price.toFixed(3)),line,source:"moviodds"};
  }
  return null;
}
function extractPinnwire(data:any,input:Match):LiveQuote|null{
  const events=Array.isArray(data?.events)?data.events:Array.isArray(data)?data:[];
  const match=events.find((x:any)=>fixtureMatches(x,input)&&x?.live===true);
  if(!match||!isFresh(match))return null;
  // PinnWire totals are goals unless explicitly tagged as corner/shot/foul markets.
  const markets=Array.isArray(match.markets)?match.markets:[];
  for(const m of markets){
    if(!marketMatches(m?.name??m?.market,input))continue;
    if(m?.suspended===true)continue;
    const line=number(m?.line??m?.points);
    const price=number(m?.over??m?.odds?.over);
    if(Number.isFinite(line)&&Math.abs(line-input.line)<=.01&&Number.isFinite(price)&&price>1.01&&price<=100)
      return {odds:Number(price.toFixed(3)),line,source:"pinnwire"};
  }
  return null;
}
async function getJSON(provider:"moviodds"|"pinnwire",input:Match,db:Rpc):Promise<any|null>{
  const url=provider==="moviodds"?
    "https://moviodds.com/odds?sport=soccer&in_play=1":
    Deno.env.get("LIVE_ODDS_PINNWIRE_DIRECT_URL")||"";
  if(!url||!url.startsWith("https://"))return null;
  const key=provider+":"+url;
  const stored=cache.get(key);
  if(stored&&Date.now()-stored.at<15000)return stored.data;
  if((disabled.get(provider)||0)>Date.now())return null;
  const limits=provider==="moviodds"?{day:cap("LIVE_MOVIODDS_DAILY_CAP",600),minute:cap("LIVE_MOVIODDS_MINUTE_CAP",12)}:
    {day:cap("LIVE_PINNWIRE_DAILY_CAP",90),minute:cap("LIVE_PINNWIRE_MINUTE_CAP",2)};
  if(provider==="pinnwire"&&!Deno.env.get("LIVE_ODDS_PINNWIRE_KEY"))return null;
  const slot=await db.rpc("odds_take_request_slot",{
    p_provider:provider,p_day_limit:limits.day,p_minute_limit:limits.minute});
  if(slot.error||slot.data!==true){console.warn("ODDS_QUOTA_BLOCK",provider);return null;}
  const ac=new AbortController();
  const timer=setTimeout(()=>ac.abort(),5000);
  try{
    const headers:Record<string,string>={Accept:"application/json"};
    if(provider==="pinnwire"){
      const secret=Deno.env.get("LIVE_ODDS_PINNWIRE_KEY");
      if(!secret)return null;
      headers["x-api-key"]=secret;
    }
    const res=await fetch(url,{headers,signal:ac.signal});
    if([401,402,403,429].includes(res.status)){disabled.set(provider,Date.now()+3600000);return null;}
    if(!res.ok)return null;
    const body=await res.json();
    cache.set(key,{at:Date.now(),data:body});
    return body;
  }catch(e){console.warn("LIVE_ODDS_UPSTREAM_UNAVAILABLE",provider, e instanceof Error?e.name:"error");return null;}
  finally{clearTimeout(timer);}
}
export async function fetchLiveBookmakerOdds(input:Match,db:Rpc):Promise<LiveQuote|null>{
  if(!input.match_id||!input.market||!Number.isFinite(input.line)||input.line<=0)return null;
  for(const p of ["moviodds","pinnwire"] as const){
    const raw=await getJSON(p,input,db);
    if(!raw)continue;
    const q=p==="moviodds"?extractMovi(raw,input):extractPinnwire(raw,input);
    if(q)return q;
  }
  return null;
}
export const __test={extractMovi,extractPinnwire,marketMatches,fixtureMatches};
