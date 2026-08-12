from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from hass_cleaner.registry_cleanup import RegistryCleanupError, RegistryCleanupManager, execute_registry_commands


class FakeConnection:
    def __init__(self) -> None:
        self.responses = [
            json.dumps({"type": "auth_required"}),
            json.dumps({"type": "auth_ok"}),
            json.dumps({"id": 1, "type": "result", "success": True, "result": None}),
            json.dumps({"id": 2, "type": "result", "success": True, "result": None}),
        ]
        self.sent: list[dict] = []
        self.closed = False

    def recv(self):
        return self.responses.pop(0)

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def close(self):
        self.closed = True


class RegistryCleanupTests(unittest.TestCase):
    @staticmethod
    def _scan() -> SimpleNamespace:
        bundle = SimpleNamespace(
            config_entry_id="entry1",
            devices=[{"device_id": "device1"}],
        )
        audit = SimpleNamespace(
            entity_workspace={"items": [{"entity_id": "sensor.old", "registry_entry": True}]},
            bundles=[bundle],
        )
        return SimpleNamespace(id="scan1", status="completed", registry_audit=audit)

    def test_user_directed_cleanup_requires_count_and_risk_confirmation(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            manager = RegistryCleanupManager(Path(folder), executor=lambda entities, devices: calls.append((entities, devices)) or [])
            scan = self._scan()
            plan = {
                "scan_id": "scan1",
                "entities": [{"entity_id": "sensor.old", "execution_allowed": True}],
                "devices": [{"device_id": "device1", "config_entry_id": "entry1", "execution_allowed": True}],
            }
            with self.assertRaises(RegistryCleanupError):
                manager.execute(scan, plan, backup_choice="none", backup_token="", backup_valid=False,
                                risk_acknowledged=False, confirmation="VERWIJDER 2", requested_by="Dennis")
            record = manager.execute(scan, plan, backup_choice="none", backup_token="", backup_valid=False,
                                     risk_acknowledged=True, confirmation="VERWIJDER 2", requested_by="Dennis")
            self.assertEqual("completed", record["status"])
            self.assertEqual([(["sensor.old"], [{"device_id": "device1", "config_entry_id": "entry1"}])], calls)

    def test_verified_choice_requires_valid_backup(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manager = RegistryCleanupManager(Path(folder), executor=lambda entities, devices: [])
            scan = self._scan()
            plan = {"scan_id": "scan1", "entities": [{"entity_id": "sensor.old", "execution_allowed": True}]}
            with self.assertRaises(RegistryCleanupError):
                manager.execute(scan, plan, backup_choice="verified", backup_token="bad", backup_valid=False,
                                risk_acknowledged=True, confirmation="VERWIJDER 1", requested_by="Dennis")

    def test_tampered_plan_object_is_rejected_against_latest_scan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manager = RegistryCleanupManager(Path(folder), executor=lambda entities, devices: self.fail("must not execute"))
            plan = {"scan_id": "scan1", "entities": [{"entity_id": "sensor.not_scanned", "execution_allowed": True}]}
            with self.assertRaises(RegistryCleanupError):
                manager.execute(self._scan(), plan, backup_choice="none", backup_token="", backup_valid=False,
                                risk_acknowledged=True, confirmation="VERWIJDER 1", requested_by="Dennis")

    def test_official_registry_commands_are_sent_with_exact_identifiers(self) -> None:
        connection = FakeConnection()
        result = execute_registry_commands(
            ["sensor.old"], [{"device_id": "device1", "config_entry_id": "entry1"}],
            token="token", connect=lambda *args, **kwargs: connection,
        )
        self.assertEqual("config/entity_registry/remove", connection.sent[1]["type"])
        self.assertEqual("sensor.old", connection.sent[1]["entity_id"])
        self.assertEqual("config/device_registry/remove_config_entry", connection.sent[2]["type"])
        self.assertEqual("device1", connection.sent[2]["device_id"])
        self.assertEqual("entry1", connection.sent[2]["config_entry_id"])
        self.assertEqual(2, len(result))
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
