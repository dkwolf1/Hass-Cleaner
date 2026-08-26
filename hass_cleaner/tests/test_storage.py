from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hass_cleaner.availability import update_entity_decision
from hass_cleaner.storage import atomic_write_json


class StorageTests(unittest.TestCase):
    def test_atomic_writer_leaves_complete_json_and_no_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda value: atomic_write_json(path, {"value": value}), range(40)))

            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(stored["value"], range(40))
            self.assertEqual([], list(path.parent.glob(f".{path.name}.*.tmp")))

    def test_concurrent_entity_choices_do_not_overwrite_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "entity-decisions.json"
            entity_ids = [f"sensor.concurrent_{index}" for index in range(30)]
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda entity_id: update_entity_decision(path, entity_id, "expected"), entity_ids))

            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(entity_ids), set(stored))


if __name__ == "__main__":
    unittest.main()
