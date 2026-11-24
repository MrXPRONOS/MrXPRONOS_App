// Regular safe expiry of bot-only public videos, never user or private media.
import {D1Remote,TelegramBot} from './manual-fallback-live.mjs';
import {sweepPublicExpiry} from './manual-fallback-expiry.mjs';

const env=process.env;
const credentials={
 films:env.CINEX_BOT_TOKEN,desir:env.DESIR_BOT_TOKEN,
 comedie:env.COMEDIE_BOT_TOKEN,action:env.ACTION_BOT_TOKEN,
 series:env.SERIES_BOT_TOKEN,animes:env.ANIME_BOT_TOKEN
};
const known=new Map();
async function main(){
 if(env.CINEX_MANUAL_FALLBACK_ENABLED!=='true'){
  console.log('MANUAL_EXPIRY_DISABLED');return;
 }
 const db=new D1Remote({
  token:env.CLOUDFLARE_API_TOKEN||env.CF_API_TOKEN,
  account:env.CLOUDFLARE_ACCOUNT_ID||'9c86118191b804d91b5f5b2c89114999',
  db:env.CINERADAR_D1_DATABASE_ID||'fa8b5009-bc1a-4a6e-b143-7a487c7297a5'
 });
 const botForCategory=category=>{
  const token=credentials[category];
  if(!token)return null;
  if(!known.has(token))known.set(token,new TelegramBot(token));
  return known.get(token);
 };
 const outcome=await sweepPublicExpiry(db,botForCategory,{limit:15});
 console.log('MANUAL_EXPIRY_RESULT',JSON.stringify(outcome));
 if(outcome.uncertain)process.exitCode=1;
}
main().catch(e=>{
 console.error('MANUAL_EXPIRY_STOPPED',String(e?.message||'error').replace(/-100\d+/g,'[private]'));
 process.exitCode=1;
});
