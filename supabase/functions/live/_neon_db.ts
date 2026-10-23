// Supabase PostgREST compatibility adapter for the original LIVE business logic.
// All queries use identifier allowlists and bound parameters, not string interpolation.
import postgres from "postgres";
const db=postgres(process.env.DATABASE_URL!,{max:3,prepare:false,connect_timeout:8,idle_timeout:20,transform:{undefined:null}});
const tables=new Set(["cron_runs","live_stats_sources","live_stats_merged","notifications","matches_live","live_predictions","espn_feed_cache","espn_match_map","actu_foot_live_events","live_scheduled_fixtures","pronostics","daily_predictions","live_refresh_control"]);
const safe=(name:string)=>{if(!/^[a-z_][a-z0-9_]*$/i.test(name))throw Error("INVALID_COLUMN");return name;};
const table=(name:string)=>{if(!tables.has(name))throw Error("INVALID_TABLE");return name;};
const functions=new Set(["espn_take_request_slot","espn_provider_backoff","upsert_live_fixture_status","renew_live_refresh","claim_live_refresh","release_live_refresh","odds_take_request_slot"]);
type Clause={text:string;value:any};
class Query implements PromiseLike<{data:any;error:any;count?:number}> {
 private action="select";private columns="*";private data:any=null;private conditions:Clause[]=[];
 private sorts:Array<{key:string;asc:boolean}>=[];private maxRows:number|null=null;private singleMode=false;
 private returning=false;private conflicts:string[]=[];private orClause:string|null=null;
 constructor(private name:string){table(name)}
 select(columns="*"){if(columns!=="*")columns.split(",").forEach(x=>safe(x.trim()));this.columns=columns;this.returning=true;return this}
 insert(data:any){this.action="insert";this.data=data;return this}
 upsert(data:any,options:any={}){this.action="upsert";this.data=data;this.conflicts=String(options.onConflict||"").split(",").map(x=>x.trim()).filter(Boolean).map(safe);return this}
 update(data:any){this.action="update";this.data=data;return this}
 delete(){this.action="delete";return this}
 eq(key:string,val:any){this.conditions.push({text:safe(key)+" = ",value:val});return this}
 gte(key:string,val:any){this.conditions.push({text:safe(key)+" >= ",value:val});return this}
 lte(key:string,val:any){this.conditions.push({text:safe(key)+" <= ",value:val});return this}
 lt(key:string,val:any){this.conditions.push({text:safe(key)+" < ",value:val});return this}
 is(key:string,val:any){if(val!==null)throw Error("UNSUPPORTED_IS");this.conditions.push({text:safe(key)+" IS NULL",value:undefined});return this}
 in(key:string,vals:any[]){if(!Array.isArray(vals)||vals.length===0){this.conditions.push({text:"1=0",value:undefined});return this;}this.conditions.push({text:safe(key)+" IN ",value:vals});return this}
 or(value:string){if(value!=="telegram_sent.is.null,telegram_sent.eq.false")throw Error("UNSUPPORTED_OR");this.orClause="(telegram_sent IS NULL OR telegram_sent = false)";return this}
 order(key:string,opts:any={}){this.sorts.push({key:safe(key),asc:opts.ascending!==false});return this}
 limit(n:number){this.maxRows=Math.max(0,Math.min(10000,Math.floor(n)));return this}
 single(){this.singleMode=true;return this}
 maybeSingle(){this.singleMode=true;return this}
 private async execute(){
  const params:any[]=[];const bind=(v:any)=>{params.push(v);return "$"+params.length};
  let where=this.conditions.map(c=>c.value===undefined?c.text:Array.isArray(c.value)?c.text+"("+c.value.map(bind).join(",")+")":c.text+bind(c.value)).join(" AND ");
  if(this.orClause)where+=(where?" AND ":"")+this.orClause;
  let clause=where?" WHERE "+where:"";
  const source="public."+this.name;
  const order=this.sorts.length?" ORDER BY "+this.sorts.map(s=>s.key+(s.asc?" ASC":" DESC")).join(","):"";
  const limit=this.maxRows!==null?" LIMIT "+this.maxRows:"";
  const cols=this.columns;
  let statement="";
  if(this.action==="select")statement="SELECT "+cols+" FROM "+source+clause+order+limit;
  else if(this.action==="delete")statement="DELETE FROM "+source+clause+(this.returning?" RETURNING "+cols:"");
  else if(this.action==="update"){
   const entries=Object.entries(this.data||{});if(!entries.length)throw Error("EMPTY_UPDATE");
   const assignments=entries.map(([key,v])=>safe(key)+"="+bind(v)).join(",");
   // Conditions were bound first; PostgreSQL permits out-of-order parameter indices.
   statement="UPDATE "+source+" SET "+assignments+clause+(this.returning?" RETURNING "+cols:"");
  }else{
   const rows=Array.isArray(this.data)?this.data:[this.data];if(!rows.length)return {data:[],error:null};
   const keys=[...new Set(rows.flatMap(x=>Object.keys(x||{})))].map(safe);
   statement="INSERT INTO "+source+" ("+keys.join(",")+") VALUES "+rows.map(row=>"("+keys.map(key=>bind(row?.[key]??null)).join(",")+")").join(",");
   if(this.action==="upsert"){
    const conflict=this.conflicts.length?this.conflicts.join(","):"id";
    const updates=keys.filter(k=>!this.conflicts.includes(k)).map(k=>k+"=EXCLUDED."+k);
    statement+=" ON CONFLICT ("+conflict+") "+(updates.length?"DO UPDATE SET "+updates.join(","):"DO NOTHING");
   }
   if(this.returning)statement+=" RETURNING "+cols;
  }
  const rows=await db.unsafe(statement,params);
  const data=this.returning||this.action==="select"?(this.singleMode?(rows[0]??null):Array.from(rows)):null;
  return {data,error:null};
 }
 then<TResult1 = {data:any;error:any}, TResult2 = never>(resolve?:((value:{data:any;error:any})=>TResult1|PromiseLike<TResult1>)|null,reject?:((reason:any)=>TResult2|PromiseLike<TResult2>)|null):Promise<TResult1|TResult2>{
  return this.execute().catch(error=>({data:null,error:{code:error?.code||"PG_ERROR",message:error?.message||String(error)}})).then(resolve as any,reject as any);
 }
}
export function createClient(_url:string,_key:string){
 return {from:(name:string)=>new Query(name),rpc:async(name:string,args:Record<string,any>={})=>{
  try{
   if(!functions.has(name))throw Error("UNSUPPORTED_RPC");
   const paramNames=Object.keys(args).map(safe);const params=paramNames.map(k=>args[k]);
   const sql="SELECT public."+name+"("+params.map((_,i)=>"$"+(i+1)).join(",")+") AS result";
   const rows=await db.unsafe(sql,params);
   return {data:rows[0]?.result,error:null};
  }catch(error:any){return {data:null,error:{code:error?.code||"PG_ERROR",message:error?.message||String(error)}}}
 }};
}
