#!/usr/bin/env python3
"""Publier un album quotidien Mr XPRONOS sur Telegram production sans doublon."""
import json,os,sys
from pathlib import Path
import requests
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"bsd"))
from bsd_v2_bluesky import claim
from send_accumulator_test import check_photo

def main():
 report=json.loads(Path(os.getenv("ACCUMULATOR_DATA_REPORT","telegram_out/accumulator_data_report.json")).read_text())
 day=report["day"];count=report["included"]
 if count<2:raise RuntimeError("Un album de combiné exige au moins deux rencontres")
 token=os.environ["TELEGRAM_BOT_TOKEN"].strip()
 chat=os.environ["TELEGRAM_CHAT_ID"].strip()
 if not token or not chat:raise RuntimeError("Configuration Telegram production absente")
 if not os.getenv("NEON_DATABASE_URL"):raise RuntimeError("NEON_DATABASE_URL obligatoire")
 base="";key=""
 preview=Path(os.getenv("ACCUMULATOR_PREVIEW","telegram_out/accumulator_preview.png"))
 complete=Path(os.getenv("ACCUMULATOR_OUTPUT","telegram_out/accumulator_reference.png"))
 check_photo(preview);check_photo(complete)
 session=requests.Session()
 ident=("accumulator_photo_telegram","mrxpronos:"+day,day)
 if not claim(session,base,key,ident):
  print("ACCUMULATOR_TELEGRAM_ALREADY_SENT",day);return
 media=[
  {"type":"photo","media":"attach://preview",
   "caption":f"⚽ Combiné du jour · Mr XPRONOS\n{count} sélections · Cote indicative : {report['combined_odds']}\nMise simulée : 50 000 F CFA.\n18+ · Joue responsablement."},
  {"type":"photo","media":"attach://full"}]
 with preview.open("rb") as a,complete.open("rb") as b:
  r=session.post("https://api.telegram.org/bot"+token+"/sendMediaGroup",
    data={"chat_id":chat,"media":json.dumps(media,ensure_ascii=False)},
    files={"preview":("combine-apercu.png",a,"image/png"),"full":("combine-complet.png",b,"image/png")},
    timeout=(10,120))
 r.raise_for_status()
 d=r.json()
 if d.get("ok") is not True or len(d.get("result") or [])!=2:
  raise RuntimeError("Album Telegram production non confirmé")
 print("ACCUMULATOR_TELEGRAM_PRODUCTION_SENT",json.dumps({"date":day,"count":count,"message_ids":[m["message_id"] for m in d["result"]]}))
if __name__=="__main__":main()
