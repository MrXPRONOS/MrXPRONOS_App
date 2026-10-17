"""Séparer les épisodes TV des films simples quand le catalogue est actif."""
import re

SEASON_EP = re.compile(
    r"(?i)(?<![a-z0-9])(?:s\d{1,2}[\s._-]*e\d{1,3}|"
    r"s(?:aison|eason)[\s._-]*\d{1,2}[\s._-]*[eé](?:pisode|p)?[\s._-]*\d{1,3}|"
    r"\d{1,2}x\d{1,3})(?!\d)"
)
EP_ONLY = re.compile(
    r"(?i)(?<![a-z0-9])(?:[eé](?:pisode|p)?[\s._-]*0*\d{1,3})(?!\d)"
)
SEASON_ONLY = re.compile(
    r"(?i)(?<![a-z0-9])s(?:aison|eason)?[\s._-]*0*\d{1,2}(?!\d)"
)


def looks_like_tv_episode(*parts: str) -> bool:
    """Only explicit numbered episodes; never infer an episode from a title."""
    text = " ".join(str(p or "") for p in parts)
    if SEASON_EP.search(text):
        return True
    return EP_ONLY.search(text) is not None


def has_season_banner(text: str) -> bool:
    return bool(SEASON_ONLY.search(text or ""))
