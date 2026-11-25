// Access recovery for an EXISTING private Formation source; never creates channels.
import {D1Remote,TelegramBot} from './manual-fallback-live.mjs';
import {pathToFileURL} from 'node:url';
const ID=/^-100\d{6,}$/;
function check(ok,s){if(!ok)throw Error(s)}
export async function recoverFormationSource({db,publisher,radar,stage}){
 check(ID.test(String(stage||'')),'source_id_invalid');
 const rows=(await db.query("SELECT chat_id,owner_approved,bot_access_verified,rights_attested,enabled FROM cine_manual_fallback_sources WHERE category='formation_general'")).results||[];
 check(rows.length===1&&String(rows[0].chat_id)===String(stage)&&rows[0].owner_approved===1&&rows[0].bot_access_verified===1,'registered_source_missing');
 const [a,b]=await Promise.all([publisher.verifyChannel(stage,{privateOnly:true}),radar.verifyChannel(stage,{privateOnly:true})]);
 check(String(a?.id)===String(stage)&&String(b?.id)===String(stage),'telegram_identity_mismatch');
 const title=String(a.title||'').replace(/[\x00-\x1f\x7f]/g,' ').trim().slice(0,120);
 check(title.length>=3,'telegram_title_missing');
 const sent=await publisher.api('sendMessage',{chat_id:stage,disable_notification:true,text:[
 '📚 DÉPÔT UNIQUE DES FORMATIONS — CinéRadar',
 'Canal privé existant — couverture et fichiers des cours.',
 'Catégories : Générale, Business, Finance, Digitale, Mindset.',
 'Couverture : Cours, Catégorie, Auteur, Titre.',
 'Fichiers : Cours, Partie, Total.',
 'La redistribution des médias reste désactivée sans droits attestés.'
 ].join('\n')});
 check(Number.isInteger(Number(sent?.message_id))&&Number(sent.message_id)>0,'message_receipt_missing');
 return {title,message_id:Number(sent.message_id),bots_verified:true,
  redistribution_enabled:rows[0].enabled===1&&rows[0].rights_attested===1};
}
async function main(){
 const e=process.env;
 const db=new D1Remote({token:e.CLOUDFLARE_API_TOKEN||e.CF_API_TOKEN,
  account:e.CLOUDFLARE_ACCOUNT_ID||'9c86118191b804d91b5f5b2c89114999',
  db:e.CINERADAR_D1_DATABASE_ID||'fa8b5009-bc1a-4a6e-b143-7a487c7297a5'});
 const data=await recoverFormationSource({db,
  publisher:new TelegramBot(e.FORMATION_BOT_TOKEN),
  radar:new TelegramBot(e.CINE_RADAR_BOT_TOKEN),
  stage:e.FORMATION_STAGE_CHAT});
 console.log('FORMATION_EXISTING_SOURCE_RECOVERED',JSON.stringify(data));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)
 main().catch(()=>{console.error('FORMATION_SOURCE_RECOVERY_FAILED');process.exitCode=1});
