"""Read-only reference checks and native Home Assistant Repairs."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .references import analyze, repair_groups
from .sources import collect_extended_sources, statistic_ids

DOMAIN = "hass_cleaner"
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    websocket_api.async_register_command(hass, websocket_references)
    return True


@websocket_api.websocket_command({vol.Required("type"): "hass_cleaner/references", vol.Optional("refresh", default=False): bool})
@websocket_api.async_response
async def websocket_references(hass, connection, msg):
    if not connection.user or not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Administrator access required")
        return
    monitor = hass.data.get(DOMAIN)
    if monitor is None:
        connection.send_error(msg["id"], "not_loaded", "Set up Hass-Cleaner Companion first")
        return
    if msg["refresh"] or monitor.report is None:
        await monitor.refresh()
    connection.send_result(msg["id"], monitor.report)


async def collect_sources(hass):
    """Keep access to HA runtime configuration isolated in this adapter."""
    sources = []
    for kind in ("automation", "script"):
        component = hass.data.get(kind)
        if component is None:
            if kind in hass.config.components:
                sources.append({"id": kind, "kind": kind, "name": kind, "error": "Configuration component unavailable"})
            continue
        for entity in list(component.entities):
            sources.append({"id": entity.entity_id, "kind": kind, "name": entity.name or entity.entity_id,
                            "config": getattr(entity, "raw_config", None)})
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if lovelace is not None and dashboards is None:
        sources.append({"id": "dashboard:all", "kind": "dashboard", "name": "Dashboards", "error": "Dashboard API unavailable"})
    for url_path, dashboard in list((dashboards or {}).items()):
        source = {"id": f"dashboard:{url_path if url_path is not None else 'default'}", "kind": "dashboard",
                  "name": (dashboard.config or {}).get("title", url_path or "Overview")}
        try:
            source["config"] = await dashboard.async_load(False)
        except Exception as exc:
            # Do not log raw exception messages: they can include configuration values.
            source["error"] = f"Dashboard could not be loaded ({type(exc).__name__})"
        sources.append(source)
    sources.extend(await collect_extended_sources(hass))
    return sources


class ReferenceMonitor:
    def __init__(self, hass):
        self.hass = hass
        self.report = None
        self.lock = asyncio.Lock()
        self.closed = False

    async def refresh(self, _now=None):
        async with self.lock:
            if self.closed:
                return
            hass = self.hass
            if not hass.is_running:
                self.report = {"schema_version": 1, "status": "starting", "summary": {}, "sources": [], "references": []}
                return
            try:
                sources = await collect_sources(hass)
                known = {"entity": set(er.async_get(hass).entities) | set(hass.states.async_entity_ids()),
                         "entity_aliases": {e.id: e.entity_id for e in er.async_get(hass).entities.values()},
                         "device": set(dr.async_get(hass).devices), "area": set(ar.async_get(hass).areas),
                         "action": {f"{domain}.{service}" for domain, services in hass.services.async_services().items() for service in services}}
                known["statistic"] = await statistic_ids(hass)
                report = await hass.async_add_executor_job(analyze, sources, known)
                if self.closed:
                    return
                self.reconcile(report)
                self.report = report
            except Exception as exc:
                if not self.report or self.report.get("status") != "unavailable":
                    _LOGGER.warning("Reference check could not complete (%s)", type(exc).__name__)
                self.report = {"schema_version": 1, "status": "unavailable", "summary": {}, "sources": [], "references": [],
                               "error": "Reference check failed; previous repair issues have been retained"}

    @callback
    def reconcile(self, report):
        groups = repair_groups(report)
        registry = ir.async_get(self.hass)
        # A failed/partial source must not falsely resolve its existing issue.
        complete = {s["id"] for s in report["sources"] if s["status"] == "checked"}
        seen = {s["id"] for s in report["sources"]}
        for (domain, issue_id), issue in list(registry.issues.items()):
            if domain != DOMAIN or not issue_id.startswith("reference_") or issue_id in groups:
                continue
            source_id = (issue.data or {}).get("source_id")
            if source_id in complete or (source_id not in seen and report["status"] == "completed"):
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for issue_id, group in groups.items():
            details = "\n".join("- " + item for item in group["items"][:30])
            ir.async_create_issue(self.hass, DOMAIN, issue_id, is_fixable=False, is_persistent=False,
                severity=ir.IssueSeverity.ERROR, translation_key="missing_references",
                translation_placeholders={"source": group["source"], "references": details, "count": str(len(group["items"]))},
                data={"source_id": group["source_id"]},
                learn_more_url="https://github.com/dkwolf1/Hass-Cleaner/blob/main/docs/reference-checks.md")


async def async_setup_entry(hass, entry):
    monitor = hass.data[DOMAIN] = ReferenceMonitor(hass)
    entry.async_on_unload(async_track_time_interval(hass, monitor.refresh, timedelta(minutes=5)))
    if hass.is_running:
        await monitor.refresh()
    else:
        async def started(_event):
            await monitor.refresh()
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, started))
    return True


async def async_unload_entry(hass, entry):
    monitor = hass.data.pop(DOMAIN)
    monitor.closed = True
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith("reference_"):
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    return True
