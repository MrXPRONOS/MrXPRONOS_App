/**
 * Mr XPRONOS V2: independently encrypted Cloudflare KV snapshots and isolated recovery.
 * Never stores keys. Two separate GitHub OIDC audiences and workflow identities.
 */
const ISSUER = 'https://token.actions.githubusercontent.com';
const REPO = 'MrXPRONOS/MrXPRONOS_App';
const REPO_ID = '1169480535', OWNER_ID = '256667374';
const BACKUP_AUD = 'mrxpronos-actufoot-v2-backup';
const RECOVERY_AUD = 'mrxpronos-actufoot-v2-recovery';
const BACKUP_WORKFLOW = REPO + '/.github/workflows/actu-foot-v2-backup.yml@refs/heads/main';
const RECOVERY_WORKFLOW = REPO + '/.github/workflows/actu-foot-v2-recovery.yml@refs/heads/main';
const V3_WORKFLOW = REPO + '/.github/workflows/actu-foot-v3-maintenance.yml@refs/heads/main';
const COLLECTIONS = ['audit','live_events','matches','news','publications','settings','statistics'];
const MAX_BODY = 22000000, MAX_FILE = 3000000;
const enc = new TextEncoder();
const respond = (status, body) => new Response(JSON.stringify(body), {status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const reject = status => respond(status,{ok:false});
function unbase64url(s) {
  const b=s.replace(/-/g,'+').replace(/_/g,'/');
  return Uint8Array.from(atob(b.padEnd(Math.ceil(b.length/4)*4,'=')),c=>c.charCodeAt(0));
}
function decodePart(p) {return JSON.parse(new TextDecoder().decode(unbase64url(p)));}
async function authenticate(auth,purpose) {
  if(typeof auth!=='string' || !auth.startsWith('Bearer ') || auth.length>10000) throw Error('auth');
  const parts=auth.slice(7).split('.');
  if(parts.length!==3) throw Error('segments');
  const head=decodePart(parts[0]),claims=decodePart(parts[1]);
  if(head.alg!=='RS256' || typeof head.kid!=='string' || !head.kid) throw Error('algorithm');
  const now=Math.floor(Date.now()/1000),backup=purpose==='backup';
  const v3=purpose==='archive'||purpose==='rehearsal';
  const aud=v3?'mrxpronos-actufoot-v3-'+purpose:backup?BACKUP_AUD:RECOVERY_AUD;
  const wf=v3?V3_WORKFLOW:backup?BACKUP_WORKFLOW:RECOVERY_WORKFLOW;
  if(claims.iss!==ISSUER || claims.aud!==aud || claims.repository!==REPO ||
     claims.repository_id!==REPO_ID || claims.repository_owner_id!==OWNER_ID ||
     claims.workflow_ref!==wf || claims.ref!=='refs/heads/main' ||
     !((backup||v3)?['schedule','workflow_dispatch','push']:['workflow_dispatch','push']).includes(claims.event_name) ||
     (purpose==='archive' && claims.environment!=='actu-foot-v2-maintenance') ||
     typeof claims.exp!=='number' || claims.exp<now-30 || claims.exp>now+900 ||
     typeof claims.iat!=='number' || claims.iat>now+60 || claims.iat<now-900 ||
     (claims.nbf!==undefined && (typeof claims.nbf!=='number'||claims.nbf>now+60)) ||
     !/^\d+$/.test(String(claims.run_id??'')) ||
     !/^\d+$/.test(String(claims.run_attempt??'')) ||
     !/^[0-9a-f]{40}$/.test(String(claims.sha??''))) throw Error('claims');
  const res=await fetch(ISSUER+'/.well-known/jwks',{cf:{cacheTtl:300,cacheEverything:true}});
  if(!res.ok) throw Error('jwks');
  const jwk=(await res.json()).keys?.find(k=>k.kid===head.kid && k.kty==='RSA' && k.use==='sig');
  if(!jwk) throw Error('kid');
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,unbase64url(parts[2]),
                              enc.encode(parts[0]+'.'+parts[1]))) throw Error('signature');
  return claims;
}
async function sha256(value) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(value)))].map(b=>b.toString(16).padStart(2,'0')).join('');
}
// D1 is the independent, strongly consistent append-only trust anchor.
export function anchorExtends(previous, manifest, anchor, hashes) {
  const validHash = h => typeof h==='string' && /^[a-f0-9]{64}$/.test(h);
  if (!previous || !Number.isSafeInteger(anchor.sequence) || anchor.sequence<0 ||
      !Array.isArray(hashes) || hashes.length!==anchor.sequence ||
      hashes.length>100000 || !hashes.every(validHash) ||
      anchor.entry_hash!==(hashes.at(-1)||'0'.repeat(64)) ||
      anchor.sequence<previous.sequence ||
      (previous.sequence>0 && hashes[previous.sequence-1]!==previous.entry_hash)) return false;
  const old=JSON.parse(previous.collections_json);
  for(const name of COLLECTIONS){
    const before=old[name],after=manifest.collections[name];
    if(!before||!after||!Number.isSafeInteger(after.generation)||after.generation<before.generation||
       !Number.isSafeInteger(after.key_version)||after.key_version<before.key_version||
       !validHash(after.sha256)||
       (after.generation===before.generation && (after.sha256!==before.sha256||after.key_version!==before.key_version))) return false;
  }
  return true;
}
async function writeBackup(req,env,claims) {
  if(Number(req.headers.get('content-length')||0)>MAX_BODY) return reject(413);
  let body,manifest;
  try{
    const raw=await req.text();
    if(raw.length>MAX_BODY) return reject(413);
    body=JSON.parse(raw);
    if(typeof body?.manifest!=='string' || !body.files || typeof body.files!=='object') return reject(400);
    manifest=JSON.parse(body.manifest);
    if(manifest.anchor_protocol!==2 || manifest.source_commit!==claims.sha) return reject(400);
    if(manifest.format!=='actufoot-v2-backup-v2' ||
       JSON.stringify(Object.keys(manifest.collections||{}).sort())!==JSON.stringify(COLLECTIONS) ||
       JSON.stringify(Object.keys(body.files).sort())!==JSON.stringify(COLLECTIONS)) return reject(400);
    for(const name of COLLECTIONS) {
      const blob=body.files[name],meta=manifest.collections[name];
      if(typeof blob!=='string' || blob.length>MAX_FILE || !meta || meta.filename!==name+'.aes.json') return reject(400);
      const hdr=JSON.parse(blob);
      if(hdr.format!=='mrxp.actufoot.v2.aes256gcm' || hdr.collection!==name ||
         !hdr.ciphertext_b64 || !hdr.nonce_b64 || hdr.generation!==meta.generation || hdr.key_version!==meta.key_version) return reject(400);
      if(await sha256(blob)!==meta.sha256) return reject(400);
    }
    const anchor=body.anchor;
    if(!anchor || !Number.isSafeInteger(anchor.sequence) || anchor.sequence<0 ||
       !/^[a-f0-9]{64}$/.test(anchor.entry_hash) ||
       anchor.audit_generation!==manifest.collections.audit.generation || anchor.sequence!==manifest.collections.audit.record_count) return reject(400);
  }catch{return reject(400);}
  const prefix='snapshots/'+claims.run_id+'/'+claims.run_attempt;
  // Fail closed if no independently seeded baseline, a replay, or a rollback.
  try{
    const head=await env.ANCHOR.prepare('SELECT * FROM anchor_log ORDER BY id DESC LIMIT 1').first();
    if(!head) return reject(503);
    if(!anchorExtends(head,manifest,body.anchor,body.audit_hashes)) return reject(409);
    const claim=await env.ANCHOR.prepare('INSERT OR IGNORE INTO snapshot_claim(run_id,attempt) VALUES (?,?)')
      .bind(String(claims.run_id),String(claims.run_attempt)).run();
    if(claim.meta.changes!==1 || await env.BACKUPS.get(prefix+'/manifest.json')!==null) return reject(409);
    for(const name of COLLECTIONS) await env.BACKUPS.put(prefix+'/'+name+'.aes.json',body.files[name]);
    const proof={repository:REPO,workflow:BACKUP_WORKFLOW,run:String(claims.run_id),
                 attempt:String(claims.run_attempt),commit:claims.sha,anchor_protocol:2,uploaded_at:new Date().toISOString()};
    await env.BACKUPS.put(prefix+'/provenance.json',JSON.stringify(proof));
    await env.BACKUPS.put(prefix+'/audit_anchor.json',JSON.stringify(body.anchor));
    await env.BACKUPS.put(prefix+'/manifest.json',body.manifest);
    // CAS append: simultaneous backups cannot both advance the same baseline.
    // A snapshot left behind by a lost CAS is never accepted for recovery.
    const committed=await env.ANCHOR.prepare(
      'INSERT INTO anchor_log(run_id,attempt,source_commit,sequence,entry_hash,collections_json,manifest_sha256) SELECT ?,?,?,?,?,?,? WHERE (SELECT MAX(id) FROM anchor_log)=?')
      .bind(proof.run,proof.attempt,proof.commit,body.anchor.sequence,body.anchor.entry_hash,
        JSON.stringify(manifest.collections),await sha256(body.manifest),head.id).run();
    if(committed.meta.changes!==1) return reject(409);
  }catch{return reject(503);}
  return respond(201,{ok:true,count:COLLECTIONS.length,run:String(claims.run_id),anchor_protocol:2});
}
async function readRecovery(req,env) {
  let run,attempt;
  try{
    const body=await req.json();
    run=body.run_id;attempt=body.attempt;
    if(typeof run!=='string'||typeof attempt!=='string'||
       !/^[1-9]\d{0,17}$/.test(run)||!/^[1-9]\d{0,17}$/.test(attempt)) return reject(400);
  }catch{return reject(400);}
  const prefix='snapshots/'+run+'/'+attempt;
  const manifest=await env.BACKUPS.get(prefix+'/manifest.json');
  if(manifest===null) return reject(404);
  try{
    const meta=JSON.parse(manifest);
    if(meta.format!=='actufoot-v2-backup-v2' ||
       JSON.stringify(Object.keys(meta.collections||{}).sort())!==JSON.stringify(COLLECTIONS)) return reject(503);
    const files={};
    for(const name of COLLECTIONS){
      const value=await env.BACKUPS.get(prefix+'/'+name+'.aes.json');
      if(typeof value!=='string'||value.length>MAX_FILE||await sha256(value)!==meta.collections[name].sha256) return reject(503);
      files[name]=value;
    }
    const proofRaw=await env.BACKUPS.get(prefix+'/provenance.json');
    if(typeof proofRaw!=='string') return reject(503);
    const proof=JSON.parse(proofRaw);
    if(proof.repository!==REPO||proof.workflow!==BACKUP_WORKFLOW||proof.run!==run||proof.attempt!==attempt||
       !/^[a-f0-9]{40}$/.test(proof.commit)) return reject(503);
    const anchorRaw=await env.BACKUPS.get(prefix+'/audit_anchor.json');
    const anchor=anchorRaw===null?null:JSON.parse(anchorRaw);
    if(meta.anchor_protocol===2 || proof.anchor_protocol===2){
      const accepted=await env.ANCHOR.prepare('SELECT * FROM anchor_log WHERE run_id=? AND attempt=?').bind(run,attempt).first();
      if(!accepted||meta.anchor_protocol!==2||proof.anchor_protocol!==2||
         accepted.manifest_sha256!==await sha256(manifest)||accepted.source_commit!==proof.commit||
         accepted.sequence!==anchor?.sequence||accepted.entry_hash!==anchor?.entry_hash||
         anchor.audit_generation!==meta.collections.audit.generation) return reject(503);
    }
    return respond(200,{ok:true,files,manifest,provenance:proof,anchor});
  }catch{return reject(503);}
}
export function validArchive(path,digest,blob){
  if(typeof path!=='string'||!/^assets\/data\/private\/actufoot_v2\/archive\/(matches|live_events|news|statistics)\/20\d{2}-(0[1-9]|1[0-2])(-[a-f0-9]{24})?\.aes\.json$/.test(path)||
     typeof digest!=='string'||!(/^[a-f0-9]{64}$/).test(digest)) return false;
  if(blob===undefined)return true;
  try{const h=JSON.parse(blob);return typeof blob==='string'&&blob.length<=3000000&&h.format==='mrxp.actufoot.v2.aes256gcm'&&h.archive_context===path&&h.collection===path.split('/')[5]&&h.key_version===2&&typeof h.ciphertext_b64==='string'&&typeof h.nonce_b64==='string';}catch{return false;}
}
async function archiveRequest(req,env,claims,rehearsal){
  if(Number(req.headers.get('content-length')||0)>4000000)return reject(413);
  try{
    const raw=await req.text();if(raw.length>4000000)return reject(413);
    const b=JSON.parse(raw),write=b.action==='write';
    if(!write&&b.action!=='read')return reject(400);
    if((write&&typeof b.ciphertext!=='string')||!validArchive(b.path,b.sha256,write?b.ciphertext:undefined))return reject(400);
    const prefix=rehearsal?'v3/rehearsal/'+claims.run_id+'/'+claims.run_attempt:'v3/archive';
    const key=prefix+'/'+b.sha256;
    if(write){
      if(await sha256(b.ciphertext)!==b.sha256)return reject(400);
      const existing=await env.BACKUPS.get(key);
      if(existing!==null&&existing!==b.ciphertext)return reject(409);
      if(existing===null)await env.BACKUPS.put(key,b.ciphertext,rehearsal?{expirationTtl:86400}:undefined);
      const check=await env.BACKUPS.get(key);
      if(check!==b.ciphertext)return reject(503);
      if(!rehearsal){
        await env.ANCHOR.prepare('INSERT OR IGNORE INTO v3_archive_receipt(sha256,path,run_id,attempt,source_commit) VALUES (?,?,?,?,?)')
          .bind(b.sha256,b.path,String(claims.run_id),String(claims.run_attempt),claims.sha).run();
      }
      return respond(201,{ok:true,sha256:b.sha256});
    }
    if(!rehearsal){
      const receipt=await env.ANCHOR.prepare('SELECT path FROM v3_archive_receipt WHERE sha256=?').bind(b.sha256).first();
      if(!receipt||receipt.path!==b.path)return reject(404);
    }
    const blob=await env.BACKUPS.get(key);
    if(blob===null||!validArchive(b.path,b.sha256,blob)||await sha256(blob)!==b.sha256)return reject(404);
    return respond(200,{ok:true,ciphertext:blob,sha256:b.sha256});
  }catch{return reject(503);}
}
export default {
  async fetch(req,env){
    const path=new URL(req.url).pathname;
    if(req.method==='GET'&&path==='/health') return respond(200,{ok:true});
    if(req.method!=='POST') return reject(404);
    if(path==='/v3/archive'||path==='/v3/archive-rehearsal'){
      const rehearsal=path.endsWith('-rehearsal');
      try{const claims=await authenticate(req.headers.get('authorization'),rehearsal?'rehearsal':'archive');return await archiveRequest(req,env,claims,rehearsal);}
      catch{return reject(401);}
    }
    if(path==='/v2/backup') {
      try{const claims=await authenticate(req.headers.get('authorization'),'backup');return await writeBackup(req,env,claims);}
      catch{return reject(401);}
    }
    if(path==='/v2/recovery') {
      try{await authenticate(req.headers.get('authorization'),'recovery');return await readRecovery(req,env);}
      catch{return reject(401);}
    }
    return reject(404);
  }
};
