from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

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
        self.assertEqual("user_directed_cleanup_with_protected_core", payload["destructive_scope"])
        self.assertFalse(payload["evidence_gate_enforced"])
        self.assertTrue(payload["user_directed_risk_acceptance"])
        self.assertFalse(payload["file_execution_enabled"])
        self.assertFalse(payload["registry_execution_enabled"])

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

    def test_plan_endpoint_allows_only_verified_quarantine_followup(self) -> None:
        cache = Path(self.config_temp.name) / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        old = time.time() - 40 * 86400
        cache.touch()
        import os
        os.utime(cache, (old, old))
        (cache.parent.parent / "demo.py").write_text("# source", encoding="utf-8")
        _, started = self.request("/api/scans", "POST", {})
        for _ in range(50):
            _, scan = self.request(f"/api/scans/{started['id']}")
            if scan["status"] == "completed":
                break
            time.sleep(0.02)
        selected_id = next(item["id"] for item in scan["items"] if item["risk"] == "safe")
        status, payload = self.request(
            "/api/plans/preview",
            "POST",
            {"backup_choice": "existing", "selected_ids": [selected_id]},
        )
        self.assertEqual(201, status)
        self.assertEqual("awaiting_execution_choice", payload["status"])
        self.assertFalse(payload["plan"]["execution_locked"])
        self.assertEqual(1, payload["plan"]["summary"]["executable_actions"])
        plan_id = payload["plan"]["id"]
        with urllib.request.urlopen(f"{self.base}/api/plans/{plan_id}.md", timeout=5) as response:
            markdown = response.read().decode("utf-8")
        self.assertIn("impact- en herstelplan", markdown)
        self.server.state.backup_manager._save([{
            "token": "verified-plan", "status": "completed", "requested_at": datetime.now(timezone.utc).isoformat()
        }])
        status, quarantined = self.request("/api/quarantine", "POST", {
            "plan_id": plan_id, "backup_evidence_token": "verified-plan", "confirmation": "QUARANTAINE",
        })
        self.assertEqual(201, status)
        self.assertFalse(cache.exists())
        self.assertEqual("quarantined", quarantined["operation"]["files"][0]["status"])

    def test_plan_endpoint_accepts_review_file_for_user_directed_quarantine(self) -> None:
        candidate = Path(self.config_temp.name) / "downloads" / "firmware.tmp"
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"unknown")
        old = time.time() - 40 * 86400
        import os
        os.utime(candidate, (old, old))
        _, started = self.request("/api/scans", "POST", {})
        for _ in range(50):
            _, scan = self.request(f"/api/scans/{started['id']}")
            if scan["status"] == "completed":
                break
            time.sleep(0.02)
        review_id = next(item["id"] for item in scan["items"] if item["risk"] == "review")
        status, payload = self.request("/api/plans/preview", "POST", {"selected_ids": [review_id]})
        self.assertEqual(201, status)
        self.assertEqual("review", payload["plan"]["files"][0]["risk"])

    def test_recorder_purge_requires_backup_and_exact_confirmation(self) -> None:
        calls = []
        self.server.state.purge_manager.purge_caller = lambda days, repack, apply_filter: calls.append((days, repack, apply_filter))
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/recorder/purge", "POST", {"keep_days": 10, "repack": False, "apply_filter": False, "backup_confirmed": False, "confirmation": "PURGE"})
        self.assertEqual(400, raised.exception.code)

        self.server.state.backup_manager._save([{"token": "verified", "status": "completed", "requested_at": datetime.now(timezone.utc).isoformat()}])
        status, payload = self.request("/api/recorder/purge", "POST", {"keep_days": 7, "repack": True, "apply_filter": False, "backup_confirmed": True, "backup_evidence_token": "verified", "confirmation": "PURGE"})
        self.assertEqual(202, status)
        self.assertEqual("accepted", payload["status"])
        self.assertEqual([(7, True, False)], calls)
        _, history = self.request("/api/recorder/purges")
        self.assertEqual(7, history["items"][0]["keep_days"])

    def test_completed_scan_exposes_downloadable_report(self) -> None:
        cache = Path(self.config_temp.name) / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        old = time.time() - 40 * 86400
        import os
        os.utime(cache, (old, old))
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
        _, summary = self.request(f"/api/scans/{scan_id}/summary")
        self.assertNotIn("items", summary)
        _, latest_summary = self.request("/api/scans/latest?summary=1")
        self.assertNotIn("items", latest_summary)
        _, page = self.request(f"/api/scans/{scan_id}/files?limit=1")
        self.assertEqual(1, page["limit"])
        self.assertLessEqual(len(page["items"]), 1)
        _, history = self.request("/api/scans/history")
        self.assertEqual(scan_id, history["items"][0]["id"])


if __name__ == "__main__":
    unittest.main()
