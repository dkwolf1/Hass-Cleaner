from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.availability import apply_availability_history
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


if __name__ == "__main__":
    unittest.main()
