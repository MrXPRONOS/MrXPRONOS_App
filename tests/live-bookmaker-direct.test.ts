import { __test } from "../supabase/functions/_shared/live_bookmaker_direct.ts";
const assert=(x:unknown,msg:string)=>{if(!x)throw new Error(msg)};
Deno.test("MoviOdds valid live corner line and observed time",()=>{
 const input={match_id:"bsd99",home:"Real Madrid",away:"Barcelona",kickoff:"2026-10-13T20:00:00Z",market:"total_corners",line:8.5,minute:56};
 const row={home:"Real Madrid",away:"Barcelona",kickoff:"2026-10-13T20:00:00Z",in_play:true,polled_at:new Date().toISOString(),
 quotes:[{group_name:"Total Corners",side:"Over",line:8.5,odds_dec:1.93,suspended:false}]};
 const quote=__test.extractMovi({matches:[row]},input);
 assert(quote?.odds===1.93,"valid quote rejected");
 assert(__test.extractMovi({matches:[{...row,away:"Arsenal"}]},input)===null,"wrong team accepted");
 assert(__test.extractMovi({matches:[{...row,quotes:[{...row.quotes[0],line:9.5}]}]},input)===null,"wrong line accepted");
 assert(__test.extractMovi({matches:[{...row,quotes:[{...row.quotes[0],group_name:"Match Goals"}]}]},input)===null,"wrong market accepted");
 assert(__test.extractMovi({matches:[{...row,polled_at:"2025-01-01T00:00:00Z"}]},input)===null,"stale quote accepted");
});
Deno.test("PinnWire avoids conflating goal totals with corners",()=>{
 const input={match_id:"x",home:"Real Madrid",away:"Barcelona",kickoff:"2026-10-13T20:00:00Z",market:"total_corners",line:8.5,minute:56};
 const base={home:"Real Madrid",away:"Barcelona",kickoff:"2026-10-13T20:00:00Z",live:true,updated_at:new Date().toISOString()};
 assert(__test.extractPinnwire({events:[{...base,markets:[{name:"Match Totals",points:8.5,over:1.9}]}]},input)===null,"unrelated totals accepted");
});

Deno.test("Official MoviOdds kickoff_utc and Total Corners Over-label format",()=>{
 const now=new Date().toISOString();
 const input={match_id:"bsd100",home:"AFC",away:"FCB",kickoff:"2026-10-13T20:00:00Z",market:"total_corners",line:8.5,minute:57};
 const row={home:"AFC",away:"FCB",kickoff_utc:"2026-10-13T20:00:00Z",in_play:true,
    polled_at:now,quotes:[{group_name:"Total Corners",label:"Over 8.5",odds_dec:1.84,ts:"2026-10-12T12:00:00Z"}]};
 assert(__test.extractMovi({matches:[row]},input)?.odds===1.84,"live market label not parsed");
 assert(__test.extractMovi({matches:[{...row,polled_at:"2025-01-01T12:00:00Z"}]},input)===null,"stale market accepted");
});
