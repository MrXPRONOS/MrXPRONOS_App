import {createHash,createHmac,createPublicKey,verify} from 'node:crypto';
const ALLOWED={"shorts/2026/06/22/1782148091-daily_pronos_shorts.mp4":2315495,"shorts/2026/06/23/1782187150-daily_pronos_shorts.mp4":2422602,"shorts/2026/06/24/1782273626-daily_pronos_shorts.mp4":2696759,"shorts/2026/06/25/1782359961-daily_pronos_shorts.mp4":1871507,"shorts/2026/06/26/1782447470-daily_pronos_shorts.mp4":1784956,"shorts/2026/06/27/1782532850-daily_pronos_shorts.mp4":2668627,"shorts/2026/06/28/1782620026-daily_pronos_shorts.mp4":2401595,"shorts/2026/06/29/1782706929-daily_pronos_shorts.mp4":543317,"shorts/2026/06/30/1782792012-daily_pronos_shorts.mp4":980253,"shorts/2026/07/01/1782879067-daily_pronos_shorts.mp4":95494,"shorts/2026/07/02/1782964491-daily_pronos_shorts.mp4":95494,"shorts/2026/07/03/1783049608-daily_pronos_shorts.mp4":95494,"shorts/2026/07/04/1783135573-daily_pronos_shorts.mp4":95494,"shorts/2026/07/05/1783222918-daily_pronos_shorts.mp4":95494,"shorts/2026/07/06/1783309837-daily_pronos_shorts.mp4":95494,"shorts/2026/07/07/1783395674-daily_pronos_shorts.mp4":95494,"shorts/2026/07/08/1783479430-daily_pronos_shorts.mp4":95494,"shorts/2026/07/09/1783568137-daily_pronos_shorts.mp4":95494,"shorts/2026/07/10/1783654592-daily_pronos_shorts.mp4":95494,"shorts/2026/07/11/1783738324-daily_pronos_shorts.mp4":95494,"shorts/2026/07/12/1783825320-daily_pronos_shorts.mp4":95494,"shorts/2026/07/13/1783911707-daily_pronos_shorts.mp4":95494,"shorts/2026/07/14/1783997014-daily_pronos_shorts.mp4":95494,"shorts/2026/07/15/1784083290-daily_pronos_shorts.mp4":95494,"shorts/2026/07/16/1784170147-daily_pronos_shorts.mp4":95494,"shorts/2026/07/17/1784258511-daily_pronos_shorts.mp4":95741,"shorts/2026/07/18/1784342611-daily_pronos_shorts.mp4":95494,"shorts/2026/07/19/1784429993-daily_pronos_shorts.mp4":95494,"shorts/2026/07/20/1784517974-daily_pronos_shorts.mp4":95494,"shorts/2026/07/21/1784602546-daily_pronos_shorts.mp4":95494,"shorts/2026/07/22/1784688735-daily_pronos_shorts.mp4":95494,"shorts/2026/07/23/1784775550-daily_pronos_shorts.mp4":95490,"shorts/2026/07/24/1784861607-daily_pronos_shorts.mp4":95659,"shorts/2026/07/25/1784947964-daily_pronos_shorts.mp4":95505,"shorts/2026/07/26/1785034881-daily_pronos_shorts.mp4":95372,"shorts/2026/07/27/1785122781-daily_pronos_shorts.mp4":95152,"shorts/2026/07/28/1785206684-daily_pronos_shorts.mp4":95585,"shorts/2026/07/29/1785293486-daily_pronos_shorts.mp4":96019,"shorts/2026/07/30/1785379066-daily_pronos_shorts.mp4":95504,"shorts/2026/07/31/1785467208-daily_pronos_shorts.mp4":95802,"shorts/2026/08/01/1785553289-daily_pronos_shorts.mp4":95253,"shorts/2026/08/02/1785639628-daily_pronos_shorts.mp4":95424,"shorts/2026/08/03/1785726131-daily_pronos_shorts.mp4":95831,"shorts/2026/08/04/1785811608-daily_pronos_shorts.mp4":95450,"shorts/2026/08/05/1785897904-daily_pronos_shorts.mp4":95514,"shorts/2026/08/06/1785984427-daily_pronos_shorts.mp4":95622,"shorts/2026/08/06/1786034184-daily_pronos_shorts.mp4":2397678,"shorts/2026/08/07/1786071532-daily_pronos_shorts.mp4":2387849,"shorts/2026/08/08/1786154489-daily_pronos_shorts.mp4":2429758,"shorts/2026/08/09/1786241239-daily_pronos_shorts.mp4":2401623,"shorts/2026/08/10/1786327647-daily_pronos_shorts.mp4":2517120,"shorts/2026/08/11/1786413990-daily_pronos_shorts.mp4":2738529,"shorts/2026/08/12/1786500998-daily_pronos_shorts.mp4":2647885,"shorts/2026/08/13/1786587592-daily_pronos_shorts.mp4":2476377,"shorts/2026/08/14/1786674273-daily_pronos_shorts.mp4":2389269,"shorts/2026/08/15/1786758051-daily_pronos_shorts.mp4":2342009,"shorts/2026/08/16/1786844379-daily_pronos_shorts.mp4":2439039,"shorts/2026/08/17/1786930414-daily_pronos_shorts.mp4":2529210,"shorts/2026/08/19/1787103052-daily_pronos_shorts.mp4":2380057,"shorts/2026/08/20/1787189475-daily_pronos_shorts.mp4":2390714,"shorts/2026/08/21/1787277505-daily_pronos_shorts.mp4":2426932,"shorts/2026/08/23/1787450741-daily_pronos_shorts.mp4":2419870,"shorts/2026/08/24/1787536094-daily_pronos_shorts.mp4":2536121,"shorts/2026/08/25/1787622463-daily_pronos_shorts.mp4":2420576,"shorts/2026/08/26/1787708892-daily_pronos_shorts.mp4":2438740,"shorts/2026/08/30/1788065639-daily_pronos_shorts.mp4":2391330,"shorts/2026/08/31/1788151568-daily_pronos_shorts.mp4":2467484,"shorts/2026/09/01/1788236796-daily_pronos_shorts.mp4":2411143,"shorts/2026/09/02/1788320854-daily_pronos_shorts.mp4":2456572,"shorts/2026/09/03/1788407864-daily_pronos_shorts.mp4":2356891,"shorts/2026/09/04/1788494439-daily_pronos_shorts.mp4":2448776,"shorts/2026/09/06/1788667546-daily_pronos_shorts.mp4":2360640,"shorts/2026/09/07/1788753300-daily_pronos_shorts.mp4":2327038,"shorts/2026/09/08/1788840044-daily_pronos_shorts.mp4":2355293,"shorts/2026/09/09/1788926748-daily_pronos_shorts.mp4":2414741,"shorts/2026/09/10/1789012974-daily_pronos_shorts.mp4":2487388,"shorts/2026/09/11/1789098829-daily_pronos_shorts.mp4":2379949,"shorts/2026/09/12/1789185924-daily_pronos_shorts.mp4":2411878,"shorts/2026/09/13/1789272366-daily_pronos_shorts.mp4":2329333,"shorts/2026/09/14/1789359300-daily_pronos_shorts.mp4":2412160,"shorts/2026/09/15/1789445093-daily_pronos_shorts.mp4":2415589,"shorts/2026/09/16/1789531438-daily_pronos_shorts.mp4":2456005,"shorts/2026/09/17/1789618416-daily_pronos_shorts.mp4":2422320,"shorts/2026/09/18/1789704035-daily_pronos_shorts.mp4":2476519,"shorts/2026/09/19/1789790778-daily_pronos_shorts.mp4":2379054,"shorts/2026/09/20/1789877763-daily_pronos_shorts.mp4":2356930,"shorts/2026/09/21/1789963585-daily_pronos_shorts.mp4":2466222,"shorts/2026/09/22/1790049830-daily_pronos_shorts.mp4":2487760,"shorts/2026/09/23/1790135806-daily_pronos_shorts.mp4":2447103,"shorts/2026/09/24/1790221853-daily_pronos_shorts.mp4":2451432,"shorts/2026/09/25/1790309288-daily_pronos_shorts.mp4":2609435,"shorts/2026/09/26/1790396002-daily_pronos_shorts.mp4":2415650,"shorts/2026/09/27/1790482987-daily_pronos_shorts.mp4":2539033,"shorts/2026/09/28/1790569603-daily_pronos_shorts.mp4":2662013,"shorts/2026/09/29/1790657863-daily_pronos_shorts.mp4":2361848,"shorts/2026/09/30/1790743396-daily_pronos_shorts.mp4":2342163,"shorts/2026/10/01/1790830498-daily_pronos_shorts.mp4":2307159,"shorts/2026/10/02/1790916337-daily_pronos_shorts.mp4":2403679,"shorts/2026/10/03/1791001822-daily_pronos_shorts.mp4":2425024,"shorts/2026/10/04/1791090067-daily_pronos_shorts.mp4":2598340,"shorts/2026/10/05/1791175668-daily_pronos_shorts.mp4":2384002,"shorts/2026/10/06/1791264856-daily_pronos_shorts.mp4":2403780,"shorts/2026/10/07/1791349387-daily_pronos_shorts.mp4":2371304,"shorts/2026/10/17/1792269031-daily_pronos_coupon_short.mp4":8127459,"shorts/2026/10/18/1792339659-validation-2026-10-18-evening.mp4":6908770,"shorts/2026/10/18/1792344549-daily_pronos_coupon_short.mp4":6929738,"shorts/2026/10/19/1792373480-validation-2026-10-18-morning.mp4":5688195,"shorts/2026/10/19/1792424562-daily_pronos_coupon_short.mp4":2547913,"shorts/2026/10/20/1792503549-daily_pronos_coupon_short.mp4":4095305,"shorts/2026/10/20/1792515711-daily_pronos_coupon_short.mp4":8200528,"shorts/2026/10/20/1792532577-daily_pronos_coupon_short.mp4":4137695,"shorts/2026/10/21/1792583709-daily_pronos_coupon_short.mp4":4110611,"shorts/2026/10/21/1792604228-validation-2026-10-21-evening.mp4":4145522};
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
  const size=ALLOWED[key];
  if(!Number.isInteger(size)||size<=0||size>MAX_BYTES)return json({error:'object_not_allowed'},403);
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