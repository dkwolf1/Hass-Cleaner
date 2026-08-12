from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scanner import ScanResult
from .settings import Settings


class PlanError(ValueError):
    pass


class PlanManager:
    def __init__(self, data_root: Path):
        self.root = data_root / "plans"

    def create(
        self,
        scan: ScanResult | None,
        settings: Settings,
        *,
        selected_ids: list[str],
        selected_bundle_ids: list[str],
        selected_entity_ids: list[str],
        backup_choice: str,
    ) -> dict[str, Any]:
        if scan is None or scan.status != "completed":
            raise PlanError("Voer eerst een volledige scan uit")
        selected_ids = list(dict.fromkeys(selected_ids))
        selected_bundle_ids = list(dict.fromkeys(selected_bundle_ids))
        selected_entity_ids = list(dict.fromkeys(selected_entity_ids))
        file_map = {item.id: item for item in scan.items}
        bundle_map = {item.id: item for item in scan.registry_audit.bundles}
        entity_map = {
            str(item.get("entity_id")): item
            for item in scan.registry_audit.entity_workspace.get("items", [])
        }
        unknown_files = [item_id for item_id in selected_ids if item_id not in file_map]
        unknown_bundles = [item_id for item_id in selected_bundle_ids if item_id not in bundle_map]
        unknown_entities = [item_id for item_id in selected_entity_ids if item_id not in entity_map]
        if unknown_files or unknown_bundles or unknown_entities:
            raise PlanError("De selectie hoort niet meer bij de laatste scan; scan opnieuw")
        if any(file_map[item_id].risk == "protected" for item_id in selected_ids):
            raise PlanError("Beschermde Home Assistant-bestanden kunnen niet aan de opschoning worden toegevoegd")
        if any(not entity_map[item_id].get("selectable_for_plan") for item_id in selected_entity_ids):
            raise PlanError("Alleen geregistreerde entities kunnen aan de opschoning worden toegevoegd")
        if not selected_ids and not selected_bundle_ids and not selected_entity_ids:
            raise PlanError("Selecteer minimaal één bestand, bundel of entity")

        files = []
        for item_id in selected_ids:
            item = file_map[item_id]
            requested_action = settings.deletion_mode
            files.append(
                {
                    "id": item.id,
                    "path": item.path,
                    "before": {"exists": True, "size_bytes": item.size_bytes, "category": item.category, "sha256": item.sha256},
                    "proposed_action": requested_action,
                    "after": {
                        "source_exists": False,
                        "quarantine_copy": settings.deletion_mode == "quarantine",
                        "retention_days": settings.retention_days if settings.deletion_mode == "quarantine" else 0,
                    },
                    "advice": item.advice,
                    "risk": item.risk,
                    "execution_allowed": settings.deletion_mode == "quarantine",
                }
            )
        bundles = []
        devices: list[dict[str, Any]] = []
        planned_entity_ids = set(selected_entity_ids)
        for bundle_id in selected_bundle_ids:
            bundle = bundle_map[bundle_id]
            planned_entity_ids.update(str(item.get("entity_id", "")) for item in bundle.entities if item.get("entity_id"))
            if bundle.config_entry_id:
                devices.extend({
                    "device_id": str(item.get("device_id", "")),
                    "name": str(item.get("name", "")),
                    "config_entry_id": bundle.config_entry_id,
                    "bundle_id": bundle.id,
                    "proposed_action": "remove_config_entry_from_device",
                    "execution_allowed": bool(item.get("device_id")),
                } for item in bundle.devices)
            bundles.append(
                {
                    "id": bundle.id,
                    "title": bundle.title,
                    "domain": bundle.domain,
                    "before": {"device_count": len(bundle.devices), "entity_count": len(bundle.entities), "review_count": bundle.review_count},
                    "proposed_action": "user_directed_registry_cleanup",
                    "after": {"device_count": 0, "entity_count": 0, "changed": True},
                    "advice": bundle.advice,
                    "execution_allowed": bool(bundle.entities or (bundle.devices and bundle.config_entry_id)),
                }
            )
        devices = list({(item["device_id"], item["config_entry_id"]): item for item in devices}.values())

        entities = []
        bundle_entity_map = {str(item.get("entity_id", "")): item for bundle in bundle_map.values() for item in bundle.entities}
        for entity_id in sorted(planned_entity_ids):
            entity = entity_map.get(entity_id) or bundle_entity_map.get(entity_id)
            if not entity:
                continue
            entities.append({
                "entity_id": entity_id,
                "name": entity.get("name", entity_id),
                "integration": entity.get("integration", ""),
                "device_id": entity.get("device_id", ""),
                "device_name": entity.get("device_name", ""),
                "area_name": entity.get("area_name", ""),
                "status": entity.get("status", ""),
                "raw_state": entity.get("raw_state"),
                "duration_days": entity.get("duration_days", 0),
                "reason": entity.get("reason", ""),
                "proposed_action": "remove_from_entity_registry",
                "required_checks": [
                    "Controleer Home Assistant-relaties en gebruik in automatiseringen, scripts en dashboards.",
                    "Controleer apparaat, integratie en configuratie-entry; Hass-Cleaner kan gevolgen niet volledig voorspellen.",
                    "Maak bij voorkeur een volledige Home Assistant-back-up voordat je het register wijzigt.",
                ],
                "execution_allowed": True,
            })

        plan_id = uuid.uuid4().hex
        plan: dict[str, Any] = {
            "schema_version": 3,
            "id": plan_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scan_id": scan.id,
            "status": "awaiting_execution_choice",
            "execution_locked": False,
            "backup_choice": backup_choice,
            "settings": settings.public_dict(),
            "files": files,
            "bundles": bundles,
            "devices": devices,
            "entities": entities,
            "summary": {
                "file_count": len(files),
                "bundle_count": len(bundles),
                "entity_count": len(entities),
                "device_count": len(devices),
                "planned_bytes": sum(item["before"]["size_bytes"] for item in files),
                "executable_actions": (len(files) if settings.deletion_mode == "quarantine" else 0) + len(entities) + len(devices),
            },
            "global_recovery": [
                "Annuleer bij twijfel; dit plan voert zelf niets uit.",
                "Herstel bestanden vanuit quarantaine zolang de bewaartermijn loopt.",
                "Gebruik een volledige Home Assistant-back-up voor register- of configuratieherstel.",
            ],
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(plan_id, "json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        self._path(plan_id, "md").write_text(_markdown(plan), encoding="utf-8")
        return plan

    def path(self, plan_id: str, extension: str) -> Path | None:
        if not plan_id.isalnum() or extension not in {"json", "md"}:
            return None
        path = self._path(plan_id, extension)
        return path if path.is_file() else None

    def get(self, plan_id: str) -> dict[str, Any]:
        path = self.path(plan_id, "json")
        if path is None:
            raise PlanError("Plan niet gevonden")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PlanError("Plan kan niet veilig worden gelezen") from exc
        if not isinstance(value, dict):
            raise PlanError("Plan heeft een ongeldig formaat")
        return value

    def _path(self, plan_id: str, extension: str) -> Path:
        return self.root / f"hass-cleaner-plan-{plan_id}.{extension}"


def _markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# Hass-Cleaner - impact- en herstelplan",
        "",
        "> VOORBEREIDE OPSCHONING: dit overzicht heeft niets gewijzigd. Hass-Cleaner toont advies en risico; de gebruiker beslist. Beschermde kernbestanden blijven uitgesloten.",
        "",
        f"- Plan-ID: `{plan['id']}`",
        f"- Scan-ID: `{plan['scan_id']}`",
        f"- Bestanden: {summary['file_count']}",
        f"- Bundels: {summary['bundle_count']}",
        f"- Entities: {summary['entity_count']}",
        f"- Uitvoerbare acties: {summary['executable_actions']}",
        "",
        "## Bestanden",
        "",
        "| Pad | Bewijs | Voorgestelde actie | Mogelijk gevolg | Herstel |",
        "|---|---|---|---|---|",
    ]
    for item in plan["files"]:
        advice = item["advice"]
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                _escape(item["path"]),
                _escape(advice.get("evidence_label", "")),
                _escape(item["proposed_action"]),
                _escape("; ".join(advice.get("possible_consequences", []))),
                _escape("; ".join(advice.get("recovery_steps", []))),
            )
        )
    lines.extend(["", "## Bundels", "", "| Bundel | Domein | Apparaten | Entities | Bewijs | Advies |", "|---|---|---:|---:|---|---|"])
    for item in plan["bundles"]:
        advice = item["advice"]
        lines.append(
            "| {} | `{}` | {} | {} | {} | {} |".format(
                _escape(item["title"]),
                _escape(item["domain"]),
                item["before"]["device_count"],
                item["before"]["entity_count"],
                _escape(advice.get("evidence_label", "")),
                _escape(advice.get("recommended_first_step", "")),
            )
        )
    lines.extend(["", "## Geselecteerde entities", "", "| Entity | Status | Duur | Integratie/apparaat | Reden |", "|---|---|---:|---|---|"])
    for item in plan["entities"]:
        owner = " / ".join(value for value in (item["integration"], item["device_name"]) if value)
        lines.append(
            "| `{}` | {} | {} dagen | {} | {} |".format(
                _escape(item["entity_id"]),
                _escape(item["status"]),
                item["duration_days"],
                _escape(owner),
                _escape(item["reason"]),
            )
        )
    lines.extend(["", "## Algemeen herstel", ""])
    lines.extend(f"- {step}" for step in plan["global_recovery"])
    lines.append("")
    return "\n".join(lines)


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
