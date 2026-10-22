"""Publish brand emblem as the Free Pronos Telegram bot's profile photo.
Requires cairosvg and pillow. Only runs on explicit tagged deployment.
Does not reveal Telegram token or output image bytes in logs.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image
import cairosvg

PROJECT = Path(__file__).resolve().parents[1]
source = PROJECT / "assets/free-pronos-emblem.svg"
png = cairosvg.svg2png(url=str(source), output_width=1024, output_height=1024)
img = Image.open(io.BytesIO(png)).convert("RGB")
out = io.BytesIO()
img.save(out, format="JPEG", quality=94, optimize=True)
photo = out.getvalue()
assert 10000 < len(photo) < 4_000_000, "The avatar JPG is empty or unexpectedly large"
token = os.environ.get("XPRONOS_CF_BOT_TOKEN")
assert token, "Missing Telegram bot token"

boundary = "----FreePronos" + uuid.uuid4().hex
parts = []

def part(name, data, filename=None, mime="application/octet-stream"):
    headers = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
    if filename:
        headers += f"; filename=\"{filename}\""
    headers += f"\r\nContent-Type: {mime}\r\n\r\n"
    parts.append(headers.encode() + data + b"\r\n")

part("photo", json.dumps({"type": "static", "photo": "attach://avatar"}).encode(), mime="application/json")
part("avatar", photo, filename="free-pronos-avatar.jpg", mime="image/jpeg")
payload = b"".join(parts) + f"--{boundary}--\r\n".encode()
url = "https://api.telegram.org/bot" + token + "/setMyProfilePhoto"
request = urllib.request.Request(
    url, data=payload, method="POST",
    headers={"Content-Type": "multipart/form-data; boundary=" + boundary}
)
try:
    with urllib.request.urlopen(request, timeout=25) as response:
        answer = json.load(response)
except urllib.error.HTTPError as e:
    raise SystemExit("Telegram refused the profile image, HTTP " + str(e.code))
if not answer.get("ok"):
    raise SystemExit("Telegram did not accept Free Pronos avatar")
print("Free Pronos profile JPG installed successfully via Telegram Bot API.")
