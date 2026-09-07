"""Read-only adapters for the additional reference source families."""
HELPERS = frozenset({"group", "template", "min_max", "integration", "utility_meter", "statistics",
                     "derivative", "threshold", "filter", "history_stats", "generic_thermostat",
                     "generic_hygrostat", "switch_as_x", "tod", "input_boolean", "input_number",
                     "input_select", "input_text", "input_datetime", "input_button", "counter",
                     "timer", "schedule", "random", "trend", "bayesian"})


def yaml_sources(config):
    """HA's loader resolves includes/packages; never return unrelated configuration."""
    result = []
    for section, value in config.items():
        domain = str(section).split(" ", 1)[0]
        if domain == "recorder" and isinstance(value, dict):
            result.append({"id": f"yaml:{section}", "kind": "statistics", "name": "Recorder entity filters",
                           "config": {k: value[k] for k in ("include", "exclude") if k in value}, "origin": "yaml"})
        elif domain == "group" and isinstance(value, dict):
            for name, group in value.items():
                result.append({"id": f"group.{name}", "kind": "group", "name": str(name),
                               "config": {"entities": group} if isinstance(group, list) else group, "origin": "yaml"})
        elif domain in HELPERS:
            kind = "template" if domain == "template" else "group" if domain == "group" else "helper"
            entries = value if isinstance(value, list) else [value]
            for index, entry in enumerate(entries):
                result.append({"id": f"yaml:{section}:{index}", "kind": kind,
                               "name": f"YAML {section} [{index}]", "config": entry,
                               "origin": "yaml"})
        elif domain in {"sensor", "binary_sensor", "light", "switch", "cover", "fan", "climate"}:
            entries = value if isinstance(value, list) else [value]
            for index, entry in enumerate(entries):
                if isinstance(entry, dict) and entry.get("platform") in HELPERS:
                    platform = entry["platform"]
                    result.append({"id": f"yaml:{section}:{index}",
                                   "kind": "template" if platform == "template" else "group" if platform == "group" else "helper",
                                   "name": str(entry.get("name") or f"YAML {section} [{index}]"), "config": entry,
                                   "origin": "yaml"})
    return result


async def collect_extended_sources(hass):
    result = []
    # Runtime scene/group memberships also cover dynamically created scenes.
    for state in hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0]
        if domain in {"scene", "group"}:
            members = state.attributes.get("entity_id")
            result.append({"id": state.entity_id, "name": state.name, "kind": domain,
                           "config": {"entity_id": members} if isinstance(members, (list, tuple)) else None})
    for entry in hass.config_entries.async_entries():
        if entry.domain not in HELPERS:
            continue
        kind = "template" if entry.domain == "template" else "group" if entry.domain == "group" else "helper"
        # Keep exact data/options paths but discard options-shadowed data values.
        result.append({"id": f"helper:{entry.entry_id}", "name": entry.title, "kind": kind,
                       "config": {"data": {k: v for k, v in entry.data.items() if k not in entry.options},
                                  "options": dict(entry.options)}})
    try:
        from homeassistant.config import async_hass_config_yaml
        saved = yaml_sources(await async_hass_config_yaml(hass))
        saved_ids = {s["id"] for s in saved}
        result = [s for s in result if s["id"] not in saved_ids] + saved
    except Exception as exc:
        for existing in result:
            if existing["kind"] == "group" and existing["id"].startswith("group."):
                existing["partial"] = True
        result.append({"id": "yaml:coverage", "name": "YAML helpers and templates", "kind": "helper",
                       "error": f"YAML configuration unavailable ({type(exc).__name__})"})
    if "energy" in hass.config.components:
        try:
            from homeassistant.components.energy.data import async_get_manager
            manager = await async_get_manager(hass)
            result.append({"id": "energy:preferences", "name": "Energy configuration", "kind": "energy",
                           "config": manager.data or {}})
        except Exception as exc:
            result.append({"id": "energy:preferences", "name": "Energy configuration", "kind": "energy",
                           "error": f"Energy configuration unavailable ({type(exc).__name__})"})
    return result


async def statistic_ids(hass):
    """None means verification unavailable, never an empty successful inventory."""
    if "recorder" not in hass.config.components:
        return None
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import list_statistic_ids
        metadata = await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)
        return {item["statistic_id"] for item in metadata}
    except Exception:
        return None
