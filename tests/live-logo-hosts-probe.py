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
