from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .impact import analyze_bundle


WEBSOCKET_URL = "ws://supervisor/core/websocket"


class HomeAssistantApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryFinding:
    id: str
    subject_type: str
    subject_id: str
    name: str
    category: str
    severity: str
    reason: str
    related_id: str = ""
    recommended_action: str = "none"


@dataclass(frozen=True)
class RegistryBundle:
    id: str
    title: str
    domain: str
    config_entry_id: str
    state: str
    devices: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    review_count: int
    informational_count: int
    advice: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegistryAudit:
    status: str
    summary: dict[str, int] = field(default_factory=dict)
    findings: list[RegistryFinding] = field(default_factory=list)
    bundles: list[RegistryBundle] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [asdict(item) for item in self.findings],
            "bundles": [asdict(item) for item in self.bundles],
            "error": self.error,
            "audit_only": True,
            "destructive_actions_available": False,
        }


def scan_home_assistant_registries() -> RegistryAudit:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return RegistryAudit(
            status="unavailable",
            error="Registerscan is alleen beschikbaar binnen Home Assistant",
        )
    try:
        snapshot = fetch_registry_snapshot(token)
        return audit_registry_snapshot(snapshot)
    except Exception as exc:  # fail closed: a file audit may still complete
        return RegistryAudit(
            status="failed",
            error=f"Home Assistant-registers konden niet read-only worden gescand: {type(exc).__name__}: {exc}",
        )


def fetch_registry_snapshot(
    token: str,
    *,
    connect: Callable[..., Any] | None = None,
    url: str = WEBSOCKET_URL,
) -> dict[str, list[dict[str, Any]]]:
    if connect is None:
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover - covered by container build
            raise HomeAssistantApiError("Python-package websocket-client ontbreekt") from exc
        connect = websocket.create_connection

    connection = connect(
        url,
        timeout=15,
        header=[f"Authorization: Bearer {token}"],
    )
    try:
        greeting = _receive_json(connection)
        if greeting.get("type") == "auth_required":
            connection.send(json.dumps({"type": "auth", "access_token": token}))
            authentication = _receive_json(connection)
        else:
            authentication = greeting
        if authentication.get("type") != "auth_ok":
            raise HomeAssistantApiError(authentication.get("message", "WebSocket-authenticatie geweigerd"))

        commands = {
            "entities": "config/entity_registry/list",
            "devices": "config/device_registry/list",
            "areas": "config/area_registry/list",
            "config_entries": "config_entries/get",
            "states": "get_states",
        }
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for command_id, (key, command_type) in enumerate(commands.items(), start=1):
            connection.send(json.dumps({"id": command_id, "type": command_type}))
            response = _receive_result(connection, command_id)
            result = response.get("result")
            if not isinstance(result, list):
                raise HomeAssistantApiError(f"Ongeldig antwoord voor {command_type}")
            snapshot[key] = [item for item in result if isinstance(item, dict)]
        return snapshot
    finally:
        connection.close()


def audit_registry_snapshot(snapshot: dict[str, list[dict[str, Any]]]) -> RegistryAudit:
    entities = snapshot.get("entities", [])
    devices = snapshot.get("devices", [])
    areas = snapshot.get("areas", [])
    config_entries = snapshot.get("config_entries", [])
    states = snapshot.get("states", [])

    device_ids = {_identifier(item, "id", "device_id") for item in devices}
    device_ids.discard("")
    area_ids = {_identifier(item, "area_id", "id") for item in areas}
    area_ids.discard("")
    config_entry_ids = {_identifier(item, "entry_id", "id") for item in config_entries}
    config_entry_ids.discard("")
    state_ids = {_identifier(item, "entity_id") for item in states}
    state_ids.discard("")

    findings: list[RegistryFinding] = []
    entities_by_device: dict[str, int] = {}
    used_areas: set[str] = set()

    for entity in entities:
        entity_id = _identifier(entity, "entity_id")
        if not entity_id:
            continue
        name = _display_name(entity, entity_id)
        device_id = _identifier(entity, "device_id")
        area_id = _identifier(entity, "area_id")
        config_entry_id = _identifier(entity, "config_entry_id")
        disabled_by = entity.get("disabled_by")

        if device_id:
            entities_by_device[device_id] = entities_by_device.get(device_id, 0) + 1
            if device_id not in device_ids:
                findings.append(_finding("entity", entity_id, name, "missing_device_reference", "review", "Entity verwijst naar een apparaat dat niet in het apparaatregister bestaat", device_id))
        else:
            findings.append(_finding("entity", entity_id, name, "entity_without_device", "info", "Entity is niet aan een apparaat gekoppeld; dit kan normaal zijn voor helpers, templates en virtuele sensoren"))

        if area_id:
            used_areas.add(area_id)
            if area_id not in area_ids:
                findings.append(_finding("entity", entity_id, name, "missing_area_reference", "review", "Entity verwijst naar een gebied dat niet in het gebiedsregister bestaat", area_id))
        if config_entry_id and config_entry_id not in config_entry_ids:
            findings.append(_finding("entity", entity_id, name, "missing_config_entry_reference", "review", "Entity verwijst naar een configuratie-entry die niet meer bestaat", config_entry_id))
        if disabled_by is not None:
            findings.append(_finding("entity", entity_id, name, "disabled_entity", "info", f"Entity is uitgeschakeld door {disabled_by}"))
        elif entity_id not in state_ids:
            findings.append(_finding("entity", entity_id, name, "entity_not_loaded", "review", "Ingeschakelde registry-entity heeft momenteel geen state in Home Assistant"))

    for device in devices:
        device_id = _identifier(device, "id", "device_id")
        if not device_id:
            continue
        name = _display_name(device, device_id)
        area_id = _identifier(device, "area_id")
        via_device_id = _identifier(device, "via_device_id")
        if entities_by_device.get(device_id, 0) == 0:
            findings.append(_finding("device", device_id, name, "device_without_entities", "info", "Apparaat heeft geen gekoppelde registry-entities; services en hubs kunnen legitiem leeg zijn"))
        if area_id:
            used_areas.add(area_id)
            if area_id not in area_ids:
                findings.append(_finding("device", device_id, name, "missing_area_reference", "review", "Apparaat verwijst naar een gebied dat niet in het gebiedsregister bestaat", area_id))
        if via_device_id and via_device_id not in device_ids:
            findings.append(_finding("device", device_id, name, "missing_parent_device_reference", "review", "Apparaat verwijst naar een bovenliggend apparaat dat niet meer bestaat", via_device_id))
        for entry_id in _device_config_entry_ids(device):
            if entry_id not in config_entry_ids:
                findings.append(_finding("device", device_id, name, "missing_config_entry_reference", "review", "Apparaat verwijst naar een configuratie-entry die niet meer bestaat", entry_id))

    for area in areas:
        area_id = _identifier(area, "area_id", "id")
        if area_id and area_id not in used_areas:
            findings.append(_finding("area", area_id, _display_name(area, area_id), "empty_area", "info", "Gebied heeft geen rechtstreeks gekoppelde entities of apparaten"))

    summary = {
        "entities_total": len(entities),
        "devices_total": len(devices),
        "areas_total": len(areas),
        "config_entries_total": len(config_entries),
        "states_total": len(states),
        "entities_without_device": _count(findings, "entity_without_device"),
        "broken_references": sum(1 for item in findings if item.category.startswith("missing_")),
        "entities_not_loaded": _count(findings, "entity_not_loaded"),
        "disabled_entities": _count(findings, "disabled_entity"),
        "devices_without_entities": _count(findings, "device_without_entities"),
        "empty_areas": _count(findings, "empty_area"),
        "unavailable_states": sum(1 for item in states if item.get("state") == "unavailable"),
        "review_findings": sum(1 for item in findings if item.severity == "review"),
        "informational_findings": sum(1 for item in findings if item.severity == "info"),
    }
    bundles = _build_bundles(entities, devices, config_entries, findings)
    summary["bundles_total"] = len(bundles)
    return RegistryAudit(status="completed", summary=summary, findings=findings, bundles=bundles)


def fetch_related(
    item_type: str,
    item_id: str,
    *,
    token: str | None = None,
    connect: Callable[..., Any] | None = None,
    url: str = WEBSOCKET_URL,
) -> dict[str, list[str]]:
    """Ask Home Assistant for the official relationship graph of one item."""
    if item_type not in {"config_entry", "device", "entity"}:
        raise HomeAssistantApiError("Dit relatietype wordt niet ondersteund")
    access_token = token or os.environ.get("SUPERVISOR_TOKEN")
    if not access_token:
        raise HomeAssistantApiError("Relatieanalyse is alleen beschikbaar binnen Home Assistant")
    if connect is None:
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover
            raise HomeAssistantApiError("Python-package websocket-client ontbreekt") from exc
        connect = websocket.create_connection
    connection = connect(url, timeout=20, header=[f"Authorization: Bearer {access_token}"])
    try:
        greeting = _receive_json(connection)
        if greeting.get("type") == "auth_required":
            connection.send(json.dumps({"type": "auth", "access_token": access_token}))
            authentication = _receive_json(connection)
        else:
            authentication = greeting
        if authentication.get("type") != "auth_ok":
            raise HomeAssistantApiError(authentication.get("message", "WebSocket-authenticatie geweigerd"))
        connection.send(json.dumps({"id": 1, "type": "search/related", "item_type": item_type, "item_id": item_id}))
        result = _receive_result(connection, 1).get("result")
        if not isinstance(result, dict):
            raise HomeAssistantApiError("Ongeldig antwoord van search/related")
        return {
            str(key): sorted(str(value) for value in values if isinstance(value, str))
            for key, values in result.items()
            if isinstance(values, list)
        }
    finally:
        connection.close()


def _build_bundles(
    entities: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    config_entries: list[dict[str, Any]],
    findings: list[RegistryFinding],
) -> list[RegistryBundle]:
    entries = {_identifier(item, "entry_id", "id"): item for item in config_entries}
    grouped_entities: dict[str, list[dict[str, Any]]] = {}
    grouped_devices: dict[str, list[dict[str, Any]]] = {}

    for entity in entities:
        entry_id = _identifier(entity, "config_entry_id")
        if not entry_id:
            platform = _identifier(entity, "platform") or _identifier(entity, "entity_id").partition(".")[0] or "overig"
            entry_id = f"unlinked:{platform}"
        grouped_entities.setdefault(entry_id, []).append(entity)

    for device in devices:
        entry_ids = _device_config_entry_ids(device)
        if not entry_ids:
            entry_ids = {"unlinked:devices"}
        for entry_id in entry_ids:
            grouped_devices.setdefault(entry_id, []).append(device)

    bundle_ids = set(entries) | set(grouped_entities) | set(grouped_devices)
    findings_by_subject: dict[str, list[RegistryFinding]] = {}
    for finding in findings:
        findings_by_subject.setdefault(finding.subject_id, []).append(finding)

    bundles: list[RegistryBundle] = []
    for entry_id in bundle_ids:
        entry = entries.get(entry_id, {})
        bundle_entities = grouped_entities.get(entry_id, [])
        bundle_devices = grouped_devices.get(entry_id, [])
        entity_ids_by_device: dict[str, list[str]] = {}
        for entity in bundle_entities:
            device_id = _identifier(entity, "device_id")
            if device_id:
                entity_ids_by_device.setdefault(device_id, []).append(_identifier(entity, "entity_id"))
        child_ids_by_parent: dict[str, list[str]] = {}
        for device in bundle_devices:
            parent_id = _identifier(device, "via_device_id")
            if parent_id:
                child_ids_by_parent.setdefault(parent_id, []).append(_identifier(device, "id", "device_id"))

        entity_summaries = [
            {
                "entity_id": _identifier(item, "entity_id"),
                "name": _display_name(item, _identifier(item, "entity_id")),
                "device_id": _identifier(item, "device_id"),
                "area_id": _identifier(item, "area_id"),
                "platform": _identifier(item, "platform"),
                "disabled": item.get("disabled_by") is not None,
            }
            for item in bundle_entities
        ]
        device_summaries = []
        for item in bundle_devices:
            device_id = _identifier(item, "id", "device_id")
            device_summaries.append(
                {
                    "device_id": device_id,
                    "name": _display_name(item, device_id),
                    "manufacturer": _identifier(item, "manufacturer"),
                    "model": _identifier(item, "model", "model_id"),
                    "area_id": _identifier(item, "area_id"),
                    "via_device_id": _identifier(item, "via_device_id"),
                    "entity_ids": sorted(entity_ids_by_device.get(device_id, [])),
                    "child_device_ids": sorted(child_ids_by_parent.get(device_id, [])),
                }
            )

        subject_ids = {item["entity_id"] for item in entity_summaries} | {item["device_id"] for item in device_summaries}
        bundle_findings = [finding for subject_id in subject_ids for finding in findings_by_subject.get(subject_id, [])]
        unlinked = entry_id.startswith("unlinked:")
        domain = _identifier(entry, "domain") or (entry_id.split(":", 1)[1] if unlinked else "onbekend")
        title = _display_name(entry, domain.replace("_", " ").title())
        bundles.append(
            RegistryBundle(
                id=entry_id,
                title=title,
                domain=domain,
                config_entry_id="" if unlinked else entry_id,
                state=_identifier(entry, "state") or ("niet gekoppeld" if unlinked else "onbekend"),
                devices=sorted(device_summaries, key=lambda item: (str(item["name"]).lower(), item["device_id"])),
                entities=sorted(entity_summaries, key=lambda item: item["entity_id"]),
                review_count=sum(1 for item in bundle_findings if item.severity == "review"),
                informational_count=sum(1 for item in bundle_findings if item.severity == "info"),
                advice=analyze_bundle(
                    devices=device_summaries,
                    entities=entity_summaries,
                    review_count=sum(1 for item in bundle_findings if item.severity == "review"),
                ),
            )
        )
    return sorted(bundles, key=lambda item: (item.review_count == 0, item.domain.lower(), item.title.lower()))


def _receive_json(connection: Any) -> dict[str, Any]:
    try:
        payload = json.loads(connection.recv())
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HomeAssistantApiError("Ongeldig WebSocket-antwoord") from exc
    if not isinstance(payload, dict):
        raise HomeAssistantApiError("Onverwacht WebSocket-antwoord")
    return payload


def _receive_result(connection: Any, command_id: int) -> dict[str, Any]:
    while True:
        response = _receive_json(connection)
        if response.get("type") == "ping":
            connection.send(json.dumps({"id": response.get("id"), "type": "pong"}))
            continue
        if response.get("id") != command_id:
            continue
        if response.get("type") != "result" or not response.get("success"):
            error = response.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            raise HomeAssistantApiError(message or f"WebSocket-commando {command_id} mislukte")
        return response


def _identifier(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _display_name(item: dict[str, Any], fallback: str) -> str:
    return _identifier(item, "name_by_user", "name", "original_name", "title") or fallback


def _device_config_entry_ids(device: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    values = device.get("config_entries")
    if isinstance(values, list):
        result.update(value for value in values if isinstance(value, str) and value)
    primary = _identifier(device, "primary_config_entry", "config_entry_id")
    if primary:
        result.add(primary)
    return result


def _finding(subject_type: str, subject_id: str, name: str, category: str, severity: str, reason: str, related_id: str = "") -> RegistryFinding:
    return RegistryFinding(
        id=uuid.uuid4().hex,
        subject_type=subject_type,
        subject_id=subject_id,
        name=name,
        category=category,
        severity=severity,
        reason=reason,
        related_id=related_id,
        recommended_action="manual_review" if severity == "review" else "none",
    )


def _count(findings: list[RegistryFinding], category: str) -> int:
    return sum(1 for item in findings if item.category == category)
