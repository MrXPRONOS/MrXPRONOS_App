"""V3 protected retention policy, activation and all-collection operational preview."""
import argparse,json,os
from datetime import datetime,timezone,timedelta
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v3_atomic import GitAtomicStore
from scripts.actu_foot_v3_archive import SAFE_FIELDS,partition,compact_month
from scripts.actu_foot_v3_cloud_archive import CloudArchive,recover_inventory
from scripts.actu_foot_v3_service import production_check,inventory,audit_receipts
DEFAULT_DAYS={"matches":90,"live_events":30,"news":60,"statistics":120}
POLICY_ID="actufoot:v3:retention"
def policy():
    return {"type":"v3_retention_policy","days":DEFAULT_DAYS,"archive":"independent_verified_before_prune","schema":3}
def policy_active(value):
    return isinstance(value,dict) and all(value.get(k)==v for k,v in policy().items())

def maintenance(store,collection,*,retention_days,execute=False,confirmation="",durable_copy=None):
    if collection not in SAFE_FIELDS:raise VaultError("Retention forbidden")
    if type(retention_days) is not int or not 30<=retention_days<=3650:raise VaultError("Invalid retention period")
    cutoff=datetime.now(timezone.utc)-timedelta(days=retention_days)
    parent,_=store.head()
    state=store.load_collection(collection,parent)
    if not state.exists:raise VaultError("Missing initialized collection")
    _,groups=partition(state.data,date_field=SAFE_FIELDS[collection],cutoff=cutoff,collection=collection)
    selected=sum(len(v) for v in groups.values())
    if not execute:return {"collection":collection,"eligible":selected,"committed":False,"partitions":len(groups)}
    if confirmation!="APPROVE_V3_ENCRYPTED_COMPACTION":raise VaultError("Explicit confirmation required")
    result=compact_month(store,collection,field=SAFE_FIELDS[collection],cutoff=cutoff,durable_copy=durable_copy)
    return {"collection":collection,"eligible":selected,"committed":bool(result["commit"]),"moved":result["moved"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--collection",choices=("all",*SAFE_FIELDS),default="all")
    p.add_argument("--retention-days",type=int,default=0)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--activate",action="store_true")
    p.add_argument("--automatic",action="store_true")
    p.add_argument("--confirmation",default="")
    p.add_argument("--recover-archives",action="store_true")
    p.add_argument("--audit-file",default="")
    p.add_argument("--destination",default="/tmp/v3-archive-recovery")
    p.add_argument("--after",default="")
    args=p.parse_args()
    store=GitAtomicStore(repo=os.environ["GITHUB_REPOSITORY"],token=os.environ["GITHUB_TOKEN"])
    if args.automatic:
        if os.getenv("GITHUB_EVENT_NAME") not in {"schedule","push"} or os.getenv("GITHUB_REF")!="refs/heads/main":
            raise VaultError("Automatic retention requires trusted scheduled or main push workflow")
        if args.activate or args.execute or args.recover_archives or args.retention_days or args.confirmation or args.collection!="all" or args.audit_file or args.after:
            raise VaultError("Automatic retention cannot override the approved policy")
        args.execute=True
        args.confirmation="APPROVE_V3_ENCRYPTED_COMPACTION"
    if args.recover_archives:
        if args.execute or args.activate:raise VaultError("Archive recovery is isolated and cannot mutate live storage")
        if args.audit_file:
            from pathlib import Path
            from scripts.actu_foot_v2_store import decrypt
            audit,_=decrypt("audit",Path(args.audit_file).read_text(encoding="utf-8"))
            receipts=audit_receipts(audit)
        else:
            head,_=store.head();receipts=inventory(store,head)
        print("V3_ARCHIVE_RECOVERY",json.dumps(recover_inventory(receipts,args.destination,CloudArchive(),after=args.after),sort_keys=True))
        return
    if args.activate:
        if not args.execute or args.confirmation!="APPROVE_V3_ENCRYPTED_COMPACTION":raise VaultError("Activation requires approval")
        parent,_=store.head()
        current=store.load_collection("settings",parent)
        if not policy_active(current.data.get(POLICY_ID,{})):
            commit=store.transact({"settings":[{"action":"upsert","id":POLICY_ID,"value":policy()}]})
            print("V3_POLICY_ACTIVATED",commit)
    parent,_=store.head()
    active=store.load_collection("settings",parent).data.get(POLICY_ID,{})
    if args.execute and not policy_active(active):raise VaultError("Retention policy not activated")
    names=list(SAFE_FIELDS) if args.collection=="all" else [args.collection]
    results=[maintenance(store,name,retention_days=args.retention_days or DEFAULT_DAYS[name],execute=args.execute,
             confirmation=args.confirmation,durable_copy=CloudArchive().persist if args.execute else None) for name in names]
    print("V3_RETENTION_SUMMARY",json.dumps(results,sort_keys=True))
    report=production_check(store)
    print("V3_REAL_READ",json.dumps(report,sort_keys=True))
    output=os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as f:
            f.write("eligible="+str(sum(r["eligible"] for r in results))+"\n")
            f.write("active="+str(policy_active(active)).lower()+"\n")
if __name__=="__main__":main()
