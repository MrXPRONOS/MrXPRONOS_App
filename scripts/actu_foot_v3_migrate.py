"""V3 conservative in-memory schema migration.

V2 encrypted file formats remain unchanged. Migration happens on decrypted
objects and is only committed through an explicit reviewed atomic Git operation.
"""
from __future__ import annotations
import copy
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import validate_records

TARGET_VERSION=3


def upgrade(collection: str, records: dict, *, from_version: int=2,
            to_version: int=TARGET_VERSION) -> dict:
    if type(from_version) is not int or from_version not in (2,3):
        raise VaultError("Unknown source schema")
    if type(to_version) is not int or to_version!=TARGET_VERSION:
        raise VaultError("Unknown target schema")
    validate_records(collection,records)
    output=copy.deepcopy(records)
    if from_version==2:
        for key,row in output.items():
            # Don't invent event IDs, dates, statistics or publication state.
            # Preserve all existing producer-defined keys, add private schema marker.
            if "_schema_version" in row and row["_schema_version"] not in (2,3):
                raise VaultError("Unknown record schema marker")
            row["_schema_version"]=3
    validate_records(collection,output)
    return output


def downgrade(collection: str, records: dict, *, from_version: int=3,
              to_version: int=2) -> dict:
    if from_version!=3 or to_version!=2:
        raise VaultError("Unsupported reverse migration")
    validate_records(collection,records)
    output=copy.deepcopy(records)
    for item in output.values():
        if item.get("_schema_version") != 3:
            raise VaultError("Reverse migration needs a V3 marker")
        del item["_schema_version"]
    validate_records(collection,output)
    return output


def migration_preview(collection: str, records: dict) -> dict:
    converted=upgrade(collection,records)
    # Dry-run roundtrip validates no loss of original data.
    if downgrade(collection,converted)!=records:
        raise VaultError("Migration roundtrip failed")
    return {"collection":collection,"records":len(records),"reversible":True,
            "target_version":TARGET_VERSION}
