from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from hass_cleaner.reporting import write_report_files
from hass_cleaner.scanner import scan_tree
from hass_cleaner.settings import Settings


class ReportingTests(unittest.TestCase):
    def test_all_report_formats_are_written_and_audit_locked(self) -> None:
        with tempfile.TemporaryDirectory() as source_folder, tempfile.TemporaryDirectory() as output_folder:
            source = Path(source_folder)
            cache = source / "custom_components" / "demo" / "__pycache__" / "demo.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cache")
            result = scan_tree(source, Settings())

            paths = write_report_files(result, Settings(), Path(output_folder))

            self.assertEqual({"json", "csv", "md"}, set(paths))
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertTrue(payload["audit_only"])
            self.assertTrue(payload["execution_locked"])
            self.assertEqual(1, payload["review_summary"]["proposed_for_cleanup_count"])
            markdown = paths["md"].read_text(encoding="utf-8")
            self.assertIn("AUDIT-ONLY", markdown)
            self.assertIn("/homeassistant/custom_components/demo/__pycache__/demo.pyc", markdown)
            with paths["csv"].open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter=";"))
            self.assertEqual("yes", rows[0]["proposed_for_cleanup"])

    def test_manifest_mount_is_read_only(self) -> None:
        manifest = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("read_only: true", manifest)
        self.assertNotIn("read_only: false", manifest)


if __name__ == "__main__":
    unittest.main()
