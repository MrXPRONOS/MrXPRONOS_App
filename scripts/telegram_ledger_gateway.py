"""Cloudflare D1 ledger gateway with GitHub OIDC. Safe for publication locks.

Never fail over a timed-out claim to another database: the original claim
might have succeeded, and a second reservation would permit duplicate posts.
"""
import os
from urllib.parse import quote
import requests

LEDGER_URL = "https://mrxpronos-telegram-ledger-staging.cinecanaux-xpronos.workers.dev"
AUDIENCE = "mrxpronos-telegram-ledger"

class LedgerError(RuntimeError):
    pass

def oidc_token(session=requests):
    url = os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not url or not bearer:
        raise LedgerError("GitHub OIDC unavailable; publication aborted")
    try:
        separator = "&" if "?" in url else "?"
        r = session.get(url + separator + "audience=" + quote(AUDIENCE),
                        headers={"Authorization": "Bearer " + bearer}, timeout=14)
        r.raise_for_status()
        token = r.json().get("value")
    except (requests.RequestException, ValueError, AttributeError) as exc:
        raise LedgerError("GitHub OIDC token request failed") from exc
    if not isinstance(token, str) or not token:
        raise LedgerError("Empty GitHub OIDC token")
    return token

class Ledger:
    def __init__(self, *, session=requests, endpoint=LEDGER_URL, token=None):
        if not endpoint.startswith("https://"):
            raise LedgerError("HTTPS ledger endpoint required")
        self.session = session
        self.endpoint = endpoint.rstrip("/")
        self.token = token if token is not None else oidc_token(session)

    def _call(self, operation, kind, ref_id, ref_date, *, message_id=None):
        if operation not in ("claim", "release", "mark"):
            raise ValueError("Unknown ledger operation")
        if not all(isinstance(v, str) and v.strip() for v in (kind, ref_id, ref_date)):
            raise ValueError("Non-empty ledger key required")
        payload = {"kind": kind, "ref_id": ref_id, "ref_date": ref_date}
        if message_id is not None:
            payload["telegram_message_id"] = int(message_id)
        try:
            response = self.session.post(
                self.endpoint + "/" + operation, json=payload,
                headers={"Authorization": "Bearer " + self.token,
                         "Accept": "application/json"}, timeout=18)
            if response.status_code != 200:
                raise LedgerError("Ledger " + operation + " rejected HTTP " + str(response.status_code))
            body = response.json()
            if not isinstance(body, dict):
                raise LedgerError("Malformed ledger response")
            return body
        except requests.RequestException as exc:
            raise LedgerError("Uncertain ledger response; do not send or retry automatically") from exc
        except ValueError as exc:
            raise LedgerError("Malformed ledger JSON response") from exc

    def claim(self, kind, ref_id, ref_date):
        result = self._call("claim", kind, ref_id, ref_date)
        if type(result.get("claimed")) is not bool:
            raise LedgerError("Missing atomic claim decision")
        return result["claimed"]

    def release(self, kind, ref_id, ref_date):
        result = self._call("release", kind, ref_id, ref_date)
        return result.get("released") is True

    def mark(self, kind, ref_id, ref_date, *, message_id):
        result = self._call("mark", kind, ref_id, ref_date, message_id=message_id)
        if result.get("marked") is not True:
            raise LedgerError("Ledger delivery acknowledgement missing")
        return True
