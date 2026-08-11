from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.reporting import write_report_files
from hass_cleaner.registry_audit import RegistryAudit, RegistryBundle, RegistryFinding
from hass_cleaner.scanner import scan_tree
from hass_cleaner.settings import Settings


class ReportingTests(unittest.TestCase):
    def test_all_report_formats_are_written_and_audit_locked(self) -> None:
        with tempfile.TemporaryDirectory() as source_folder, tempfile.TemporaryDirectory() as output_folder:
            source = Path(source_folder)
            cache = source / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cache")
            old = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
            os.utime(cache, (old, old))
            (cache.parent.parent / "demo.py").write_text("# source", encoding="utf-8")
            (source / "secrets.yaml").write_text("api_token: ultra-private-report-value", encoding="utf-8")
            result = scan_tree(source, Settings())
            result.registry_audit = RegistryAudit(
                status="completed",
                summary={"entities_total": 1, "review_findings": 0, "informational_findings": 1},
                findings=[
                    RegistryFinding(
                        id="registry-item",
                        subject_type="entity",
                        subject_id="sensor.helper",
                        name="Helper",
                        category="entity_without_device",
                        severity="info",
                        reason="Entity is niet aan een apparaat gekoppeld",
                    )
                ],
                bundles=[
                    RegistryBundle(
                        id="entry-1",
                        title="Demo integration",
                        domain="demo",
                        config_entry_id="entry-1",
                        state="loaded",
                        devices=[{"device_id": "device-1"}],
                        entities=[{"entity_id": "sensor.helper"}],
                        review_count=0,
                        informational_count=1,
                    )
                ],
            )

            paths = write_report_files(result, Settings(), Path(output_folder))

            self.assertEqual({"json", "csv", "md"}, set(paths))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertNotIn("ultra-private-report-value", paths["json"].read_text(encoding="utf-8"))
            self.assertTrue(payload["audit_only"])
            self.assertTrue(payload["execution_locked"])
            self.assertEqual("sensor.helper", payload["scan"]["registry_audit"]["findings"][0]["subject_id"])
            self.assertEqual(1, payload["review_summary"]["proposed_for_cleanup_count"])
            markdown = paths["md"].read_text(encoding="utf-8")
            self.assertNotIn("ultra-private-report-value", markdown)
            self.assertIn("AUDIT-ONLY", markdown)
            self.assertIn("/homeassistant/custom_components/demo/__pycache__/demo.cpython-313.pyc", markdown)
            self.assertIn("Home Assistant-registercontrole", markdown)
            self.assertIn("sensor.helper", markdown)
            self.assertIn("Bundels per integratie", markdown)
            self.assertIn("Demo integration", markdown)
            with paths["csv"].open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter=";"))
            self.assertTrue(all(None not in row for row in rows))
            self.assertNotIn("ultra-private-report-value", paths["csv"].read_text(encoding="utf-8-sig"))
            cache_row = next(row for row in rows if row["path"].endswith("demo.cpython-313.pyc"))
            self.assertEqual("yes", cache_row["proposed_for_cleanup"])
            self.assertEqual("strong", cache_row["evidence_level"])
            registry_row = next(row for row in rows if row["record_type"] == "registry")
            self.assertEqual("no", registry_row["proposed_for_cleanup"])
            self.assertNotEqual("delete", registry_row["recommended_action"])
            bundle_row = next(row for row in rows if row["record_type"] == "bundle")
            self.assertEqual("Demo integration", bundle_row["name"])

    def test_manifest_mount_is_read_only(self) -> None:
        manifest = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("read_only: true", manifest)
        self.assertNotIn("read_only: false", manifest)

    def test_build_uses_published_multi_arch_python_tag(self) -> None:
        app_root = Path(__file__).resolve().parents[1]
        expected = "ghcr.io/home-assistant/base-python:3.13-alpine3.24"
        build_manifest = (app_root / "build.yaml").read_text(encoding="utf-8")
        dockerfile = (app_root / "Dockerfile").read_text(encoding="utf-8")

        self.assertEqual(2, build_manifest.count(expected))
        self.assertIn(f"ARG BUILD_FROM={expected}", dockerfile)
        self.assertNotIn("amd64-base-python:3.13\n", build_manifest)


if __name__ == "__main__":
    unittest.main()
