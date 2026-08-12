from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Protocol


class ScannedFile(Protocol):
    id: str
    path: str
    category: str
    risk: str
    size_bytes: int


SAFE_TITLES = {
    "old_log": ("Oude logbestanden", "Oude diagnosegegevens die niet meer actief worden geschreven."),
    "python_cache": ("Tijdelijke Python-cache", "Gegenereerde bytecode; Home Assistant maakt deze zo nodig opnieuw."),
    "editor_artifact": ("Editor- en systeemrestanten", "Bekende restbestanden zonder Home Assistant-functie."),
    "brand_cache": ("Home Assistant pictogramcache", "Gegenereerde integratiepictogrammen; Home Assistant kan deze opnieuw ophalen."),
}

INVENTORY_CATEGORIES = {
    "custom_components", "frontend_package", "www_asset_inventory",
    "core_configuration", "home_assistant_storage", "database", "symlink",
}


def build_cleanup_guidance(items: Iterable[ScannedFile]) -> dict[str, object]:
    """Turn the complete audit into a small beginner-safe set of recipes."""
    grouped: dict[tuple[str, str, str], list[ScannedFile]] = defaultdict(list)
    inventory: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "size_bytes": 0})

    for item in items:
        if item.category in INVENTORY_CATEGORIES or item.risk == "protected":
            inventory[item.category]["count"] += 1
            inventory[item.category]["size_bytes"] += item.size_bytes
            continue
        if item.category in SAFE_TITLES:
            kind = "safe"
        elif item.category == "integration_cache_candidate":
            kind = "investigate"
        elif item.category == "personal_media":
            kind = "personal"
        else:
            kind = "advanced"
        producer = _producer(item.path)
        grouped[(kind, item.category, "all" if kind == "safe" else producer)].append(item)

    recipes = [_recipe(kind, category, producer, members) for (kind, category, producer), members in grouped.items()]
    order = {"safe": 0, "investigate": 1, "personal": 2, "advanced": 3}
    recipes.sort(key=lambda recipe: (order[str(recipe["kind"])], -int(recipe["size_bytes"]), str(recipe["title"])))
    safe = [recipe for recipe in recipes if recipe["kind"] == "safe"]
    investigate = [recipe for recipe in recipes if recipe["kind"] != "safe"]
    return {
        "mode": "beginner",
        "execution_locked": False,
        "safe_recipes": safe,
        "investigation_recipes": investigate,
        "safe_total_bytes": sum(int(recipe["size_bytes"]) for recipe in safe),
        "investigation_total_bytes": sum(int(recipe["size_bytes"]) for recipe in investigate),
        "inventory": [{"category": category, **values} for category, values in sorted(inventory.items())],
        "inventory_total_bytes": sum(values["size_bytes"] for values in inventory.values()),
    }


def _recipe(kind: str, category: str, producer: str, members: list[ScannedFile]) -> dict[str, object]:
    producer_groups: dict[str, dict[str, int]] = defaultdict(lambda: {"file_count": 0, "size_bytes": 0})
    for item in members:
        item_producer = _producer(item.path)
        producer_groups[item_producer]["file_count"] += 1
        producer_groups[item_producer]["size_bytes"] += item.size_bytes
    producer_details = [
        {"producer": name, **values}
        for name, values in sorted(producer_groups.items(), key=lambda pair: (-pair[1]["size_bytes"], pair[0]))
    ]
    display_producer = producer_details[0]["producer"] if len(producer_details) == 1 else "Meerdere integraties"
    if category in SAFE_TITLES:
        title, description = SAFE_TITLES[category]
    elif category == "integration_cache_candidate":
        title = f"Mogelijke cache van {display_producer}"
        description = "De mapnaam wijst op cache, maar actief gebruik en automatische herbouw zijn nog niet bewezen."
    elif category == "personal_media":
        title = f"Persoonlijke media van {display_producer}"
        description = "Opnames, timelapses of snapshots zijn gebruikersdata en worden nooit als cache aangenomen."
    else:
        title = f"Nader beoordelen: {display_producer}"
        description = "Niet genoeg bewijs voor een veilig opruimadvies."

    safe = kind == "safe"
    user_selectable = kind in {"safe", "investigate", "personal", "advanced"}
    gates = [
        _gate("path_and_owner", True, "Bestandstype en producer zijn herkend."),
        _gate("minimum_age", True, "De ingestelde minimumleeftijd is gehaald."),
        _gate("not_referenced", safe, "Geen actieve verwijzing verwacht." if safe else "Gebruik door dashboards, automatiseringen of de integratie is niet uitgesloten."),
        _gate("recovery", safe, "Quarantaine of automatische herbouw is mogelijk." if safe else "Automatische herbouw of herstel is niet bewezen."),
    ]
    return {
        "id": f"{kind}:{category}:{_slug(producer)}",
        "kind": kind,
        "category": category,
        "producer": display_producer,
        "producer_groups": producer_details,
        "title": title,
        "description": description,
        "file_count": len(members),
        "size_bytes": sum(item.size_bytes for item in members),
        "item_ids": [item.id for item in members],
        "sample_paths": [item.path for item in sorted(members, key=lambda item: item.size_bytes, reverse=True)[:3]],
        "gate_passed": all(bool(gate["passed"]) for gate in gates),
        "gates": gates,
        "recommendation": "Kan aan het opruimplan worden toegevoegd." if safe else "Beoordeel risico en herstel; alleen de gebruiker kan bepalen of deze inhoud gemist kan worden.",
        "selectable_for_dry_run": user_selectable,
        "execution_allowed": False,
    }


def _producer(path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    for marker in ("custom_components", "community"):
        if marker in parts and parts.index(marker) + 1 < len(parts):
            return parts[parts.index(marker) + 1]
    if "media" in parts and parts.index("media") + 1 < len(parts):
        return parts[parts.index("media") + 1]
    if "www" in parts and parts.index("www") + 1 < len(parts):
        return parts[parts.index("www") + 1]
    return "Home Assistant"


def _gate(key: str, passed: bool, explanation: str) -> dict[str, object]:
    return {"key": key, "passed": passed, "explanation": explanation}


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "unknown"
