from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
import hashlib
import json
from dataclasses import replace
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
            operation = manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, backup_choice="verified", risk_acknowledged=False, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertFalse(source.exists())
            self.assertTrue(manager.test_restore(operation["id"], "file1")["passed"])
            restored = manager.restore(operation["id"], "file1", confirmation="HERSTEL", requested_by="Dennis")
            self.assertTrue(source.is_file())
            self.assertEqual("restored", restored["files"][0]["status"])

    def test_english_confirmation_words_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            operation = manager.execute(
                scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                backup_choice="none", risk_acknowledged=True,
                confirmation="QUARANTINE", requested_by="Dennis",
            )
            self.assertFalse(source.exists())
            manager.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="Dennis")
            self.assertTrue(source.is_file())

    def test_changed_file_blocks_complete_batch_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            source.write_bytes(b"changed after scan")
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            with self.assertRaises(QuarantineError):
                manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, backup_choice="verified", risk_acknowledged=False, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertTrue(source.exists())

    def test_backup_and_exact_confirmation_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            with self.assertRaises(QuarantineError):
                manager.execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False, backup_choice="verified", risk_acknowledged=False, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertTrue(source.exists())

    def test_user_can_explicitly_accept_running_without_backup(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            operation = manager.execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False, backup_choice="none", risk_acknowledged=True, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertFalse(source.exists())
            self.assertEqual("none", operation["backup_choice"])

    def test_permanent_purge_is_blocked_until_retention_expires(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            _, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            operation = manager.execute(scan, Settings(), plan=plan, backup_token="verified", backup_valid=True, backup_choice="verified", risk_acknowledged=False, confirmation="QUARANTAINE", requested_by="Dennis")
            with self.assertRaises(QuarantineError):
                manager.purge_expired(operation["id"], "file1", confirmation="VERWIJDER", requested_by="Dennis")
            stored = manager.list()[0]
            stored["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            manager._save([stored])
            deleted = manager.purge_expired(operation["id"], "file1", confirmation="VERWIJDER", requested_by="Dennis")
            self.assertEqual("deleted", deleted["files"][0]["status"])

    def test_review_content_requires_separate_risk_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            scan.items[0] = replace(scan.items[0], risk="review")
            plan["files"][0]["risk"] = "review"
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            with self.assertRaises(QuarantineError):
                manager.execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                                backup_choice="none", risk_acknowledged=True,
                                content_risk_acknowledged=False, confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertTrue(source.exists())

    def test_personal_media_can_be_quarantined_after_explicit_user_choice(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            config = Path(config_folder)
            source = config / "www" / "media" / "camera" / "snapshots" / "porch.jpg"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"personal image fixture")
            modified = source.stat().st_mtime
            item = ScanItem(
                id="personal1", path="/homeassistant/www/media/camera/snapshots/porch.jpg",
                category="personal_media", risk="review", reason="persoonlijke inhoud",
                recommended_action="review", size_bytes=source.stat().st_size,
                modified_at=datetime.fromtimestamp(modified, tz=timezone.utc).isoformat(),
                advice=analyze_file(source, "personal_media", "review", "persoonlijke inhoud"),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
            scan = ScanResult(id="scan-personal", status="completed", items=[item])
            plan = {"scan_id": scan.id, "files": [{"id": item.id, "risk": "review"}]}
            manager = QuarantineManager(config, Path(data_folder))
            operation = manager.execute(
                scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                backup_choice="none", risk_acknowledged=True, content_risk_acknowledged=True,
                confirmation="QUARANTAINE", requested_by="Dennis",
            )
            self.assertFalse(source.exists())
            self.assertEqual("quarantined", operation["files"][0]["status"])

    def test_clearing_log_preserves_active_quarantine_and_removes_restored_record(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            active = manager.execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                                     backup_choice="none", risk_acknowledged=True,
                                     confirmation="QUARANTAINE", requested_by="Dennis")
            self.assertEqual(0, manager.clear_completed_history())
            self.assertEqual(active["id"], manager.list()[0]["id"])
            manager.restore(active["id"], "file1", confirmation="HERSTEL", requested_by="Dennis")
            self.assertEqual(1, manager.clear_completed_history())
            self.assertEqual([], manager.list())

    def test_startup_reconciles_completed_copy_after_interrupted_journal_update(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            config = Path(config_folder)
            data = Path(data_folder)
            relative = Path("custom_components/demo/__pycache__/demo.pyc")
            payload = b"recoverable cache"
            destination = data / "quarantine" / "operation1" / "files" / relative
            destination.parent.mkdir(parents=True)
            destination.write_bytes(payload)
            operation = {
                "id": "operation1", "status": "running", "files": [{
                    "id": "file1", "relative_path": relative.as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(), "status": "planned",
                }],
            }
            (data / "quarantine" / "manifest.json").write_text(json.dumps([operation]), encoding="utf-8")

            recovered = QuarantineManager(config, data).list()[0]
            self.assertEqual("quarantined", recovered["status"])
            self.assertEqual("quarantined", recovered["files"][0]["status"])
            self.assertTrue(destination.is_file())

    def test_startup_rolls_back_duplicate_copy_when_original_still_exists(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            config = Path(config_folder)
            data = Path(data_folder)
            relative = Path("custom_components/demo/__pycache__/demo.pyc")
            payload = b"original preserved"
            source = config / relative
            destination = data / "quarantine" / "operation2" / "files" / relative
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_bytes(payload)
            destination.write_bytes(payload)
            operation = {
                "id": "operation2", "status": "running", "files": [{
                    "id": "file1", "relative_path": relative.as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(), "status": "copied",
                }],
            }
            (data / "quarantine" / "manifest.json").write_text(json.dumps([operation]), encoding="utf-8")

            recovered = QuarantineManager(config, data).list()[0]
            self.assertEqual("rolled_back", recovered["status"])
            self.assertEqual("rolled_back", recovered["files"][0]["status"])
            self.assertTrue(source.is_file())
            self.assertFalse(destination.exists())

    def test_second_quarantine_action_is_rejected_while_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as config_folder, tempfile.TemporaryDirectory() as data_folder:
            source, scan, plan = self._fixture(Path(config_folder))
            manager = QuarantineManager(Path(config_folder), Path(data_folder))
            locked = threading.Event()
            release = threading.Event()

            def hold_lock() -> None:
                with manager._lock:
                    locked.set()
                    release.wait(timeout=5)

            thread = threading.Thread(target=hold_lock)
            thread.start()
            self.assertTrue(locked.wait(timeout=2))
            try:
                with self.assertRaisesRegex(QuarantineError, "al een quarantaineactie"):
                    manager.execute(
                        scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                        backup_choice="none", risk_acknowledged=True,
                        confirmation="QUARANTAINE", requested_by="Dennis",
                    )
                self.assertTrue(source.exists())
            finally:
                release.set()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
