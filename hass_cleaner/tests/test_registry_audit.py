from __future__ import annotations

import json
import unittest

from hass_cleaner.registry_audit import audit_registry_snapshot, fetch_registry_snapshot, fetch_related


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
                {"entity_id": "sensor.runtime_only", "state": "idle", "attributes": {"friendly_name": "Runtime", "reachable": True, "secret": "never-copy"}},
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
        self.assertEqual(2, audit.summary["bundles_total"])
        demo = next(bundle for bundle in audit.bundles if bundle.config_entry_id == "entry-1")
        self.assertEqual("Demo", demo.title)
        self.assertEqual(1, len(demo.devices))
        self.assertEqual(3, len(demo.entities))
        self.assertEqual(["sensor.normal"], demo.devices[0]["entity_ids"])
        self.assertEqual(1, audit.summary["state_only_entities"])
        self.assertEqual("sensor.runtime_only", audit.state_only_entities[0]["entity_id"])
        self.assertEqual({"reachable": True}, audit.state_only_entities[0]["connectivity_signals"])
        self.assertNotIn("secret", json.dumps(audit.to_dict()))

    def test_related_search_uses_official_read_only_command(self) -> None:
        connection = FakeConnection([
            {"type": "auth_required"},
            {"type": "auth_ok"},
            {"id": 1, "type": "result", "success": True, "result": {"entity": ["sensor.one"], "automation": ["automation.test"]}},
        ])
        result = fetch_related("config_entry", "entry-1", token="test-token", connect=lambda *args, **kwargs: connection)
        self.assertEqual(["automation.test"], result["automation"])
        self.assertEqual("search/related", connection.sent[-1]["type"])
        self.assertEqual("config_entry", connection.sent[-1]["item_type"])

    def test_large_orphan_group_becomes_one_generic_anomaly(self) -> None:
        devices = [
            {"id": f"device-{index}", "name": f"device-{index}", "config_entries": ["entry-1"]}
            for index in range(120)
        ]
        audit = audit_registry_snapshot({
            "entities": [], "devices": devices, "areas": [],
            "config_entries": [{"entry_id": "entry-1", "title": "Any integration", "domain": "example"}],
            "states": [],
        })
        self.assertEqual(1, audit.summary["anomalies_total"])
        anomaly = audit.anomalies[0]
        self.assertEqual("large_orphan_device_group", anomaly["category"])
        self.assertEqual(120, anomaly["counts"]["orphans"])
        self.assertEqual("insufficient", anomaly["evidence_level"])
        self.assertIn("ouderdom", anomaly["evidence_summary"])
        self.assertEqual(10, len(anomaly["sample_device_ids"]))
        self.assertTrue(anomaly["possible_consequences"])
        self.assertTrue(anomaly["recovery_steps"])
        self.assertTrue(anomaly["recommended_first_step"])
        self.assertFalse(anomaly["execution_allowed"])


if __name__ == "__main__":
    unittest.main()
