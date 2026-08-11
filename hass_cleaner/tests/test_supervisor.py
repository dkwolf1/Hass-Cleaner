from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hass_cleaner.supervisor import BackupEvidenceManager


class BackupEvidenceTests(unittest.TestCase):
    def test_accepted_request_is_audited_but_not_called_completed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            manager = BackupEvidenceManager(Path(folder), creator=lambda: {"slug": "backup-123"})
            record = manager.create("Dennis")

            self.assertEqual("accepted", record["status"])
            self.assertEqual("backup-123", record["backup_reference"])
            self.assertEqual("Dennis", record["requested_by"])
            self.assertTrue(manager.valid(str(record["token"])))
            self.assertFalse(manager.valid("onbekend"))


if __name__ == "__main__":
    unittest.main()
