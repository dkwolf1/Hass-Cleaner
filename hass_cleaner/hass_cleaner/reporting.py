from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .scanner import ScanResult
from .settings import Settings


REPORT_SCHEMA_VERSION = 7
REPORT_EXTENSIONS = {"json", "csv", "md"}


def build_report(scan: ScanResult, settings: Settings) -> dict[str, object]:
    scan_data = scan.to_dict(include_items=True)
    safe_items = [item for item in scan.items if item.risk == "safe"]
    review_items = [item for item in scan.items if item.risk == "review"]
    protected_items = [item for item in scan.items if item.risk == "protected"]
    registry_data = scan.registry_audit.to_dict()
    registry_summary = registry_data.get("summary", {})
    assert isinstance(registry_summary, dict)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_only": True,
        "execution_locked": True,
        "source_root": "/homeassistant",
        "settings": settings.public_dict(),
        "review_summary": {
            "proposed_for_cleanup_count": len(safe_items),
            "requires_manual_review_count": len(review_items),
            "protected_count": len(protected_items),
            "proposed_for_cleanup_bytes": sum(item.size_bytes for item in safe_items),
            "requires_manual_review_bytes": sum(item.size_bytes for item in review_items),
            "registry_review_findings": registry_summary.get("review_findings", 0),
            "registry_informational_findings": registry_summary.get("informational_findings", 0),
            "registry_anomalies": registry_summary.get("anomalies_total", 0),
        },
        "cleanup_guidance": scan_data.get("cleanup_guidance", {}),
        "scan": scan_data,
    }


def write_report_files(scan: ScanResult, settings: Settings, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(scan, settings)
    paths = {
        "json": output_dir / f"hass-cleaner-audit-{scan.id}.json",
        "csv": output_dir / f"hass-cleaner-audit-{scan.id}.csv",
        "md": output_dir / f"hass-cleaner-audit-{scan.id}.md",
    }
    paths["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(scan, paths["csv"])
    paths["md"].write_text(_markdown(report), encoding="utf-8")
    return paths


def report_path(output_dir: Path, scan_id: str, extension: str) -> Path | None:
    if not scan_id.isalnum() or extension not in REPORT_EXTENSIONS:
        return None
    path = output_dir / f"hass-cleaner-audit-{scan_id}.{extension}"
    return path if path.is_file() else None


def _write_csv(scan: ScanResult, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(
            [
                "record_type",
                "item_id",
                "path",
                "subject_type",
                "subject_id",
                "name",
                "category",
                "risk",
                "proposed_for_cleanup",
                "recommended_action",
                "size_bytes",
                "modified_at",
                "reason",
                "evidence_level",
                "possible_consequences",
                "recovery_steps",
                "content_preview",
            ]
        )
        for item in scan.items:
            writer.writerow(
                [
                    "file",
                    item.id,
                    item.path,
                    "",
                    "",
                    "",
                    item.category,
                    item.risk,
                    "yes" if item.risk == "safe" else "no",
                    item.recommended_action,
                    item.size_bytes,
                    item.modified_at,
                    item.reason,
                    item.advice.get("evidence_level", ""),
                    " | ".join(str(value) for value in item.advice.get("possible_consequences", [])),
                    " | ".join(str(value) for value in item.advice.get("recovery_steps", [])),
                    json.dumps(item.advice.get("content_preview", {}), ensure_ascii=False),
                ]
            )
        for item in scan.registry_audit.findings:
            writer.writerow(
                [
                    "registry",
                    item.id,
                    "",
                    item.subject_type,
                    item.subject_id,
                    item.name,
                    item.category,
                    item.severity,
                    "no",
                    item.recommended_action,
                    0,
                    "",
                    item.reason,
                    "",
                    "",
                    "",
                    "",
                ]
            )
        for bundle in scan.registry_audit.bundles:
            writer.writerow(
                [
                    "bundle",
                    bundle.id,
                    "",
                    "integration_bundle",
                    bundle.config_entry_id,
                    bundle.title,
                    "integration_bundle",
                    "review" if bundle.review_count else "info",
                    "no",
                    "manual_review",
                    0,
                    "",
                    f"{len(bundle.devices)} apparaten; {len(bundle.entities)} entities; {bundle.review_count} waarschuwingen",
                    bundle.advice.get("evidence_level", ""),
                    " | ".join(str(value) for value in bundle.advice.get("possible_consequences", [])),
                    " | ".join(str(value) for value in bundle.advice.get("recovery_steps", [])),
                    json.dumps(bundle.advice.get("content_preview", {}), ensure_ascii=False),
                ]
            )
        for entity in scan.registry_audit.entity_workspace.get("items", []):
            if not entity.get("attention"):
                continue
            writer.writerow(
                [
                    "entity_health",
                    entity.get("entity_id", ""),
                    "",
                    "entity",
                    entity.get("entity_id", ""),
                    entity.get("name", ""),
                    entity.get("status", ""),
                    "review",
                    "no",
                    "manual_review",
                    0,
                    entity.get("last_changed", ""),
                    entity.get("reason", ""),
                    "insufficient",
                    "Verwijderen kan dashboards, automatiseringen of integraties breken",
                    "Herstel via Home Assistant-back-up en herstel van de integratie/configuratie-entry",
                    json.dumps({
                        "raw_state": entity.get("raw_state"),
                        "duration_days": entity.get("duration_days", 0),
                        "integration": entity.get("integration", ""),
                        "device": entity.get("device_name", ""),
                        "area": entity.get("area_name", ""),
                    }, ensure_ascii=False),
                ]
            )
        for anomaly in scan.registry_audit.anomalies:
            writer.writerow(
                [
                    "registry_anomaly",
                    anomaly.get("id", ""),
                    "",
                    "integration_bundle",
                    anomaly.get("bundle_id", ""),
                    anomaly.get("title", ""),
                    anomaly.get("category", ""),
                    anomaly.get("severity", "review"),
                    "no",
                    "manual_review",
                    0,
                    "",
                    anomaly.get("summary", ""),
                    "insufficient",
                    "Geen verwijdering zonder aanvullende controle",
                    "Herstel via volledige Home Assistant-back-up",
                    json.dumps(anomaly.get("counts", {}), ensure_ascii=False),
                ]
            )


def _markdown(report: dict[str, object]) -> str:
    scan = report["scan"]
    summary = report["review_summary"]
    assert isinstance(scan, dict)
    assert isinstance(summary, dict)
    items = scan.get("items", [])
    registry = scan.get("registry_audit", {})
    assert isinstance(items, list)
    assert isinstance(registry, dict)

    lines = [
        "# Hass-Cleaner - auditrapport",
        "",
        "> AUDIT-ONLY: dit rapport heeft niets verwijderd, verplaatst of gewijzigd.",
        "",
        f"- Scan-ID: `{scan.get('id')}`",
        f"- Gestart: {scan.get('started_at')}",
        f"- Voltooid: {scan.get('finished_at')}",
        f"- Bekeken bestanden: {scan.get('visited_files')}",
        f"- Genegeerd volgens beleid: {scan.get('ignored_files', 0)} bestanden",
        f"- Voorgesteld voor cleanup: {summary.get('proposed_for_cleanup_count')} bestanden",
        f"- Handmatig beoordelen: {summary.get('requires_manual_review_count')} bestanden",
        f"- Beschermd: {summary.get('protected_count')} bestanden",
        "",
        "## Beginnersadvies - opruimrecepten",
        "",
    ]
    guidance = report.get("cleanup_guidance", {})
    if isinstance(guidance, dict):
        lines.extend(_markdown_recipes(guidance.get("safe_recipes", []), "Volledig bewezen"))
        lines.extend(["", "### Eerst nader onderzoeken", ""])
        lines.extend(_markdown_recipes(guidance.get("investigation_recipes", []), "Geblokkeerd"))
        lines.extend(["", "### Systeeminventaris - behouden", ""])
        lines.extend(_markdown_inventory(guidance.get("inventory", [])))
    lines.extend([
        "",
        "> De volledige afzonderlijke bestandsinventaris staat in de JSON- en CSV-export.",
        "",
        "## Voorgesteld voor cleanup",
        "",
    ])
    lines.extend(_markdown_table([item for item in items if isinstance(item, dict) and item.get("risk") == "safe"]))
    lines.extend(["", "## Home Assistant-registercontrole", ""])
    registry_status = registry.get("status")
    if registry_status == "completed":
        registry_summary = registry.get("summary", {})
        findings = registry.get("findings", [])
        assert isinstance(registry_summary, dict)
        assert isinstance(findings, list)
        lines.extend(
            [
                f"- Entities: {registry_summary.get('entities_total', 0)}",
                f"- Apparaten: {registry_summary.get('devices_total', 0)}",
                f"- Entities zonder apparaat: {registry_summary.get('entities_without_device', 0)} (informatief)",
                f"- Gebroken registerverwijzingen: {registry_summary.get('broken_references', 0)}",
                f"- Ingeschakelde entities zonder actuele state: {registry_summary.get('entities_not_loaded', 0)}",
                f"- Onbeschikbare states: {registry_summary.get('unavailable_states', 0)} (alleen geteld)",
                f"- Tijdelijk onbeschikbare entities: {registry_summary.get('temporarily_unavailable_entities', 0)} (informatief)",
                f"- Langdurig onbeschikbare entities: {registry_summary.get('long_unavailable_entities', 0)} (gebundeld aandachtspunt, geen verwijderadvies)",
                f"- Tijdelijk/langdurig unknown: {registry_summary.get('temporarily_unknown_entities', 0)} / {registry_summary.get('long_unknown_entities', 0)}",
                f"- Problem-state: {registry_summary.get('problem_entities', 0)}",
                "",
                "### Concrete aandachtspunten",
                "",
            ]
        )
        lines.extend(_markdown_anomalies(registry.get("anomalies", [])))
        lines.extend(
            [
                "",
                "### Handmatig beoordelen",
                "",
            ]
        )
        lines.extend(_markdown_registry_table([item for item in findings if isinstance(item, dict) and item.get("severity") == "review"]))
        lines.extend(["", "### Informatief - nooit automatisch opruimen", ""])
        lines.extend(_markdown_registry_table([item for item in findings if isinstance(item, dict) and item.get("severity") == "info"]))
        bundles = registry.get("bundles", [])
        assert isinstance(bundles, list)
        lines.extend(["", "### Bundels per integratie", ""])
        lines.extend(_markdown_bundle_table([item for item in bundles if isinstance(item, dict)]))
        workspace = registry.get("entity_workspace", {})
        if isinstance(workspace, dict):
            entity_items = workspace.get("items", [])
            if isinstance(entity_items, list):
                lines.extend(["", "### Entiteiten met aandacht", ""])
                lines.extend(_markdown_entity_table([item for item in entity_items if isinstance(item, dict) and item.get("attention")]))
    else:
        lines.append(f"Registerscan niet beschikbaar: {registry.get('error') or registry_status}.")
    lines.extend(
        [
            "",
            "## Beoordelingsregels",
            "",
            "- Alleen items onder 'Voorgesteld voor cleanup' zouden in een latere versie selecteerbaar zijn.",
            "- Review-items worden nooit automatisch geselecteerd.",
            "- Beschermde items zijn technisch uitgesloten.",
            "- Alleen langdurige statusproblemen, niet-geladen entities en kapotte verwijzingen kunnen aan een geblokkeerd onderzoeksplan worden toegevoegd.",
            "- Een onderzoeksselectie is geen verwijderadvies en bevat altijd nul uitvoerbare acties.",
            "- In deze versie bestaat geen verwijder- of verplaatsfunctie.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_table(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen bestanden gevonden."]
    lines = [
        "| Pad | Categorie | Bewijs | Grootte | Reden | Mogelijk gevolg | Herstel |",
        "|---|---:|---|---:|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| `{path}` | {category} | {evidence} | {size} B | {reason} | {consequence} | {recovery} |".format(
                path=str(item.get("path", "")).replace("|", "\\|"),
                category=str(item.get("category", "")).replace("|", "\\|"),
                size=item.get("size_bytes", 0),
                modified=str(item.get("modified_at", "")),
                reason=str(item.get("reason", "")).replace("|", "\\|"),
                evidence=str(item.get("advice", {}).get("evidence_label", "")) if isinstance(item.get("advice"), dict) else "",
                consequence=_advice_join(item, "possible_consequences"),
                recovery=_advice_join(item, "recovery_steps"),
            )
        )
    return lines


def _markdown_entity_table(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen entiteiten met een aandachtspunt gevonden."]
    lines = [
        "| Entity | Status | Duur | Integratie | Apparaat | Ruimte | Selecteerbaar voor onderzoek | Reden |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| `{}` | {} | {} dagen | {} | {} | {} | {} | {} |".format(
                _md(item.get("entity_id", "")),
                _md(item.get("status", "")),
                item.get("duration_days", 0),
                _md(item.get("integration", "")),
                _md(item.get("device_name", "")),
                _md(item.get("area_name", "")),
                "ja" if item.get("selectable_for_plan") else "nee",
                _md(item.get("reason", "")),
            )
        )
    return lines


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_recipes(value: object, status: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["Geen recepten gevonden."]
    lines = ["| Recept | Producer | Bestanden | Grootte | Bewijspoort | Advies |", "|---|---|---:|---:|---|---|"]
    for recipe in value:
        if not isinstance(recipe, dict):
            continue
        lines.append("| {title} | {producer} | {count} | {size} B | {status} | {advice} |".format(
            title=str(recipe.get("title", "")).replace("|", "\\|"),
            producer=str(recipe.get("producer", "")).replace("|", "\\|"),
            count=recipe.get("file_count", 0), size=recipe.get("size_bytes", 0), status=status,
            advice=str(recipe.get("recommendation", "")).replace("|", "\\|"),
        ))
    return lines


def _markdown_inventory(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["Geen beschermde systeeminventaris gevonden."]
    lines = ["| Categorie | Bestanden | Grootte |", "|---|---:|---:|"]
    for item in value:
        if isinstance(item, dict):
            lines.append(f"| {str(item.get('category', '')).replace('|', '\\|')} | {item.get('count', 0)} | {item.get('size_bytes', 0)} B |")
    return lines


def _markdown_registry_table(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen registerbevindingen gevonden."]
    lines = [
        "| Type | Naam | ID | Categorie | Gerelateerd ID | Reden |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        values = {
            key: str(item.get(key, "")).replace("|", "\\|")
            for key in ("subject_type", "name", "subject_id", "category", "related_id", "reason")
        }
        lines.append(
            "| {subject_type} | {name} | `{subject_id}` | {category} | `{related_id}` | {reason} |".format(**values)
        )
    return lines


def _markdown_anomalies(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["Geen concrete registry-afwijkingen gevonden."]
    lines = ["| Aandachtspunt | Integratie | Samenvatting | Uitvoering |", "|---|---|---|---|"]
    for item in value:
        if isinstance(item, dict):
            lines.append("| {title} | `{domain}` | {summary} | Geblokkeerd |".format(
                title=str(item.get("title", "")).replace("|", "\\|"),
                domain=str(item.get("domain", "")).replace("|", "\\|"),
                summary=str(item.get("summary", "")).replace("|", "\\|"),
            ))
    return lines


def _markdown_bundle_table(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen bundels gevonden."]
    lines = [
        "| Integratie | Domein | Apparaten | Entities | Waarschuwingen | Bewijs | Advies | Config-entry |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in items:
        devices = item.get("devices", [])
        entities = item.get("entities", [])
        lines.append(
            "| {title} | `{domain}` | {devices} | {entities} | {review} | {evidence} | {advice} | `{entry}` |".format(
                title=str(item.get("title", "")).replace("|", "\\|"),
                domain=str(item.get("domain", "")).replace("|", "\\|"),
                devices=len(devices) if isinstance(devices, list) else 0,
                entities=len(entities) if isinstance(entities, list) else 0,
                review=item.get("review_count", 0),
                entry=str(item.get("config_entry_id", "")).replace("|", "\\|"),
                evidence=str(item.get("advice", {}).get("evidence_label", "")) if isinstance(item.get("advice"), dict) else "",
                advice=str(item.get("advice", {}).get("recommended_first_step", "")).replace("|", "\\|") if isinstance(item.get("advice"), dict) else "",
            )
        )
    return lines


def _advice_join(item: dict[str, object], key: str) -> str:
    advice = item.get("advice", {})
    if not isinstance(advice, dict):
        return ""
    values = advice.get(key, [])
    if not isinstance(values, list):
        return ""
    return "; ".join(str(value).replace("|", "\\|") for value in values)
