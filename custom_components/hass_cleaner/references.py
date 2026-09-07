"""Static reference analysis. Never evaluate templates or expose config values."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

ENTITY = re.compile(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z")
DEVICE = re.compile(r"[a-f0-9]{32}\Z")
KEY_TYPES = {"entity_id": "entity", "entity": "entity", "device_id": "device", "area_id": "area"}
HELPER_ENTITY_KEYS = {"source", "source_entity", "source_entity_id", "entity_ids", "entities", "sensor", "heater",
                      "target_sensor", "humidity_sensor", "humidifier", "cooler", "switch", "input_entity"}
STATISTIC_KEYS = {"statistic_id", "statistic_ids", "stat_energy_from", "stat_energy_to", "stat_cost",
                  "stat_compensation", "stat_consumption", "included_in_stat", "stat_rate", "stat_rate_inverted",
                  "stat_rate_from", "stat_rate_to", "stat_soc"}


def template_entities(value):
    """Inspect syntax only; quoted examples/comments are not dependencies."""
    from jinja2 import Environment, nodes, TemplateSyntaxError
    try:
        tree = Environment().parse(value)
    except TemplateSyntaxError:
        return set()
    result = set()
    for call in tree.find_all(nodes.Call):
        if (isinstance(call.node, nodes.Name)
                and call.node.name in {"states", "is_state", "is_state_attr", "state_attr", "expand"}):
            for arg in call.args[:1] if call.node.name != "expand" else call.args:
                if isinstance(arg, nodes.Const) and isinstance(arg.value, str) and ENTITY.fullmatch(arg.value):
                    result.add(arg.value)
    for attr in tree.find_all(nodes.Getattr):
        if (isinstance(attr.node, nodes.Getattr) and isinstance(attr.node.node, nodes.Name)
                and attr.node.node.name == "states"):
            target = f"{attr.node.attr}.{attr.attr}"
            if ENTITY.fullmatch(target):
                result.add(target)
    return result


def analyze(sources, known):
    """Sources are {id, kind, name, config, error?}; known contains sets of IDs."""
    references, coverage = [], []
    for source in sources:
        record = {key: str(source.get(key, "")) for key in ("id", "kind", "name")}
        record.update(dynamic=0, custom_cards=0, status="partial" if source.get("partial") else "checked")
        found = set()
        visited = 0

        def add(kind, target, location):
            if not isinstance(target, str):
                return
            if target in {"all", "none", "", "this.entity_id"}:
                return
            if kind == "entity" and DEVICE.fullmatch(target):
                # Device automations can store the entity registry UUID instead
                # of the public entity_id. Resolve known UUIDs for inbound use.
                target = known.get("entity_aliases", {}).get(target, target)
                if DEVICE.fullmatch(target):
                    kind = "entity_registry"
            if kind in {"entity", "action"} and not ENTITY.fullmatch(target):
                if kind == "entity" or "." in target:
                    record["status"] = "partial"
                return
            if kind == "device" and not DEVICE.fullmatch(target):
                record["dynamic"] += 1
                return
            if kind == "statistic" and not re.fullmatch(r"[a-z_][a-z0-9_]*[.:][A-Za-z0-9_.:-]+", target):
                record["status"] = "partial"
                return
            key = (kind, target, location)
            if key in found:
                return
            found.add(key)
            inventory = known.get(kind, set())
            if inventory is None:
                record["status"] = "partial"
            references.append({"source_id": record["id"], "source_kind": record["kind"],
                "source_name": record["name"], "target_type": kind, "target_id": target,
                "location": location, "missing": inventory is not None and target not in inventory,
                "verification": "unavailable" if inventory is None else "checked"})

        def walk(value, location="$", key="", depth=0, statistic_context=False):
            nonlocal visited
            visited += 1
            if visited > 100000 or depth > 60:
                record["status"] = "partial"
                return
            if isinstance(value, dict):
                statistic_context = statistic_context or (record["kind"] == "dashboard" and value.get("type") in {"statistic", "statistics-graph"})
                if key == "entities" and record["kind"] == "scene":
                    for entity_id in value:
                        add("entity", entity_id, f"{location}[{entity_id}]")
                    return
                if str(value.get("type", "")).startswith("custom:"):
                    record["custom_cards"] += 1
                if any(key in value for key in ("use_blueprint", "strategy", "label_id", "floor_id", "entity_globs", "domains")):
                    record["status"] = "partial"
                for child_key, child in value.items():
                    if visited > 100000:
                        break
                    # Keys, not contents: output never contains credentials or template text.
                    walk(child, f"{location}.{child_key}", str(child_key), depth + 1, statistic_context)
            elif isinstance(value, (list, tuple)):
                for index, child in enumerate(value):
                    if visited > 100000:
                        break
                    walk(child, f"{location}[{index}]", key, depth + 1, statistic_context)
            else:
                # HA validated configurations can hold Template objects.
                value = getattr(value, "template", value)
                if not isinstance(value, str):
                    return
                if "{{" in value or "{%" in value:
                    if not (record["kind"] in {"automation", "script", "template", "dashboard"} or key.endswith("_template")):
                        if key in KEY_TYPES or key in HELPER_ENTITY_KEYS or key in STATISTIC_KEYS:
                            record["status"] = "partial"
                        return
                    record["dynamic"] += 1
                    if len(value) > 65536:
                        return
                    for target in template_entities(value):
                        add("entity", target, location)
                    return
                if statistic_context and key in {"entity", "entities"}:
                    add("statistic", value, location)
                elif key in KEY_TYPES:
                    add(KEY_TYPES[key], value, location)
                elif key in STATISTIC_KEYS:
                    add("statistic", value, location)
                elif record["kind"] == "energy" and key in {"entity_energy_price", "entity_energy_price_export"}:
                    add("entity", value, location)
                elif record["kind"] in {"helper", "group", "template", "statistics"} and key in HELPER_ENTITY_KEYS:
                    add("entity", value, location)
                elif key == "entities" and record["kind"] == "dashboard":
                    add("entity", value, location)
                elif key in {"service", "action"}:
                    add("action", value, location)

        if source.get("error") or not isinstance(source.get("config"), dict):
            record.update(status="unavailable", error=str(source.get("error") or "Configuration is unavailable"))
        else:
            walk(source["config"])
            if record["dynamic"] or record["custom_cards"]:
                record["status"] = "partial"
        coverage.append(record)
    references.sort(key=lambda r: (r["source_id"], r["location"], r["target_id"]))
    missing = [item for item in references if item["missing"]]
    return {"schema_version": 1, "status": "partial" if any(s["status"] != "checked" for s in coverage) else "completed",
        "checked_at": datetime.now(timezone.utc).isoformat(), "sources": coverage, "references": references,
        "summary": {"sources": len(coverage), "references": len(references), "missing": len(missing),
                    "partial_sources": sum(s["status"] != "checked" for s in coverage)},
        "limitations": ["Static references in automations, scripts, dashboards, scenes, groups, supported helpers, templates and energy/statistics configuration.",
                        "Dynamic templates, blueprint inputs, custom cards and sources that failed to load may hide dependencies.",
                        "No references found does not establish that removal is safe."]}


def repair_groups(report):
    """Stable issue per source: changing a target must not reset ignored issues."""
    groups = {}
    for reference in report.get("references", []):
        if not reference["missing"]:
            continue
        source_id = reference["source_id"]
        issue_id = "reference_" + hashlib.sha256(source_id.encode()).hexdigest()[:24]
        group = groups.setdefault(issue_id, {"source_id": source_id, "source": reference["source_name"], "items": []})
        group["items"].append(f"{reference['target_type']} {reference['target_id']} — {reference['location']}")
    return groups
