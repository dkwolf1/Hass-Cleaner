from __future__ import annotations

import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


RISK_SAFE = "safe"
RISK_REVIEW = "review"
RISK_PROTECTED = "protected"

CORE_FILES = {
    "automations.yaml",
    "configuration.yaml",
    "scenes.yaml",
    "scripts.yaml",
    "secrets.yaml",
}
DATABASE_SUFFIXES = (".db", ".db-shm", ".db-wal")
EDITOR_NAMES = {".DS_Store", "Thumbs.db"}
REVIEW_SUFFIXES = {".tmp", ".bak", ".old", ".orig"}


@dataclass(frozen=True)
class Classification:
    category: str
    risk: str
    reason: str
    recommended_action: str


def age_days(modified: float, *, now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    changed = datetime.fromtimestamp(modified, tz=timezone.utc)
    return max(0, int((current - changed).total_seconds() // 86400))


def classify(
    root: Path,
    path: Path,
    mode: int,
    modified: float,
    *,
    min_temp_age_days: int,
    min_log_age_days: int,
    now: datetime | None = None,
) -> Classification | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return Classification("outside_root", RISK_PROTECTED, "Pad ligt buiten de toegestane root", "none")

    parts = relative.parts
    name = path.name
    lower_name = name.lower()
    suffix = path.suffix.lower()
    item_age = age_days(modified, now=now)

    if stat.S_ISLNK(mode):
        return Classification("symlink", RISK_PROTECTED, "Symbolische links worden nooit gevolgd", "none")
    if not stat.S_ISREG(mode):
        return None
    if ".storage" in parts:
        return Classification("home_assistant_storage", RISK_PROTECTED, ".storage is absoluut beschermd", "none")
    if len(parts) == 1 and name in CORE_FILES:
        return Classification("core_configuration", RISK_PROTECTED, "Kritiek Home Assistant-configuratiebestand", "none")
    if lower_name.endswith(DATABASE_SUFFIXES):
        return Classification("database", RISK_PROTECTED, "Databases vallen buiten scope", "none")

    in_custom_components = "custom_components" in parts
    in_python_cache = "__pycache__" in parts
    if in_python_cache and suffix in {".pyc", ".pyo"}:
        return Classification("python_cache", RISK_SAFE, "Gegenereerde Python-bytecode in __pycache__", "delete")
    if in_custom_components:
        return Classification("custom_components", RISK_REVIEW, "Integratiebroncode wordt alleen geïnventariseerd", "review")
    if "www" in parts:
        return Classification("www_assets", RISK_REVIEW, "Gebruik van www-bestanden is niet betrouwbaar vast te stellen", "review")

    if name in EDITOR_NAMES or name.endswith("~"):
        if item_age >= min_temp_age_days:
            return Classification("editor_artifact", RISK_SAFE, f"Bekend editorrestant van {item_age} dagen oud", "delete")
        return None
    if _is_known_old_log(lower_name) and item_age >= min_log_age_days:
        return Classification("old_log", RISK_SAFE, f"Bekend niet-actief logbestand van {item_age} dagen oud", "delete")
    if suffix in REVIEW_SUFFIXES and item_age >= min_temp_age_days:
        return Classification("temporary_or_backup", RISK_REVIEW, f"Mogelijk tijdelijk of backupbestand van {item_age} dagen oud", "quarantine")
    return None


def _is_known_old_log(name: str) -> bool:
    return (
        name == "home-assistant.log.old"
        or name.startswith("home-assistant.log.")
        or name.endswith(".fault")
    )
