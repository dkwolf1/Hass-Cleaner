from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hass_cleaner.scanner import scan_tree
from hass_cleaner.settings import Settings


class ScannerTests(unittest.TestCase):
    def test_scan_is_read_only_and_counts_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "custom_components" / "demo" / "__pycache__" / "demo.cpython-313.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cache")
            source = cache.parent.parent / "demo.py"
            source.write_text("# source", encoding="utf-8")
            protected = root / "secrets.yaml"
            protected.write_text("password: secret", encoding="utf-8")
            before = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in (cache, source, protected)}

            result = scan_tree(root, Settings())

            after = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in (cache, source, protected)}
            self.assertEqual("completed", result.status)
            self.assertEqual(before, after)
            self.assertEqual(3, result.visited_files)
            risks = {item.risk for item in result.items}
            self.assertEqual({"safe", "review", "protected"}, risks)

    def test_python_cache_without_source_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "custom_components" / "demo" / "__pycache__" / "missing.cpython-314.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cache")

            result = scan_tree(root, Settings())

            self.assertEqual("python_cache_without_source", result.items[0].category)
            self.assertEqual("review", result.items[0].risk)
            self.assertNotEqual("delete", result.items[0].recommended_action)

    def test_old_log_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / "home-assistant.log.old"
            log.write_bytes(b"old log")
            old = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
            os.utime(log, (old, old))
            result = scan_tree(root, Settings(min_log_age_days=14))
            self.assertEqual("old_log", result.items[0].category)


if __name__ == "__main__":
    unittest.main()
