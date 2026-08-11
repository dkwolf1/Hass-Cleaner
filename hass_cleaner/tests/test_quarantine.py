from __future__ import annotations

import os
import tempfile
import time
import unittest
import hashlib
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path

from hass_cleaner.impact import analyze_file
from hass_cleaner.quarantine import QuarantineError, QuarantineManager
from hass_cleaner.scanner import ScanItem, ScanResult
from hass_cleaner.settings import Settings


class QuarantineTests(unittest.TestCase):
    def _fixture(self, config: Path) -> tuple[Path, ScanResult, dict]:
        source = config / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"safe generated cache")
        (source.parent.parent / "demo.py").write_text("# source", encoding="utf-8")
        old = time.time() - 40 * 86400
        os.utime(source, (old, old))
        item = ScanItem(
            id="file1", path="/homeassistant/custom_components/demo/__pycache__/demo.cpython-313.pyc",
            category="python_cache", risk="safe", reason="oud", recommended_action="delete",
            size_bytes=source.stat().st_size,
            modified_at=datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat(),
            advice=analyze_file(source, "python_cache", "safe", "oud"),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        scan = ScanResult(id="scan1", status="completed", items=[item])
        plan = {"scan_id": "scan1", "files": [{"id": "file1"}]}
        return source, scan, plan

    def test_move_restore_test_and_restore_are_checksum_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            operation = manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertFalse(source.exists())
            self.assertTrue(manager.test_restore(operation["id"], "file1")["passed"])
            restored = manager.restore(operation["id"], "file1", confirmation="HERSTEL", requested_by="Dennis")
            self.assertTrue(source.is_file())
            self.assertEqual("restored", restored["files"][0]["status"])

    def test_changed_file_blocks_complete_batch_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            source.write_bytes(b"changed after scan")
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            with self.assertRaises(QuarantineError):
                manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertTrue(source.exists())

    def test_backup_and_exact_confirmation_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            with self.assertRaises(QuarantineError):
                manager.execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertTrue(source.exists())

    def test_permanent_purge_is_blocked_until_retention_expires(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            _, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            operation = manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, confirmation="QUARANTAINE", requested_by="Dennis")
            with self.assertRaises(QuarantineError):
                manager.purge_expired(operation["id"], "file1", confirmation="VERWIJDER", requested_by="Dennis")
            stored = manager.list()[0]
            stored["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            manager._save([stored])
            deleted = manager.purge_expired(operation["id"], "file1", confirmation="VERWIJDER", requested_by="Dennis")
            self.assertEqual("deleted", deleted["files"][0]["status"])


if __name__ == "__main__":
    unittest.main()
