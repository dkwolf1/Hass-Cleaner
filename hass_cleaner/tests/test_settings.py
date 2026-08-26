from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hass_cleaner.settings import Settings, load_effective_settings, load_settings, save_local_settings


class SettingsTests(unittest.TestCase):
    def test_legacy_permanent_mode_is_ignored_in_supervisor_options(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "options.json").write_text(json.dumps({
                "min_temp_age_days": 31,
                "min_log_age_days": 15,
                "deletion_mode": "permanent",
                "retention_days": 8,
                "advanced_mode": False,
                "report_retention_count": 11,
                "language": "nl",
            }), encoding="utf-8")

            settings = load_settings(root)
            self.assertEqual(8, settings.retention_days)
            self.assertFalse(hasattr(settings, "deletion_mode"))

    def test_legacy_permanent_mode_is_ignored_in_ui_override(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ui-settings.json").write_text(json.dumps({
                "min_temp_age_days": 32,
                "min_log_age_days": 16,
                "deletion_mode": "permanent",
                "retention_days": 9,
                "advanced_mode": True,
                "report_retention_count": 12,
                "language": "en",
            }), encoding="utf-8")

            settings = load_effective_settings(root)
            self.assertEqual(9, settings.retention_days)
            self.assertFalse(hasattr(settings, "deletion_mode"))

    def test_new_ui_settings_do_not_persist_removed_mode(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            save_local_settings(root, Settings(retention_days=6))
            stored = json.loads((root / "ui-settings.json").read_text(encoding="utf-8"))
            self.assertNotIn("deletion_mode", stored)


if __name__ == "__main__":
    unittest.main()
