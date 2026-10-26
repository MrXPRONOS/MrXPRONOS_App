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
const COLLECTIONS = ['audit','live_events','matches','news','publications','settings','statistics'];
const MAX_BODY = 14500000, MAX_FILE = 2200000;
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
  const aud=backup?BACKUP_AUD:RECOVERY_AUD;
  const wf=backup?BACKUP_WORKFLOW:RECOVERY_WORKFLOW;
  if(claims.iss!==ISSUER || claims.aud!==aud || claims.repository!==REPO ||
     claims.repository_id!==REPO_ID || claims.repository_owner_id!==OWNER_ID ||
     claims.workflow_ref!==wf || claims.ref!=='refs/heads/main' ||
     !(backup?['schedule','workflow_dispatch','push']:['workflow_dispatch','push']).includes(claims.event_name) ||
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
async function writeBackup(req,env,claims) {
  if(Number(req.headers.get('content-length')||0)>MAX_BODY) return reject(413);
  let body,manifest;
  try{
    const raw=await req.text();
    if(raw.length>MAX_BODY) return reject(413);
    body=JSON.parse(raw);
    if(typeof body?.manifest!=='string' || !body.files || typeof body.files!=='object') return reject(400);
    manifest=JSON.parse(body.manifest);
    if(manifest.format!=='actufoot-v2-backup-v2' ||
       JSON.stringify(Object.keys(manifest.collections||{}).sort())!==JSON.stringify(COLLECTIONS) ||
       JSON.stringify(Object.keys(body.files).sort())!==JSON.stringify(COLLECTIONS)) return reject(400);
    for(const name of COLLECTIONS) {
      const blob=body.files[name],meta=manifest.collections[name];
      if(typeof blob!=='string' || blob.length>MAX_FILE || !meta || meta.filename!==name+'.aes.json') return reject(400);
      const hdr=JSON.parse(blob);
      if(hdr.format!=='mrxp.actufoot.v2.aes256gcm' || hdr.collection!==name ||
         !hdr.ciphertext_b64 || !hdr.nonce_b64) return reject(400);
      if(await sha256(blob)!==meta.sha256) return reject(400);
    }
    const anchor=body.anchor;
    if(!anchor || !Number.isSafeInteger(anchor.sequence) || anchor.sequence<0 ||
       !/^[a-f0-9]{64}$/.test(anchor.entry_hash) ||
       anchor.audit_generation!==manifest.collections.audit.generation) return reject(400);
  }catch{return reject(400);}
  const prefix='snapshots/'+claims.run_id+'/'+claims.run_attempt;
  if(await env.BACKUPS.get(prefix+'/manifest.json')!==null) return reject(409);
  try{
    for(const name of COLLECTIONS) await env.BACKUPS.put(prefix+'/'+name+'.aes.json',body.files[name]);
    const proof={repository:REPO,workflow:BACKUP_WORKFLOW,run:String(claims.run_id),
                 attempt:String(claims.run_attempt),commit:claims.sha,uploaded_at:new Date().toISOString()};
    await env.BACKUPS.put(prefix+'/provenance.json',JSON.stringify(proof));
    await env.BACKUPS.put(prefix+'/audit_anchor.json',JSON.stringify(body.anchor));
    await env.BACKUPS.put(prefix+'/manifest.json',body.manifest);
  }catch{return reject(503);}
  return respond(201,{ok:true,count:COLLECTIONS.length,run:String(claims.run_id)});
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
    return respond(200,{ok:true,files,manifest,provenance:proof,anchor});
  }catch{return reject(503);}
}
export default {
  async fetch(req,env){
    const path=new URL(req.url).pathname;
    if(req.method==='GET'&&path==='/health') return respond(200,{ok:true});
    if(req.method!=='POST') return reject(404);
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
