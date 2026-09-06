"""Regression coverage for configuration, request, scan and export fixes."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from hass_cleaner.plans import PlanManager, _markdown as plan_markdown
from hass_cleaner.quarantine import QuarantineManager, QuarantineError
from hass_cleaner.registry_audit import RegistryAudit
from hass_cleaner.reporting import write_report_files
from hass_cleaner.scanner import ScanManager, scan_tree
from hass_cleaner.server import create_server, _scan_summary
from hass_cleaner.settings import Settings, load_effective_settings, save_local_settings


class ReviewFixTests(unittest.TestCase):
    def root(self):
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_supervisor_changes_only_replace_changed_fields(self):
        root = self.root()
        options = root / "options.json"
        options.write_text(json.dumps({"language": "en", "retention_days": 7}))
        save_local_settings(root, Settings(language="nl", retention_days=3))
        options.write_text(json.dumps({"language": "en", "retention_days": 2}))
        result = load_effective_settings(root)
        self.assertEqual(("nl", 2), (result.language, result.retention_days))
        self.assertEqual(result, load_effective_settings(root))
        save_local_settings(root, Settings(language="nl", retention_days=5))
        self.assertEqual(5, load_effective_settings(root).retention_days)
        self.assertEqual(2, json.loads(options.read_text())["retention_days"])

    def test_clear_rejects_active_scan_and_blocks_new_scan_during_clear(self):
        root = self.root()
        entered, release = threading.Event(), threading.Event()
        def registry():
            entered.set()
            release.wait(5)
            return RegistryAudit(status="completed")
        manager = ScanManager(root, Settings, root / "reports", registry)
        scan = manager.start()
        self.assertTrue(entered.wait(3))
        try:
            with self.assertRaises(RuntimeError):
                manager.clear_history()
        finally:
            release.set()
        self.wait_scan(manager, scan.id)
        (root / "entity-snapshot.json").write_text("{}")
        original = manager._clear_history_files
        def clearing():
            with self.assertRaises(RuntimeError):
                manager.start()
            original()
        with patch.object(manager, "_clear_history_files", side_effect=clearing):
            manager.clear_history()
        self.assertIsNone(manager.latest())
        self.assertEqual([], manager.history())
        self.assertFalse((root / "entity-snapshot.json").exists())

    def wait_scan(self, manager, scan_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if manager.get(scan_id).status not in {"queued", "running"}:
                self.assertEqual("completed", manager.get(scan_id).status, manager.get(scan_id).error)
                return
            time.sleep(0.01)
        self.fail("Scan did not finish")

    def test_memory_is_bounded_without_removing_retained_reports(self):
        root = self.root()
        manager = ScanManager(root / "config", Settings, root / "reports", lambda: RegistryAudit(status="completed"))
        manager.root.mkdir()
        for _ in range(5):
            scan = manager.start()
            self.wait_scan(manager, scan.id)
        self.assertLessEqual(len(manager._scans), 2)
        self.assertEqual(5, len(list((root / "reports").glob("*.json"))))
        self.assertEqual(5, len(manager.history()))

    def test_summary_does_not_serialize_full_registry_and_keeps_error(self):
        scan = scan_tree(self.root(), Settings())
        scan.registry_audit.error = "Connection failed"
        with patch.object(RegistryAudit, "to_dict", side_effect=AssertionError("full serialization")):
            self.assertEqual("Connection failed", _scan_summary(scan)["registry_audit"]["error"])

    def orphan(self):
        root, data = self.root(), self.root()
        cache = root / "custom_components/demo/__pycache__/demo.cpython-313.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        old = time.time() - 45 * 86400
        os.utime(cache, (old, old))
        scan = scan_tree(root, Settings())
        plan = PlanManager(data).create(scan, Settings(), selected_ids=[scan.items[0].id], selected_bundle_ids=[], selected_entity_ids=[], backup_choice="skip")
        return root, data, cache, scan, plan

    def test_orphan_cache_can_be_quarantined_with_explicit_risk_acceptance(self):
        root, data, cache, scan, plan = self.orphan()
        self.assertEqual("python_cache_without_source", scan.items[0].category)
        QuarantineManager(root, data).execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False,
            backup_choice="none", risk_acknowledged=True, content_risk_acknowledged=True, confirmation="QUARANTINE", requested_by="test")
        self.assertFalse(cache.exists())

    def test_changed_orphan_classification_still_blocks_execution(self):
        root, data, cache, scan, plan = self.orphan()
        (cache.parent.parent / "demo.py").write_text("# new source")
        with self.assertRaises(QuarantineError):
            QuarantineManager(root, data).execute(scan, Settings(), plan=plan, backup_token="", backup_valid=False,
                backup_choice="none", risk_acknowledged=True, content_risk_acknowledged=True, confirmation="QUARANTINE", requested_by="test")
        self.assertTrue(cache.exists())

    def test_readable_exports_follow_language_and_preserve_risk_guidance(self):
        root, data, cache, scan, plan = self.orphan()
        english = write_report_files(scan, Settings(language="en"), data / "reports")["md"].read_text(encoding="utf-8")
        self.assertIn("cleanup", english.lower())
        self.assertIn("may prevent the integration from loading", english)
        self.assertIn("cleanup preparation", plan_markdown(plan, "en"))
        self.assertIn("herstelplan", plan_markdown(plan, "nl"))

    def test_invalid_bodies_do_not_mutate_settings(self):
        config, data = self.root(), self.root()
        save_local_settings(data, Settings(language="en", retention_days=2))
        before = (data / "ui-settings.json").read_bytes()
        server = create_server("127.0.0.1", 0, config, data)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for body, headers, expected in [(b"{broken", {}, 400), (b"[]", {}, 400),
                (b"null", {}, 400), (b"", {"Content-Length": "-1"}, 400),
                (b"", {"Content-Length": "1000001"}, 413), (b"", {"Transfer-Encoding": "chunked"}, 400)]:
                with self.subTest(body=body, headers=headers):
                    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                    try:
                        connection.request("POST", "/api/settings", body, headers)
                        response = connection.getresponse()
                        self.assertEqual(expected, response.status)
                        self.assertIn("error", json.loads(response.read()))
                    finally:
                        connection.close()
            self.assertEqual(before, (data / "ui-settings.json").read_bytes())
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)
