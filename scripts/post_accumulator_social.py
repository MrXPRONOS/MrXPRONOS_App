#!/usr/bin/env python3
"""Photo du coupon quotidien sur Facebook, Instagram et Threads.
Publie UNIQUEMENT la couverture recadrée, jamais YouTube.
Registre anti-doublon Cloudflare D1 avec un kind propre par plateforme.
"""
import io, json, os, sys, time
from pathlib import Path
import requests
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"bsd"))
from d1_publication_ledger import D1Ledger

def need(name):
 value=os.getenv(name,"").strip()
 if not value:raise RuntimeError("Configuration absente: "+name)
 return value

def post(url,**kwargs):
 r=requests.post(url,timeout=90,**kwargs)
 if not r.ok:raise RuntimeError("API HTTP "+str(r.status_code)+" "+str(r.text)[:180])
 d=r.json()
 if d.get("error"):raise RuntimeError("API provider: "+str(d["error"].get("message","erreur")))
 return d

def public_url(image,day):
 base=need("SUPABASE_URL").rstrip("/")
 key=need("SUPABASE_SERVICE_ROLE_KEY")
 bucket=os.getenv("SUPABASE_BUCKET","videos")
 obj="images/mrxpronos-combine/"+day+"/preview.jpg"
 buffer=io.BytesIO()
 with Image.open(image) as im:
  rgb=im.convert("RGB")
  rgb.save(buffer,"JPEG",quality=88,optimize=True)
 url=base+"/storage/v1/object/"+bucket+"/"+obj
 r=requests.post(url,headers={"apikey":key,"Authorization":"Bearer "+key,
   "Content-Type":"image/jpeg","x-upsert":"true"},data=buffer.getvalue(),timeout=120)
 if not r.ok:raise RuntimeError("Upload photo publique: HTTP "+str(r.status_code))
 public=base+"/storage/v1/object/public/"+bucket+"/"+obj
 check=requests.get(public,timeout=30)
 if check.status_code!=200 or not check.headers.get("content-type","").startswith("image/"):
  raise RuntimeError("Bucket photo non public / photo non accessible")
 return public

def publish(platform,public,image,caption):
 if platform=="facebook":
  with open(image,"rb") as photo:
   d=post("https://graph.facebook.com/v25.0/"+need("META_PAGE_ID")+"/photos",
       data={"message":caption,"access_token":need("META_PAGE_ACCESS_TOKEN")},
       files={"source":("combine.jpg",photo,"image/jpeg")})
  return str(d["id"])
 if platform=="instagram":
  user=need("IG_USER_ID");token=need("META_ACCESS_TOKEN")
  d=post("https://graph.facebook.com/v25.0/"+user+"/media",
       data={"image_url":public,"caption":caption,"access_token":token})
  creation=str(d["id"])
  for i in range(12):
   response=requests.get("https://graph.facebook.com/v25.0/"+creation,
     params={"fields":"status_code","access_token":token},timeout=20)
   response.raise_for_status();state=response.json().get("status_code")
   if state=="FINISHED":break
   if state in ("ERROR","EXPIRED"):raise RuntimeError("Instagram processing: "+str(state))
   time.sleep(5)
  else:raise RuntimeError("Instagram photo container not ready")
  d=post("https://graph.facebook.com/v25.0/"+user+"/media_publish",
    data={"creation_id":creation,"access_token":token})
  return str(d["id"])
 if platform=="threads":
  user=need("THREADS_USER_ID");token=need("THREADS_ACCESS_TOKEN")
  d=post("https://graph.threads.net/v1.0/"+user+"/threads",
    data={"media_type":"IMAGE","image_url":public,"text":caption,"access_token":token})
  creation=str(d["id"])
  for i in range(12):
   r=requests.get("https://graph.threads.net/v1.0/"+creation,
    params={"fields":"status","access_token":token},timeout=20)
   r.raise_for_status();state=r.json().get("status")
   if state=="FINISHED":break
   if state in ("ERROR","EXPIRED"):raise RuntimeError("Threads processing: "+str(state))
   time.sleep(5)
  else:raise RuntimeError("Threads image not ready")
  d=post("https://graph.threads.net/v1.0/"+user+"/threads_publish",
    data={"creation_id":creation,"access_token":token})
  return str(d["id"])
 raise ValueError("Plateforme interdite: "+platform)

def main():
 report=json.loads(Path(os.getenv("ACCUMULATOR_DATA_REPORT","telegram_out/accumulator_data_report.json")).read_text())
 day=report["day"]
 image=Path(os.getenv("ACCUMULATOR_SOCIAL_IMAGE","telegram_out/accumulator_preview.jpg"))
 if not image.exists():raise RuntimeError("Aperçu JPEG absent")
 odds=report["combined_odds"];count=report["included"]
 caption=(f"⚽ Combiné Mr XPRONOS · {day}\n{count} sélections · Cote indicative : {odds}\n"
          "Mise simulée : 50 000 F CFA.\n"
          "18+ · Joue responsablement.\n#football #pronostics #mrxpronos")
 public=None
 ledger=D1Ledger()
 results=[];failures=[]
 for platform in ("facebook","instagram","threads"):
  identity=("accumulator_photo_"+platform,day,day)
  try:
   if not ledger.claim(*identity):
    print("ACCUMULATOR_SOCIAL_ALREADY_SENT",platform,day)
    results.append({"platform":platform,"status":"already_sent"});continue
   # Après claim, ne pas relancer en cas d'erreur réseau ambiguë (protection anti-doublon).
   # Facebook accepts the image bytes directly. Only IG/Threads need a URL.
   if platform!="facebook" and public is None:
    public=public_url(image,day)
   pid=publish(platform,public,image,caption)
   ledger.mark(*identity)
   results.append({"platform":platform,"status":"sent","id":pid})
   print("ACCUMULATOR_SOCIAL_SENT",platform,pid)
  except Exception as exc:
   failures.append(platform);results.append({"platform":platform,"status":"error","type":type(exc).__name__})
   print("ACCUMULATOR_SOCIAL_FAILED",platform,type(exc).__name__,str(exc)[:140])
 Path("telegram_out/accumulator_social_results.json").write_text(json.dumps(results,indent=2))
 if failures:raise RuntimeError("Échecs publications sociales: "+",".join(failures))
if __name__=="__main__":main()
