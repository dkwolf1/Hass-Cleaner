"""HA adapter contract tests. These do not replace testing inside a live HA Core."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tests.test_references import COMPANION, analyzer, source


def load_companion():
    identity = lambda func: func
    ws = SimpleNamespace(websocket_command=lambda schema: identity, async_response=identity,
                         async_register_command=Mock())
    modules = {
        "homeassistant": SimpleNamespace(),
        "homeassistant.components": SimpleNamespace(websocket_api=ws),
        "homeassistant.const": SimpleNamespace(EVENT_HOMEASSISTANT_STARTED="started"),
        "homeassistant.core": SimpleNamespace(callback=identity),
        "homeassistant.helpers": SimpleNamespace(area_registry=SimpleNamespace(), device_registry=SimpleNamespace(),
                                                  entity_registry=SimpleNamespace(), issue_registry=SimpleNamespace()),
        "homeassistant.helpers.event": SimpleNamespace(async_track_time_interval=Mock()),
    }
    spec = importlib.util.spec_from_file_location("_companion_contract", COMPANION / "__init__.py",
                                                 submodule_search_locations=[str(COMPANION)])
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**modules, "_companion_contract": module}):
        spec.loader.exec_module(module)
    module.collect_extended_sources = AsyncMock(return_value=[])
    return module


class CompanionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.companion = load_companion()
        self.issues = {}
        def create(hass, domain, issue_id, **kwargs):
            previous = self.issues.get((domain, issue_id))
            self.issues[domain, issue_id] = SimpleNamespace(**kwargs, ignored=getattr(previous, "ignored", False))
        def delete(hass, domain, issue_id):
            self.issues.pop((domain, issue_id), None)
        self.companion.ir = SimpleNamespace(async_get=lambda hass: SimpleNamespace(issues=self.issues),
                                            async_create_issue=create, async_delete_issue=delete,
                                            IssueSeverity=SimpleNamespace(ERROR="error"))
        self.hass = SimpleNamespace(data={}, config=SimpleNamespace(components=set()), is_running=True,
                                    async_add_executor_job=AsyncMock(side_effect=lambda func, *args: func(*args)))
        self.monitor = self.companion.ReferenceMonitor(self.hass)

    async def test_repairs_stable_ignored_and_auto_resolved(self):
        broken = analyzer.analyze([source({"entity_id": "sensor.old"})], {})
        self.monitor.reconcile(broken)
        key = next(iter(self.issues))
        self.assertFalse(self.issues[key].is_fixable)
        self.assertFalse(self.issues[key].is_persistent)
        self.issues[key].ignored = True
        self.monitor.reconcile(broken)
        self.assertTrue(self.issues[key].ignored)
        self.monitor.reconcile(analyzer.analyze([source({"entity_id": "sensor.old"})], {"entity": {"sensor.old"}}))
        self.assertEqual({}, self.issues)

    async def test_failed_or_partial_source_does_not_resolve_issue(self):
        self.monitor.reconcile(analyzer.analyze([source({"entity_id": "sensor.old"})], {}))
        self.monitor.reconcile(analyzer.analyze([source(None)], {}))
        self.assertEqual(1, len(self.issues))
        self.monitor.reconcile(analyzer.analyze([source({"value_template": "{{ dynamic }}"})], {}))
        self.assertEqual(1, len(self.issues))
        self.monitor.reconcile(analyzer.analyze([], {}))
        self.assertEqual({}, self.issues)

    async def test_other_integrations_and_other_issues_untouched(self):
        self.issues["spook", "reference_test"] = SimpleNamespace(data={})
        self.issues["hass_cleaner", "other"] = SimpleNamespace(data={})
        self.monitor.reconcile(analyzer.analyze([], {}))
        self.assertEqual(2, len(self.issues))

    async def test_collect_loaded_configs_and_isolate_dashboard_failure(self):
        self.hass.data = {
            "automation": SimpleNamespace(entities=[SimpleNamespace(entity_id="automation.a", name="A", raw_config={"entity_id": "light.a"})]),
            "script": SimpleNamespace(entities=[SimpleNamespace(entity_id="script.a", name=None, raw_config=None)]),
            "lovelace": SimpleNamespace(dashboards={
                None: SimpleNamespace(config=None, async_load=AsyncMock(return_value={"views": []})),
                "lovelace": SimpleNamespace(config={"title": "Overview YAML"}, async_load=AsyncMock(return_value={"views": []})),
                "broken": SimpleNamespace(config={"title": "Broken"}, async_load=AsyncMock(side_effect=ValueError("SECRET")))})}
        sources = await self.companion.collect_sources(self.hass)
        self.assertEqual(5, len(sources))
        self.assertEqual(5, len({s["id"] for s in sources}))
        self.assertNotIn("SECRET", json.dumps(sources))
        self.assertIsNone(sources[1]["config"])
        self.assertIn("error", sources[-1])

    async def test_websocket_admin_only_and_not_loaded(self):
        connection = SimpleNamespace(user=SimpleNamespace(is_admin=False), send_error=Mock(), send_result=Mock())
        await self.companion.websocket_references(self.hass, connection, {"id": 1, "refresh": True})
        self.assertEqual("unauthorized", connection.send_error.call_args.args[1])
        connection.user.is_admin = True
        await self.companion.websocket_references(self.hass, connection, {"id": 2, "refresh": True})
        self.assertEqual("not_loaded", connection.send_error.call_args.args[1])
        monitor = SimpleNamespace(report={"status": "completed"}, refresh=AsyncMock())
        self.hass.data["hass_cleaner"] = monitor
        await self.companion.websocket_references(self.hass, connection, {"id": 3, "refresh": False})
        monitor.refresh.assert_not_awaited()
        connection.send_result.assert_called_once_with(3, monitor.report)
        await self.companion.websocket_references(self.hass, connection, {"id": 4, "refresh": True})
        monitor.refresh.assert_awaited_once()

    async def test_waits_for_startup_and_failed_refresh_retains_issues(self):
        self.hass.is_running = False
        await self.monitor.refresh()
        self.assertEqual("starting", self.monitor.report["status"])
        self.monitor.reconcile(analyzer.analyze([source({"entity_id": "sensor.old"})], {}))
        self.hass.is_running = True
        with patch.object(self.companion, "collect_sources", AsyncMock(side_effect=ValueError("SECRET"))):
            with self.assertLogs(self.companion._LOGGER, "WARNING") as logs:
                await self.monitor.refresh()
            self.assertNotIn("SECRET", str(logs.output))
        self.assertEqual("unavailable", self.monitor.report["status"])
        self.assertEqual(1, len(self.issues))

    async def test_refresh_runs_analyzer_off_event_loop(self):
        self.hass.states = SimpleNamespace(async_entity_ids=lambda: ["sensor.runtime"])
        self.hass.services = SimpleNamespace(async_services=lambda: {"light": {"turn_on": {}}})
        self.companion.er = SimpleNamespace(async_get=lambda h: SimpleNamespace(entities={"sensor.disabled": SimpleNamespace(id="a" * 32, entity_id="sensor.disabled")}))
        self.companion.dr = SimpleNamespace(async_get=lambda h: SimpleNamespace(devices={}))
        self.companion.ar = SimpleNamespace(async_get=lambda h: SimpleNamespace(areas={}))
        with patch.object(self.companion, "collect_sources", AsyncMock(return_value=[source({"entity_id": ["sensor.runtime", "sensor.disabled"], "action": "light.turn_on"})])):
            await self.monitor.refresh()
        self.assertEqual(0, self.monitor.report["summary"]["missing"])
        self.hass.async_add_executor_job.assert_awaited_once()

    async def test_unload_stops_future_work_and_removes_only_own_repairs(self):
        self.hass.data["hass_cleaner"] = self.monitor
        self.monitor.reconcile(analyzer.analyze([source({"entity_id": "sensor.old"})], {}))
        self.issues["spook", "reference_test"] = SimpleNamespace(data={})
        await self.companion.async_unload_entry(self.hass, None)
        self.assertTrue(self.monitor.closed)
        await self.monitor.refresh()
        self.hass.async_add_executor_job.assert_not_awaited()
        self.assertEqual([("spook", "reference_test")], list(self.issues))

    async def test_translation_placeholders_match(self):
        from hass_cleaner import __version__
        manifest = json.loads((COMPANION / "manifest.json").read_text())
        self.assertEqual(__version__, manifest["version"])
        self.assertTrue(manifest["config_flow"])
        strings = json.loads((COMPANION / "strings.json").read_text())
        for language in ("en", "nl"):
            value = json.loads((COMPANION / "translations" / f"{language}.json").read_text())
            issue = value["issues"]["missing_references"]
            for placeholder in ("source", "count", "references"):
                self.assertIn("{" + placeholder + "}", issue["description"])
        self.assertEqual(strings, json.loads((COMPANION / "translations" / "en.json").read_text()))
