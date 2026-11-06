"""Data contracts with explicit venue and result provenance."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc

RESULT_PROVENANCE = frozenset({
    "provider_reported",     # football-data.org: third-party reported, not independently certified
    "community_reported",    # OpenFootball: public community-maintained scores
    "csv_import",            # User-supplied data; its accuracy is not verified
    "manual_entry",          # User manually entered final score
    "manual_correction",     # Explicit audited score amendment
    "synthetic_demo",        # Clearly fictitious
})


def utc_datetime(value: str | datetime) -> datetime:
    """Require explicit UTC or timezone; never interpret a date as host-local."""
    if isinstance(value, datetime):
        date = value
    else:
        raw = str(value).strip()
        date = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("Une date doit contenir un fuseau horaire (ex. 2026-11-06T18:00:00Z).")
    return date.astimezone(UTC)


def iso_date(value: datetime) -> str:
    return utc_datetime(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def inferred_provenance(source: str) -> str:
    if source == "demo":
        return "synthetic_demo"
    if source == "football-data.org":
        return "provider_reported"
    if source == "openfootball/football.json":
        return "community_reported"
    if source == "csv":
        return "csv_import"
    return "manual_entry"


@dataclass(frozen=True)
class Match:
    id: str
    competition: str
    kickoff: datetime
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    status: str = "SCHEDULED"
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    season: str = ""
    source: str = "manual"
    neutral_venue: bool = False
    result_provenance: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "kickoff", utc_datetime(self.kickoff))
        if not self.id or not self.competition:
            raise ValueError("Identifiant et compétition obligatoires.")
        if not self.home_id or not self.away_id or self.home_id == self.away_id:
            raise ValueError("Les deux équipes doivent être distinctes et identifiées.")
        if not self.home_name or not self.away_name:
            raise ValueError("Le nom des équipes est obligatoire.")
        if type(self.neutral_venue) is not bool:
            raise ValueError("Le terrain neutre doit être un booléen explicite.")
        if self.status not in ("SCHEDULED", "FINISHED"):
            raise ValueError("Statut de rencontre inconnu.")
        if self.status == "FINISHED":
            for score in (self.home_goals, self.away_goals):
                if type(score) is not int or score < 0:
                    raise ValueError("Match terminé : scores entiers positifs ou nuls obligatoires.")
            provenance = self.result_provenance or inferred_provenance(self.source)
            if provenance not in RESULT_PROVENANCE:
                raise ValueError("Provenance du score non reconnue.")
            object.__setattr__(self, "result_provenance", provenance)
        else:
            if self.home_goals is not None or self.away_goals is not None:
                raise ValueError("Aucun score ne doit être fourni avant le résultat final.")
            if self.result_provenance is not None:
                raise ValueError("Une rencontre non terminée ne possède pas de résultat final.")

    def as_json(self) -> dict:
        out = asdict(self)
        out["kickoff"] = iso_date(self.kickoff)
        return out
