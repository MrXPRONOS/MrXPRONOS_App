"""Export real top-five crypto gainers for V2 visual; never publish here."""
import json
from datetime import datetime,timezone
from pathlib import Path
from crypto.publish_crypto_1_5 import market,movers

def main():
    rows,provider=market()
    top=movers(rows,"up")
    if len(top)!=5 or any(r["change"]<=0 for r in top):
        raise RuntimeError("Five real positive movers required")
    out=Path("crypto/generated/test/gainers_v2_data.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"timestamp":datetime.now(timezone.utc).isoformat(),
       "provider":provider,"rows":top},ensure_ascii=False),encoding="utf-8")
    print("GAINERS_V2_DATA",out,[(r["symbol"],r["change"]) for r in top])

if __name__=="__main__":main()
