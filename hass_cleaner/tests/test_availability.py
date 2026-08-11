from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.availability import apply_availability_history, apply_saved_decisions, update_entity_decision
from hass_cleaner.registry_audit import audit_registry_snapshot


def snapshot(last_changed: str, *, disabled_by=None, count: int = 3):
    return {
        "entities": [
            {"entity_id": f"sensor.offline_{index}", "config_entry_id": "entry-1", "platform": "example", "disabled_by": disabled_by}
            for index in range(count)
        ],
        "devices": [], "areas": [],
        "config_entries": [{"entry_id": "entry-1", "title": "Example", "domain": "example"}],
        "states": [
            {"entity_id": f"sensor.offline_{index}", "state": "unavailable", "last_changed": last_changed}
            for index in range(count)
        ],
    }


class AvailabilityTests(unittest.TestCase):
    def test_long_unavailable_entities_are_one_blocked_bundle_anomaly(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        audit = audit_registry_snapshot(snapshot((now - timedelta(days=40)).isoformat()))
        with tempfile.TemporaryDirectory() as folder:
            apply_availability_history(audit, Path(folder) / "history.json", now=now)
        anomaly = next(item for item in audit.anomalies if item["category"] == "long_unavailable_entity_group")
        self.assertEqual(3, anomaly["counts"]["long_unavailable"])
        self.assertFalse(anomaly["execution_allowed"])
        self.assertTrue(all(not item["cleanup_candidate"] for item in audit.bundles[0].entities))
        workspace_item = audit.entity_workspace["items"][0]
        self.assertEqual(40, workspace_item["duration_days"])
        self.assertEqual("home_assistant", workspace_item["duration_source"])
        self.assertEqual(now.isoformat(), workspace_item["first_observed"])

    def test_disabled_entities_never_become_availability_candidates(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        audit = audit_registry_snapshot(snapshot((now - timedelta(days=100)).isoformat(), disabled_by="integration"))
        with tempfile.TemporaryDirectory() as folder:
            apply_availability_history(audit, Path(folder) / "history.json", now=now)
        self.assertEqual(0, audit.summary["long_unavailable_entities"])
        self.assertFalse(any(item["category"] == "long_unavailable_entity_group" for item in audit.anomalies))

    def test_repeated_observations_need_elapsed_time(self) -> None:
        start = datetime(2026, 8, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            for offset in (0, 4, 8):
                now = start + timedelta(days=offset)
                audit = audit_registry_snapshot(snapshot(start.isoformat()))
                apply_availability_history(audit, path, now=now)
            self.assertEqual(3, audit.summary["long_unavailable_entities"])

    def test_unknown_and_integration_connectivity_signals_stay_distinct(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        audit = audit_registry_snapshot({
            "entities": [
                {"entity_id": "sensor.unknown", "config_entry_id": "entry-1", "device_id": "device-1", "area_id": "office", "platform": "example"},
                {"entity_id": "sensor.vendor_offline", "config_entry_id": "entry-1", "device_id": "device-1", "area_id": "office", "platform": "example"},
                {"entity_id": "sensor.disabled", "config_entry_id": "entry-1", "platform": "example", "disabled_by": "integration"},
                {"entity_id": "binary_sensor.problem", "config_entry_id": "entry-1", "platform": "example"},
            ],
            "devices": [{"id": "device-1", "name": "Meter", "config_entries": ["entry-1"]}],
            "areas": [{"area_id": "office", "name": "Kantoor"}],
            "config_entries": [{"entry_id": "entry-1", "title": "Example", "domain": "example"}],
            "states": [
                {"entity_id": "sensor.unknown", "state": "unknown", "last_changed": (now - timedelta(days=40)).isoformat()},
                {"entity_id": "sensor.vendor_offline", "state": "idle", "last_changed": now.isoformat(), "attributes": {"reachable": False, "secret": "never-copy"}},
                {"entity_id": "binary_sensor.problem", "state": "problem", "last_changed": (now - timedelta(days=40)).isoformat()},
            ],
        })
        with tempfile.TemporaryDirectory() as folder:
            apply_availability_history(audit, Path(folder) / "history.json", now=now)

        items = {item["entity_id"]: item for item in audit.entity_workspace["items"]}
        self.assertEqual("long_unknown", items["sensor.unknown"]["status"])
        self.assertTrue(items["sensor.unknown"]["selectable_for_plan"])
        self.assertEqual("available", items["sensor.vendor_offline"]["status"])
        self.assertTrue(items["sensor.vendor_offline"]["integration_signal_problem"])
        self.assertFalse(items["sensor.vendor_offline"]["selectable_for_plan"])
        self.assertEqual({"reachable": False}, items["sensor.vendor_offline"]["connectivity_signals"])
        self.assertEqual("Meter", items["sensor.unknown"]["device_name"])
        self.assertEqual("Kantoor", items["sensor.unknown"]["area_name"])
        self.assertEqual("disabled_by_integration", items["sensor.disabled"]["status"])
        self.assertFalse(items["sensor.disabled"]["selectable_for_plan"])
        self.assertEqual("long_problem", items["binary_sensor.problem"]["status"])
        self.assertTrue(items["binary_sensor.problem"]["selectable_for_plan"])

    def test_disabled_and_runtime_only_entities_are_separated_from_status_problems(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        audit = audit_registry_snapshot({
            "entities": [
                {"entity_id": "sensor.registered", "config_entry_id": "entry-1", "platform": "example"},
                {"entity_id": "sensor.disabled", "config_entry_id": "entry-1", "platform": "example", "disabled_by": "integration"},
            ],
            "devices": [], "areas": [],
            "config_entries": [{"entry_id": "entry-1", "title": "Example", "domain": "example"}],
            "states": [
                {"entity_id": "sensor.registered", "state": "ok", "last_changed": now.isoformat()},
                {"entity_id": "sensor.runtime_ok", "state": "idle", "last_changed": now.isoformat()},
                {"entity_id": "sensor.runtime_bad", "state": "unavailable", "last_changed": now.isoformat()},
            ],
        })
        with tempfile.TemporaryDirectory() as folder:
            apply_availability_history(audit, Path(folder) / "history.json", now=now)

        items = {item["entity_id"]: item for item in audit.entity_workspace["items"]}
        summary = audit.entity_workspace["summary"]
        self.assertEqual(2, summary["registered_total"])
        self.assertEqual(2, summary["state_only_total"])
        self.assertEqual(0, summary["attention"])
        self.assertEqual(1, summary["temporary_signals"])
        self.assertEqual(1, summary["disabled"])
        self.assertFalse(items["sensor.disabled"]["attention"])
        self.assertTrue(items["sensor.disabled"]["informational"])
        self.assertFalse(items["sensor.runtime_ok"]["registry_entry"])
        self.assertFalse(items["sensor.runtime_ok"]["attention"])
        self.assertFalse(items["sensor.runtime_bad"]["attention"])
        self.assertTrue(items["sensor.runtime_bad"]["watch"])
        self.assertFalse(items["sensor.runtime_bad"]["selectable_for_plan"])

    def test_first_measurement_and_saved_choice_are_explicit(self) -> None:
        now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
        audit = audit_registry_snapshot(snapshot(now.isoformat(), count=1))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apply_availability_history(audit, root / "availability-history.json", now=now)
            item = audit.entity_workspace["items"][0]
            self.assertEqual(0, item["duration_seconds"])
            self.assertEqual(1, item["observations"])
            self.assertEqual("baseline", item["diff_status"])
            update_entity_decision(root / "entity-decisions.json", item["entity_id"], "expected", now=now)
            apply_saved_decisions(audit.entity_workspace, root / "entity-decisions.json", now=now)
            self.assertTrue(item["muted_by_decision"])
            self.assertEqual(0, audit.entity_workspace["summary"]["temporary_visible"])

    def test_scan_diff_marks_recovery_without_deleting_anything(self) -> None:
        start = datetime(2026, 8, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "availability-history.json"
            first = audit_registry_snapshot(snapshot(start.isoformat(), count=1))
            apply_availability_history(first, path, now=start)
            recovered_snapshot = snapshot((start + timedelta(days=1)).isoformat(), count=1)
            recovered_snapshot["states"][0]["state"] = "ok"
            recovered = audit_registry_snapshot(recovered_snapshot)
            apply_availability_history(recovered, path, now=start + timedelta(days=1))
            item = recovered.entity_workspace["items"][0]
            self.assertEqual("recovered", item["diff_status"])
            self.assertEqual(1, recovered.entity_workspace["changes"]["counts"]["recovered"])


if __name__ == "__main__":
    unittest.main()
