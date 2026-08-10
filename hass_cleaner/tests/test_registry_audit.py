from __future__ import annotations

import json
import unittest

from hass_cleaner.registry_audit import audit_registry_snapshot, fetch_registry_snapshot


class FakeConnection:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = [json.dumps(item) for item in responses]
        self.sent: list[dict] = []
        self.closed = False

    def recv(self) -> str:
        return self.responses.pop(0)

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def close(self) -> None:
        self.closed = True


class RegistryAuditTests(unittest.TestCase):
    def test_websocket_snapshot_uses_read_only_commands(self) -> None:
        responses = [{"type": "auth_required"}, {"type": "auth_ok"}]
        responses.extend(
            {"id": index, "type": "result", "success": True, "result": []}
            for index in range(1, 6)
        )
        connection = FakeConnection(responses)

        result = fetch_registry_snapshot("test-token", connect=lambda *args, **kwargs: connection)

        self.assertEqual({"entities", "devices", "areas", "config_entries", "states"}, set(result))
        self.assertEqual("auth", connection.sent[0]["type"])
        self.assertEqual(
            [
                "config/entity_registry/list",
                "config/device_registry/list",
                "config/area_registry/list",
                "config_entries/get",
                "get_states",
            ],
            [message["type"] for message in connection.sent[1:]],
        )
        self.assertTrue(connection.closed)

    def test_registry_relationships_are_classified_without_delete_actions(self) -> None:
        snapshot = {
            "entities": [
                {"entity_id": "sensor.normal", "name": "Normal", "device_id": "device-1", "area_id": "kitchen", "config_entry_id": "entry-1", "disabled_by": None},
                {"entity_id": "sensor.helper", "name": "Helper", "device_id": None, "config_entry_id": "entry-1", "disabled_by": None},
                {"entity_id": "sensor.broken", "device_id": "missing-device", "area_id": "missing-area", "config_entry_id": "missing-entry", "disabled_by": None},
                {"entity_id": "sensor.disabled", "device_id": None, "config_entry_id": "entry-1", "disabled_by": "user"},
            ],
            "devices": [
                {"id": "device-1", "name": "Device", "area_id": "kitchen", "config_entries": ["entry-1"]},
                {"id": "device-empty", "name": "Hub", "via_device_id": "missing-parent", "config_entries": ["missing-entry"]},
            ],
            "areas": [{"area_id": "kitchen", "name": "Keuken"}, {"area_id": "empty", "name": "Leeg"}],
            "config_entries": [{"entry_id": "entry-1", "title": "Demo"}],
            "states": [
                {"entity_id": "sensor.normal", "state": "ok"},
                {"entity_id": "sensor.helper", "state": "unavailable"},
            ],
        }

        audit = audit_registry_snapshot(snapshot)
        categories = [item.category for item in audit.findings]

        self.assertEqual("completed", audit.status)
        self.assertEqual(2, audit.summary["entities_without_device"])
        self.assertEqual(5, audit.summary["broken_references"])
        self.assertEqual(1, audit.summary["entities_not_loaded"])
        self.assertEqual(1, audit.summary["unavailable_states"])
        self.assertIn("device_without_entities", categories)
        self.assertIn("empty_area", categories)
        self.assertTrue(all(item.recommended_action != "delete" for item in audit.findings))


if __name__ == "__main__":
    unittest.main()
