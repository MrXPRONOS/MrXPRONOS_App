"""Bounded schema reconnaissance for public bookmaker JSON; no payload persistence."""
import re

TARGETS={"corners":re.compile(r"corners?|corner kicks?",re.I),
         "shots":re.compile(r"shots?|tirs?",re.I),
         "fouls":re.compile(r"fouls?|fautes?",re.I)}
SENSITIVE=re.compile(r"auth|token|secret|password|cookie|session|user|email|phone|api.?key|signature",re.I)
def inspect_json(obj, max_nodes=2500):
    stack=[(obj,0)];scanned=0; hits={k:0 for k in TARGETS}; signatures={}; examples=[]
    while stack and scanned<max_nodes:
        item,depth=stack.pop()
        scanned+=1
        if depth>10:continue
        if isinstance(item,dict):
            keys=tuple(sorted(str(k) for k in item if not SENSITIVE.search(str(k))))[:15]
            if keys:
                sig=",".join(keys)
                signatures[sig]=signatures.get(sig,0)+1
            for k,v in item.items():
                if SENSITIVE.search(str(k)):continue
                if isinstance(v,(dict,list)):stack.append((v,depth+1))
                elif isinstance(v,str) and len(v)<100 and str(k).lower() in ("name","desc","label","marketname","title","market"):
                    for kind,pat in TARGETS.items():
                        if pat.search(v):
                            hits[kind]+=1
                            if len(examples)<10 and v not in examples:examples.append(v)
        elif isinstance(item,list):
            stack.extend((v,depth+1) for v in item[:100] if isinstance(v,(dict,list)))
    return {"nodes_scanned":scanned,"label_hits":hits,"structure_count":len(signatures),
            "top_structures":[{"keys":k,"count":v} for k,v in sorted(signatures.items(),key=lambda kv:-kv[1])[:8]],
            "sample_market_labels":examples}
