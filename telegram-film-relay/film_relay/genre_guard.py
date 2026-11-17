"""Strict explicit-category conflict detection for owner-authorized sources.

Genre inferred from source permissions ONLY if no contrary explicit tags exist.
Never guess genres from the movie's title, cast, or video appearance.
"""
import re
import unicodedata

GENRE_FIELD = re.compile(r"(?i)\b(?:genre|cat[eé]gorie|category|type)\s*[:=]\s*([^\n;|]{1,90})")
TAGS = re.compile(r"(?i)(?<!\w)#(comedie|com[eé]die|comedy|romance|romantique|romantic|anime|anim[eé])\b")
TYPES = re.compile(r"(?i)\bfilm\s+(?:de\s+)?(com[eé]die|romantique|romance|anime|anim[eé])\b")


def _normalize(value):
    return unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()


def explicit_genres(*texts):
    genres = set()
    for text in texts:
        value = str(text or "")
        fields = [m.group(1) for m in GENRE_FIELD.finditer(value)]
        tagged = [m.group(1) for m in TAGS.finditer(value)]
        types = [m.group(1) for m in TYPES.finditer(value)]
        for token in tagged + types:
            low = _normalize(token)
            if low in ("comedie", "comedy"):
                genres.add("comedie")
            elif low in ("romance", "romantique", "romantic"):
                genres.add("desir")
            elif low in ("anime", "anime"):
                genres.add("anime")
        for field in fields:
            low = _normalize(field)
            if re.search(r"\b(?:comedie|comedy)\b", low):
                genres.add("comedie")
            if re.search(r"\b(?:romance|romantique|romantic)\b", low):
                genres.add("desir")
            if re.search(r"\banime\b", low):
                genres.add("anime")
    return genres


def category_allowed(category, poster, video):
    captions = (
        str(getattr(poster, "raw_text", "") or ""),
        str(getattr(video, "raw_text", "") or ""),
    )
    tags = explicit_genres(*captions)
    if not tags:
        return True  # Existing source-specific authorization remains authoritative.
    return tags == {category}  # Mixed genres require explicit owner review.
