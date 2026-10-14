#!/usr/bin/env python3
"""Private channel reports: one collection/day, protected by a DB lease."""
import asyncio,html,os,secrets,statistics
from datetime import datetime,timedelta,timezone
import requests
from telethon import TelegramClient,errors
from telethon.sessions import StringSession
from telethon.tl.types import Channel
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.stats import GetBroadcastStatsRequest
UTC=timezone.utc
def env(k):
 v=os.getenv(k,"").strip()
 if not v:raise RuntimeError("Missing "+k)
 return v
def n(x):
 try:return int(x) if x is not None else None
 except (TypeError,ValueError):return None
def f(x):return "—" if x is None else f"{x:,.0f}".replace(","," ")
def esc(x):return html.escape(str(x or ""),quote=True)
class DB:
 def __init__(self):
  self.base=env("SUPABASE_URL").rstrip("/")+"/rest/v1/"
  key=env("SUPABASE_SERVICE_ROLE_KEY")
  self.s=requests.Session();self.s.headers.update({"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/json"})
 def call(self,method,path,**kw):
  r=self.s.request(method,self.base+path,timeout=30,**kw);r.raise_for_status()
  return r.json() if r.content and r.text.strip() else None
 def rpc(self,name,**args):return self.call("POST","rpc/"+name,json=args)
 def read(self,table,**params):return self.call("GET",table,params=params) or []
 def put(self,table,rows,conflict):
  if rows:self.call("POST",table,params={"on_conflict":conflict},headers={"Prefer":"resolution=merge-duplicates,return=minimal"},json=rows)
 def history(self,id,day,window):
  start=(datetime.fromisoformat(day).date()-timedelta(days=window)).isoformat()
  return self.read("telegram_channel_metrics_daily",select="observed_on,subscriber_count",channel_id="eq."+str(id),observed_on="gte."+start,order="observed_on.asc")
def change(rows,now):
 if not rows or now is None or rows[0]["subscriber_count"] is None:return None
 return now-int(rows[0]["subscriber_count"])
def react(msg):
 x=getattr(msg,"reactions",None)
 return sum(n(getattr(r,"count",0)) or 0 for r in (getattr(x,"results",None) or [])) if x else None
async def collect(client,ch,db,day,now):
 subscribers=n(getattr(ch,"participants_count",None))
 try:
  full=await client(GetFullChannelRequest(ch));x=n(getattr(full.full_chat,"participants_count",None))
  if x is not None:subscribers=x
 except errors.FloodWaitError:raise
 except (errors.RPCError,ValueError) as e:print("COUNT_UNAVAILABLE",ch.id,type(e).__name__)
 messages=await client.get_messages(ch,limit=30)
 posts=[];seen=set()
 for m in messages:
  if getattr(m,"action",None) is not None or not getattr(m,"date",None):continue
  key=getattr(m,"grouped_id",None) or ("single",m.id)
  if key in seen:continue
  seen.add(key)
  posts.append(dict(channel_id=ch.id,post_id=m.id,observed_on=day,post_at=m.date.isoformat(),
   public_url=f"https://t.me/{ch.username}/{m.id}",views=n(getattr(m,"views",None)),
   forwards=n(getattr(m,"forwards",None)),reactions=react(m)))
  if len(posts)>=10:break
 db.put("telegram_channel_post_snapshots",posts,"channel_id,post_id,observed_on")
 values=[p["views"] for p in posts if p["views"] is not None]
 mature=[p["views"] for p in posts if p["views"] is not None and datetime.fromisoformat(p["post_at"])<=now-timedelta(hours=24)]
 last=posts[0] if posts else None
 prior=db.read("telegram_channel_metrics_daily",select="subscriber_count",channel_id="eq."+str(ch.id),
  observed_on="lt."+day,order="observed_on.desc",limit="1")
 prior_value=prior[0]["subscriber_count"] if prior else None
 daily=subscribers-int(prior_value) if subscribers is not None and prior_value is not None else None
 row=dict(channel_id=ch.id,observed_on=day,title=ch.title or "Canal",username=ch.username,
  public_url=f"https://t.me/{ch.username}",subscriber_count=subscribers,
  last_post_id=last["post_id"] if last else None,last_post_at=last["post_at"] if last else None,
  last_post_views=last["views"] if last else None,
  last_post_forwards=last["forwards"] if last else None,
  last_post_reactions=last["reactions"] if last else None,
  average_views_10=round(statistics.mean(values),2) if values else None,
  sampled_posts=len(values),mature_average_views=round(statistics.mean(mature),2) if mature else None,
  mature_sampled_posts=len(mature),
  posts_7d=sum(datetime.fromisoformat(p["post_at"])>=now-timedelta(days=7) for p in posts))
 db.put("telegram_channel_metrics_daily",[row],"channel_id,observed_on")
 return dict(**row,delta=daily,week=change(db.history(ch.id,day,7),subscribers),
  month=change(db.history(ch.id,day,30),subscribers),
  top=sorted((p for p in posts if p["views"] is not None),key=lambda p:p["views"],reverse=True)[:3])
def official_value(value):
 value=getattr(value,"current",value)
 return float(value) if isinstance(value,(int,float)) else None

def official_graph(value):
 import json
 graph=getattr(value,"json",None)
 if graph is None:return None
 try:
  content=json.loads(graph.data)
  return content if isinstance(content,(dict,list)) else None
 except (AttributeError,ValueError,TypeError):
  return None

async def official(client,ch,db,week):
 if db.read("telegram_channel_official_stats",select="status",channel_id="eq."+str(ch.id),week_start="eq."+week,limit="1"):return
 data=dict(channel_id=ch.id,week_start=week,status="unavailable")
 try:
  stats=await client(GetBroadcastStatsRequest(channel=ch,dark=False))
  data["status"]="ok"
  for k in ("views_per_post","shares_per_post","reactions_per_post"):
   x=official_value(getattr(stats,k,None))
   if x is not None:data[k]=x
  followers=getattr(stats,"followers",None)
  data["followers"]=n(getattr(followers,"current",None))
  previous=n(getattr(followers,"previous",None))
  if data["followers"] is not None and previous is not None:
   data["weekly_growth"]=data["followers"]-previous
  for name,attribute in (("hours_graph","top_hours_graph"),("source_graph","views_by_source_graph"),
                         ("followers_source_graph","new_followers_by_source_graph")):
   graph=official_graph(getattr(stats,attribute,None))
   if graph is not None:data[name]=graph
 except errors.FloodWaitError:raise
 except (errors.RPCError,ValueError,TypeError) as e:
  data["status"]="ineligible";data["error_class"]=type(e).__name__
 db.put("telegram_channel_official_stats",[data],"channel_id,week_start")
def card(r,i):
 d=r["delta"];direction=("🆕 Référence" if d is None else "🟢 +" +f(d) if d>0 else "🔴 −"+f(-d) if d<0 else "⚪ 0")
 recent=(f"https://t.me/{r['username']}/{r['last_post_id']}" if r["last_post_id"] else r["public_url"])
 reach=100*r["average_views_10"]/r["subscriber_count"] if r["average_views_10"] is not None and r["subscriber_count"] else None
 top="\n".join(f"🏅 <a href=\"{esc(p['public_url'])}\">Top {j}</a> : <b>{f(p['views'])}</b> vues" for j,p in enumerate(r["top"],1))
 before=r["subscriber_count"]-d if d is not None and r["subscriber_count"] is not None else None
 alert=("⚠️ <b>Baisse supérieure à 5 %</b>" if before and d/before<=-.05 else "🚀 <b>Hausse supérieure à 15 %</b>" if before and d/before>=.15 else "")
 return (f"\n<b>{i}. {esc(r['title'])}</b>\n<blockquote>🔗 <a href=\"{esc(r['public_url'])}\">Canal</a> · 👥 <b>{f(r['subscriber_count'])}</b>\n"
 f"📈 24h: <b>{direction}</b> · 7j: <b>{('+' if r['week']>0 else '')+f(r['week']) if r['week'] is not None else '—'}</b> · 30j: <b>{('+' if r['month']>0 else '')+f(r['month']) if r['month'] is not None else '—'}</b>\n"
 f"👁 <a href=\"{esc(recent)}\">Dernier post</a> : <b>{f(r['last_post_views'])}</b> vues\n"
 f"📊 <b>{f(r['average_views_10'])}</b> vues moyennes ({r['sampled_posts']} posts) · portée <b>{f(reach)} %</b>\n"
 f"⏳ 24h+ : <b>{f(r['mature_average_views'])}</b> vues moyennes · 📝 {r['posts_7d']} posts récents\n"
 f"{top}\n{alert}</blockquote>\n")
def parts(rows,now):
 head=f"📊 <b>MR XPRONOS · BILAN DES CANAUX</b>\n<i>{now.strftime('%d/%m/%Y')} · Rapport privé à 06h (Togo)</i>\n"
 result=[];current=head
 for i,row in enumerate(rows,1):
  b=card(row,i)
  if len(current)+len(b)>3600 and current!=head:result.append(current);current=head+"<i>Suite</i>\n"
  current+=b
 deltas=[r["delta"] for r in rows if r["delta"] is not None]
 summary=("\n<b>📌 SYNTHÈSE</b>\n<blockquote>"
 f"Canaux : <b>{len(rows)}</b>\nAbonnements cumulés : <b>{f(sum(r['subscriber_count'] or 0 for r in rows))}</b>\n"
 f"Variation nette : <b>{f(sum(deltas)) if deltas else 'Référence initiale'}</b> ({len(deltas)}/{len(rows)} comparables)\n"
 "<i>Les variations ne représentent pas séparément les entrées et sorties. Les vues évoluent avec le temps.</i></blockquote>")
 if len(current)+len(summary)>3800:result.append(current);current=head
 result.append(current+summary)
 return result
async def main():
 now=datetime.now(UTC);day=now.date().isoformat();owner=secrets.token_hex(20)
 test_mode=os.getenv("TELEGRAM_MONITOR_TEST_MODE","").strip().lower() in ("true","1","yes")
 db=DB()
 if not test_mode:
  prior_dispatch=db.read("telegram_channel_report_dispatch",select="status",report_on="eq."+day,limit="1")
  if prior_dispatch:
   print("SKIP_REPORT_ALREADY_RESERVED",day,prior_dispatch[0].get("status"))
   return
 status=db.rpc("telegram_monitor_acquire",p_owner=owner,p_minutes=25)
 if status!="ok":print("SKIP_LEASE",status);return
 cooldown=0;failure=None;client=None
 try:
  api=env("TG_API_ID")
  if not api.isdecimal():raise RuntimeError("Bad API id")
  client=TelegramClient(StringSession(env("TG_SESSION_STRING")),int(api),env("TG_API_HASH"),
    request_retries=0,connection_retries=2,flood_sleep_threshold=0,receive_updates=False)
  await client.connect()
  if not await client.is_user_authorized():raise RuntimeError("Telegram session not authorized")
  channels={}
  async for dialog in client.iter_dialogs():
   e=dialog.entity
   if isinstance(e,Channel) and e.broadcast and e.username and (e.creator or e.admin_rights is not None):
    channels[e.id]=e
  if not channels:raise RuntimeError("No public administered channels")
  print("DISCOVERED_CHANNELS",len(channels))
  week=(now.date()-timedelta(days=now.weekday())).isoformat()
  rows=[]
  for ch in sorted(channels.values(),key=lambda c:(c.title or "").casefold()):
   try:
    rows.append(await collect(client,ch,db,day,now))
    if now.weekday()==0:await official(client,ch,db,week)
   except errors.FloodWaitError:raise
   except (errors.RPCError,ValueError) as e:print("CHANNEL_SKIPPED",ch.id,type(e).__name__)
   await asyncio.sleep(2)
  if not rows:raise RuntimeError("No channel collected")
  print("SAVED_CHANNELS",len(rows))
  if not test_mode:
   if not db.rpc("telegram_monitor_reserve_report",p_on=day,p_owner=owner,p_count=len(rows)):
    print("REPORT_ALREADY_RESERVED",day);return
  sent=[]
  for part in parts(rows,now):
   if test_mode:
    part="🧪 <b>TEST RÉEL V2 — MR XPRONOS</b>\n<i>Déclenchement manuel, distinct du bilan quotidien.</i>\n\n"+part
   sent.append(await client.send_message("me",part,parse_mode="html",link_preview=False))
   await asyncio.sleep(1)
  if test_mode:
   print("PRIVATE_TEST_SENT",day,len(rows),"messages",len(sent))
  else:
   db.call("PATCH","telegram_channel_report_dispatch",
    params={"report_on":"eq."+day,"reservation_owner":"eq."+owner},
    json={"status":"sent","message_id":sent[-1].id})
   print("PRIVATE_REPORT_SENT",day,len(rows))
 except errors.FloodWaitError as e:
  cooldown=min(604800,max(60,n(e.seconds) or 60)+120);failure="FloodWaitError"
  raise RuntimeError("Telegram requested cooldown; no retry") from e
 except Exception as e:
  failure=type(e).__name__;raise
 finally:
  if client:await client.disconnect()
  db.rpc("telegram_monitor_release",p_owner=owner,p_cooldown_seconds=cooldown,p_error=failure)
if __name__=="__main__":asyncio.run(main())
