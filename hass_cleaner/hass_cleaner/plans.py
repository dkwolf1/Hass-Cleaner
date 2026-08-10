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
        backup_choice: str,
    ) -> dict[str, Any]:
        if scan is None or scan.status != "completed":
            raise PlanError("Voer eerst een volledige scan uit")
        file_map = {item.id: item for item in scan.items}
        bundle_map = {item.id: item for item in scan.registry_audit.bundles}
        unknown_files = [item_id for item_id in selected_ids if item_id not in file_map]
        unknown_bundles = [item_id for item_id in selected_bundle_ids if item_id not in bundle_map]
        if unknown_files or unknown_bundles:
            raise PlanError("De selectie hoort niet meer bij de laatste scan; scan opnieuw")
        if not selected_ids and not selected_bundle_ids:
            raise PlanError("Selecteer minimaal één bestand of bundel")

        files = []
        for item_id in selected_ids:
            item = file_map[item_id]
            requested_action = settings.deletion_mode if item.risk == "safe" else "manual_review_only"
            files.append(
                {
                    "id": item.id,
                    "path": item.path,
                    "before": {"exists": True, "size_bytes": item.size_bytes, "category": item.category},
                    "proposed_action": requested_action,
                    "after": {
                        "source_exists": False if item.risk == "safe" else True,
                        "quarantine_copy": item.risk == "safe" and settings.deletion_mode == "quarantine",
                        "retention_days": settings.retention_days if settings.deletion_mode == "quarantine" else 0,
                    },
                    "advice": item.advice,
                    "execution_allowed": False,
                }
            )
        bundles = []
        for bundle_id in selected_bundle_ids:
            bundle = bundle_map[bundle_id]
            bundles.append(
                {
                    "id": bundle.id,
                    "title": bundle.title,
                    "domain": bundle.domain,
                    "before": {"device_count": len(bundle.devices), "entity_count": len(bundle.entities), "review_count": bundle.review_count},
                    "proposed_action": "manual_review_only",
                    "after": {"device_count": len(bundle.devices), "entity_count": len(bundle.entities), "changed": False},
                    "advice": bundle.advice,
                    "execution_allowed": False,
                }
            )

        plan_id = uuid.uuid4().hex
        plan: dict[str, Any] = {
            "schema_version": 1,
            "id": plan_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scan_id": scan.id,
            "status": "dry_run_only",
            "execution_locked": True,
            "backup_choice": backup_choice,
            "settings": settings.public_dict(),
            "files": files,
            "bundles": bundles,
            "summary": {
                "file_count": len(files),
                "bundle_count": len(bundles),
                "planned_bytes": sum(item["before"]["size_bytes"] for item in files),
                "executable_actions": 0,
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

    def _path(self, plan_id: str, extension: str) -> Path:
        return self.root / f"hass-cleaner-plan-{plan_id}.{extension}"


def _markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# Hass-Cleaner - impact- en herstelplan",
        "",
        "> DRY-RUN: dit plan heeft niets gewijzigd en kan niet worden uitgevoerd.",
        "",
        f"- Plan-ID: `{plan['id']}`",
        f"- Scan-ID: `{plan['scan_id']}`",
        f"- Bestanden: {summary['file_count']}",
        f"- Bundels: {summary['bundle_count']}",
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
    lines.extend(["", "## Algemeen herstel", ""])
    lines.extend(f"- {step}" for step in plan["global_recovery"])
    lines.append("")
    return "\n".join(lines)


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
