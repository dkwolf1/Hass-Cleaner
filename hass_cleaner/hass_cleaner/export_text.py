"""English readable exports. Object names and identifiers are kept verbatim."""

CATEGORIES = {
    "python_cache": "Generated Python bytecode; the matching source file is present.",
    "python_cache_without_source": "Python bytecode has no matching source file. Removing it may prevent the integration from loading.",
    "old_log": "Old diagnostic log; removing it discards diagnostic history.",
    "editor_artifact": "Editor or operating-system metadata.",
    "brand_cache": "Home Assistant icon cache; icons may need to be downloaded again.",
    "personal_media": "Personal recordings, snapshots or timelapses. Moving them may break links or remove access to personal content.",
    "integration_cache_candidate": "Cache-like path. Active use and automatic regeneration have not been established.",
    "temporary_or_backup": "Possible temporary or backup file. The name alone does not establish that it is unused.",
    "large_orphan_device_group": "Large group of devices without entities. Integration ownership and active use must be checked before removal.",
    "long_unavailable_entities": "Persistent availability problems. Check the integration, device and dependencies before removal.",
}


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return ["", "| " + " | ".join(headers) + " |", "|" + "---|" * len(headers),
            *["| " + " | ".join(cell(value) for value in row) + " |" for row in rows], ""]


def guidance(category, risk="review"):
    if risk == "protected":
        return "Protected system content; excluded from cleanup."
    return CATEGORIES.get(category, "Review ownership, dependencies and recovery before proceeding. Status alone does not prove that removal is safe.")


def report_markdown(report):
    scan = report["scan"]
    summary = report["review_summary"]
    lines = ["# Hass-Cleaner audit report", "", "> AUDIT-ONLY: this report has not deleted, moved or changed anything.", "",
             f"- Scan ID: `{scan['id']}`", f"- Started: {scan.get('started_at')}", f"- Finished: {scan.get('finished_at')}",
             f"- Files checked: {scan.get('visited_files', 0)}", f"- Files ignored by policy: {scan.get('ignored_files', 0)}",
             f"- Suggested candidates: {summary['proposed_for_cleanup_count']}",
             f"- Review yourself: {summary['requires_manual_review_count']}", f"- Protected: {summary['protected_count']}",
             "", "## Cleanup categories", ""]
    cleanup = report.get("cleanup_guidance", {})
    recipes = cleanup.get("safe_recipes", []) + cleanup.get("investigation_recipes", [])
    lines += table(["Category", "Files", "Bytes", "Assessment", "Guidance"],
                   [(item["category"], item["file_count"], item["size_bytes"],
                     "Suggested candidate" if item["kind"] == "safe" else "Review yourself", guidance(item["category"])) for item in recipes])
    lines += ["", "Restore moved files from quarantine. Review items require explicit acceptance of the content risk.",
              "", "### System inventory — retained", ""]
    lines += table(["Category", "Files", "Bytes"], [(item["category"], item["count"], item["size_bytes"]) for item in cleanup.get("inventory", [])])
    lines += ["", "The complete file inventory and original technical details are available in the JSON and CSV exports.",
              "", "## Home Assistant registry audit", ""]
    registry = scan.get("registry_audit", {})
    lines += [f"Status: {cell(registry.get('status', 'unavailable'))}"]
    if registry.get("status") == "completed":
        lines += table(["Metric", "Count"], sorted(registry.get("summary", {}).items()))
        lines += ["", "### Findings requiring review", ""]
        anomalies = registry.get("anomalies", [])
        lines += table(["Category", "Integration", "Sample device IDs", "Guidance"],
                       [(item.get("category", ""), item.get("domain", ""), ", ".join(item.get("sample_device_ids", [])),
                         guidance(item.get("category", ""))) for item in anomalies[:100]])
        findings = registry.get("findings", [])
        review = [item for item in findings if item.get("severity") == "review"]
        lines += table(["Type", "Name", "ID", "Category", "Related ID"],
                       [(item.get("subject_type", ""), item.get("name", ""), item.get("subject_id", ""), item.get("category", ""), item.get("related_id", "")) for item in review[:100]])
        lines += ["", "### Informational findings", ""]
        counts = {}
        for item in findings:
            if item.get("severity") == "info":
                key = item.get("category", "unknown")
                counts[key] = counts.get(key, 0) + 1
        lines += table(["Category", "Count"], sorted(counts.items()))
        lines += ["", "### Bundles with warnings", ""]
        bundles = [item for item in registry.get("bundles", []) if item.get("review_count", 0)]
        lines += table(["Integration", "Domain", "Devices", "Entities", "Warnings", "Config entry"],
                       [(item["title"], item["domain"], len(item["devices"]), len(item["entities"]), item["review_count"], item["config_entry_id"]) for item in bundles[:50]])
        workspace = registry.get("entity_workspace", {})
        lines += ["", "### Entity review", ""]
        lines += table(["State", "Count"], sorted(workspace.get("summary", {}).get("by_status", {}).items()))
        entities = [item for item in workspace.get("items", []) if item.get("selectable_for_plan")]
        lines += table(["Entity", "State", "Days", "Integration", "Device", "Area"],
                       [(item["entity_id"], item.get("status", ""), item.get("duration_days", 0), item.get("integration", ""), item.get("device_name", ""), item.get("area_name", "")) for item in entities[:100]])
        lines += ["", "### Temporary and persistent signals", ""]
        lines += table(["Integration", "Total", "Needs attention", "Monitored", "Longest observation (hours)"],
                       [(item["integration"], item.get("total", 0), item.get("attention", 0), item.get("watch", 0),
                         round(float(item.get("max_duration_seconds", 0)) / 3600, 1)) for item in workspace.get("signal_groups", [])[:50]])
        lines += ["", "Tables show up to 100 findings/entities and 50 bundles/signal groups. JSON and CSV contain all results."]
    else:
        lines += ["Registry information could not be loaded. This does not mean the registry is empty; check the connection and technical report."]
    lines += ["", "## Recovery and execution", "",
              "- Only explicitly selected, non-protected files may enter quarantine after revalidation.",
              "- Review personal or uncertain content and accept its risks before proceeding.",
              "- A completed Home Assistant backup is strongly recommended; the user confirms their backup choice.",
              "- Restore files from quarantine. Existing target files are never overwritten.",
              "- Registry changes may break dashboards and automations; integrations may recreate objects. Recovery requires a Home Assistant backup.",
              "- Permanent file deletion requires an expired quarantine period and a separate confirmation.", ""]
    return "\n".join(lines)


def plan_markdown(plan):
    summary = plan["summary"]
    lines = ["# Hass-Cleaner cleanup preparation", "",
             "> PREPARED CLEANUP: nothing has changed. Review the consequences and your backup choice before confirming execution.", "",
             f"- Plan ID: `{plan['id']}`", f"- Scan ID: `{plan['scan_id']}`",
             f"- Files: {summary['file_count']}", f"- Entities: {summary['entity_count']}",
             f"- Devices: {summary.get('device_count', 0)}", f"- Executable actions: {summary['executable_actions']}",
             "", "## Files", ""]
    lines += table(["Path", "Bytes", "Assessment", "Action", "Guidance"],
                   [(item["path"], item["before"]["size_bytes"], item.get("risk", "review"), "Quarantine", guidance(item["before"]["category"], item.get("risk", "review"))) for item in plan["files"]])
    lines += ["", f"Restore from quarantine; retention: {plan['settings']['retention_days']} days. Existing target files are never overwritten.",
              "", "## Bundles", ""]
    lines += table(["Integration", "Domain", "Devices", "Entities"],
                   [(item["title"], item["domain"], item["before"]["device_count"], item["before"]["entity_count"]) for item in plan["bundles"]])
    lines += ["", "## Entities", ""]
    lines += table(["Entity", "State", "Days", "Integration", "Device"],
                   [(item["entity_id"], item.get("status", ""), item.get("duration_days", 0), item.get("integration", ""), item.get("device_name", "")) for item in plan["entities"]])
    lines += ["", "## Recovery and risks", "",
              "- Check official relationships, dashboards, scripts and automations before removal.",
              "- Removing registry objects has no individual undo. Integrations may recreate objects and references may break.",
              "- Use a complete Home Assistant backup for registry recovery. Creating and checking one is strongly recommended.",
              "- Personal content may be lost or unavailable after moving it. Quarantine does not prove that content is unused.",
              "- Protected system files remain excluded. Cancel if the consequences are unclear.", ""]
    return "\n".join(lines)
