import os,json,hashlib,sys
from urllib.parse import quote
import requests,boto3
from botocore.config import Config
inventory=json.load(open("migration/free-stack/media-inventory.json"))
assert len(inventory)==113 and sum(int(x["size"]) for x in inventory)==215013480
endpoint=os.environ["NEON_S3_ENDPOINT"]
s3=boto3.client("s3",endpoint_url=endpoint,region_name="eu-central-1",aws_access_key_id=os.environ["NEON_S3_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["NEON_S3_SECRET_ACCESS_KEY"],config=Config(s3={"addressing_style":"path"}))
done=[]
for item in inventory:
    key=item["name"]
    assert not key.startswith("/") and ".." not in key.split("/")
    url="https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/"+quote(key,safe="/")
    response=requests.get(url,timeout=120)
    response.raise_for_status()
    data=response.content
    assert len(data)==int(item["size"]), "Source object size mismatch"
    sha=hashlib.sha256(data).hexdigest()
    s3.put_object(Bucket="videos",Key=key,Body=data,ContentType="video/mp4")
    actual=s3.get_object(Bucket="videos",Key=key)["Body"].read()
    assert len(actual)==len(data) and hashlib.sha256(actual).hexdigest()==sha, "Destination hash mismatch"
    done.append({"name":key,"bytes":len(data),"sha256":sha})
    print("verified",len(done),"/",len(inventory),flush=True)
print("DONE",len(done))
