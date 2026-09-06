from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from hass_cleaner.quarantine import QuarantineError, QuarantineManager
from hass_cleaner.registry_cleanup import RegistryCleanupError, RegistryCleanupManager, execute_registry_commands
from hass_cleaner.settings import Settings
from tests import test_quarantine, test_registry_cleanup


class RecoveryJournalTests(unittest.TestCase):
    def assert_unlocked(self, lock):
        acquired = []
        def check():
            success = lock.acquire(blocking=False)
            acquired.append(success)
            if success:
                lock.release()
        worker = threading.Thread(target=check)
        worker.start()
        worker.join(timeout=2)
        self.assertEqual([True], acquired)

    def fixture(self):
        config = Path(self.enterContext(tempfile.TemporaryDirectory()))
        data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        source, scan, plan = test_quarantine.QuarantineTests()._fixture(config)
        manager = QuarantineManager(config, data)
        operation = manager.execute(scan, Settings(), plan=plan, backup_token="ok", backup_valid=True,
                                    backup_choice="verified", risk_acknowledged=False,
                                    confirmation="QUARANTINE", requested_by="test")
        return config, data, source, manager, operation

    def test_concurrent_restore_target_is_never_overwritten(self):
        config, data, source, manager, operation = self.fixture()
        link = os.link

        def concurrent_writer(temporary, target):
            Path(target).write_bytes(b"new integration data")
            link(temporary, target)

        with patch("hass_cleaner.quarantine.os.link", side_effect=concurrent_writer):
            with self.assertRaises(QuarantineError):
                manager.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="test")
        restarted = QuarantineManager(config, data)
        self.assertEqual(b"new integration data", source.read_bytes())
        self.assertEqual("quarantined", restarted.list()[0]["files"][0]["status"])
        self.assertTrue(restarted.test_restore(operation["id"], "file1")["passed"])

    def test_interrupted_copy_is_removed_and_restore_can_be_retried(self):
        config, data, source, manager, operation = self.fixture()

        def interrupted_copy(input_file, output_file, *args):
            output_file.write(b"partial")
            raise KeyboardInterrupt()

        with patch("hass_cleaner.quarantine.shutil.copyfileobj", side_effect=interrupted_copy):
            with self.assertRaises(KeyboardInterrupt):
                manager.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="test")
        restarted = QuarantineManager(config, data)
        self.assertFalse(source.exists())
        self.assertFalse(list(source.parent.glob("*.hass-cleaner-restore")))
        restarted.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="test")
        self.assertEqual(b"safe generated cache", source.read_bytes())

    def test_restore_commit_failure_recovers_published_file(self):
        config, data, source, manager, operation = self.fixture()
        save = manager._replace_operation

        def fail_commit(value):
            if value["files"][0]["status"] == "restored":
                raise OSError("disk full")
            save(value)

        with patch.object(manager, "_replace_operation", side_effect=fail_commit):
            with self.assertRaises(QuarantineError):
                manager.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="test")
        self.assertTrue(source.exists())
        restarted = QuarantineManager(config, data)
        record = restarted.list()[0]["files"][0]
        self.assertEqual("restored", record["status"])
        self.assertFalse((restarted.root / operation["id"] / "files" / record["relative_path"]).exists())
        self.assertFalse(list(source.parent.glob("*.hass-cleaner-restore")))

    def test_restore_intent_failure_keeps_source_in_quarantine(self):
        _, _, source, manager, operation = self.fixture()
        with patch.object(manager, "_replace_operation", side_effect=OSError("disk full")):
            with self.assertRaises(QuarantineError):
                manager.restore(operation["id"], "file1", confirmation="RESTORE", requested_by="test")
        self.assertFalse(source.exists())
        self.assertTrue(manager.test_restore(operation["id"], "file1")["passed"])

    def test_interrupted_purge_is_reconciled(self):
        config, data, _, manager, operation = self.fixture()
        operation["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        manager._save([operation])
        save = manager._replace_operation

        def fail_commit(value):
            if value["files"][0]["status"] == "deleted":
                raise OSError("disk full")
            save(value)

        with patch.object(manager, "_replace_operation", side_effect=fail_commit):
            with self.assertRaises(QuarantineError):
                manager.purge_expired(operation["id"], "file1", confirmation="DELETE", requested_by="test")
        restarted = QuarantineManager(config, data)
        self.assertEqual("deleted", restarted.list()[0]["files"][0]["status"])

    def test_corrupt_manifests_are_preserved_and_block_clear(self):
        for contents in ("{broken", "{}", '[{"id":"x","status":"quarantined","files":[null]}]'):
            with self.subTest(contents=contents):
                config, data, _, manager, operation = self.fixture()
                manager.manifest_path.write_text(contents, encoding="utf-8")
                restarted = QuarantineManager(config, data)
                with self.assertRaises(QuarantineError):
                    restarted.clear_completed_history()
                with self.assertRaises(QuarantineError):
                    restarted._insert_operation(operation)
                self.assertEqual(contents, manager.manifest_path.read_text(encoding="utf-8"))
                self.assertTrue((manager.root / operation["id"]).exists())

    def test_unreadable_manifest_is_not_empty(self):
        _, _, _, manager, _ = self.fixture()
        original = manager.manifest_path.read_bytes()
        with patch.object(Path, "read_text", side_effect=PermissionError("unreadable")):
            with self.assertRaises(QuarantineError):
                manager.clear_completed_history()
        self.assertEqual(original, manager.manifest_path.read_bytes())

    def test_missing_manifest_with_existing_data_is_blocked(self):
        config, data, _, manager, _ = self.fixture()
        manager.manifest_path.unlink()
        restarted = QuarantineManager(config, data)
        with self.assertRaises(QuarantineError):
            restarted.clear_completed_history()
        self.assertFalse(manager.manifest_path.exists())

    def registry_fixture(self, executor):
        data = Path(self.enterContext(tempfile.TemporaryDirectory()))
        manager = RegistryCleanupManager(data, executor=executor)
        plan = {"scan_id": "scan1", "entities": [{"entity_id": "sensor.old", "execution_allowed": True}],
                "devices": [{"device_id": "device1", "config_entry_id": "entry1", "execution_allowed": True}]}
        def execute():
            return manager.execute(test_registry_cleanup.RegistryCleanupTests._scan(), plan, backup_choice="none", backup_token="",
                                   backup_valid=False, risk_acknowledged=True, confirmation="DELETE 2", requested_by="test")
        return data, manager, execute

    def test_registry_intent_storage_failure_prevents_execution_and_unlocks(self):
        calls = []
        _, manager, execute = self.registry_fixture(lambda *args, **kwargs: calls.append(args) or [])
        with patch.object(manager, "_save", side_effect=RegistryCleanupError("disk full")):
            with self.assertRaises(RegistryCleanupError):
                execute()
        self.assertFalse(calls)
        self.assert_unlocked(manager._lock)
        execute()
        self.assertEqual(1, len(calls))

    def test_registry_progress_failure_stops_batch_and_recovers_pending_command(self):
        connection = test_registry_cleanup.FakeConnection()
        def executor(entities, devices, **kwargs):
            return execute_registry_commands(entities, devices, token="test", connect=lambda *args, **opts: connection, **kwargs)
        data, manager, execute = self.registry_fixture(executor)
        save = manager._save

        def fail_after_command(history):
            if history[0]["completed"]:
                raise RegistryCleanupError("disk full")
            save(history)

        with patch.object(manager, "_save", side_effect=fail_after_command):
            with self.assertRaises(RegistryCleanupError):
                execute()
        self.assert_unlocked(manager._lock)
        self.assertTrue(connection.closed)
        self.assertEqual(2, len(connection.sent))  # auth and first entity command only
        restarted = RegistryCleanupManager(data)
        record = restarted.history()[0]
        self.assertEqual("interrupted", record["status"])
        self.assertEqual("sensor.old", record["pending"]["id"])
        restarted.clear_history()
        self.assertEqual(1, len(restarted.history()))

    def test_registry_progress_is_saved_before_next_command(self):
        snapshots = []
        connection = test_registry_cleanup.FakeConnection()
        def executor(entities, devices, **kwargs):
            return execute_registry_commands(entities, devices, token="test", connect=lambda *args, **opts: connection, **kwargs)
        _, manager, execute = self.registry_fixture(executor)
        send = connection.send
        def inspect_send(payload):
            snapshots.append(manager.history()[0])
            send(payload)
        connection.send = inspect_send
        execute()
        self.assertEqual("sensor.old", snapshots[1]["pending"]["id"])
        self.assertEqual("sensor.old", snapshots[2]["completed"][0]["id"])
        self.assertEqual("device1", snapshots[2]["pending"]["id"])
        self.assertEqual("completed", manager.history()[0]["status"])


if __name__ == "__main__":
    unittest.main()
