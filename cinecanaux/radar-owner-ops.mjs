// Ciné Radar — propriétaire : rattachement sûr des 3 canaux et suggestions privées.
// N'effectue aucun transfert ni téléchargement des médias Telegram.
export const PRIMARY_CHANNELS = Object.freeze([
  {kind:'films', username:'CineXFilms_vf'},
  {kind:'series', username:'seriesvf_cinex'},
  {kind:'animes', username:'CineXAnimeFR'}
]);
const headings={films:'🎬 FILMS',series:'📺 SÉRIES',animes:'🎌 ANIMÉS'};
const apiUrl=token=>'https://api.telegram.org/bot'+token+'/';
async function botCall(env,method,payload){
  if(!env.TELEGRAM_TOKEN)throw Error('TELEGRAM_TOKEN absent');
  const response=await fetch(apiUrl(env.TELEGRAM_TOKEN)+method,{
    method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload),
    signal:AbortSignal.timeout(9500)
  });
  const data=await response.json();
  if(!response.ok||!data.ok)throw Error('Telegram '+method+' failed ('+(data.error_code||response.status)+')');
  return data.result;
}
export async function bindPrimaryRadarChannels(env){
  const result={bound:0,alreadyBound:0,errors:[]};
  let me;
  try{me=await botCall(env,'getMe',{});}catch(e){return {...result,errors:['getMe: '+String(e).slice(0,90)]};}
  for(const channel of PRIMARY_CHANNELS){
    try{
      const chat=await botCall(env,'getChat',{chat_id:'@'+channel.username});
      if(chat.type!=='channel'||!Number.isSafeInteger(chat.id)||String(chat.username||'').toLowerCase()!==channel.username.toLowerCase())
        throw Error('Identité du canal non confirmée');
      const membership=await botCall(env,'getChatMember',{chat_id:chat.id,user_id:me.id});
      if(!['administrator','creator'].includes(membership.status))throw Error('Le bot n’est pas administrateur');
      const existing=await env.DB.prepare('SELECT chat_id FROM radar_primary_channels WHERE kind=? AND LOWER(username)=LOWER(?)')
        .bind(channel.kind,channel.username).first();
      if(!existing)throw Error('Canal non inscrit dans D1');
      if(existing.chat_id&&String(existing.chat_id)!==String(chat.id))throw Error('Identifiant Telegram changé : contrôle manuel requis');
      if(existing.chat_id){result.alreadyBound++;continue;}
      const write=await env.DB.prepare("UPDATE radar_primary_channels SET chat_id=?,updated_at=CURRENT_TIMESTAMP WHERE kind=? AND LOWER(username)=LOWER(?) AND chat_id IS NULL")
        .bind(String(chat.id),channel.kind,channel.username).run();
      if(Number(write.meta?.changes||0)===1)result.bound++;
    }catch(e){result.errors.push(channel.kind+': '+String(e.message||e).slice(0,100));}
  }
  return result;
}
export async function missingRadarTitles(env,ownerId,{limit=24,onlyUnnotified=false}={}){
  const n=Math.max(1,Math.min(30,Number(limit)||24));
  const filter=onlyUnnotified?" AND NOT EXISTS (SELECT 1 FROM radar_notice_log l WHERE l.owner_id=? AND l.title_id=t.id )":'';
  const sql="SELECT t.id,t.kind,t.title,t.year,t.source_url,t.trend_rank FROM radar_titles t "+
    "WHERE t.last_seen_at>=datetime('now','-8 days') "+
    "AND NOT EXISTS (SELECT 1 FROM radar_matches m WHERE m.title_id=t.id AND m.media_kind='video')"+
    filter+" ORDER BY CASE t.kind WHEN 'films' THEN 0 WHEN 'series' THEN 1 ELSE 2 END,t.trend_rank ASC,t.last_seen_at DESC LIMIT ?";
  const statement=env.DB.prepare(sql);
  const params=onlyUnnotified?[ownerId,n]:[n];
  return (await statement.bind(...params).all()).results||[];
}
export function formatRadarMissing(rows){
  if(!rows.length)return '✅ Aucun nouveau titre manquant parmi les tendances déjà indexées.';
  const blocks=['🎬 CINÉ RADAR — TITRES À RECHERCHER',
    'Ces suggestions sont des références de titres. Vérifie les droits avant toute diffusion.'];
  for(const kind of ['films','series','animes']){
    const selected=rows.filter(x=>x.kind===kind);
    if(!selected.length)continue;
    blocks.push(headings[kind]);
    for(const x of selected){
      const label='• '+String(x.title).slice(0,105)+(x.year?' ('+x.year+')':'');
      const source=/^https:\/\/(?:www\.themoviedb\.org\/(?:movie|tv)\/\d+|anilist\.co\/anime\/\d+)\/?$/.test(String(x.source_url||''))?String(x.source_url):'';
      blocks.push(label+(source?'\n'+source:''));
    }
  }
  blocks.push('Après publication dans le canal correspondant, Ciné Radar tentera de reconnaître automatiquement le titre.');
  return blocks.join('\n\n').slice(0,3900);
}
// Notification uniquement en message privé, jamais dans les canaux.
// On ne marque une suggestion comme envoyée qu'après confirmation Telegram.
export async function notifyOwnerMissingRadarTitles(env){
  const output={sent:0,listed:0,errors:[]};
  const owners=(await env.DB.prepare("SELECT user_id FROM admin_users WHERE role='owner' LIMIT 3").all()).results||[];
  for(const owner of owners){
    try{
      const rows=await missingRadarTitles(env,owner.user_id,{limit:12,onlyUnnotified:true});
      if(!rows.length)continue;
      output.listed+=rows.length;
      await botCall(env,'sendMessage',{chat_id:owner.user_id,text:formatRadarMissing(rows),disable_web_page_preview:true});
      output.sent++;
      for(const title of rows)await env.DB.prepare(
        "INSERT INTO radar_notice_log(owner_id,title_id,sent_at) VALUES(?,?,CURRENT_TIMESTAMP) "+
        "ON CONFLICT(owner_id,title_id) DO UPDATE SET sent_at=CURRENT_TIMESTAMP"
      ).bind(owner.user_id,title.id).run();
    }catch(e){output.errors.push('owner_notify: '+String(e.message||e).slice(0,100));}
  }
  return output;
}
