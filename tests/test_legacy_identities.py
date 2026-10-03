"""Legacy allocation evidence is audited offline without exposing coordinates."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "legacy", Path(__file__).resolve().parents[1] / "scripts/export_legacy_identities.py"
)
legacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(legacy)


class LegacyIdentitiesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot = self.root / "old.sqlite"
        self.output = self.root / "evidence.json"
        with sqlite3.connect(self.snapshot) as db:
            db.execute("CREATE TABLE identities(id INTEGER PRIMARY KEY AUTOINCREMENT, lat TEXT NOT NULL, lon TEXT NOT NULL, source_osm_type TEXT, source_osm_id INTEGER, outside_mainland INTEGER NOT NULL DEFAULT 0, UNIQUE(lat,lon))")
            db.execute("INSERT INTO identities VALUES(1,'48.858400123','2.294500456','way',42,1)")
            db.execute("INSERT INTO identities VALUES(10,'48.858400124','2.294500457',NULL,NULL,0)")
            db.execute("INSERT INTO identities VALUES(100,'0','0',NULL,NULL,0)")
            db.execute("DELETE FROM identities WHERE id=100")

    def test_complete_sequence_includes_deleted_and_unreferenced_allocations(self):
        result = legacy.audit(self.snapshot)
        self.assertEqual(result["allocated_high_water"], 100)
        self.assertEqual([r["osm_id"] for r in result["identities"]], [-1, -10])
        self.assertEqual(result["identities"][0]["context"],
                         {"source_osm_type": "way", "source_osm_id": 42, "outside_mainland": True})
        legacy.export_evidence(self.output, result)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertEqual(json.loads(self.output.read_text()), result)
        with self.assertRaises(FileExistsError):
            legacy.export_evidence(self.output, result)

    def test_preview_never_writes_evidence_or_prints_exact_data(self):
        before = self.snapshot.read_bytes()
        out = io.StringIO()
        with patch.object(sys, "argv", ["export", str(self.snapshot), "--output", str(self.output)]), contextlib.redirect_stdout(out):
            self.assertEqual(legacy.main(), 0)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot.read_bytes(), before)
        self.assertEqual(json.loads(out.getvalue()), {"mode": "preview", "identities": 2,
                                                     "allocated_high_water": 100})
        self.assertNotIn("48.8584", out.getvalue())

    def test_exact_normalization_does_not_round_long_decimal(self):
        self.assertEqual(legacy.canonical("1.123456789012345678901234567890123000", 90),
                         "1.123456789012345678901234567890123")
        self.assertEqual(legacy.canonical("-0.000", 90), "0")
        self.assertEqual(legacy.canonical("4.8858400123e1", 90), "48.858400123")
        self.assertEqual(legacy.canonical("1e-1024", 90), "0." + "0" * 1023 + "1")
        with self.assertRaisesRegex(legacy.AuditError, "invalid_coordinates"):
            legacy.canonical("1e-1025", 90)

    def test_legacy_region_inference_requires_explicit_known_schema_assertion(self):
        with sqlite3.connect(self.snapshot) as db:
            db.execute("ALTER TABLE identities DROP COLUMN outside_mainland")
        with self.assertRaisesRegex(legacy.AuditError, "legacy_region_evidence_required"):
            legacy.audit(self.snapshot)
        result = legacy.audit(self.snapshot, legacy_osm_implies_outside=True)
        self.assertTrue(result["identities"][0]["context"]["outside_mainland"])
        self.assertFalse(result["identities"][1]["context"]["outside_mainland"])

    def test_invalid_coordinate_source_region_or_high_water_stops(self):
        for sql, reason in [
            ("UPDATE identities SET lat='NaN' WHERE id=1", "invalid_coordinates"),
            ("UPDATE identities SET lat='91' WHERE id=1", "invalid_coordinates"),
            ("UPDATE identities SET lat='90.000000000000000000000000000001' WHERE id=1", "invalid_coordinates"),
            ("UPDATE identities SET source_osm_id=-1 WHERE id=1", "invalid_provenance"),
            ("UPDATE identities SET source_osm_type='bad' WHERE id=1", "invalid_provenance"),
            ("UPDATE identities SET outside_mainland=2 WHERE id=1", "invalid_region_evidence"),
            ("UPDATE identities SET outside_mainland=1 WHERE id=10", "invalid_region_evidence"),
            ("UPDATE sqlite_sequence SET seq=9", "invalid_allocation_high_water"),
            (f"UPDATE sqlite_sequence SET seq={legacy.MAX_ID}", "identity_range_exhausted"),
        ]:
            with self.subTest(reason=reason):
                copy = self.root / "bad.sqlite"
                shutil.copyfile(self.snapshot, copy)
                with sqlite3.connect(copy) as db:
                    db.execute(sql)
                with self.assertRaisesRegex(legacy.AuditError, reason):
                    legacy.audit(copy)

    def test_canonical_duplicate_wal_and_symlink_are_rejected(self):
        with sqlite3.connect(self.snapshot) as db:
            db.execute("INSERT INTO identities(lat,lon) VALUES('48.8584001230','2.2945004560')")
        with self.assertRaisesRegex(legacy.AuditError, "duplicate_canonical_coordinates"):
            legacy.audit(self.snapshot)
        wal = Path(str(self.snapshot) + "-wal")
        wal.write_bytes(b"active")
        with self.assertRaisesRegex(legacy.AuditError, "consistent_snapshot_required"):
            legacy.audit(self.snapshot)
        link = self.root / "link.sqlite"
        link.symlink_to(self.snapshot)
        with self.assertRaisesRegex(legacy.AuditError, "snapshot_required"):
            legacy.audit(link)


if __name__ == "__main__":
    unittest.main()
