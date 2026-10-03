#!/usr/bin/env python3
"""Audit a consistent legacy SQLite snapshot; export private evidence explicitly.

No provider requests or PostgreSQL writes. Use SQLite's online backup API or a
stopped-service snapshot, never copy an active WAL database. Preview is default.
"""

import argparse
import contextlib
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import sqlite3
import sys

MAX_ID = 2**63 - 1
FORMAT = "georelay-legacy-identities-v1"


class AuditError(ValueError):
    pass


def canonical(value, limit):
    if not isinstance(value, str) or len(value) > 2050:
        raise AuditError("invalid_coordinates")
    try:
        number = Decimal(value)
        if (not number.is_finite() or number.copy_abs() > limit
                or not -1024 <= number.as_tuple().exponent <= 1024
                or len(number.as_tuple().digits) > 1024):
            raise AuditError("invalid_coordinates")
        # Decimal.normalize() follows the active precision; fixed formatting does
        # not round even evidence with more than 28 significant digits.
        if number == 0:
            return "0"
        result = format(number, "f")
        return result.rstrip("0").rstrip(".") if "." in result else result
    except (InvalidOperation, ValueError):
        raise AuditError("invalid_coordinates") from None


def audit(path, *, legacy_osm_implies_outside=False):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise AuditError("snapshot_required")
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise AuditError("consistent_snapshot_required")
    try:
        with contextlib.closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise AuditError("sqlite_integrity_failed")
            schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='identities'").fetchone()
            columns = {row[1] for row in db.execute("PRAGMA table_info(identities)")}
            if not schema or "AUTOINCREMENT" not in schema[0].upper() or not {"id", "lat", "lon"} <= columns:
                raise AuditError("unsupported_legacy_schema")
            source_columns = {"source_osm_type", "source_osm_id"}
            if columns & source_columns and not source_columns <= columns:
                raise AuditError("unsupported_legacy_schema")
            has_sources = source_columns <= columns
            has_outside = "outside_mainland" in columns
            if has_sources and not has_outside and not legacy_osm_implies_outside:
                raise AuditError("legacy_region_evidence_required")
            source_sql = "source_osm_type,source_osm_id" if has_sources else "NULL,NULL"
            outside_sql = "outside_mainland" if has_outside else "NULL"
            rows = db.execute(f"SELECT id,lat,lon,{source_sql},{outside_sql} FROM identities ORDER BY id").fetchall()
            sequence = db.execute("SELECT seq FROM sqlite_sequence WHERE name='identities'").fetchall()
            if len(sequence) > 1:
                raise AuditError("invalid_allocation_high_water")
            high_water = sequence[0][0] if sequence else 0
            if type(high_water) is not int or not 0 <= high_water < MAX_ID:
                raise AuditError("identity_range_exhausted")
            identities, ids, points = [], set(), set()
            for identity, lat, lon, source_type, source_id, outside in rows:
                if type(identity) is not int or not 0 < identity <= high_water or identity in ids:
                    raise AuditError("invalid_allocation_high_water")
                lat, lon = canonical(lat, 90), canonical(lon, 180)
                if (lat, lon) in points:
                    raise AuditError("duplicate_canonical_coordinates")
                source_present = source_type is not None or source_id is not None
                if source_present and (source_type not in {"node", "way", "relation"}
                                       or type(source_id) is not int or not 0 < source_id <= MAX_ID):
                    raise AuditError("invalid_provenance")
                if has_outside and (type(outside) is not int or outside not in (0, 1)):
                    raise AuditError("invalid_region_evidence")
                confirmed_outside = bool(outside) if has_outside else bool(source_present and legacy_osm_implies_outside)
                if confirmed_outside and not source_present:
                    raise AuditError("invalid_region_evidence")
                context = {"outside_mainland": confirmed_outside}
                if source_present:
                    context.update(source_osm_type=source_type, source_osm_id=source_id)
                identities.append({"osm_id": -identity, "osm_type": "node", "lat": lat,
                                   "lon": lon, "context": context})
                ids.add(identity)
                points.add((lat, lon))
    except sqlite3.Error:
        raise AuditError("sqlite_audit_failed") from None
    return {"format": FORMAT, "allocated_high_water": high_water, "identities": identities}


def export_evidence(path, payload):
    """Never overwrite evidence and never make exact coordinates world-readable."""
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, help="private evidence file, never overwritten")
    parser.add_argument("--export", action="store_true", help="explicitly write the audited evidence")
    parser.add_argument("--legacy-osm-implies-outside", action="store_true",
                        help="attest the known pre-outside_mainland GeoRelay schema contract")
    args = parser.parse_args()
    if args.export and args.output is None:
        parser.error("--export requires --output")
    try:
        payload = audit(args.snapshot, legacy_osm_implies_outside=args.legacy_osm_implies_outside)
        if args.export:
            export_evidence(args.output, payload)
        print(json.dumps({"mode": "exported" if args.export else "preview",
                          "identities": len(payload["identities"]),
                          "allocated_high_water": payload["allocated_high_water"]}, sort_keys=True))
    except AuditError as exc:
        print("Legacy audit failed: " + str(exc), file=sys.stderr)
        return 1
    except OSError:
        print("Legacy audit failed: evidence_io_failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
