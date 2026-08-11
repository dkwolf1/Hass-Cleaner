from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.reporting import prune_report_files, write_report_files
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
                entity_workspace={"items": [{
                    "entity_id": "sensor.runtime_only",
                    "name": "Runtime only",
                    "status": "available",
                    "attention": False,
                    "registry_entry": False,
                    "reason": "Runtime-state zonder registeritem",
                }]},
            )

            paths = write_report_files(result, Settings(), Path(output_folder))

            self.assertEqual({"json", "csv", "md"}, set(paths))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(9, payload["schema_version"])
            self.assertNotIn("ultra-private-report-value", paths["json"].read_text(encoding="utf-8"))
            self.assertTrue(payload["audit_only"])
            self.assertTrue(payload["execution_locked"])
            self.assertEqual("sensor.helper", payload["scan"]["registry_audit"]["findings"][0]["subject_id"])
            self.assertEqual(1, payload["review_summary"]["proposed_for_cleanup_count"])
            markdown = paths["md"].read_text(encoding="utf-8")
            self.assertNotIn("ultra-private-report-value", markdown)
            self.assertIn("AUDIT-ONLY", markdown)
            self.assertNotIn("/homeassistant/custom_components/demo/__pycache__/demo.cpython-313.pyc", markdown)
            self.assertIn("volledige bestandsinventaris", markdown)
            self.assertIn("Home Assistant-registercontrole", markdown)
            self.assertIn("entity_without_device", markdown)
            self.assertIn("Bundels met waarschuwingen", markdown)
            self.assertNotIn("Demo integration", markdown)
            self.assertIn("Concrete aandachtspunten", markdown)
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
            runtime_row = next(row for row in rows if row["record_type"] == "entity_health")
            self.assertEqual("info", runtime_row["risk"])
            self.assertIn('"registry_entry": false', runtime_row["content_preview"])

    def test_manifest_mount_is_read_only(self) -> None:
        manifest = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("read_only: true", manifest)
        self.assertNotIn("read_only: false", manifest)

    def test_build_uses_published_multi_arch_python_tag(self) -> None:
        app_root = Path(__file__).resolve().parents[1]
        expected = "ghcr.io/home-assistant/base-python:3.13-alpine3.24"
        dockerfile = (app_root / "Dockerfile").read_text(encoding="utf-8")
        app_manifest = (app_root / "config.yaml").read_text(encoding="utf-8")

        self.assertIn(f"ARG BUILD_FROM={expected}", dockerfile)
        self.assertIn('image: "ghcr.io/dkwolf1/hass-cleaner"', app_manifest)
        self.assertFalse((app_root / "build.yaml").exists())

    def test_manifest_uses_native_container_healthcheck_and_normalized_version(self) -> None:
        app_root = Path(__file__).resolve().parents[1]
        repository_root = app_root.parent
        app_manifest = (app_root / "config.yaml").read_text(encoding="utf-8")
        dockerfile = (app_root / "Dockerfile").read_text(encoding="utf-8")
        workflow = (repository_root / ".github" / "workflows" / "build-app.yaml").read_text(encoding="utf-8")

        self.assertNotIn("watchdog:", app_manifest)
        self.assertNotIn("ingress_port:", app_manifest)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("version: ${{ steps.normalize.outputs.version }}", workflow)
        self.assertIn('echo "version=${version}"', workflow)

    def test_report_retention_only_removes_owned_old_report_sets(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, scan_id in enumerate(("oldscan", "middlescan", "newscan")):
                for extension in ("json", "csv", "md"):
                    path = root / f"hass-cleaner-audit-{scan_id}.{extension}"
                    path.write_text(scan_id, encoding="utf-8")
                    os.utime(path, (100 + index, 100 + index))
            foreign = root / "gebruikersrapport.json"
            foreign.write_text("behouden", encoding="utf-8")

            removed = prune_report_files(root, 2)

            self.assertEqual(["oldscan"], removed)
            self.assertFalse((root / "hass-cleaner-audit-oldscan.json").exists())
            self.assertTrue((root / "hass-cleaner-audit-middlescan.json").exists())
            self.assertEqual("behouden", foreign.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
