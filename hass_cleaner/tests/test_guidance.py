from __future__ import annotations

import unittest
from dataclasses import dataclass

from hass_cleaner.guidance import build_cleanup_guidance


@dataclass
class Item:
    id: str
    path: str
    category: str
    risk: str
    size_bytes: int


class GuidanceTests(unittest.TestCase):
    def test_safe_files_are_grouped_into_selectable_recipes(self) -> None:
        guidance = build_cleanup_guidance([
            Item("1", "/homeassistant/home-assistant.log.old", "old_log", "safe", 100),
            Item("2", "/homeassistant/home-assistant.log.1", "old_log", "safe", 200),
        ])
        recipe = guidance["safe_recipes"][0]
        self.assertEqual(2, recipe["file_count"])
        self.assertEqual(300, recipe["size_bytes"])
        self.assertTrue(recipe["gate_passed"])
        self.assertTrue(recipe["selectable_for_dry_run"])

    def test_cache_is_grouped_by_generic_producer_and_blocked(self) -> None:
        guidance = build_cleanup_guidance([
            Item("1", "/homeassistant/www/media/frigate/cache/cam.jpg", "integration_cache_candidate", "review", 500),
        ])
        recipe = guidance["investigation_recipes"][0]
        self.assertEqual("frigate", recipe["producer"])
        self.assertFalse(recipe["gate_passed"])
        self.assertFalse(recipe["selectable_for_dry_run"])

    def test_installed_code_is_inventory_not_cleanup(self) -> None:
        guidance = build_cleanup_guidance([
            Item("1", "/homeassistant/custom_components/demo/__init__.py", "custom_components", "protected", 50),
        ])
        self.assertEqual([], guidance["safe_recipes"])
        self.assertEqual([], guidance["investigation_recipes"])
        self.assertEqual(50, guidance["inventory_total_bytes"])


if __name__ == "__main__":
    unittest.main()
