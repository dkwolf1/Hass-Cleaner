"""Additional source-family and Recorder verification regressions."""
import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests.test_references import COMPANION, analyzer, source

spec = importlib.util.spec_from_file_location("extended_sources_test", COMPANION / "sources.py")
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class ExtraSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_yaml_group_dedup_and_options_override(self):
        hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda: [SimpleNamespace(entity_id="group.lights", name="Lights", attributes={"entity_id": ["light.a"]})]),
                               config_entries=SimpleNamespace(async_entries=lambda: [SimpleNamespace(domain="derivative", entry_id="h1", title="Slope", data={"source": "sensor.old"}, options={"source": "sensor.new"})]),
                               config=SimpleNamespace(components=set()))
        with patch.dict(sys.modules, {"homeassistant.config": SimpleNamespace(async_hass_config_yaml=AsyncMock(return_value={"group": {"lights": ["light.a"]}}))}):
            result = await sources.collect_extended_sources(hass)
        self.assertEqual(1, len([s for s in result if s["id"] == "group.lights"]))
        ids = {r["target_id"] for r in analyzer.analyze(result, {})["references"]}
        self.assertIn("sensor.new", ids)
        self.assertNotIn("sensor.old", ids)

    def test_yaml_groups_helpers_templates_and_recorder(self):
        config = {"group": {"lights": ["light.one", "light.two"]},
                  "sensor": [{"platform": "derivative", "source": "sensor.power"},
                             {"platform": "template", "sensors": {"calculated": {"value_template": "{{ states('sensor.input') }}"}}}],
                  "utility_meter": {"monthly": {"source": "sensor.energy"}},
                  "recorder": {"db_url": "SECRET", "include": {"entities": ["sensor.temperature"]}},
                  "http": {"password": "SECRET"}}
        found = sources.yaml_sources(config)
        self.assertEqual(5, len(found))
        self.assertNotIn("SECRET", str(found))
        report = analyzer.analyze(found, {})
        self.assertEqual({"light.one", "light.two", "sensor.power", "sensor.input", "sensor.energy", "sensor.temperature"},
                         {r["target_id"] for r in report["references"]})

    def test_scene_members_not_scene_attributes_are_targets(self):
        report = analyzer.analyze([source({"entities": {"light.one": {"state": "on", "effect": "sensor.not_reference"}}}, "scene")], {})
        self.assertEqual(["light.one"], [r["target_id"] for r in report["references"]])

    def test_helpers_plain_text_is_not_executed_as_template(self):
        report = analyzer.analyze([source({"initial": "{{ states('sensor.example') }}"}, "helper")], {})
        self.assertEqual([], report["references"])
        energy = analyzer.analyze([source({"stat_energy_from": "{{ SECRET }}"}, "energy")], {"statistic": set()})
        self.assertNotIn("SECRET", str(energy))
        self.assertEqual("partial", energy["status"])

    def test_energy_statistics_external_history_and_prices(self):
        report = analyzer.analyze([source({"energy_sources": [{"stat_energy_from": "sensor.old_meter", "stat_energy_to": "external:meter",
                    "entity_energy_price": "sensor.price"}], "device_consumption": [{"stat_consumption": "sensor.missing"}]}, "energy")],
                    {"statistic": {"sensor.old_meter", "external:meter"}, "entity": {"sensor.price"}})
        self.assertEqual(["sensor.missing"], [r["target_id"] for r in report["references"] if r["missing"]])
        self.assertEqual(1, len(analyzer.repair_groups(report)))

    def test_missing_recorder_never_claims_statistics_are_missing_or_checked(self):
        report = analyzer.analyze([source({"stat_energy_from": "external:meter"}, "energy")], {"statistic": None})
        self.assertEqual("partial", report["status"])
        self.assertEqual("unavailable", report["references"][0]["verification"])
        self.assertFalse(report["references"][0]["missing"])
        self.assertEqual({}, analyzer.repair_groups(report))

    def test_statistics_dashboard_uses_statistics_not_entity_existence(self):
        report = analyzer.analyze([source({"type": "statistics-graph", "entities": ["external:meter", {"entity": "sensor.old"}]}, "dashboard")],
                                 {"statistic": {"external:meter", "sensor.old"}})
        self.assertEqual(2, len(report["references"]))
        self.assertTrue(all(r["target_type"] == "statistic" and not r["missing"] for r in report["references"]))

    async def test_runtime_and_config_entry_sources_plus_energy(self):
        states = [SimpleNamespace(entity_id="scene.night", name="Night", attributes={"entity_id": ["light.one"]}),
                  SimpleNamespace(entity_id="group.all", name="All", attributes={"entity_id": ["light.one"]}),
                  SimpleNamespace(entity_id="scene.remote", name="Remote", attributes={})]
        entries = [SimpleNamespace(domain="min_max", entry_id="helper1", title="Average", data={}, options={"entity_ids": ["sensor.a"]}),
                   SimpleNamespace(domain="unrelated", entry_id="private", title="Other", data={"password": "SECRET"}, options={})]
        hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda: states), config_entries=SimpleNamespace(async_entries=lambda: entries),
                               config=SimpleNamespace(components={"energy"}))
        modules = {"homeassistant.config": SimpleNamespace(async_hass_config_yaml=AsyncMock(return_value={})),
                   "homeassistant.components.energy.data": SimpleNamespace(async_get_manager=AsyncMock(return_value=SimpleNamespace(data={"stat_energy_from": "sensor.energy"})))}
        with patch.dict(sys.modules, modules):
            result = await sources.collect_extended_sources(hass)
        self.assertEqual(5, len(result))
        self.assertNotIn("SECRET", str(result))
        report = analyzer.analyze(result, {"statistic": set()})
        self.assertEqual("unavailable", report["sources"][2]["status"])
        self.assertIn("sensor.a", [r["target_id"] for r in report["references"]])

    async def test_yaml_and_energy_errors_are_isolated_and_redacted(self):
        hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda: []), config_entries=SimpleNamespace(async_entries=lambda: []),
                               config=SimpleNamespace(components={"energy"}))
        with patch.dict(sys.modules, {"homeassistant.config": SimpleNamespace(async_hass_config_yaml=AsyncMock(side_effect=ValueError("SECRET"))),
                          "homeassistant.components.energy.data": SimpleNamespace(async_get_manager=AsyncMock(side_effect=ValueError("SECRET")))}):
            result = await sources.collect_extended_sources(hass)
        self.assertEqual(2, len(result))
        self.assertNotIn("SECRET", str(result))
        self.assertTrue(all("error" in r for r in result))

    async def test_statistics_executor_success_and_failure(self):
        hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
        executor = AsyncMock(return_value=[{"statistic_id": "external:energy"}])
        with patch.dict(sys.modules, {"homeassistant.components.recorder": SimpleNamespace(get_instance=lambda h: SimpleNamespace(async_add_executor_job=executor)),
                   "homeassistant.components.recorder.statistics": SimpleNamespace(list_statistic_ids=lambda h: None)}):
            self.assertEqual({"external:energy"}, await sources.statistic_ids(hass))
            executor.side_effect = RuntimeError("offline")
            self.assertIsNone(await sources.statistic_ids(hass))
