from __future__ import annotations

import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.policy import RISK_PROTECTED, RISK_REVIEW, RISK_SAFE, classify


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def classify_file(self, relative: str, *, old: bool = True):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
        if old:
            os.utime(path, (self.old, self.old))
        metadata = path.lstat()
        return classify(
            self.root,
            path,
            metadata.st_mode,
            metadata.st_mtime,
            min_temp_age_days=30,
            min_log_age_days=14,
        )

    def test_storage_is_absolutely_protected(self) -> None:
        decision = self.classify_file(".storage/core.entity_registry")
        self.assertEqual(RISK_PROTECTED, decision.risk)

    def test_database_is_protected(self) -> None:
        decision = self.classify_file("home-assistant_v2.db-wal")
        self.assertEqual(RISK_PROTECTED, decision.risk)

    def test_custom_component_source_is_review_only(self) -> None:
        decision = self.classify_file("custom_components/example/__init__.py")
        self.assertEqual(RISK_REVIEW, decision.risk)

    def test_python_cache_inside_custom_component_is_safe(self) -> None:
        decision = self.classify_file("custom_components/example/__pycache__/code.cpython-313.pyc")
        self.assertEqual(RISK_SAFE, decision.risk)
        self.assertEqual("python_cache", decision.category)

    def test_tmp_is_never_marked_safe(self) -> None:
        decision = self.classify_file("downloads/firmware.tmp")
        self.assertEqual(RISK_REVIEW, decision.risk)

    def test_recent_editor_file_is_ignored(self) -> None:
        decision = self.classify_file("dashboard.yaml~", old=False)
        self.assertIsNone(decision)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks niet beschikbaar")
    def test_symlink_is_protected(self) -> None:
        target = self.root / "target.txt"
        target.write_text("target", encoding="utf-8")
        link = self.root / "link.tmp"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlink maken vereist extra rechten")
        metadata = link.lstat()
        self.assertTrue(stat.S_ISLNK(metadata.st_mode))
        decision = classify(
            self.root,
            link,
            metadata.st_mode,
            metadata.st_mtime,
            min_temp_age_days=1,
            min_log_age_days=1,
        )
        self.assertEqual(RISK_PROTECTED, decision.risk)


if __name__ == "__main__":
    unittest.main()
