"""Offline checks for HACS metadata and the manual companion package."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
COMPANION = ROOT / "custom_components" / "hass_cleaner"


class HacsPackagingTests(unittest.TestCase):
    def test_hacs_selects_source_directory_not_manual_zip(self):
        metadata = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["name"], "Hass-Cleaner Companion")
        self.assertEqual(metadata["homeassistant"], "2026.9.0")
        self.assertFalse(metadata["content_in_root"])
        self.assertFalse(metadata["zip_release"])
        domains = sorted(p.parent.name for p in (ROOT / "custom_components").glob("*/manifest.json"))
        self.assertEqual(domains, ["hass_cleaner"])
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        for key in ("domain", "documentation", "issue_tracker", "codeowners", "name", "version"):
            self.assertTrue(manifest[key], key)

    def test_brand_reuses_existing_icon(self):
        icon = (COMPANION / "brand" / "icon.png").read_bytes()
        self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(icon, (ROOT / "hass_cleaner" / "icon.png").read_bytes())

    def test_manual_zip_contains_brand_but_no_caches(self):
        spec = importlib.util.spec_from_file_location("package_companion_test", ROOT / "tools" / "package_companion.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copytree(COMPANION, target / "custom_components" / "hass_cleaner")
            shutil.copyfile(ROOT / "LICENSE", target / "LICENSE")
            with patch.object(module, "__file__", str(target / "tools" / "package_companion.py")):
                module.build()
            with ZipFile(next((target / "dist").glob("*.zip"))) as archive:
                names = archive.namelist()
                self.assertIn("custom_components/hass_cleaner/brand/icon.png", names)
                self.assertIn("custom_components/hass_cleaner/manifest.json", names)
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertTrue(all(name.startswith("custom_components/hass_cleaner/") for name in names))
