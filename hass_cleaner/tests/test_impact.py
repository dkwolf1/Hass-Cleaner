from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hass_cleaner.impact import analyze_file


class ImpactTests(unittest.TestCase):
    def test_yaml_preview_lists_keys_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "configuration.yaml.bak"
            path.write_text("recorder:\n  purge_keep_days: 10\npassword: super-secret-value\n", encoding="utf-8")
            advice = analyze_file(path, "temporary_or_backup", "review", "backup")
            serialized = json.dumps(advice, ensure_ascii=False)
            self.assertNotIn("super-secret-value", serialized)
            self.assertEqual("yaml_keys", advice["content_preview"]["kind"])
            self.assertEqual(1, advice["content_preview"]["redacted_sensitive_keys"])

    def test_json_preview_never_contains_values(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.json.old"
            path.write_text('{"api_token":"do-not-leak","nested":{"enabled":true}}', encoding="utf-8")
            advice = analyze_file(path, "temporary_or_backup", "review", "backup")
            serialized = json.dumps(advice, ensure_ascii=False)
            self.assertNotIn("do-not-leak", serialized)
            self.assertIn("nested.enabled", advice["content_preview"]["key_paths"])

    def test_protected_storage_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "core.entity_registry"
            path.write_text("{}", encoding="utf-8")
            advice = analyze_file(path, "home_assistant_storage", "protected", "storage")
            self.assertEqual("blocked", advice["evidence_level"])
            self.assertFalse(advice["execution_allowed"])


if __name__ == "__main__":
    unittest.main()
