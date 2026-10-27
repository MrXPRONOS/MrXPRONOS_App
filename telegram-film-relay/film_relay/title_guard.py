"""Conservative title evidence for Telegram poster/video pairs.

Missing or generic titles are not evidence. Proximity alone is never enough
for automatic redistribution; a reply/album is explicit structural evidence.
"""
import re
import unicodedata
from .matching import filename_of

STOP = {"film","movie","video","vf","vostfr","french","fr","hd","full","complet",
        "complete","mkv","mp4","1080p","720p","2026","2025","2024","partie",
        "part","episode","ep","saison","titre","nouveau","nouvelle","le","la",
        "les","un","une","des","de","du","et","en","the","of","a","and"}

def tokens(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii","ignore").decode().lower()
    text = re.sub(r"https?://\S+|t\.me/\S+|@[a-z0-9_]+", " ", text)
    text = re.sub(r"[^a-z0-9]+"," ",text)
    return {w for w in text.split() if len(w)>2 and w not in STOP and not w.isdigit()}

def title_line(message):
    raw = str(getattr(message,"raw_text","") or "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return lines[0] if lines else ""

def title_assessment(poster,video):
    """Return verified, mismatch or uncertain. Fail closed on weak evidence."""
    if poster is None or video is None:return "uncertain"
    related = (getattr(getattr(video,"reply_to",None),"reply_to_msg_id",None)
               == getattr(poster,"id",None) and getattr(poster,"id",None) is not None)
    pg = getattr(poster,"grouped_id",None)
    related = related or (pg is not None and pg==getattr(video,"grouped_id",None))
    a=tokens(title_line(poster))
    # A video caption is stronger than a filename; both are checked if meaningful.
    evidence=[tokens(title_line(video)),tokens(filename_of(video))]
    evidence=[b for b in evidence if b]
    if a and evidence:
        for b in evidence:
            if len(a & b)>=1 and (len(a & b)/min(len(a),len(b)))>=0.5:
                return "verified"
        return "mismatch" if not related else "uncertain"
    return "verified" if related else "uncertain"
