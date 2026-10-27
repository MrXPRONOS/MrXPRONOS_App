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

ROMAN_SEQUELS = {"ii": "2", "iii": "3", "iv": "4", "v": "5",
                 "vi": "6", "vii": "7", "viii": "8", "ix": "9"}
YEAR = re.compile(r"(?<![0-9])(?:19[0-9]{2}|20[0-9]{2})(?![0-9])")

def release_year(text):
    return set(YEAR.findall(str(text or "")))

def tokens(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"https?://\\S+|t\\.me/\\S+|@[a-z0-9_]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    result = set()
    for word in text.split():
        if word in STOP:
            continue
        if word in ROMAN_SEQUELS:
            result.add(ROMAN_SEQUELS[word])
        elif word.isdigit() and len(word) <= 2:
            result.add(str(int(word)))
        elif len(word) > 2 and not word.isdigit():
            result.add(word)
    return result

def title_line(message):
    raw = str(getattr(message,"raw_text","") or "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for line in lines[:3]:
        if tokens(line):
            return line
    return lines[0] if lines else ""

def _compatible(a, b):
    """Require convincing agreement; a shared word is not enough."""
    if a == b:
        return True
    # A sequel number is discriminating even when the other title words match.
    # Require exactly the same short numeric markers on both sides.
    numeric_a = {w for w in a if w.isdigit()}
    numeric_b = {w for w in b if w.isdigit()}
    if numeric_a != numeric_b:
        return False
    common = len(a & b)
    return common >= 2 and 3 * common >= 2 * max(len(a), len(b))


def title_assessment(poster,video):
    """Return verified, mismatch or uncertain. Fail closed on conflicting evidence."""
    if poster is None or video is None:
        return "uncertain"
    related = (getattr(getattr(video, "reply_to", None), "reply_to_msg_id", None)
               == getattr(poster, "id", None) and getattr(poster, "id", None) is not None)
    pg = getattr(poster, "grouped_id", None)
    related = related or (pg is not None and pg == getattr(video, "grouped_id", None))
    a = tokens(title_line(poster))
    # Both a meaningful caption AND a meaningful filename must agree with the
    # poster. A matching caption must never override a contradictory filename.
    caption = title_line(video)
    filename = filename_of(video)
    evidence = [tokens(caption), tokens(filename)]
    evidence = [b for b in evidence if b]
    # Equal titles do not identify the same remake when years conflict.
    poster_years = release_year(title_line(poster))
    video_years = release_year(caption) | release_year(filename)
    if poster_years and video_years and poster_years.isdisjoint(video_years):
        return "uncertain" if related else "mismatch"
    if a and evidence:
        if all(_compatible(a, b) for b in evidence):
            return "verified"
        return "uncertain" if related else "mismatch"
    return "verified" if related else "uncertain"
