from __future__ import annotations
import json, urllib.request, urllib.error, time
from datetime import datetime
LEAGUES=['uefa.wchampions','eng.trophy','esp.copa_del_rey','eng.w.1','esp.w.1','uefa.w.eurocup']
PERIODS=['20261110','20261001-20261108','20250801-20260531','20240801-20250531']
def fetch(league,dates):
 url=f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={dates}&limit=400'
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; MrXpronos/1.0)'}),timeout=16) as response: data=json.load(response)
  events=data.get('events') or []
  finished=[e for e in events if (e.get('status') or {}).get('type',{}).get('completed') is True]
  sample=[]
  for e in events[:2]:
   comp=(e.get('competitions') or [{}])[0]
   sample.append({'id':e.get('id'),'date':e.get('date'),'name':e.get('name'),'status':(e.get('status') or {}).get('type',{}).get('name'),
     'teams':[{'id':(x.get('team') or {}).get('id'),'name':(x.get('team') or {}).get('displayName'),'logo':(x.get('team') or {}).get('logo')} for x in (comp.get('competitors') or [])]})
  return {'count':len(events),'completed':len(finished),'first':sample,'league':((data.get('leagues') or [{}])[0]).get('name')}
 except Exception as e: return {'error':f'{type(e).__name__}: {str(e)[:100]}'}
for league in LEAGUES:
 for dates in PERIODS:
  result=fetch(league,dates)
  print('PROBE',json.dumps({'league':league,'dates':dates,**result},ensure_ascii=False),flush=True)
