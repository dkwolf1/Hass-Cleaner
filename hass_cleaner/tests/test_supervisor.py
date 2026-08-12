from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hass_cleaner.supervisor import BackupEvidenceManager


class BackupEvidenceTests(unittest.TestCase):
    def test_request_only_becomes_valid_after_job_and_backup_verification(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            def getter(path: str):
                self.assertEqual("/backups", path)
                return {"backups": [{"slug": "backup-123", "name": "Hass-Cleaner test", "size": 1234}]}

            manager = BackupEvidenceManager(Path(folder), creator=lambda: {"slug": "backup-123", "job_id": "job-1", "requested_name": "Hass-Cleaner test"}, getter=getter)
            record = manager.create("Dennis")

            self.assertEqual("accepted", record["status"])
            self.assertEqual("backup-123", record["backup_reference"])
            self.assertEqual("Dennis", record["requested_by"])
            self.assertFalse(manager.valid(str(record["token"])))
            verified = manager.refresh(str(record["token"]))
            self.assertEqual("completed", verified["status"])
            self.assertTrue(manager.valid(str(record["token"])))
            self.assertFalse(manager.valid("onbekend"))


if __name__ == "__main__":
    unittest.main()
