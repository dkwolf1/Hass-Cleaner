from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hass_cleaner.recorder import PurgeManager, call_recorder_purge


class FakeConnection:
    def __init__(self) -> None:
        self.responses = [
            json.dumps({"type": "auth_required"}),
            json.dumps({"type": "auth_ok"}),
            json.dumps({"id": 1, "type": "result", "success": True, "result": None}),
        ]
        self.sent = []
        self.closed = False

    def recv(self):
        return self.responses.pop(0)

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def close(self):
        self.closed = True


class RecorderTests(unittest.TestCase):
    def test_service_call_contains_only_supported_purge_fields(self) -> None:
        connection = FakeConnection()
        call_recorder_purge(12, True, False, token="token", connect=lambda *args, **kwargs: connection)
        command = connection.sent[-1]
        self.assertEqual("call_service", command["type"])
        self.assertEqual("recorder", command["domain"])
        self.assertEqual("purge", command["service"])
        self.assertEqual({"keep_days": 12, "repack": True, "apply_filter": False}, command["service_data"])
        self.assertTrue(connection.closed)

    def test_manager_persists_audit_record(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            manager = PurgeManager(Path(folder), lambda days, repack, apply_filter: calls.append((days, repack, apply_filter)))
            record = manager.execute(keep_days=5, repack=False, apply_filter=True, backup_confirmed=True, confirmation="PURGE")
            self.assertEqual("accepted", record.status)
            self.assertEqual([(5, False, True)], calls)
            self.assertEqual(record.id, manager.history()[0]["id"])

    def test_manager_fails_closed_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manager = PurgeManager(Path(folder), lambda *args: self.fail("purge should not be called"))
            with self.assertRaises(ValueError):
                manager.execute(keep_days=5, repack=False, apply_filter=False, backup_confirmed=True, confirmation="purge")


if __name__ == "__main__":
    unittest.main()
