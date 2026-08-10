from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .scanner import ScanResult
from .settings import Settings


REPORT_SCHEMA_VERSION = 2
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
        },
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
        "## Voorgesteld voor cleanup",
        "",
    ]
    lines.extend(_markdown_table([item for item in items if isinstance(item, dict) and item.get("risk") == "safe"]))
    lines.extend(["", "## Handmatig beoordelen", ""])
    lines.extend(_markdown_table([item for item in items if isinstance(item, dict) and item.get("risk") == "review"]))
    lines.extend(["", "## Beschermd - nooit wijzigen", ""])
    lines.extend(_markdown_table([item for item in items if isinstance(item, dict) and item.get("risk") == "protected"]))
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
                "",
                "### Handmatig beoordelen",
                "",
            ]
        )
        lines.extend(_markdown_registry_table([item for item in findings if isinstance(item, dict) and item.get("severity") == "review"]))
        lines.extend(["", "### Informatief - nooit automatisch opruimen", ""])
        lines.extend(_markdown_registry_table([item for item in findings if isinstance(item, dict) and item.get("severity") == "info"]))
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
            "- Registerbevindingen zijn uitsluitend informatief of voor handmatige beoordeling en zijn nooit selecteerbaar.",
            "- In deze versie bestaat geen verwijder- of verplaatsfunctie.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_table(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen bestanden gevonden."]
    lines = [
        "| Pad | Categorie | Grootte | Gewijzigd | Reden |",
        "|---|---:|---:|---:|---|",
    ]
    for item in items:
        lines.append(
            "| `{path}` | {category} | {size} B | {modified} | {reason} |".format(
                path=str(item.get("path", "")).replace("|", "\\|"),
                category=str(item.get("category", "")).replace("|", "\\|"),
                size=item.get("size_bytes", 0),
                modified=str(item.get("modified_at", "")),
                reason=str(item.get("reason", "")).replace("|", "\\|"),
            )
        )
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
