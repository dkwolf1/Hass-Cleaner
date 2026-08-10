from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from hass_cleaner.server import create_server


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_temp = tempfile.TemporaryDirectory()
        self.data_temp = tempfile.TemporaryDirectory()
        self.server = create_server(
            "127.0.0.1",
            0,
            Path(self.config_temp.name),
            Path(self.data_temp.name),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.config_temp.cleanup()
        self.data_temp.cleanup()

    def request(self, path: str, method: str = "GET", payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_and_status(self) -> None:
        status, health = self.request("/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", health["status"])
        status, payload = self.request("/api/status")
        self.assertEqual(200, status)
        self.assertFalse(payload["destructive_execution_enabled"])

    def test_retention_range_is_enforced(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request(
                "/api/settings",
                "POST",
                {
                    "min_temp_age_days": 30,
                    "min_log_age_days": 14,
                    "deletion_mode": "quarantine",
                    "retention_days": 11,
                },
            )
        self.assertEqual(400, raised.exception.code)

    def test_plan_endpoint_is_dry_run_only(self) -> None:
        status, payload = self.request(
            "/api/plans/preview",
            "POST",
            {"backup_choice": "existing", "deletion_mode": "quarantine", "retention_days": 4, "selected_ids": ["abc"]},
        )
        self.assertEqual(202, status)
        self.assertEqual("dry_run_only", payload["status"])

    def test_completed_scan_exposes_downloadable_report(self) -> None:
        cache = Path(self.config_temp.name) / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        (cache.parent.parent / "demo.py").write_text("# source", encoding="utf-8")
        _, started = self.request("/api/scans", "POST", {})
        scan_id = started["id"]
        for _ in range(50):
            _, scan = self.request(f"/api/scans/{scan_id}")
            if scan["status"] == "completed":
                break
            time.sleep(0.02)
        else:
            self.fail("scan werd niet voltooid")
        with urllib.request.urlopen(f"{self.base}/api/reports/{scan_id}.json", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual("attachment", response.headers["Content-Disposition"].split(";", 1)[0])
        self.assertTrue(payload["audit_only"])
        self.assertTrue(payload["execution_locked"])


if __name__ == "__main__":
    unittest.main()
