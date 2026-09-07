from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hass_cleaner.references import fetch_references, selection_review, markdown_lines
from hass_cleaner.references import validate_before_cleanup
from hass_cleaner.registry_cleanup import RegistryCleanupError, RegistryCleanupManager
from hass_cleaner.registry_audit import audit_registry_snapshot
from hass_cleaner.server import _paged_scan_items, _scan_summary
from hass_cleaner.scanner import ScanResult
from hass_cleaner.plans import PlanManager, _markdown
from hass_cleaner.settings import Settings
from hass_cleaner.reporting import _write_csv
from tests.test_registry_audit import FakeConnection

COMPANION = Path(__file__).resolve().parents[2] / "custom_components" / "hass_cleaner"
spec = importlib.util.spec_from_file_location("reference_analyzer", COMPANION / "references.py")
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)


def source(config, kind="automation", source_id="automation.test"):
    return {"id": source_id, "name": "Test source", "kind": kind, "config": config}


class ReferenceTests(unittest.TestCase):
    def test_cleanup_rechecks_unchanged_changed_and_unavailable_references(self):
        snapshot = {"entities": [{"entity_id": "light.a"}]}
        audit = audit_registry_snapshot(snapshot)
        audit.references = analyzer.analyze([source({"entity_id": "light.a"})], {"entity": {"light.a"}})
        scan = SimpleNamespace(registry_audit=audit)
        plan = {"entities": [{"entity_id": "light.a"}], "reference_review": selection_review(audit, ["light.a"])}
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test"}), patch("hass_cleaner.registry_audit.fetch_registry_snapshot", return_value=snapshot), patch("hass_cleaner.references.fetch_references", return_value=audit.references) as fetch:
            validate_before_cleanup(scan, plan)
            fetch.return_value = analyzer.analyze([source({"target": {"entity_id": "light.a"}})], {"entity": {"light.a"}})
            with self.assertRaisesRegex(RegistryCleanupError, "changed"):
                validate_before_cleanup(scan, plan)
            fetch.return_value = {"status": "unavailable"}
            with self.assertRaisesRegex(RegistryCleanupError, "unavailable"):
                validate_before_cleanup(scan, plan)
            validate_before_cleanup(scan, {"reference_review": {"status": "unavailable"}})

    def test_cleanup_coverage_change_blocks_even_without_matches(self):
        audit = audit_registry_snapshot({})
        audit.references = analyzer.analyze([source({})], {})
        plan = {"reference_review": selection_review(audit)}
        after = analyzer.analyze([source({"use_blueprint": {}})], {})
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test"}), patch("hass_cleaner.registry_audit.fetch_registry_snapshot", return_value={}), patch("hass_cleaner.references.fetch_references", return_value=after):
            with self.assertRaisesRegex(RegistryCleanupError, "coverage"):
                validate_before_cleanup(SimpleNamespace(registry_audit=audit), plan)

    def test_failed_reference_recheck_prevents_executor_and_releases_lock(self):
        from tests.test_registry_cleanup import RegistryCleanupTests
        calls = []
        plan = {"scan_id": "scan1", "entities": [{"entity_id": "sensor.old", "execution_allowed": True}]}
        with tempfile.TemporaryDirectory() as temp:
            manager = RegistryCleanupManager(Path(temp), executor=lambda *a, **k: calls.append(True))
            with patch("hass_cleaner.references.validate_before_cleanup", side_effect=RegistryCleanupError("changed")):
                with self.assertRaisesRegex(RegistryCleanupError, "changed"):
                    manager.execute(RegistryCleanupTests._scan(), plan, backup_choice="manual", backup_token="",
                                    backup_valid=False, risk_acknowledged=True, confirmation="DELETE 1", requested_by="test")
            self.assertEqual([], calls)
            self.assertEqual([], manager.history())
            self.assertTrue(manager._lock.acquire(blocking=False))
            manager._lock.release()

    def test_nested_static_targets_and_locations(self):
        report = analyzer.analyze([source({"actions": [{"action": "light.turn_on", "target": {
            "entity_id": ["light.present", "light.missing"], "device_id": "a" * 32, "area_id": "kitchen"}}]})],
            {"entity": {"light.present"}, "device": {"a" * 32}, "area": {"kitchen"}, "action": {"light.turn_on"}})
        self.assertEqual("completed", report["status"])
        self.assertEqual(5, report["summary"]["references"])
        self.assertEqual(1, report["summary"]["missing"])
        missing = next(r for r in report["references"] if r["missing"])
        self.assertEqual("$.actions[0].target.entity_id[1]", missing["location"])

    def test_registry_entities_need_not_have_a_state(self):
        report = analyzer.analyze([source({"entity_id": "sensor.disabled"})], {"entity": {"sensor.disabled"}})
        self.assertEqual(0, report["summary"]["missing"])

    def test_device_automation_entity_uuid(self):
        report = analyzer.analyze([source({"entity_id": ["a" * 32, "b" * 32]})],
                                  {"entity": {"light.present"}, "entity_aliases": {"a" * 32: "light.present"}})
        self.assertEqual(["light.present", "b" * 32], [r["target_id"] for r in report["references"]])
        self.assertEqual("entity_registry", report["references"][1]["target_type"])
        self.assertTrue(report["references"][1]["missing"])

    def test_templates_are_parsed_not_evaluated(self):
        config = {"value_template": "{{ states('sensor.literal') }} {{ states.sensor.attribute.state }} {{ states(entity_variable) }}"}
        report = analyzer.analyze([source(config)], {})
        self.assertEqual("partial", report["status"])
        self.assertEqual({"sensor.literal", "sensor.attribute"}, {r["target_id"] for r in report["references"]})
        self.assertNotIn("entity_variable", json.dumps(report))
        self.assertEqual(set(), analyzer.template_entities("{{ 'states.sensor.example' }} {# states('sensor.comment') #}"))
        self.assertEqual(set(), analyzer.template_entities("{{ invalid syntax !!! }}"))

    def test_dashboard_lists_blueprints_custom_cards_and_unreadable_sources(self):
        report = analyzer.analyze([source({"views": [{"cards": [{"type": "custom:test", "entities": ["sensor.a", {"entity": "sensor.b"}]}]}]}, "dashboard"),
                                  source({"use_blueprint": {"path": "example.yaml"}}, source_id="automation.blueprint"),
                                  source(None, source_id="script.failed")], {})
        self.assertEqual(2, report["summary"]["missing"])
        self.assertEqual(3, report["summary"]["partial_sources"])
        self.assertEqual("unavailable", report["sources"][2]["status"])

    def test_no_credentials_or_entire_configuration_exported(self):
        report = analyzer.analyze([source({"password": "SECRET", "message": "sensor.not_a_reference", "entity_id": "all", "action": "choose"})], {})
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertEqual([], report["references"])

    def test_issue_id_stays_stable_for_changed_targets(self):
        first = analyzer.repair_groups(analyzer.analyze([source({"entity_id": "sensor.a"})], {}))
        second = analyzer.repair_groups(analyzer.analyze([source({"entity_id": "sensor.b"})], {}))
        self.assertEqual(list(first), list(second))

    def test_depth_limit_marks_partial(self):
        config = {}
        for _ in range(65):
            config = {"nested": config}
        self.assertEqual("partial", analyzer.analyze([source(config)], {})["status"])

    def test_bridge_read_only_and_missing_companion(self):
        report = analyzer.analyze([source({"entity_id": "sensor.a"})], {})
        connection = FakeConnection([{"type": "auth_required"}, {"type": "auth_ok"},
                                     {"type": "result", "id": 1, "success": True, "result": report}])
        self.assertEqual(report, fetch_references("test-token", connect=lambda *a, **k: connection))
        self.assertEqual("hass_cleaner/references", connection.sent[-1]["type"])
        self.assertTrue(connection.closed)
        connection = FakeConnection([{"type": "auth_ok"}, {"type": "result", "id": 1, "success": False,
                                                               "error": {"code": "unknown_command", "message": "unknown"}}])
        self.assertEqual("unavailable", fetch_references("test", connect=lambda *a, **k: connection)["status"])
        self.assertTrue(connection.closed)

    def test_bridge_auth_and_malformed_report(self):
        for replies in [[{"type": "auth_invalid", "message": "SECRET"}],
                        [{"type": "auth_ok"}, {"type": "result", "id": 1, "success": True, "result": {"schema_version": 2}}]]:
            connection = FakeConnection(replies)
            result = fetch_references("test", connect=lambda *a, **k: connection)
            self.assertEqual("unavailable", result["status"])
            self.assertNotIn("SECRET", json.dumps(result))
            self.assertTrue(connection.closed)

    def test_indirect_device_and_area_use_pagination_and_summary(self):
        audit = audit_registry_snapshot({"entities": [{"entity_id": "light.a", "device_id": "a" * 32}],
                                         "devices": [{"id": "a" * 32, "area_id": "kitchen"}]})
        audit.references = analyzer.analyze([source({"entity_id": "light.a", "device_id": "a" * 32, "area_id": "kitchen"})], {})
        review = selection_review(audit, ["light.a"])
        self.assertEqual(3, review["count"])
        scan = ScanResult(id="test", started_at="now", registry_audit=audit)
        page = _paged_scan_items(scan, "references", {"entity_id": ["light.a"], "limit": ["1"]})
        self.assertEqual(3, page["total"])
        self.assertTrue(page["has_more"])
        self.assertEqual(1, len(page["items"]))
        self.assertNotIn("references", _scan_summary(scan)["registry_audit"]["references"])
        self.assertNotIn("sources", _scan_summary(scan)["registry_audit"]["references"])
        self.assertEqual(0, _paged_scan_items(scan, "references", {"bundle_id": ["unknown"]})["total"])

    def test_exports_and_plan_preserve_references(self):
        audit = audit_registry_snapshot({"entities": [{"entity_id": "light.a"}]})
        audit.entity_workspace = {"items": [{"entity_id": "light.a", "selectable_for_plan": True}]}
        audit.references = analyzer.analyze([source({"entity_id": "light.a"})], {})
        audit.references["references"][0]["source_name"] = "=FORMULA"
        scan = ScanResult(id="test", started_at="now", status="completed", registry_audit=audit)
        with tempfile.TemporaryDirectory() as temp:
            plan = PlanManager(Path(temp)).create(scan, Settings(), selected_ids=[], selected_bundle_ids=[],
                                                  selected_entity_ids=["light.a"], backup_choice="verified")
            self.assertEqual(1, plan["reference_review"]["count"])
            self.assertIn("## Reference checks", _markdown(plan, "en"))
            self.assertIn("## Referentiecontrole", _markdown(plan, "nl"))
            path = Path(temp) / "report.csv"
            _write_csv(scan, path)
            self.assertIn("'=FORMULA", path.read_text(encoding="utf-8-sig"))
        self.assertIn("$.entity_id", "\n".join(markdown_lines(audit.references)))
