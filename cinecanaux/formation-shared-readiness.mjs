// Read-only production readiness check for ONE private Formation upload inbox.
// No personal Telegram login, no Telegram mutations and no D1 updates.
import {D1Remote,TelegramBot} from './manual-fallback-live.mjs';

const ID=/^-100\d{6,}$/;
const HANDLE=/^@[A-Za-z][A-Za-z0-9_]{4,31}$/;
const CATS=['general','business','finance','digitale','mindset'];
const norm=x=>String(x||'').trim();
function insist(ok,reason){if(!ok)throw Error(reason)}
export function formationDestinations(raw){
 let data;
 try{data=JSON.parse(raw||'{}')}catch{throw Error('destinations_json_invalid')}
 insist(data&&typeof data==='object'&&!Array.isArray(data)&&
  Object.keys(data).sort().join(',')===CATS.slice().sort().join(','),
  'formation_destinations_missing_or_extra_categories');
 const out={};
 for(const cat of CATS){
  const ref=norm(data[cat]);
  insist(ID.test(ref)||HANDLE.test(ref),'formation_destination_reference_invalid');
  out[cat]=ref;
 }
 insist(new Set(Object.values(out).map(x=>x.toLowerCase())).size===5,
  'formation_destination_repeated');
 return out;
}
export async function auditSharedFormation({db,bot,radar,stage,destinations}){
 insist(ID.test(norm(stage)),'shared_formation_stage_id_missing');
 insist(bot&&radar,'formation_or_radar_bot_missing');
 const sourceRows=(await db.query(
  "SELECT chat_id,bot_access_verified,owner_approved "+
  "FROM cine_manual_fallback_sources WHERE category='formation_general'"
 )).results||[];
 insist(sourceRows.length===1&&
  sourceRows[0].bot_access_verified===1&&
  sourceRows[0].owner_approved===1&&
  ID.test(String(sourceRows[0].chat_id)),'verified_formation_general_source_missing');
 const source=String(sourceRows[0].chat_id);
 insist(source===stage,'shared_formation_source_stage_mismatch');
 const [ownerSource,radarSource,botIdentity]=await Promise.all([
  bot.verifyChannel(source,{privateOnly:true}),
  radar.verifyChannel(source,{privateOnly:true}),
  bot.identity()
 ]);
 insist(String(ownerSource.id)===source&&String(radarSource.id)===source&&
  botIdentity.is_bot===true,'formation_source_not_verified_live');
 const routes=(await db.query(
  "SELECT category,bot_access_verified,owner_approved,enabled,rights_attested "+
  "FROM cine_manual_fallback_sources WHERE category IN "+
  "('formation_general','formation_business','formation_finance',"+
  "'formation_digitale','formation_mindset')"
 )).results||[];
 insist(routes.length===5&&new Set(routes.map(x=>x.category)).size===5&&
  routes.every(x=>x.bot_access_verified===1&&x.owner_approved===1),
  'five_verified_formation_routes_missing');
 const checked=new Set([source]);
 for(const cat of CATS){
  const dest=await bot.verifyChannel(destinations[cat]);
  insist(dest?.type==='channel','formation_target_not_channel');
  if(cat==='general'){
   insist(Boolean(dest.username),'formation_general_target_not_public');
  }else{
   insist(!dest.username,'formation_specialty_target_not_private');
  }
  insist(!checked.has(String(dest.id)),
   'formation_target_overlaps_other_destination_or_shared_source');
  checked.add(String(dest.id));
 }
 return {
  private_inboxes:1,
  destinations_verified:checked.size-1,
  routes_verified:routes.length,
  redistribution_routes_active:routes.filter(x=>x.enabled===1&&x.rights_attested===1).length
 };
}
async function main(){
 const env=process.env;
 const db=new D1Remote({
  token:env.CLOUDFLARE_API_TOKEN||env.CF_API_TOKEN,
  account:env.CLOUDFLARE_ACCOUNT_ID||'9c86118191b804d91b5f5b2c89114999',
  db:env.CINERADAR_D1_DATABASE_ID||'fa8b5009-bc1a-4a6e-b143-7a487c7297a5'
 });
 const result=await auditSharedFormation({
  db,bot:new TelegramBot(env.FORMATION_BOT_TOKEN),
  radar:new TelegramBot(env.CINE_RADAR_BOT_TOKEN),
  stage:norm(env.FORMATION_STAGE_CHAT),
  destinations:formationDestinations(env.FORMATION_DESTINATIONS_JSON)
 });
 console.log('FORMATION_SHARED_INBOX_READINESS',JSON.stringify(result));
}
main().catch(e=>{
 // Only fixed program error codes, never raw Telegram errors or private peers.
 const msg=norm(e?.message);
 const allowed=/^(formation_|shared_formation_|five_verified_|destinations_|verified_formation_)/;
 console.error('FORMATION_SHARED_INBOX_BLOCKED',
  allowed.test(msg)?msg:'private_readiness_failed');
 process.exitCode=1;
});
