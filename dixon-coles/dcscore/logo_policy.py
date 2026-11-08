"""Minimal safe allowlist for externally supplied team crest URLs.

Avoid importing video libraries when running the forecast-only pipeline.
"""
from urllib.parse import urlparse

ALLOWED_LOGO_DOMAINS = frozenset({'crests.football-data.org', 'upload.wikimedia.org'})


def valid_logo_url(url: object) -> bool:
    if not isinstance(url,str) or not url or len(url)>500:
        return False
    try:
        p=urlparse(url)
        return (p.scheme=='https' and p.hostname in ALLOWED_LOGO_DOMAINS
                and not p.username and not p.password and p.port in (None,443)
                and not p.query and not p.fragment)
    except ValueError:
        return False
