"""Private Neon PostgreSQL bridge for the existing Actu Foot PostgREST call shapes.

Intentionally narrow: only explicitly approved tables and RPCs. No public API,
no legacy Supabase network fallback and no dynamic SQL identifiers from callers.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlsplit
import requests

TABLES = {
 "actu_foot_publications","actu_foot_live_events",
 "actu_foot_run_metrics","actu_foot_provider_health",
 "actu_foot_source_snapshots","live_stats_merged","matches_live",
 "actu_foot_news_snapshot","actu_foot_client_errors",
 "telegram_channel_metrics_daily","telegram_channel_official_stats",
 "telegram_channel_post_snapshots","telegram_channel_report_dispatch",
}
RPCS={"actu_foot_claim_publication","actu_foot_retryable_publications",
      "actu_foot_store_live_events"}

def _serialize(value):
 if hasattr(value,"isoformat"):return value.isoformat()
 if isinstance(value,dict):return {k:_serialize(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [_serialize(x) for x in value]
 return value

class Response:
 def __init__(self, rows, status=200):
  self._rows=_serialize(rows)
  self.status_code=status
  self.ok=status<400
  self.text=json.dumps(self._rows,ensure_ascii=False)
 def json(self):return self._rows
 def raise_for_status(self):
  if not self.ok:raise requests.HTTPError("Neon SQL operation failed")

class NeonRestSession:
 def __init__(self, fallback):
  self.fallback=fallback
 def get(self,url,**kwargs):return self._request("GET",url,**kwargs)
 def post(self,url,**kwargs):return self._request("POST",url,**kwargs)
 def patch(self,url,**kwargs):return self._request("PATCH",url,**kwargs)
 def delete(self,url,**kwargs):return self._request("DELETE",url,**kwargs)
 def _request(self,method,url,**kwargs):
  if not url.startswith("neon://private/rest/v1/"):
   return getattr(self.fallback,method.lower())(url,**kwargs)
  try:
   return _neon_query(method,url,kwargs.get("params") or {},kwargs.get("json"),kwargs.get("headers") or {})
  except Exception as exc:
   raise requests.RequestException("Neon database call failed: "+type(exc).__name__) from exc


def _filter_parts(params, allowed_columns):
 from psycopg import sql
 where=[];values=[]
 for name,raw in params.items():
  if name in {"select","limit","offset","order","on_conflict"}:continue
  if name not in allowed_columns:raise ValueError("Unsupported filter "+name)
  value=str(raw)
  if "." not in value:raise ValueError("Invalid filter")
  op,needle=value.split(".",1)
  if op in {"eq","gte","gt","lte","lt","neq"}:
   operator={"eq":"=","gte":">=","gt":">","lte":"<=","lt":"<","neq":"<>"}[op]
   if needle.lower()=="null" and op in {"eq","neq"}:
    where.append(sql.SQL("{} IS {}NULL").format(sql.Identifier(name),sql.SQL("NOT " if op=="neq" else "")))
   else:
    where.append(sql.SQL("{} "+operator+" %s").format(sql.Identifier(name)))
    values.append(needle)
  elif op=="in":
   choices=[z.strip() for z in needle.strip("()").split(",") if z.strip()]
   if not choices or len(choices)>60:raise ValueError("Invalid IN choices")
   where.append(sql.SQL("{} = ANY(%s)").format(sql.Identifier(name)))
   values.append(choices)
  else:raise ValueError("Unsupported filter op "+op)
 return where,values


def _neon_query(method,url,params,body,headers):
 import psycopg
 from psycopg import sql
 from psycopg.rows import dict_row
 from psycopg.types.json import Jsonb
 dsn=os.getenv("NEON_DATABASE_URL","").strip()
 if not dsn:raise RuntimeError("NEON_DATABASE_URL missing")
 segment=url.removeprefix("neon://private/rest/v1/").strip("/")
 if not segment or "/" in segment and not segment.startswith("rpc/"):
  raise ValueError("Unknown database path")
 with psycopg.connect(dsn,connect_timeout=12,row_factory=dict_row) as db:
  with db.cursor() as cur:
   if segment.startswith("rpc/"):
    name=segment[4:]
    if name not in RPCS or method!="POST" or not isinstance(body,dict):
     raise ValueError("Unauthorized Neon RPC")
    if name=="actu_foot_claim_publication":
     cur.execute("SELECT public.actu_foot_claim_publication(%s,%s,%s,%s,%s,%s) AS result",
      (body["p_event_key"],body["p_category"],body["p_payload_hash"],
       Jsonb(body["p_payload"]),body["p_expires_at"],body.get("p_max_attempts",5)))
     return Response(cur.fetchone()["result"])
    if name=="actu_foot_retryable_publications":
     cur.execute("SELECT * FROM public.actu_foot_retryable_publications(%s)",
                 (body.get("p_limit",20),))
     return Response(cur.fetchall())
    cur.execute("SELECT public.actu_foot_store_live_events(%s) AS result",
                (Jsonb(body["p_events"]),))
    return Response(cur.fetchone()["result"])
   table=segment
   if table not in TABLES:raise ValueError("Unauthorized Neon table: "+table)
   cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                  WHERE table_schema='public' AND table_name=%s""",(table,))
   types={r["column_name"]:r["data_type"] for r in cur.fetchall()}
   columns=set(types)
   def adapt(name,value):
    return Jsonb(value) if types.get(name) in {"json","jsonb"} else value
   if not columns:raise ValueError("Neon table unavailable: "+table)
   tab=sql.Identifier("public",table)
   if method=="GET":
    selected=str(params.get("select","*")).strip()
    names=list(columns) if selected=="*" else [n.strip() for n in selected.split(",")]
    if not names or not set(names).issubset(columns):raise ValueError("Unauthorized projection")
    wh,vals=_filter_parts(params,columns)
    query=sql.SQL("SELECT {} FROM {}").format(
      sql.SQL(",").join(sql.Identifier(x) for x in names),tab)
    if wh:query+=sql.SQL(" WHERE ")+sql.SQL(" AND ").join(wh)
    ordering=str(params.get("order","")).strip()
    if ordering:
     bits=ordering.split(",")
     if len(bits)>3:raise ValueError("Too many ORDER clauses")
     order=[]
     for bit in bits:
      pair=bit.split(".")
      if pair[0] not in columns:raise ValueError("Unauthorized ORDER column")
      if len(pair)>2 or len(pair)>1 and pair[1] not in {"asc","desc"}:
       raise ValueError("Invalid ORDER")
      order.append(sql.SQL("{} {}").format(sql.Identifier(pair[0]),sql.SQL(pair[1].upper() if len(pair)>1 else "ASC")))
     query+=sql.SQL(" ORDER BY ")+sql.SQL(",").join(order)
    query+=sql.SQL(" LIMIT %s OFFSET %s")
    vals.extend([max(1,min(int(params.get("limit",500)),2000)),max(0,int(params.get("offset",0)))])
    cur.execute(query,vals)
    return Response(cur.fetchall())
   if method=="POST":
    items=body if isinstance(body,list) else [body]
    if not items or not all(isinstance(x,dict) for x in items):raise ValueError("Expected JSON rows")
    conflict=str(params.get("on_conflict","")).strip()
    conflict_cols=[x.strip() for x in conflict.split(",") if x.strip()]
    if conflict_cols and not set(conflict_cols).issubset(columns):raise ValueError("Bad ON CONFLICT")
    results=[]
    for item in items:
     names=list(item.keys())
     if not names or not set(names).issubset(columns):raise ValueError("Unauthorized insert columns")
     vals=[adapt(x,item[x]) for x in names]
     query=sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
       tab,sql.SQL(",").join(map(sql.Identifier,names)),
       sql.SQL(",").join(sql.Placeholder() for _ in names))
     if conflict_cols:
      query+=sql.SQL(" ON CONFLICT ({}) DO UPDATE SET ").format(
        sql.SQL(",").join(map(sql.Identifier,conflict_cols)))
      mutable=[x for x in names if x not in conflict_cols]
      if not mutable:query=sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING").format(tab,sql.SQL(",").join(map(sql.Identifier,names)),sql.SQL(",").join(sql.Placeholder() for _ in names),sql.SQL(",").join(map(sql.Identifier,conflict_cols)))
      else:query+=sql.SQL(",").join(sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(n),sql.Identifier(n)) for n in mutable)
     pref=str(headers.get("Prefer",""))
     if "return=representation" in pref:query+=sql.SQL(" RETURNING *")
     cur.execute(query,vals)
     if "return=representation" in pref:results.extend(cur.fetchall())
    return Response(results,201)
   if method=="PATCH":
    if not isinstance(body,dict) or not body or not set(body).issubset(columns):
     raise ValueError("Unauthorized update columns")
    wh,vals=_filter_parts(params,columns)
    if not wh:raise ValueError("PATCH without filter forbidden")
    upd=list(body)
    query=sql.SQL("UPDATE {} SET {} WHERE {}").format(
      tab,sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(x)) for x in upd),
      sql.SQL(" AND ").join(wh))
    if "return=representation" in str(headers.get("Prefer","")):query+=sql.SQL(" RETURNING *")
    cur.execute(query,[adapt(x,body[x]) for x in upd]+vals)
    return Response(cur.fetchall() if "RETURNING" in query.as_string(db) else [])
   raise ValueError("Unsupported method "+method)
