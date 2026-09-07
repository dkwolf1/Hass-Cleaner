"""Optional, read-only bridge to the Home Assistant companion integration."""
from __future__ import annotations

import json
import os


def unavailable(reason="companion_unavailable"):
    return {"schema_version": 1, "status": "unavailable", "reason": reason,
            "sources": [], "references": [], "summary": {}}


def fetch_references(token, *, connect=None):
    from .registry_audit import WEBSOCKET_URL, _receive_json, _receive_result
    connection = None
    try:
        if connect is None:
            import websocket
            connect = websocket.create_connection
        connection = connect(WEBSOCKET_URL, timeout=30, header=[f"Authorization: Bearer {token}"])
        authentication = _receive_json(connection)
        if authentication.get("type") == "auth_required":
            connection.send(json.dumps({"type": "auth", "access_token": token}))
            authentication = _receive_json(connection)
        if authentication.get("type") != "auth_ok":
            return unavailable("authentication_failed")
        connection.send(json.dumps({"id": 1, "type": "hass_cleaner/references", "refresh": True}))
        report = _receive_result(connection, 1).get("result")
        if not isinstance(report, dict) or report.get("schema_version") != 1:
            return unavailable("unsupported_report")
        if report.get("status") not in {"completed", "partial", "starting", "unavailable"}:
            return unavailable("invalid_report")
        if not isinstance(report.get("sources"), list) or not isinstance(report.get("references"), list):
            return unavailable("invalid_report")
        if not isinstance(report.get("summary"), dict) or any(type(v) is not int or v < 0 for v in report["summary"].values()):
            return unavailable("invalid_report")
        for source in report["sources"]:
            if (not isinstance(source, dict) or source.get("status") not in {"checked", "partial", "unavailable"}
                    or not all(isinstance(source.get(k), str) for k in ("id", "kind", "name"))):
                return unavailable("invalid_report")
        for item in report["references"]:
            if (not isinstance(item, dict) or type(item.get("missing")) is not bool
                    or item.get("target_type") not in {"entity", "entity_registry", "device", "area", "action", "statistic"}
                    or not all(isinstance(item.get(key), str) for key in
                               ("source_id", "source_kind", "source_name", "target_id", "location"))):
                return unavailable("invalid_report")
        return {key: value for key, value in report.items() if key in {
            "schema_version", "status", "checked_at", "sources", "references", "summary", "limitations"}}
    except Exception:
        # Missing companion, permission refusal and connectivity failures never
        # masquerade as a successful check or break the normal registry scan.
        return unavailable()
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def selection_review(audit, entity_ids=(), device_ids=()):
    """Include direct references plus potential device/area-targeted effects."""
    report = audit.references
    entities, devices = set(entity_ids), set(device_ids)
    areas = set()
    for bundle in audit.bundles:
        for entity in bundle.entities:
            if entity.get("entity_id") in entities:
                devices.add(entity.get("device_id", ""))
                areas.add(entity.get("area_id", ""))
        for device in bundle.devices:
            if device.get("device_id") in devices:
                areas.add(device.get("area_id", ""))
    targets = {"entity": entities, "statistic": entities, "device": devices - {""}, "area": areas - {""}}
    matches = [r for r in report.get("references", []) if r["target_id"] in targets.get(r["target_type"], set())]
    return {"status": report.get("status", "unavailable"), "checked_at": report.get("checked_at"),
            "summary": report.get("summary", {}), "references": matches,
            "count": len(matches), "limitations": report.get("limitations", [])}


def markdown_lines(report, language="en"):
    from .export_text import table, cell
    nl = language == "nl"
    lines = ["", "## Referentiecontrole" if nl else "## Reference checks", "",
             f"Status: {cell(report.get('status', 'unavailable'))}",
             f"{'Momentopname' if nl else 'Snapshot'}: {cell(report.get('checked_at') or '—')}", "",
             "Geen verwijzingen gevonden betekent niet dat verwijderen veilig is. Dynamische templates, blueprints, aangepaste kaarten en onleesbare bronnen beperken de dekking. Apparaat- en ruimtedoelen tonen mogelijk indirect gebruik."
             if nl else "No references found does not mean removal is safe. Dynamic templates, blueprints, custom cards and unreadable sources limit coverage. Device and area targets indicate potential indirect use."]
    lines += table(["Bron", "Bron-ID", "Doeltype", "Doel", "Locatie", "Ontbreekt"] if nl else
                   ["Source", "Source ID", "Target type", "Target", "Location", "Missing"],
                   [(r["source_name"], r["source_id"], r["target_type"], r["target_id"], r["location"],
                     ("onbekend" if nl else "unknown") if r.get("verification") == "unavailable" else
                     ("ja" if nl else "yes") if r["missing"] else ("nee" if nl else "no")) for r in report.get("references", [])])
    if report.get("sources"):
        lines += table(["Bron", "Dekking"] if nl else ["Source", "Coverage"],
                       [(s["name"], s["status"]) for s in report["sources"]])
    return lines


def validate_before_cleanup(scan, plan):
    """Do not execute against dependencies that differ from the reviewed scan."""
    from .registry_cleanup import RegistryCleanupError
    from .registry_audit import audit_registry_snapshot, fetch_registry_snapshot
    before = plan.get("reference_review", {})
    if before.get("status") not in {"completed", "partial"}:
        return  # Optional companion was explicitly unavailable in the preview.
    token = os.environ.get("SUPERVISOR_TOKEN")
    report = fetch_references(token) if token else unavailable()
    if report.get("status") not in {"completed", "partial"}:
        raise RegistryCleanupError("Reference recheck unavailable. No registry changes were made; scan again before proceeding.")
    try:
        audit = audit_registry_snapshot(fetch_registry_snapshot(token))
    except Exception as exc:
        raise RegistryCleanupError("Reference targets could not be revalidated. Scan again before proceeding.") from exc
    audit.references = report
    after = selection_review(audit, [e["entity_id"] for e in plan.get("entities", [])],
                             [d["device_id"] for d in plan.get("devices", [])])
    def signature(value):
        return sorted((r["source_id"], r["target_type"], r["target_id"], r["location"], r["missing"], r.get("verification", "checked"))
                      for r in value.get("references", []))
    coverage_before = sorted((s["id"], s["status"]) for s in scan.registry_audit.references.get("sources", []))
    coverage_after = sorted((s["id"], s["status"]) for s in report.get("sources", []))
    if signature(before) != signature(after) or coverage_before != coverage_after:
        raise RegistryCleanupError("References or check coverage have changed. No registry changes were made; scan again and review the new cleanup preparation.")
