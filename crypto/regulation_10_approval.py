"""#10: produce publicly usable cards only from explicit, recent editorial approvals.

A candidate's stage is inferred from its *title* and is never approval.
A human must check the source text, jurisdiction, effective date and exceptions.
The approval record must be committed to the repository by an authorized editor.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from crypto import export_regulation_v2 as reg

UTC = timezone.utc
APPROVALS = Path("crypto/regulation_10_approvals.json")
CANDIDATE = Path("crypto/generated/test/regulation_v2_candidate.json")
OUTPUT = Path("crypto/generated/test/regulation_v2_approved.json")
APPROVED_STAGES = {
    "CONSULTATION", "PROPOSITION", "ADOPTION ANNONCÉE",
    "ENTRÉE EN VIGUEUR ANNONCÉE", "SANCTION / DÉCISION",
}
OFFICIAL_HOSTS = {
    "SEC": {"sec.gov"},
    "ESMA": {"esma.europa.eu"},
    "Commission européenne": {"ec.europa.eu", "commission.europa.eu"},
}


def official_url(source: str, url: str) -> str:
    # Force an official primary text, not a media article passed as evidence.
    from urllib.parse import urlsplit, urlunsplit
    u = urlsplit(str(url))
    host = (u.hostname or "").lower().removeprefix("www.")
    if (source not in OFFICIAL_HOSTS or host not in OFFICIAL_HOSTS[source]
            or u.scheme != "https" or u.username or u.password
            or u.port not in (None, 443) or len(u.path) < 9):
        raise ValueError("Invalid official legal primary-source URL")
    return urlunsplit(("https", u.hostname.lower(), u.path.rstrip("/"), "", ""))


def approved_report(candidate: dict, approval: dict, now: datetime | None = None):
    now = now or datetime.now(UTC)
    reg.validate_candidate(candidate, now)
    a = candidate["primary"]
    if (approval.get("candidate_fingerprint") != candidate["fingerprint"]
            or approval.get("source_url") != a["url"]):
        raise ValueError("Approval is not for this exact selected RSS article")
    if approval.get("human_approved") is not True:
        raise ValueError("Explicit human editorial approval required")
    for check in ("jurisdiction_checked", "stage_checked", "effective_date_checked",
                  "primary_text_checked", "exceptions_checked"):
        if approval.get(check) is not True:
            raise ValueError("Legal review item not confirmed: " + check)
    for key, lo, hi in (
        ("approved_by", 4, 80), ("title_fr", 35, 135),
        ("summary_fr", 60, 340), ("jurisdiction", 4, 95),
        ("review_note", 20, 300)):
        value = approval.get(key)
        if not isinstance(value, str) or not lo <= len(value.strip()) <= hi or re.search(r"[<>]", value):
            raise ValueError("Missing/unusable human-reviewed field " + key)
    stage = approval.get("verified_stage")
    if stage not in APPROVED_STAGES:
        raise ValueError("Legislative stage must be verified and specific")
    effective = approval.get("effective_date")
    if stage == "ENTRÉE EN VIGUEUR ANNONCÉE":
        try:
            datetime.strptime(effective, "%Y-%m-%d")
        except (TypeError, ValueError):
            raise ValueError("Effective legal date must be verified") from None
    elif effective != "non_applicable":
        # Unknown date should not be invented by the application.
        raise ValueError("Non-effective stage requires 'non_applicable' date")
    official_source = approval.get("official_source")
    official_primary = official_url(official_source, approval.get("official_url", ""))
    signed_at = datetime.fromisoformat(str(approval.get("reviewed_at", "")).replace("Z", "+00:00"))
    if signed_at.tzinfo is None or not 0 <= (now - signed_at).total_seconds() <= 72 * 3600:
        raise ValueError("Editorial approval timestamp absent, stale or future")
    return {
        "publication": 10, "status": "editorially_approved", "is_demo": False,
        "collected_at": now.isoformat(), "primary": a,
        "fingerprint": candidate["fingerprint"], "human_approved": True,
        "approval": {
            "title_fr": approval["title_fr"].strip(),
            "summary_fr": approval["summary_fr"].strip(),
            "jurisdiction": approval["jurisdiction"].strip(),
            "verified_stage": stage,
            "effective_date": effective,
            "approved_by": approval["approved_by"].strip(),
            "reviewed_at": signed_at.isoformat(),
            "official_source": official_source,
            "official_url": official_primary,
        },
    }


def run() -> bool:
    OUTPUT.unlink(missing_ok=True)
    if not CANDIDATE.exists():
        print("REG10_NO_CANDIDATE_NO_PUBLICATION")
        return False
    approvals = json.loads(APPROVALS.read_text(encoding="utf-8"))
    if not isinstance(approvals, dict) or not isinstance(approvals.get("approved"), list):
        raise ValueError("Broken editor approval list")
    d = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    matches = [x for x in approvals["approved"]
               if isinstance(x, dict) and x.get("candidate_fingerprint") == d.get("fingerprint")]
    if len(matches) != 1:
        print("REG10_HOLD_EDITORIAL_APPROVAL", d.get("fingerprint"), "matched",len(matches))
        return False
    public = approved_report(d, matches[0])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REG10_HUMAN_APPROVED", public["fingerprint"], public["approval"]["official_source"])
    return True


if __name__ == "__main__":
    run()
