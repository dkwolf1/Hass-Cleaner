from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry_audit import RegistryAudit


LONG_UNAVAILABLE_DAYS = 30
REPEATED_OBSERVATION_DAYS = 7
REQUIRED_OBSERVATIONS = 3
DECISION_ACTIONS = {"follow", "expected", "snooze_7", "snooze_30", "snooze_90", "clear"}


def apply_availability_history(audit: RegistryAudit, path: Path, *, now: datetime | None = None) -> None:
    """Classify entity health conservatively and persist only non-sensitive counters."""
    if audit.status != "completed":
        return
    current = now or datetime.now(timezone.utc)
    previous = _load(path)
    snapshot_path = path.with_name("entity-snapshot.json")
    decisions_path = path.with_name("entity-decisions.json")
    previous_snapshot = _load(snapshot_path)
    decisions = _load(decisions_path)
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
    _apply_decisions(audit.entity_workspace, decisions, current)
    _apply_scan_diff(audit.entity_workspace, previous_snapshot)
    _save(snapshot_path, _workspace_snapshot(audit.entity_workspace))


def _annotate_entity(
    entity: dict[str, Any], previous: dict[str, dict[str, Any]], current: datetime
) -> dict[str, Any] | None:
    entity_id = str(entity.get("entity_id", ""))
    disabled_by = entity.get("disabled_by")
    entity["ha_last_changed"] = entity.get("last_changed", "")
    if disabled_by is not None:
        entity["availability_status"] = f"disabled_by_{disabled_by}"
        entity["health_duration_days"] = 0
        entity["cleanup_candidate"] = False
        entity["health_observations"] = 0
        return None
    if not entity.get("loaded"):
        entity["availability_status"] = "not_loaded"
        raw_state = "not_loaded"
    else:
        raw_state = str(entity.get("state", ""))
        if raw_state not in {"unavailable", "unknown", "problem"}:
            entity["availability_status"] = "available"
            entity["health_duration_days"] = 0
            entity["health_duration_seconds"] = 0
            entity["health_observations"] = 0
            entity["cleanup_candidate"] = False
            return None

    prior = previous.get(entity_id, {})
    if prior.get("kind") != raw_state:
        prior = {}
    ha_last_changed = _parse(str(entity.get("last_changed", "")))
    first_seen = _parse(str(prior.get("first_seen", ""))) or current
    duration_anchor = ha_last_changed or first_seen
    scans = int(prior.get("observations", 0)) + 1
    duration_seconds = max(0, int((current - duration_anchor).total_seconds()))
    duration_days = duration_seconds // 86400
    persistent = duration_days >= LONG_UNAVAILABLE_DAYS or (
        scans >= REQUIRED_OBSERVATIONS and duration_days >= REPEATED_OBSERVATION_DAYS
    )
    if raw_state == "not_loaded":
        entity["availability_status"] = "not_loaded"
    else:
        entity["availability_status"] = f"long_{raw_state}" if persistent else f"temporarily_{raw_state}"
    entity["health_duration_days"] = duration_days
    entity["health_duration_seconds"] = duration_seconds
    entity["health_observations"] = scans
    entity["health_first_seen"] = first_seen.isoformat()
    entity["health_last_seen"] = current.isoformat()
    entity["health_duration_source"] = "home_assistant" if ha_last_changed else "hass_cleaner"
    entity["persistent_issue"] = persistent
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
                "evidence_level": "insufficient",
                "evidence_summary": "De status en meetduur zijn aangetoond; gebruik door dashboards, automatiseringen en integraties is nog niet uitgesloten.",
                "risk_summary": "Verwijderen kan apparaten, dashboards, automatiseringen of integratielogica breken.",
                "possible_consequences": [
                    "De entiteiten kunnen na herstel van het apparaat of de integratie weer nodig zijn.",
                    "Dashboardkaarten en automatiseringen kunnen ontbrekende verwijzingen krijgen.",
                ],
                "recovery_steps": [
                    "Herstel eerst de integratie of het apparaat en voer een nieuwe scan uit.",
                    "Gebruik bij registerwijzigingen een volledige Home Assistant-back-up om terug te keren.",
                ],
                "recommended_first_step": "Open de bundel, controleer de officiële relaties en bepaal waarom de entiteiten langdurig onbeschikbaar zijn.",
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
            watch = status.startswith("temporarily_") or (status == "not_loaded" and not entity.get("persistent_issue"))
            attention = status in {"long_unavailable", "long_unknown", "long_problem", "broken_reference"} or (
                status == "not_loaded" and bool(entity.get("persistent_issue"))
            )
            # Temporary registered entities may be selected for a read-only
            # research plan. Selection is not deletion permission.
            selectable_for_plan = True
            observations = int(entity.get("health_observations", 0) or 0)
            duration_seconds = int(entity.get("health_duration_seconds", 0) or 0)
            remaining_days = max(0, LONG_UNAVAILABLE_DAYS - duration_seconds // 86400)
            remaining_observations = max(0, REQUIRED_OBSERVATIONS - observations)
            evidence_needed = (
                "Actiecriterium bereikt; controleer officiële relaties en actief gebruik."
                if attention else
                f"Nog {remaining_days} dag(en) tot {LONG_UNAVAILABLE_DAYS} dagen, of nog {remaining_observations} meting(en) "
                f"met minimaal {REPEATED_OBSERVATION_DAYS} dagen tussen eerste en laatste meting."
            )
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
                "duration_seconds": entity.get("health_duration_seconds", 0),
                "observations": entity.get("health_observations", 0),
                "first_observed": entity.get("health_first_seen", ""),
                "last_observed": entity.get("health_last_seen", ""),
                "duration_source": entity.get("health_duration_source", ""),
                "last_changed": entity.get("last_changed", ""),
                "disabled_by": entity.get("disabled_by"),
                "loaded": bool(entity.get("loaded")),
                "connectivity_signals": signal,
                "integration_signal_problem": signal_problem,
                "registry_entry": True,
                "attention": attention,
                "watch": watch,
                "informational": not attention and not watch,
                "selectable_for_plan": selectable_for_plan,
                "execution_allowed": False,
                "evidence_needed": evidence_needed,
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
        watch = status.startswith("temporarily_") or status == "not_loaded"
        attention = False
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
            "duration_seconds": entity.get("health_duration_seconds", 0),
            "observations": entity.get("health_observations", 0),
            "first_observed": entity.get("health_first_seen", ""),
            "last_observed": entity.get("health_last_seen", ""),
            "duration_source": entity.get("health_duration_source", ""),
            "last_changed": entity.get("last_changed", ""),
            "disabled_by": None,
            "loaded": True,
            "connectivity_signals": signal,
            "integration_signal_problem": signal_problem,
            "registry_entry": False,
            "attention": attention,
            "watch": watch,
            "informational": not watch,
            "selectable_for_plan": False,
            "execution_allowed": False,
            "reason": reason,
        })
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    sorted_items = sorted(
        items,
        key=lambda item: (not item["attention"], -int(item["duration_days"]), item["entity_id"]),
    )
    return {
        "items": sorted_items,
        "signal_groups": _build_signal_groups(sorted_items),
        "summary": {
            "total": len(items),
            "registered_total": sum(1 for item in items if item["registry_entry"]),
            "state_only_total": sum(1 for item in items if not item["registry_entry"]),
            "attention": sum(1 for item in items if item["attention"]),
            "temporary_signals": sum(1 for item in items if item["watch"]),
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


def _build_signal_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize health signals per integration and device for a compact UI/export."""
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        if not item.get("attention") and not item.get("watch"):
            continue
        integration = str(item.get("integration") or "Geen integratie")
        group = groups.setdefault(
            integration,
            {
                "integration": integration,
                "total": 0,
                "attention": 0,
                "watch": 0,
                "registered": 0,
                "runtime_only": 0,
                "status_counts": {},
                "max_duration_seconds": 0,
                "max_observations": 0,
                "sample_entity_ids": [],
                "devices": {},
            },
        )
        status = str(item.get("status", "unknown"))
        group["total"] += 1
        group["attention"] += int(bool(item.get("attention")))
        group["watch"] += int(bool(item.get("watch")))
        group["registered"] += int(item.get("registry_entry") is not False)
        group["runtime_only"] += int(item.get("registry_entry") is False)
        group["status_counts"][status] = group["status_counts"].get(status, 0) + 1
        group["max_duration_seconds"] = max(
            int(group["max_duration_seconds"]), int(item.get("duration_seconds", 0) or 0)
        )
        group["max_observations"] = max(
            int(group["max_observations"]), int(item.get("observations", 0) or 0)
        )
        if len(group["sample_entity_ids"]) < 10:
            group["sample_entity_ids"].append(str(item.get("entity_id", "")))

        device_id = str(item.get("device_id") or "")
        device_name = str(item.get("device_name") or "Zonder apparaat")
        device_key = device_id or f"none:{device_name}"
        device = group["devices"].setdefault(
            device_key,
            {
                "device_id": device_id,
                "device_name": device_name,
                "area_name": str(item.get("area_name") or ""),
                "total": 0,
                "attention": 0,
                "watch": 0,
                "status_counts": {},
            },
        )
        device["total"] += 1
        device["attention"] += int(bool(item.get("attention")))
        device["watch"] += int(bool(item.get("watch")))
        device["status_counts"][status] = device["status_counts"].get(status, 0) + 1

    result: list[dict[str, Any]] = []
    for group in groups.values():
        devices = sorted(
            group.pop("devices").values(),
            key=lambda value: (-int(value["attention"]), -int(value["total"]), value["device_name"]),
        )
        group["device_groups"] = devices[:100]
        group["omitted_device_groups"] = max(0, len(devices) - len(group["device_groups"]))
        result.append(group)
    return sorted(
        result,
        key=lambda value: (-int(value["attention"]), -int(value["total"]), value["integration"]),
    )


def update_entity_decision(
    path: Path, entity_id: str, action: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Store a local triage choice; this never writes to Home Assistant."""
    if action not in DECISION_ACTIONS:
        raise ValueError("Ongeldige entitykeuze")
    if not entity_id or len(entity_id) > 255:
        raise ValueError("Ongeldige entity-id")
    decisions = _load(path)
    if action == "clear":
        decisions.pop(entity_id, None)
        _save(path, decisions)
        return {"entity_id": entity_id, "action": "clear"}
    current = now or datetime.now(timezone.utc)
    days = {"snooze_7": 7, "snooze_30": 30, "snooze_90": 90}.get(action)
    until = ""
    if days:
        from datetime import timedelta

        until = (current + timedelta(days=days)).isoformat()
    record = {"action": action, "set_at": current.isoformat(), "until": until}
    decisions[entity_id] = record
    _save(path, decisions)
    return {"entity_id": entity_id, **record}


def apply_saved_decisions(workspace: dict[str, Any], path: Path, *, now: datetime | None = None) -> None:
    _apply_decisions(workspace, _load(path), now or datetime.now(timezone.utc))


def _apply_decisions(workspace: dict[str, Any], decisions: dict[str, Any], current: datetime) -> None:
    for item in workspace.get("items", []):
        record = decisions.get(str(item.get("entity_id", "")), {})
        if not isinstance(record, dict):
            record = {}
        action = str(record.get("action", "follow"))
        until = _parse(str(record.get("until", "")))
        if action.startswith("snooze_") and (until is None or until <= current):
            action = "follow"
        item["decision"] = action
        item["decision_until"] = until.isoformat() if until else ""
        item["muted_by_decision"] = action == "expected" or action.startswith("snooze_")
    _refresh_workspace_summary(workspace)


def _apply_scan_diff(workspace: dict[str, Any], previous: dict[str, Any]) -> None:
    items = workspace.get("items", [])
    baseline = not bool(previous)
    counts = {"new": 0, "changed": 0, "recovered": 0, "unchanged": 0, "removed": 0}
    current_ids: set[str] = set()
    for item in items:
        entity_id = str(item.get("entity_id", ""))
        current_ids.add(entity_id)
        old = previous.get(entity_id)
        if baseline or not isinstance(old, dict):
            diff = "baseline" if baseline else "new"
        elif _is_problem_status(str(old.get("status", ""))) and not _is_problem_status(str(item.get("status", ""))):
            diff = "recovered"
        elif old.get("status") != item.get("status") or old.get("raw_state") != item.get("raw_state"):
            diff = "changed"
        else:
            diff = "unchanged"
        item["diff_status"] = diff
        if diff in counts:
            counts[diff] += 1
    removed = sorted(entity_id for entity_id in previous if entity_id not in current_ids)
    counts["removed"] = len(removed)
    workspace["changes"] = {"baseline": baseline, "counts": counts, "removed_entity_ids": removed[:100]}


def _workspace_snapshot(workspace: dict[str, Any]) -> dict[str, Any]:
    return {
        str(item.get("entity_id", "")): {
            "status": item.get("status", ""),
            "raw_state": item.get("raw_state"),
            "registry_entry": item.get("registry_entry", True),
        }
        for item in workspace.get("items", [])
        if item.get("entity_id")
    }


def _refresh_workspace_summary(workspace: dict[str, Any]) -> None:
    items = workspace.get("items", [])
    summary = workspace.setdefault("summary", {})
    summary["muted"] = sum(1 for item in items if item.get("muted_by_decision"))
    summary["attention_visible"] = sum(
        1 for item in items if item.get("attention") and not item.get("muted_by_decision")
    )
    summary["temporary_visible"] = sum(
        1 for item in items if item.get("watch") and not item.get("muted_by_decision")
    )


def _is_problem_status(status: str) -> bool:
    return status.startswith(("temporarily_", "long_")) or status in {"not_loaded", "broken_reference"}


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
