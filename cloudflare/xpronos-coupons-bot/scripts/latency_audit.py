#!/usr/bin/env python3
"""Read-only timing from GitHub runner to production Cloudflare Worker."""
import argparse,hashlib,hmac,json,os,statistics,time,urllib.error,urllib.parse,urllib.request
p=argparse.ArgumentParser();p.add_argument('--phase',default='baseline');p.add_argument('--samples',type=int,default=10);a=p.parse_args()
url=os.environ.get('WORKER_URL','https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev').rstrip('/')
token=os.getenv('XPRONOS_CF_BOT_TOKEN','');admin=os.getenv('CF_BOT_ADMIN_IDS','').split(',')[0].strip()
auth=''
if token and admin.isdecimal():
 d={'auth_date':str(int(time.time())),'user':json.dumps({'id':int(admin),'first_name':'Audit'},separators=(',',':'))}
 k=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
 d['hash']=hmac.new(k,'\n'.join(f'{x}={y}' for x,y in sorted(d.items())).encode(),hashlib.sha256).hexdigest()
 auth=urllib.parse.urlencode(d)
endpoints=[('health','/health',False),('app','/app',False),('logo','/brand.svg',False),('auth_denied','/api/me',False)]
if auth:
 endpoints += [('dashboard','/api/me',True),('coupons','/api/coupons?category=ALL',True),('missions','/api/tasks',True),('history','/api/history',True),('results','/api/results',True),('support','/api/mytickets',True),('admin','/api/admin/overview',True)]
def nth(values,p):
 v=sorted(values)
 return round(v[min(len(v)-1,max(0,int(len(v)*p+0.999999)-1))],1) if v else None
def run(path,private):
 hdr={'User-Agent':'FreePronos-Latency-Audit/1.0','Accept':'application/json,text/html,*/*'}
 if private:hdr['X-Telegram-Init-Data']=auth
 start=time.perf_counter()
 try:
  with urllib.request.urlopen(urllib.request.Request(url+path,headers=hdr),timeout=15) as response:
   ttfb=1000*(time.perf_counter()-start);body=response.read()
   return (response.status,round(ttfb,1),round(1000*(time.perf_counter()-start),1),len(body))
 except urllib.error.HTTPError as err:
  first=1000*(time.perf_counter()-start);err.read(512)
  return (err.code,round(first,1),round(1000*(time.perf_counter()-start),1),0)
 except Exception as err:
  return (0,None,None,0)
metrics={}
for label,path,private in endpoints:
 items=[run(path,private) for _ in range(max(3,a.samples)+1)][1:]
 statuses={str(code):sum(z[0]==code for z in items) for code in sorted(set(x[0] for x in items))}
 wanted=401 if label=='auth_denied' else 200
 good=[x for x in items if x[0]==wanted]
 metrics[label]={'statuses':statuses,'samples':len(items),'ttfb_p50_ms':nth([x[1] for x in good],.5),'ttfb_p95_ms':nth([x[1] for x in good],.95),'total_p50_ms':nth([x[2] for x in good],.5),'total_p95_ms':nth([x[2] for x in good],.95),'bytes_median':int(statistics.median([x[3] for x in good])) if good else None}
 print(f"{label:13} status={str(statuses):18} p50={str(metrics[label]['total_p50_ms']):>7}ms p95={str(metrics[label]['total_p95_ms']):>7}ms ttfb={str(metrics[label]['ttfb_p50_ms']):>7}ms bytes={metrics[label]['bytes_median']}")
with open('latency-report.json','w') as output:json.dump({'phase':a.phase,'network':'GitHub Actions Ubuntu -> Cloudflare Worker, not Togo','authenticated':bool(auth),'measurements':metrics},output,indent=2)
