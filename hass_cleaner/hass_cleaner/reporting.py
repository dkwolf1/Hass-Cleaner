from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .scanner import ScanResult
from .settings import Settings


REPORT_SCHEMA_VERSION = 1
REPORT_EXTENSIONS = {"json", "csv", "md"}


def build_report(scan: ScanResult, settings: Settings) -> dict[str, object]:
    scan_data = scan.to_dict(include_items=True)
    safe_items = [item for item in scan.items if item.risk == "safe"]
    review_items = [item for item in scan.items if item.risk == "review"]
    protected_items = [item for item in scan.items if item.risk == "protected"]
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
                "item_id",
                "path",
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
                    item.id,
                    item.path,
                    item.category,
                    item.risk,
                    "yes" if item.risk == "safe" else "no",
                    item.recommended_action,
                    item.size_bytes,
                    item.modified_at,
                    item.reason,
                ]
            )


def _markdown(report: dict[str, object]) -> str:
    scan = report["scan"]
    summary = report["review_summary"]
    assert isinstance(scan, dict)
    assert isinstance(summary, dict)
    items = scan.get("items", [])
    assert isinstance(items, list)

    lines = [
        "# Hass-Cleaner - auditrapport",
        "",
        "> AUDIT-ONLY: dit rapport heeft niets verwijderd, verplaatst of gewijzigd.",
        "",
        f"- Scan-ID: `{scan.get('id')}`",
        f"- Gestart: {scan.get('started_at')}",
        f"- Voltooid: {scan.get('finished_at')}",
        f"- Bekeken bestanden: {scan.get('visited_files')}",
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
    lines.extend(
        [
            "",
            "## Beoordelingsregels",
            "",
            "- Alleen items onder 'Voorgesteld voor cleanup' zouden in een latere versie selecteerbaar zijn.",
            "- Review-items worden nooit automatisch geselecteerd.",
            "- Beschermde items zijn technisch uitgesloten.",
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
