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
    """Annotate availability conservatively and persist only non-sensitive counters."""
    if audit.status != "completed":
        return
    current = now or datetime.now(timezone.utc)
    previous = _load(path)
    observations: dict[str, dict[str, Any]] = {}

    for bundle in audit.bundles:
        for entity in bundle.entities:
            entity_id = str(entity.get("entity_id", ""))
            disabled_by = entity.get("disabled_by")
            if disabled_by is not None:
                entity["availability_status"] = f"disabled_by_{disabled_by}"
                entity["cleanup_candidate"] = False
                continue
            if not entity.get("loaded"):
                entity["availability_status"] = "not_loaded"
                entity["cleanup_candidate"] = False
                continue
            if entity.get("state") != "unavailable":
                entity["availability_status"] = "available"
                entity["cleanup_candidate"] = False
                continue

            prior = previous.get(entity_id, {})
            first_seen = _parse(str(prior.get("first_seen", ""))) or _parse(str(entity.get("last_changed", ""))) or current
            scans = int(prior.get("observations", 0)) + 1
            unavailable_days = max(0, int((current - first_seen).total_seconds() // 86400))
            persistent = unavailable_days >= LONG_UNAVAILABLE_DAYS or (scans >= REQUIRED_OBSERVATIONS and unavailable_days >= REPEATED_OBSERVATION_DAYS)
            entity["availability_status"] = "long_unavailable" if persistent else "temporarily_unavailable"
            entity["unavailable_days"] = unavailable_days
            entity["unavailable_observations"] = scans
            entity["cleanup_candidate"] = False
            observations[entity_id] = {
                "first_seen": first_seen.isoformat(),
                "last_seen": current.isoformat(),
                "observations": scans,
            }

    _save(path, observations)
    _append_bundle_anomalies(audit)


def _append_bundle_anomalies(audit: RegistryAudit) -> None:
    long_total = 0
    temporary_total = 0
    for bundle in audit.bundles:
        enabled = [item for item in bundle.entities if item.get("disabled_by") is None]
        long_items = [item for item in enabled if item.get("availability_status") == "long_unavailable"]
        temporary_total += sum(1 for item in enabled if item.get("availability_status") == "temporarily_unavailable")
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
    audit.summary["anomalies_total"] = len(audit.anomalies)


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
