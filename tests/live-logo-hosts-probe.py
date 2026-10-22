import urllib.request, urllib.error
urls=[
 ("espn_1","https://a.espncdn.com/i/teamlogos/ncaa/500/2066.png"),
 ("espn_2","https://a.espncdn.com/i/teamlogos/ncaa/500/2885.png"),
 ("sportscore_1","https://img.thesports.com/football/team/8fa50258352c8079c5fcc2f31a77a0ce.png"),
 ("sportscore_2","https://img.thesports.com/football/team/eed5c3c3c14be4180be2114f1eda1890.png")
]
failures=0
for label,url in urls:
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; MrXPRONOS-LIVE-Legal-Logo-Check/1.0)","Accept":"image/avif,image/webp,image/png,image/jpeg,*/*"})
  with urllib.request.urlopen(req,timeout=15) as r:
   b=r.read(128)
   png=b.startswith(b"\x89PNG\r\n\x1a\n")
   jpg=b.startswith(b"\xff\xd8")
   webp=b.startswith(b"RIFF") and b[8:12]==b"WEBP"
   ok=r.status==200 and (png or jpg or webp)
   print(label,"status",r.status,"mime",r.headers.get("content-type"),"valid_image",ok,"final_url",r.url,flush=True)
   if not ok:failures+=1
 except urllib.error.HTTPError as e:
  print(label,"HTTP",e.code,flush=True);failures+=1
 except Exception as e:
  print(label,type(e).__name__,str(e)[:160],flush=True);failures+=1
print("MISSING_OR_BLOCKED",failures)
assert failures==0,"Some real LIVE image hosts did not provide valid images; investigate an allowed cache/proxy."

print("LIVE_SITE_CHECK")
url="https://mrxpronos.github.io/MrXPRONOS_App/live.html"
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=16) as r:
  html=r.read().decode(errors="replace")
  assert "assets/js/live.precompiled.js?v=20261022-real-logos1" in html,"published live.html still points to old script"
  print("GITHUB_PAGES_NEW_BUNDLE",r.status)
except Exception as e:
 print("PAGES_ERROR",type(e).__name__,str(e)[:250]);raise
api="https://br-winter-truth-b9of9tss-live.compute.c-7.eu-central-1.aws.neon.tech/matches"
try:
 import json
 with urllib.request.urlopen(urllib.request.Request(api,headers={"Accept":"application/json"}),timeout=22) as r:
  body=json.load(r)
  matches=body.get("matches") or []
  paired=sum(bool(x.get("home_logo")) and bool(x.get("away_logo")) for x in matches)
  print("NEON_LIVE_MATCHES",len(matches),"WITH_LOGO_PAIRS",paired,"status",r.status)
  if matches: assert paired>0,"Neon /matches does not provide team logos"
except Exception as e:
 print("NEON_LOGO_CHECK_ERROR",type(e).__name__,str(e)[:250]);raise
