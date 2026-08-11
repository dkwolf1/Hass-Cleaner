from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry_audit import RegistryAudit


LONG_UNAVAILABLE_DAYS = 30
REPEATED_OBSERVATION_DAYS = 7
REQUIRED_OBSERVATIONS = 3


def apply_availability_history(audit: RegistryAudit, path: Path, *, now: datetime | None = None) -> None:
    """Classify entity health conservatively and persist only non-sensitive counters."""
    if audit.status != "completed":
        return
    current = now or datetime.now(timezone.utc)
    previous = _load(path)
    observations: dict[str, dict[str, Any]] = {}

    entities = [entity for bundle in audit.bundles for entity in bundle.entities]
    entities.extend(audit.state_only_entities)
    for entity in entities:
        observation = _annotate_entity(entity, previous, current)
        if observation is not None:
            observations[str(entity.get("entity_id", ""))] = observation

    _save(path, observations)
    _append_bundle_anomalies(audit)
    audit.entity_workspace = _build_entity_workspace(audit)


def _annotate_entity(
    entity: dict[str, Any], previous: dict[str, dict[str, Any]], current: datetime
) -> dict[str, Any] | None:
    entity_id = str(entity.get("entity_id", ""))
    disabled_by = entity.get("disabled_by")
    if disabled_by is not None:
        entity["availability_status"] = f"disabled_by_{disabled_by}"
        entity["health_duration_days"] = 0
        entity["cleanup_candidate"] = False
        return None
    if not entity.get("loaded"):
        entity["availability_status"] = "not_loaded"
        entity["health_duration_days"] = 0
        entity["cleanup_candidate"] = False
        return None
    raw_state = str(entity.get("state", ""))
    if raw_state not in {"unavailable", "unknown", "problem"}:
        entity["availability_status"] = "available"
        entity["health_duration_days"] = 0
        entity["cleanup_candidate"] = False
        return None

    prior = previous.get(entity_id, {})
    if prior.get("kind") != raw_state:
        prior = {}
    first_seen = _parse(str(prior.get("first_seen", ""))) or _parse(str(entity.get("last_changed", ""))) or current
    scans = int(prior.get("observations", 0)) + 1
    duration_days = max(0, int((current - first_seen).total_seconds() // 86400))
    persistent = duration_days >= LONG_UNAVAILABLE_DAYS or (
        scans >= REQUIRED_OBSERVATIONS and duration_days >= REPEATED_OBSERVATION_DAYS
    )
    entity["availability_status"] = f"long_{raw_state}" if persistent else f"temporarily_{raw_state}"
    entity["health_duration_days"] = duration_days
    entity["health_observations"] = scans
    entity["cleanup_candidate"] = False
    return {
        "kind": raw_state,
        "first_seen": first_seen.isoformat(),
        "last_seen": current.isoformat(),
        "observations": scans,
    }


def _append_bundle_anomalies(audit: RegistryAudit) -> None:
    long_total = 0
    temporary_total = 0
    long_unknown_total = 0
    temporary_unknown_total = 0
    problem_total = 0
    for bundle in audit.bundles:
        enabled = [item for item in bundle.entities if item.get("disabled_by") is None]
        long_items = [item for item in enabled if item.get("availability_status") == "long_unavailable"]
        temporary_total += sum(1 for item in enabled if item.get("availability_status") == "temporarily_unavailable")
        long_unknown_total += sum(1 for item in enabled if item.get("availability_status") == "long_unknown")
        temporary_unknown_total += sum(1 for item in enabled if item.get("availability_status") == "temporarily_unknown")
        problem_total += sum(1 for item in enabled if str(item.get("availability_status", "")).endswith("_problem"))
        long_total += len(long_items)
        ratio = len(long_items) / len(enabled) if enabled else 0
        if len(long_items) >= 3 or (len(long_items) >= 2 and ratio >= 0.5):
            audit.anomalies.append({
                "id": f"long-unavailable:{bundle.id}",
                "category": "long_unavailable_entity_group",
                "severity": "review",
                "bundle_id": bundle.id,
                "domain": bundle.domain,
                "title": "Groep langdurig onbeschikbare entiteiten",
                "summary": f"{len(long_items)} van {len(enabled)} ingeschakelde entiteiten zijn langdurig onbeschikbaar.",
                "counts": {"enabled_entities": len(enabled), "long_unavailable": len(long_items)},
                "sample_entity_ids": [str(item.get("entity_id", "")) for item in long_items[:10]],
                "execution_allowed": False,
            })
    audit.anomalies.sort(key=lambda item: -sum(value for value in item.get("counts", {}).values() if isinstance(value, int)))
    audit.summary["long_unavailable_entities"] = long_total
    audit.summary["temporarily_unavailable_entities"] = temporary_total
    audit.summary["long_unknown_entities"] = long_unknown_total
    audit.summary["temporarily_unknown_entities"] = temporary_unknown_total
    audit.summary["problem_entities"] = problem_total
    audit.summary["anomalies_total"] = len(audit.anomalies)


def _build_entity_workspace(audit: RegistryAudit) -> dict[str, Any]:
    """Build a UI-safe entity index without treating state names as deletion proof."""
    broken_by_entity = {
        finding.subject_id: finding.category
        for finding in audit.findings
        if finding.subject_type == "entity" and finding.severity == "review"
    }
    items: list[dict[str, Any]] = []
    for bundle in audit.bundles:
        for entity in bundle.entities:
            entity_id = str(entity.get("entity_id", ""))
            status = str(entity.get("availability_status", "available"))
            broken_category = broken_by_entity.get(entity_id, "")
            if broken_category.startswith("missing_"):
                status = "broken_reference"
            signal = dict(entity.get("connectivity_signals", {}))
            signal_problem = any(value is False or str(value).lower() in {"false", "offline", "disconnected", "unreachable"} for value in signal.values())
            attention = status in {
                "temporarily_unavailable", "long_unavailable", "temporarily_unknown",
                "long_unknown", "temporarily_problem", "long_problem", "not_loaded",
                "broken_reference",
            }
            selectable_for_plan = status in {"long_unavailable", "long_unknown", "long_problem", "not_loaded", "broken_reference"}
            items.append({
                "entity_id": entity_id,
                "name": entity.get("name", entity_id),
                "domain": entity_id.partition(".")[0],
                "integration": bundle.domain,
                "bundle_id": bundle.id,
                "bundle_title": bundle.title,
                "config_entry_id": bundle.config_entry_id,
                "device_id": entity.get("device_id", ""),
                "device_name": entity.get("device_name", ""),
                "area_id": entity.get("area_id", ""),
                "area_name": entity.get("area_name", ""),
                "platform": entity.get("platform", ""),
                "status": status,
                "raw_state": entity.get("state"),
                "duration_days": entity.get("health_duration_days", 0),
                "observations": entity.get("health_observations", 0),
                "last_changed": entity.get("last_changed", ""),
                "disabled_by": entity.get("disabled_by"),
                "loaded": bool(entity.get("loaded")),
                "connectivity_signals": signal,
                "integration_signal_problem": signal_problem,
                "registry_entry": True,
                "attention": attention,
                "informational": not attention and (status.startswith("disabled_by_") or signal_problem),
                "selectable_for_plan": selectable_for_plan,
                "execution_allowed": False,
                "reason": _entity_reason(status, signal_problem),
            })
    for entity in audit.state_only_entities:
        entity_id = str(entity.get("entity_id", ""))
        status = str(entity.get("availability_status", "available"))
        signal = dict(entity.get("connectivity_signals", {}))
        signal_problem = any(
            value is False or str(value).lower() in {"false", "offline", "disconnected", "unreachable"}
            for value in signal.values()
        )
        attention = status != "available"
        reason = _entity_reason(status, signal_problem)
        if status == "available":
            reason = "Actieve runtime-state zonder entity-registry-item; dit kan normaal zijn voor entities zonder unique_id."
        else:
            reason += " Deze runtime-state heeft geen entity-registry-item en kan daarom niet als registeritem worden verwijderd."
        items.append({
            "entity_id": entity_id,
            "name": entity.get("name", entity_id),
            "domain": entity_id.partition(".")[0],
            "integration": entity.get("platform", entity_id.partition(".")[0]),
            "bundle_id": "",
            "bundle_title": "Runtime-state zonder registeritem",
            "config_entry_id": "",
            "device_id": "",
            "device_name": "",
            "area_id": "",
            "area_name": "",
            "platform": entity.get("platform", ""),
            "status": status,
            "raw_state": entity.get("state"),
            "duration_days": entity.get("health_duration_days", 0),
            "observations": entity.get("health_observations", 0),
            "last_changed": entity.get("last_changed", ""),
            "disabled_by": None,
            "loaded": True,
            "connectivity_signals": signal,
            "integration_signal_problem": signal_problem,
            "registry_entry": False,
            "attention": attention,
            "informational": not attention,
            "selectable_for_plan": False,
            "execution_allowed": False,
            "reason": reason,
        })
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "items": sorted(items, key=lambda item: (not item["attention"], -int(item["duration_days"]), item["entity_id"])),
        "summary": {
            "total": len(items),
            "registered_total": sum(1 for item in items if item["registry_entry"]),
            "state_only_total": sum(1 for item in items if not item["registry_entry"]),
            "attention": sum(1 for item in items if item["attention"]),
            "informational": sum(1 for item in items if item["informational"]),
            "disabled": sum(1 for item in items if str(item["status"]).startswith("disabled_by_")),
            "selectable_for_plan": sum(1 for item in items if item["selectable_for_plan"]),
            "by_status": counts,
        },
        "universal_problem_states": ["unavailable", "unknown", "problem"],
        "persistence_thresholds": {
            "long_days": LONG_UNAVAILABLE_DAYS,
            "repeated_observations": REQUIRED_OBSERVATIONS,
            "repeated_days": REPEATED_OBSERVATION_DAYS,
        },
        "integration_signals_are_informational": True,
        "execution_locked": True,
    }


def _entity_reason(status: str, signal_problem: bool) -> str:
    reasons = {
        "temporarily_unavailable": "Home Assistant meldt unavailable; nog niet lang genoeg waargenomen.",
        "long_unavailable": "Home Assistant meldt langdurig unavailable; controleer eerst apparaat, integratie en afhankelijkheden.",
        "temporarily_unknown": "Home Assistant heeft momenteel geen bruikbare waarde; dit is nog geen verwijderbewijs.",
        "long_unknown": "Home Assistant heeft langdurig geen bruikbare waarde; oorzaak en gebruik moeten worden onderzocht.",
        "temporarily_problem": "Home Assistant meldt problem; controleer eerst of dit voor dit entiteitstype een normale domeinstatus is.",
        "long_problem": "Home Assistant meldt langdurig problem; onderzoek oorzaak, gebruik en herstel voordat verwijdering wordt overwogen.",
        "not_loaded": "De ingeschakelde registerentity heeft momenteel geen state.",
        "broken_reference": "De entity bevat een ontbrekende registerverwijzing.",
        "disabled_by_user": "De entity is bewust door een gebruiker uitgeschakeld.",
        "disabled_by_integration": "De integratie levert deze entity standaard uitgeschakeld; dit is normaal gedrag.",
        "disabled_by_config_entry": "Nieuwe entities zijn via de configuratie-entry uitgeschakeld.",
    }
    if status == "available" and signal_problem:
        return "Een integratiespecifiek connectiviteitssignaal is negatief; dit is alleen een aanwijzing."
    return reasons.get(status, "Geen algemeen Home Assistant-statusprobleem vastgesteld.")


def _load(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(path: Path, observations: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
