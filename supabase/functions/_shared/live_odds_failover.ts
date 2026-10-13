/** Provider chain for LIVE football prices. Each adapter is an HTTPS JSON bridge
 * returning a verified individual quote, not an inferred model price.
 * Provider URLs are optional; unconfigured providers are skipped.
 * No guessed vendor API endpoints or site scraping in an Edge Function.
 */
export type LiveOddsQuote = { odds: number; source: string; line: number };
type Input = { match_id: string; home: string; away: string; kickoff?: string;
               market: string; line: number; minute: number };
const PROVIDERS = ["MOVIODDS", "PINNWIRE", "ODDSLINK", "GOALDIR", "ODDSHARVESTER"] as const;
const usage = new Map<string, {day:string; count:number; disabledUntil:number}>();
const normalize = (v:unknown) => String(v??"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]/gi,"").toLowerCase();
function number(v:unknown):number|null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
const date = (v:unknown) => typeof v === "string" ? Date.parse(v) : NaN;
function status(provider:string, dailyCap:number) {
  const day = new Date().toISOString().slice(0,10);
  const old = usage.get(provider);
  const state = old?.day === day ? old : {day,count:0,disabledUntil:0};
  usage.set(provider,state);
  return state.count < dailyCap && Date.now() >= state.disabledUntil ? state : null;
}
export async function fetchFiveSourceLiveOdds(input:Input): Promise<LiveOddsQuote|null> {
  if (!Number.isFinite(input.line) || input.line <= 0 || !input.match_id || !input.market) return null;
  for (const provider of PROVIDERS) {
    const base = Deno.env.get("LIVE_ODDS_"+provider+"_URL")?.trim();
    if (!base || !base.startsWith("https://")) continue;
    const capRaw = Number(Deno.env.get("LIVE_ODDS_"+provider+"_DAILY_LIMIT")||"");
    const cap = Number.isFinite(capRaw) && capRaw > 0 ? Math.floor(capRaw) : (provider==="PINNWIRE"?90:provider==="ODDSLINK"?30:provider==="GOALDIR"?100:provider==="MOVIODDS"?250:20);
    const state=status(provider,cap);
    if (!state) continue;
    try {
      const u=new URL(base);
      for (const [key,value] of Object.entries({
        match_id:input.match_id,home:input.home,away:input.away,
        kickoff:input.kickoff||"", market:input.market,
        line:String(input.line),minute:String(input.minute),phase:"live"}))
        u.searchParams.set(key,value);
      const token=Deno.env.get("LIVE_ODDS_"+provider+"_TOKEN")||"";
      const headers:Record<string,string>={"Accept":"application/json"};
      if(token) headers["Authorization"]="Bearer "+token;
      const ctl=new AbortController();
      const id=setTimeout(()=>ctl.abort(),4500);
      let response:Response;
      try { response=await fetch(u, {headers,signal:ctl.signal}); }
      finally {clearTimeout(id);}
      state.count++;
      if ([401,402,403,429].includes(response.status)) {
        state.disabledUntil=response.status===429?Date.now()+3600_000:Date.now()+86400_000;
        console.warn("LIVE_ODDS_PROVIDER_RESTRICTED",provider,response.status);
        continue;
      }
      if (!response.ok) continue;
      const payload=await response.json().catch(()=>null);
      const body=payload?.data??payload;
      if(!body || Array.isArray(body) || typeof body!=="object") continue;
      // Never accept a naked price: require identity, exact market/line, phase, observed time.
      const sourceMatch=String(body.match_id??body.event_id??"");
      const identityOk=sourceMatch === input.match_id ||
         (normalize(body.home_team??body.home)===normalize(input.home) &&
          normalize(body.away_team??body.away)===normalize(input.away) &&
          input.home.length>0 && input.away.length>0 &&
          Number.isFinite(date(body.kickoff)) && Number.isFinite(date(input.kickoff)) &&
          Math.abs(date(body.kickoff)-date(input.kickoff))<7200_000);
      const market=normalize(body.market??body.market_type);
      const requested=normalize(input.market);
      const line=number(body.line??body.threshold??body.point);
      const price=number(body.odds??body.price??body.decimal_odds);
      const seen=date(body.updated_at??body.captured_at??body.timestamp);
      const age=Date.now()-seen;
      const phase=String(body.phase??"").toLowerCase();
      if (!identityOk || !market || market!==requested || line===null ||
          Math.abs(line-input.line)>0.01 || price===null || price<=1.01 || price>100 ||
          !Number.isFinite(seen) || age< -30_000 || age>120_000 ||
          !["live","inplay","in-play"].includes(phase)) continue;
      return {odds:Number(price.toFixed(3)),source:provider.toLowerCase(),line};
    } catch(e) {
      console.warn("LIVE_ODDS_PROVIDER_FAILED",provider,String(e).slice(0,130));
      continue;
    }
  }
  return null;
}
