#!/usr/bin/env python3
"""Private Telegram channel monitoring using GitHub-versioned JSON only."""
import asyncio,html,os,statistics,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
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
STATE = Path(__file__).resolve().parents[1] / "telegram-film-relay" / "state" / "channel_monitor.json"
METRICS = "telegram_channel_metrics_daily"
OFFICIAL = "telegram_channel_official_stats"

class DB:
 """Local JSON-backed history committed by GitHub Actions, never an HTTP database."""
 def __init__(self, path=None):
  self.path=Path(path) if path is not None else STATE
  if self.path.exists():
   self.data=json.loads(self.path.read_text(encoding="utf-8"))
  else:
   self.data={"schema":1,"tables":{},"reports":{}}
  if self.data.get("schema")!=1:raise RuntimeError("Unsupported channel monitor state schema")
  self.data.setdefault("tables",{})
  self.data.setdefault("reports",{})

 def read(self,table,**params):
  if table not in (METRICS,OFFICIAL):raise ValueError("Unknown GitHub state table: "+table)
  rows=list(self.data["tables"].get(table,[]))
  for key,criterion in params.items():
   if key in ("select","order","limit"):continue
   operator,sep,expected=str(criterion).partition(".")
   if not sep or operator not in ("eq","lt","gte"):
    raise ValueError("Unsupported local filter")
   def matches(row):
    actual=row.get(key)
    if actual is None:return False
    a,b=str(actual),str(expected)
    return a==b if operator=="eq" else a<b if operator=="lt" else a>=b
   rows=[r for r in rows if matches(r)]
  order=params.get("order")
  if order:
   key,_,way=str(order).partition(".")
   rows.sort(key=lambda row:str(row.get(key) or ""),reverse=way=="desc")
  if params.get("limit"):rows=rows[:int(params["limit"])]
  if params.get("select") and params["select"]!="*":
   keys=str(params["select"]).split(",")
   rows=[{k:v for k,v in item.items() if k in keys} for item in rows]
  return rows

 def put(self,table,rows,conflict):
  if not rows:return
  # Post snapshots are only needed to render today's report, not for long-term
  # subscriber trends. Avoid bloating the GitHub JSON with copied Telegram posts.
  if table=="telegram_channel_post_snapshots":return
  if table not in (METRICS,OFFICIAL):raise ValueError("Unknown GitHub state table: "+table)
  keys=tuple(str(conflict).split(","))
  entries={tuple(str(r.get(k)) for k in keys):r for r in self.data["tables"].get(table,[])}
  for row in rows:
   key=tuple(str(row.get(k)) for k in keys)
   entries[key]={**entries.get(key,{}),**row}
  self.data["tables"][table]=list(entries.values())

 def history(self,identifier,day,window):
  start=(datetime.fromisoformat(day).date()-timedelta(days=window)).isoformat()
  return self.read(METRICS,select="observed_on,subscriber_count",channel_id="eq."+str(identifier),
                   observed_on="gte."+start,order="observed_on.asc")

 def report(self,day):
  return self.data["reports"].setdefault(day,{"status":"pending","parts":{}})

 def mark_part(self,day,index,message_id):
  self.report(day)["parts"][str(index)]=int(message_id)
  self.save()

 def mark_complete(self,day,parts,channels):
  report=self.report(day)
  if set(report["parts"]) != {str(i) for i in range(1, parts+1)}:raise RuntimeError("Incomplete Telegram report")
  report["status"]="sent"
  report["channels_count"]=channels
  report["sent_at"]=datetime.now(UTC).isoformat()
  self.save()

 def save(self):
  # Keep 40 days for 30-day growth; retain recent weekly official stats.
  cutoff=(datetime.now(UTC)-timedelta(days=40)).date().isoformat()
  recent=self.data["tables"].get(METRICS,[])
  self.data["tables"][METRICS]=[r for r in recent if str(r.get("observed_on",""))>=cutoff]
  cutoff_off=(datetime.now(UTC)-timedelta(days=120)).date().isoformat()
  recent=self.data["tables"].get(OFFICIAL,[])
  self.data["tables"][OFFICIAL]=[r for r in recent if str(r.get("week_start",""))>=cutoff_off]
  self.data["reports"]={d:v for d,v in self.data["reports"].items() if d>=cutoff}
  self.path.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.path.with_name(self.path.name+".tmp")
  tmp.write_text(json.dumps(self.data,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
  tmp.replace(self.path)

def change(rows,now,reference_day=None):
 # A same-day observation is not a historical comparison baseline.
 if reference_day is not None:
  rows=[r for r in rows if str(r.get("observed_on","")) < reference_day]
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
  if len(posts)>=30:break
 db.put("telegram_channel_post_snapshots",posts,"channel_id,post_id,observed_on")
 # Engagement averages use the ten newest posts, while the activity counter
 # draws on up to thirty. Counts from partial samples are lower bounds.
 sample=posts[:10]
 values=[p["views"] for p in sample if p["views"] is not None]
 mature=[p["views"] for p in sample if p["views"] is not None and datetime.fromisoformat(p["post_at"])<=now-timedelta(hours=24)]
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
  posts_7d=sum(datetime.fromisoformat(p["post_at"])>=now-timedelta(days=7) for p in posts),
  scanned_posts=len(posts))
 db.put("telegram_channel_metrics_daily",[row],"channel_id,observed_on")
 return dict(**row,delta=daily,week=change(db.history(ch.id,day,7),subscribers,day),
  month=change(db.history(ch.id,day,30),subscribers,day),
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
 f"⏳ 24h+ : <b>{f(r['mature_average_views'])}</b> vues moyennes · 📝 ≥{r['posts_7d']} posts sur échantillon de {r.get('scanned_posts',10)}\n"
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
MARKER_PREFIX = "#MRX_CANAL_"

def marker(day,index,testing=False):
 return MARKER_PREFIX + ("TEST_" if testing else "") + day.replace("-","") + "_" + f"{index:02d}"

async def existing_parts(client,day,testing=False):
 """Reconcile successful Telegram sends not yet committed to GitHub."""
 prefix=MARKER_PREFIX+("TEST_" if testing else "")+day.replace("-","")+"_"
 found={}
 async for msg in client.iter_messages("me",limit=120):
  body=str(getattr(msg,"raw_text","") or "")
  for value in body.split():
   if value.startswith(prefix) and value[len(prefix):].isdigit():
    index=int(value[len(prefix):])
    found.setdefault(str(index),int(msg.id))
 return found

async def main():
 now=datetime.now(UTC);day=now.date().isoformat()
 test_mode=os.getenv("TELEGRAM_MONITOR_TEST_MODE","").strip().lower() in ("true","1","yes")
 dry_run=os.getenv("TELEGRAM_MONITOR_DRY_RUN","").strip().lower() in ("true","1","yes")
 if dry_run and test_mode:raise RuntimeError("Dry-run and private live test are mutually exclusive")
 db=DB()
 if not dry_run and not test_mode and db.report(day).get("status")=="sent":
  print("SKIP_REPORT_ALREADY_SENT_GITHUB",day)
  return
 api=env("TG_API_ID")
 if not api.isdecimal():raise RuntimeError("Bad Telegram API id")
 session=(os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or "").strip()
 if not session:raise RuntimeError("Missing Telegram session")
 client=TelegramClient(StringSession(session),int(api),env("TG_API_HASH"),
   request_retries=0,connection_retries=2,flood_sleep_threshold=0,receive_updates=False)
 try:
  await client.connect()
  if not await client.is_user_authorized():raise RuntimeError("Telegram session not authorized")
  remote_parts={} if dry_run else await existing_parts(client,day,test_mode)
  if not test_mode and remote_parts:
   for index,msgid in remote_parts.items():
    if index not in db.report(day)["parts"]:
     db.mark_part(day,index,msgid)
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
   await asyncio.sleep(4)
  if not rows:raise RuntimeError("No channel collected")
  if dry_run:
   print("DRY_RUN_READ_ONLY",day,"administered_channels",len(channels),"collected",len(rows))
   return
  db.save()
  messages=parts(rows,now)
  for index,body in enumerate(messages,1):
   if test_mode:
    body="🧪 <b>TEST RÉEL V2 — MR XPRONOS</b>\n<i>Déclenchement manuel, distinct du bilan quotidien.</i>\n\n"+body
   if str(index) in remote_parts or (not test_mode and str(index) in db.report(day)["parts"]):
    print("RECONCILED_PRIVATE_PART",day,index)
    continue
   tag=marker(day,index,test_mode)
   sent=await client.send_message("me",body+"\n\n<code>"+tag+"</code>",
                     parse_mode="html",link_preview=False)
   if not test_mode:
    db.mark_part(day,index,sent.id)
   print("PRIVATE_PART_SENT",day,index,int(sent.id))
   await asyncio.sleep(2)
  if test_mode:
   print("PRIVATE_TEST_SENT",day,len(rows),"messages",len(messages))
  else:
   db.mark_complete(day,len(messages),len(rows))
   print("PRIVATE_REPORT_SENT_GITHUB",day,len(rows),"messages",len(messages))
 except errors.FloodWaitError as e:
  raise RuntimeError("Telegram requested FloodWait, no automatic retry") from e
 finally:
  if not dry_run:db.save()
  await client.disconnect()

if __name__=="__main__":
 asyncio.run(main())
