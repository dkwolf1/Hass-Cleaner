from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hass_cleaner.plans import PlanError, PlanManager
from hass_cleaner.registry_audit import RegistryAudit
from hass_cleaner.scanner import ScanResult
from hass_cleaner.settings import Settings


class PlanTests(unittest.TestCase):
    def test_registered_entity_becomes_user_directed_cleanup_action(self) -> None:
        audit = RegistryAudit(status="completed", entity_workspace={
            "items": [{
                "entity_id": "sensor.old",
                "name": "Old sensor",
                "integration": "example",
                "device_id": "device-1",
                "device_name": "Meter",
                "area_name": "Kantoor",
                "status": "long_unavailable",
                "raw_state": "unavailable",
                "duration_days": 45,
                "reason": "Langdurig onbeschikbaar",
                "selectable_for_plan": True,
            }]
        })
        scan = ScanResult(id="scan-1", status="completed", registry_audit=audit)
        with tempfile.TemporaryDirectory() as folder:
            plan = PlanManager(Path(folder)).create(
                scan,
                Settings(),
                selected_ids=[],
                selected_bundle_ids=[],
                selected_entity_ids=["sensor.old"],
                backup_choice="not_required_for_dry_run",
            )
        self.assertEqual(1, plan["summary"]["entity_count"])
        self.assertEqual(1, plan["summary"]["executable_actions"])
        self.assertTrue(plan["entities"][0]["execution_allowed"])
        self.assertEqual("remove_from_entity_registry", plan["entities"][0]["proposed_action"])

    def test_non_candidate_entity_is_rejected_even_for_direct_api_use(self) -> None:
        audit = RegistryAudit(status="completed", entity_workspace={
            "items": [{"entity_id": "sensor.healthy", "selectable_for_plan": False}]
        })
        scan = ScanResult(id="scan-1", status="completed", registry_audit=audit)
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(PlanError):
            PlanManager(Path(folder)).create(
                scan,
                Settings(),
                selected_ids=[],
                selected_bundle_ids=[],
                selected_entity_ids=["sensor.healthy"],
                backup_choice="not_required_for_dry_run",
            )


if __name__ == "__main__":
    unittest.main()
