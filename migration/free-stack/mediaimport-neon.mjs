import {createHash,createHmac,createPublicKey,verify} from 'node:crypto';
const AUD='mrxpronos-neon-media-transfer';
const WORKFLOW='MrXPRONOS/MrXPRONOS_App/.github/workflows/neon-media-oidc.yml@refs/heads/main';
const REPO='MrXPRONOS/MrXPRONOS_App';
const SIGNHOST='https://token.actions.githubusercontent.com';
const MAX_BYTES=9000000;
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json','cache-control':'no-store'}});
const sha=b=>createHash('sha256').update(b).digest('hex');
const hmac=(k,s)=>createHmac('sha256',k).update(s).digest();
const enc=s=>encodeURIComponent(s).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());
let jwksCache={at:0,keys:[]};
async function verifyGitHub(token){
  if(!token || token.length>16000) return false;
  const p=token.split('.');if(p.length!==3)return false;
  let head,claims;try{head=JSON.parse(Buffer.from(p[0],'base64url').toString());claims=JSON.parse(Buffer.from(p[1],'base64url').toString())}catch{return false}
  const now=Math.floor(Date.now()/1000);
  if(head.alg!=='RS256'||typeof head.kid!=='string'||claims.iss!==SIGNHOST||claims.aud!==AUD||claims.repository!==REPO||claims.ref!=='refs/heads/main'||claims.workflow_ref!==WORKFLOW||claims.sub!==('repo:'+REPO+':ref:refs/heads/main')||typeof claims.exp!=='number'||claims.exp<now||claims.exp>now+600||typeof claims.iat!=='number'||claims.iat>now+60)return false;
  if(Date.now()-jwksCache.at>3600000){const res=await fetch(SIGNHOST+'/.well-known/jwks',{signal:AbortSignal.timeout(8000)});if(!res.ok)throw Error('OIDC key service unavailable');const d=await res.json();jwksCache={at:Date.now(),keys:d.keys||[]}}
  const jwk=jwksCache.keys.find(x=>x.kid===head.kid&&x.kty==='RSA');if(!jwk)return false;
  const pub=createPublicKey({key:jwk,format:'jwk'});
  return verify('RSA-SHA256',Buffer.from(p[0]+'.'+p[1]),pub,Buffer.from(p[2],'base64url'));
}
function s3auth(method,key,buffer){
  const region=process.env.AWS_REGION||'eu-central-1';
  const secret=process.env.AWS_SECRET_ACCESS_KEY,access=process.env.AWS_ACCESS_KEY_ID,origin=process.env.AWS_ENDPOINT_URL_S3;
  if(!secret||!access||!origin)throw Error('Storage not configured');
  const ep=new URL(origin);
  const uri=ep.pathname.replace(/\/$/,'')+'/videos/'+key.split('/').map(enc).join('/');
  const now=new Date().toISOString().replace(/[:-]|\.\d{3}/g,'');
  const day=now.slice(0,8),bodyhash=sha(buffer||Buffer.alloc(0));
  const headers={'x-amz-date':now,'x-amz-content-sha256':bodyhash};
  const signed='host;x-amz-content-sha256;x-amz-date';
  const canonical=[method,uri,'','host:'+ep.host+'\n'+'x-amz-content-sha256:'+bodyhash+'\n'+'x-amz-date:'+now+'\n',signed,bodyhash].join('\n');
  const scope=day+'/'+region+'/s3/aws4_request';
  const payload='AWS4-HMAC-SHA256\n'+now+'\n'+scope+'\n'+sha(Buffer.from(canonical));
  let k=hmac('AWS4'+secret,day);k=hmac(k,region);k=hmac(k,'s3');k=hmac(k,'aws4_request');
  headers.authorization='AWS4-HMAC-SHA256 Credential='+access+'/'+scope+', SignedHeaders='+signed+', Signature='+hmac(k,payload).toString('hex');
  return {url:ep.origin+uri,headers};
}
async function s3call(method,key,body){
  const auth=s3auth(method,key,body);
  const headers={...auth.headers};
  if(method==='PUT')headers['content-type']='video/mp4';
  const resp=await fetch(auth.url,{method,headers,body:method==='PUT'?body:undefined,signal:AbortSignal.timeout(65000)});
  if(!resp.ok){await resp.body?.cancel().catch(()=>{});throw Error('storage '+method+' failed '+resp.status)}
  if(method==='GET')return Buffer.from(await resp.arrayBuffer());
  await resp.body?.cancel().catch(()=>{});
}
export default {async fetch(req){
 if(req.method==='GET')return json({service:'mediaimport',ready:Boolean(process.env.AWS_ACCESS_KEY_ID&&process.env.AWS_SECRET_ACCESS_KEY&&process.env.AWS_ENDPOINT_URL_S3)});
 if(req.method!=='POST')return json({error:'method_not_allowed'},405);
 try{
  const auth=req.headers.get('authorization')||'';
  if(!auth.startsWith('Bearer ')||!(await verifyGitHub(auth.slice(7))))return json({error:'unauthorized'},401);
  const key=req.headers.get('x-mrx-object-key')||'';
  const size=Number(req.headers.get('x-mrx-object-size')||0);
  if(!/^shorts\/2026\/(?:0[1-9]|1[0-2])\/[0-3][0-9]\/[0-9]{10}-[a-zA-Z0-9._-]+\.mp4$/.test(key)||!Number.isInteger(size)||size<=0||size>MAX_BYTES)return json({error:'object_not_allowed'},403);
  if(Number(req.headers.get('content-length')||size)>MAX_BYTES)return json({error:'too_large'},413);
  const body=Buffer.from(await req.arrayBuffer());
  if(body.length!==size)return json({error:'size_mismatch'},400);
  const digest=sha(body);
  if(req.headers.get('x-mrx-sha256')!==digest)return json({error:'checksum_mismatch'},400);
  await s3call('PUT',key,body);
  const downloaded=await s3call('GET',key);
  if(downloaded.length!==size||sha(downloaded)!==digest)return json({error:'destination_mismatch'},502);
  return json({verified:true,bytes:size,key});
 }catch(e){console.error('mediaimport failed',String(e?.message||e).slice(0,120));return json({error:'migration_failed'},503)}
 }};