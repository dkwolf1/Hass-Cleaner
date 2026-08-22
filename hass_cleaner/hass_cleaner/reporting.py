from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .scanner import ScanResult
from .settings import Settings


REPORT_SCHEMA_VERSION = 11
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
        # The report itself is an immutable scan artifact. Execution is always
        # performed separately from a freshly revalidated cleanup plan.
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


def prune_report_files(output_dir: Path, keep_scans: int) -> list[str]:
    """Remove only old Hass-Cleaner-owned report sets from the app data directory."""
    if not output_dir.is_dir():
        return []
    grouped: dict[str, list[Path]] = {}
    for path in output_dir.glob("hass-cleaner-audit-*.*"):
        match = path.name.removeprefix("hass-cleaner-audit-").rsplit(".", 1)
        if len(match) == 2 and match[0].isalnum() and match[1] in REPORT_EXTENSIONS:
            grouped.setdefault(match[0], []).append(path)
    ordered = sorted(
        grouped.items(),
        key=lambda entry: max((item.stat().st_mtime for item in entry[1]), default=0),
        reverse=True,
    )
    removed: list[str] = []
    for scan_id, paths in ordered[max(1, keep_scans):]:
        for path in paths:
            try:
                path.unlink()
            except OSError:
                continue
        removed.append(scan_id)
    return removed


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
            writer.writerow(
                [
                    "entity_health",
                    entity.get("entity_id", ""),
                    "",
                    "entity",
                    entity.get("entity_id", ""),
                    entity.get("name", ""),
                    entity.get("status", ""),
                    "review" if entity.get("attention") else "info",
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
                        "registry_entry": entity.get("registry_entry", True),
                    }, ensure_ascii=False),
                ]
            )
        for anomaly in scan.registry_audit.anomalies:
            consequences = anomaly.get("possible_consequences", [])
            recovery = anomaly.get("recovery_steps", [])
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
                    anomaly.get("evidence_level", "insufficient"),
                    " | ".join(str(value) for value in consequences) if isinstance(consequences, list) else "",
                    " | ".join(str(value) for value in recovery) if isinstance(recovery, list) else "",
                    json.dumps({
                        "counts": anomaly.get("counts", {}),
                        "evidence_summary": anomaly.get("evidence_summary", ""),
                        "risk_summary": anomaly.get("risk_summary", ""),
                        "recommended_first_step": anomaly.get("recommended_first_step", ""),
                        "sample_device_ids": anomaly.get("sample_device_ids", []),
                        "sample_entity_ids": anomaly.get("sample_entity_ids", []),
                    }, ensure_ascii=False),
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
        "## Beginnersadvies - opruimcategorieën",
        "",
    ]
    guidance = report.get("cleanup_guidance", {})
    if isinstance(guidance, dict):
        lines.extend(_markdown_recipes(guidance.get("safe_recipes", []), "Volledig bewezen"))
        lines.extend(["", "### Eerst nader onderzoeken", ""])
        lines.extend(_markdown_recipes(guidance.get("investigation_recipes", []), "Geblokkeerd"))
        lines.extend(["", "### Systeeminventaris - behouden", ""])
        lines.extend(_markdown_inventory(guidance.get("inventory", [])))
    safe_items = [item for item in items if isinstance(item, dict) and item.get("risk") == "safe"]
    lines.extend([
        "",
        "## Afzonderlijke bestanden",
        "",
        f"{len(safe_items)} bestanden voldoen aan een bewezen veilig recept. Het Markdownrapport toont bewust geen duizenden losse paden.",
        "",
        "> De volledige bestandsinventaris en alle technische details staan in de JSON- en CSV-export.",
    ])
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
                f"- Runtime-only states zonder entityregister-item: {registry_summary.get('state_only_entities', 0)} (informatief)",
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
        review_findings = [item for item in findings if isinstance(item, dict) and item.get("severity") == "review"]
        lines.extend(_markdown_registry_table(review_findings[:100]))
        if len(review_findings) > 100:
            lines.append(f"\nNog {len(review_findings) - 100} aandachtspunten staan in JSON en CSV.")
        lines.extend(["", "### Informatieve registerbevindingen - samenvatting", ""])
        lines.extend(_markdown_finding_summary([item for item in findings if isinstance(item, dict) and item.get("severity") == "info"]))
        bundles = registry.get("bundles", [])
        assert isinstance(bundles, list)
        warning_bundles = [item for item in bundles if isinstance(item, dict) and int(item.get("review_count", 0)) > 0]
        lines.extend(["", "### Bundels met waarschuwingen", ""])
        lines.extend(_markdown_bundle_table(warning_bundles[:50]))
        if len(warning_bundles) > 50:
            lines.append(f"\nNog {len(warning_bundles) - 50} bundels staan in JSON en CSV.")
        workspace = registry.get("entity_workspace", {})
        if isinstance(workspace, dict):
            entity_items = workspace.get("items", [])
            entity_summary = workspace.get("summary", {})
            if isinstance(entity_summary, dict):
                lines.extend([
                    "",
                    "### Entity-onderzoek",
                    "",
                    f"- Geregistreerd: {entity_summary.get('registered_total', 0)}",
                    f"- Runtime-only: {entity_summary.get('state_only_total', 0)}",
                    f"- Statusproblemen: {entity_summary.get('attention', 0)}",
                    f"- Uitgeschakeld (informatief): {entity_summary.get('disabled', 0)}",
                    f"- Selecteerbaar voor geblokkeerd onderzoek: {entity_summary.get('selectable_for_plan', 0)}",
                ])
                lines.extend(["", "#### Statusverdeling", ""])
                lines.extend(_markdown_status_summary(entity_summary.get("by_status", {})))
            if isinstance(entity_items, list):
                selectable = [item for item in entity_items if isinstance(item, dict) and item.get("selectable_for_plan")]
                lines.extend(["", "#### Selecteerbaar voor opschoning", ""])
                lines.extend(_markdown_entity_table(selectable[:100]))
                if len(selectable) > 100:
                    lines.append(f"\nNog {len(selectable) - 100} entities staan in JSON en CSV.")
            signal_groups = workspace.get("signal_groups", [])
            if isinstance(signal_groups, list):
                lines.extend(["", "#### Tijdelijke en langdurige signalen per integratie", ""])
                lines.extend(_markdown_signal_groups(signal_groups[:50]))
                if len(signal_groups) > 50:
                    lines.append(f"\nNog {len(signal_groups) - 50} integratiegroepen staan in JSON en CSV.")
    else:
        lines.append(f"Registerscan niet beschikbaar: {registry.get('error') or registry_status}.")
    lines.extend(
        [
            "",
            "## Beoordelingsregels",
            "",
            "- Alleen door de gebruiker geselecteerde, niet-beschermde bestanden kunnen na een nieuwe servercontrole naar quarantaine.",
            "- Review-items worden nooit automatisch geselecteerd en vereisen een extra risicoacceptatie.",
            "- Beschermde items zijn technisch uitgesloten.",
            "- Geregistreerde entities en gebundelde apparaten kunnen door de gebruiker aan de opschoning worden toegevoegd.",
            "- Status en advies zijn geen garantie; registerwijzigingen vereisen een aparte waarschuwing en exacte bevestiging.",
            "- Permanente bestandsverwijdering buiten de bewaartermijn en wijzigingen aan beschermde kernbestanden blijven technisch uitgesloten.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_finding_summary(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["Geen informatieve registerbevindingen gevonden."]
    counts: dict[str, int] = {}
    for item in items:
        category = str(item.get("category", "onbekend"))
        counts[category] = counts.get(category, 0) + 1
    lines = ["| Categorie | Aantal |", "|---|---:|"]
    lines.extend(f"| {_md(category)} | {count} |" for category, count in sorted(counts.items()))
    return lines


def _markdown_status_summary(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["Geen entity-statussen gevonden."]
    lines = ["| Status | Aantal |", "|---|---:|"]
    lines.extend(f"| {_md(status)} | {count} |" for status, count in sorted(value.items()))
    return lines


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
        return ["Geen opruimcategorieën gevonden."]
    lines = ["| Opruimcategorie | Producer | Bestanden | Grootte | Beoordeling | Advies |", "|---|---|---:|---:|---|---|"]
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
    lines = [
        "| Aandachtspunt | Integratie | Bewijs | Risico | Eerste stap | Uitvoering |",
        "|---|---|---|---|---|---|",
    ]
    for item in value:
        if isinstance(item, dict):
            lines.append("| {title} | `{domain}` | {evidence} | {risk} | {step} | Geblokkeerd |".format(
                title=str(item.get("title", "")).replace("|", "\\|"),
                domain=str(item.get("domain", "")).replace("|", "\\|"),
                evidence=str(item.get("evidence_summary") or item.get("summary", "")).replace("|", "\\|"),
                risk=str(item.get("risk_summary", "")).replace("|", "\\|"),
                step=str(item.get("recommended_first_step", "")).replace("|", "\\|"),
            ))
    return lines


def _markdown_signal_groups(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["Geen tijdelijke of langdurige entitysignalen gevonden."]
    lines = [
        "| Integratie | Totaal | Actie nodig | Tijdelijk volgen | Apparaten | Langste meting |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in value:
        if not isinstance(item, dict):
            continue
        devices = item.get("device_groups", [])
        duration_hours = int(item.get("max_duration_seconds", 0) or 0) / 3600
        duration = f"{duration_hours:.1f} uur" if duration_hours < 24 else f"{duration_hours / 24:.1f} dagen"
        lines.append(
            "| `{integration}` | {total} | {attention} | {watch} | {devices} | {duration} |".format(
                integration=str(item.get("integration", "")).replace("|", "\\|"),
                total=item.get("total", 0),
                attention=item.get("attention", 0),
                watch=item.get("watch", 0),
                devices=len(devices) if isinstance(devices, list) else 0,
                duration=duration,
            )
        )
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
