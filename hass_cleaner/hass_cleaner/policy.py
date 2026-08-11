from __future__ import annotations

import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


RISK_SAFE = "safe"
RISK_REVIEW = "review"
RISK_PROTECTED = "protected"

CORE_FILES = {"automations.yaml", "configuration.yaml", "scenes.yaml", "scripts.yaml", "secrets.yaml"}
DATABASE_SUFFIXES = (".db", ".db-shm", ".db-wal")
EDITOR_NAMES = {".DS_Store", "Thumbs.db"}
REVIEW_SUFFIXES = {".tmp", ".bak", ".old", ".orig"}
CACHE_DIRECTORY_NAMES = {"cache", "caches", ".cache", "thumbs", "thumbnail", "thumbnails", "tmp", "temp"}
PERSONAL_MEDIA_DIRECTORY_NAMES = {"recording", "recordings", "snapshot", "snapshots", "timelapse", "timelapses"}


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


def classify(root: Path, path: Path, mode: int, modified: float, *, min_temp_age_days: int, min_log_age_days: int, now: datetime | None = None) -> Classification | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return Classification("outside_root", RISK_PROTECTED, "Pad ligt buiten de toegestane root", "none")

    parts = relative.parts
    lowered_parts = {part.lower() for part in parts}
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

    if len(parts) >= 2 and parts[0].lower() == ".cache" and parts[1].lower() == "brands":
        if item_age >= min_temp_age_days:
            return Classification("brand_cache", RISK_SAFE, f"Home Assistant-pictogramcache van {item_age} dagen oud", "delete")
        return None

    in_custom_components = "custom_components" in parts
    if "__pycache__" in parts and suffix in {".pyc", ".pyo"}:
        if item_age >= min_temp_age_days:
            return Classification("python_cache", RISK_SAFE, f"Gegenereerde Python-bytecode van {item_age} dagen oud", "delete")
        return None
    if in_custom_components:
        return Classification("custom_components", RISK_PROTECTED, "Geïnstalleerde integratiebroncode wordt behouden", "none")
    if "www" in parts:
        if "community" in lowered_parts:
            return Classification("frontend_package", RISK_PROTECTED, "HACS/frontendpakket wordt behouden", "none")
        if lowered_parts & CACHE_DIRECTORY_NAMES and item_age >= min_temp_age_days:
            return Classification("integration_cache_candidate", RISK_REVIEW, f"Cache-achtig pad van {item_age} dagen oud; actief gebruik is onbekend", "review")
        if lowered_parts & PERSONAL_MEDIA_DIRECTORY_NAMES:
            return Classification("personal_media", RISK_REVIEW, "Opname, snapshot of timelapse is persoonlijke inhoud", "review")
        return Classification("www_asset_inventory", RISK_PROTECTED, "Dashboard- of webbestand wordt behouden tenzij ongebruik aantoonbaar is", "none")

    if lowered_parts & CACHE_DIRECTORY_NAMES and item_age >= min_temp_age_days:
        return Classification("integration_cache_candidate", RISK_REVIEW, f"Cache-achtig pad van {item_age} dagen oud; eigenaar en gebruik moeten worden bewezen", "review")
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
    return name == "home-assistant.log.old" or name.startswith("home-assistant.log.") or name.endswith(".fault")
